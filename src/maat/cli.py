from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import typer
import yaml
from ulid import ULID

from maat.agents.orchestrator import ApprovalNeeded
from maat.catalog.c2at import VersionMismatchError, render_markdown, render_view
from maat.catalog.loader import CatalogError, applicable_controls, load_catalog
from maat.config import ConfigError, load_config
from maat.evidence.artifacts import ArtifactStore
from maat.evidence.bundle import read_bundle
from maat.evidence.ledger import Ledger
from maat.evidence.signing import RunKey
from maat.evidence.verify import verify_run
from maat.gates.engine import GateEngineError, OpaEngine, policy_bundle_version
from maat.llm.cache import LLMCache
from maat.llm.policy import ModelPolicyError
from maat.llm.untrusted import NullScreen, PromptGuardScreen
from maat.mcp.server import build_server
from maat.profile.loader import ProfileError, load_profile
from maat.remediation.apply import SandboxError
from maat.report.render import render_html, render_pdf, report_context
from maat.review.queue import Waiver, add_waiver, pending_reviews, record_human_decision
from maat.runner import (
    RunConfig,
    RunError,
    RunHandles,
    gate_controls,
    open_run,
    seal_run,
    tool_context,
    waivers_from,
)
from maat.schemas.evidence import EvidenceType
from maat.schemas.profile import SystemProfile
from maat.service import AuditOptions, execute_audit, propose, remediate_run, replay_audit
from maat.targets import factory
from maat.targets.base import Target, TargetError
from maat.tools import load_builtin_tools
from maat.tools.registry import default_registry
from maat.tools.services import default_services

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="MAAT - Multi-Agent AI Audit and Trust Framework",
)


def build_target(profile: SystemProfile) -> Target:
    return factory.build_target(profile)


def fail(msg: str, code: int = 2) -> None:
    typer.secho(f"error: {msg}", err=True, fg="red")
    raise typer.Exit(code)


def parse_as_of(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        fail(f"--as-of must be ISO-8601, got {value!r}")
    if t.tzinfo is None:
        fail("--as-of must include a timezone, e.g. 2026-11-14T10:00:00+00:00")
    return t


def ask_human(question: dict) -> dict:
    typer.echo(json.dumps(question, indent=2))
    ok = typer.confirm(f"Accept suggested tier {question['suggested_tier']!r}?", default=False)
    return {"approve_tier": ok, "ers": None}


@app.command()
def audit(
    profile: Path = typer.Option(..., "--profile", "-p", help="system_profile.yaml"),
    out: Path = typer.Option(Path("runs"), "--out", help="directory for run folders"),
    key: Path | None = typer.Option(None, "--key", help="Ed25519 PEM key (default: ephemeral)"),
    as_of: str | None = typer.Option(None, "--as-of", help="audit timestamp (ISO-8601 with tz)"),
    planner: str = typer.Option("agents", "--planner", help="agents | static"),
    config: Path = typer.Option(Path("maat.toml"), "--config", help="model/runtime config"),
    llm_mode: str | None = typer.Option(None, "--llm-mode", help="live | record | replay"),
    auto_approve: bool = typer.Option(False, "--auto-approve", help="accept suggested tier/ERS"),
    allow_same_family_judges: bool = typer.Option(
        False, "--allow-same-family-judges", hidden=True, help="ablation only"
    ),
    no_screen: bool = typer.Option(False, "--no-screen", hidden=True, help="testing only"),
) -> None:
    """Audit the system described by PROFILE (agent planner by default, or static B0)."""
    if planner not in ("agents", "static"):
        fail(f"--planner must be 'agents' or 'static', got {planner!r}")
    if llm_mode not in (None, "live", "record", "replay"):
        fail(f"--llm-mode must be live, record or replay, got {llm_mode!r}")
    try:
        prof = load_profile(profile)
        target = build_target(prof)
        OpaEngine()  # fail early if opa is missing
        load_catalog()
        maat_cfg = load_config(config) if (planner == "agents" or config.exists()) else None
    except (ProfileError, TargetError, GateEngineError, CatalogError, ConfigError) as e:
        fail(str(e))
    if maat_cfg is not None and llm_mode:
        maat_cfg.llm_mode = llm_mode
    when = parse_as_of(as_of)
    signer = RunKey.load_pem(key) if key else RunKey.generate()
    run_id = f"run-{when:%Y%m%d-%H%M%S}-{str(ULID())[-6:].lower()}"
    options = AuditOptions(planner=planner, allow_same_family_judges=allow_same_family_judges)
    meta = {
        "run_id": run_id,
        "as_of": when.isoformat(),
        "planner": planner,
        "options": options.model_dump(),
        "auto_approve": auto_approve,
        "allow_same_family": allow_same_family_judges,
        "llm_mode": maat_cfg.llm_mode if maat_cfg else None,
    }
    cfg = RunConfig(run_id=run_id, run_dir=out / run_id, signer=signer, as_of=when, meta=meta)
    screen = NullScreen() if no_screen else PromptGuardScreen()
    try:
        bundle = execute_audit(
            prof,
            target,
            cfg,
            maat_cfg,
            options,
            screen,
            resume=None if auto_approve else ask_human,
            auto_approve=auto_approve,
        )
    except (ConfigError, ModelPolicyError, ApprovalNeeded, RunError, GateEngineError) as e:
        fail(str(e))
    shutil.copy2(profile, cfg.run_dir / "profile.yaml")
    if planner == "agents":
        shutil.copy2(config, cfg.run_dir / "maat.toml")
    typer.echo(f"run:    {cfg.run_dir}")
    typer.echo(f"bundle: {bundle.header.bundle_id}")
    typer.echo(f"status: {bundle.status}")
    for d in bundle.decisions:
        typer.echo(f"{d.clause_id:<14} {d.outcome.value:<15} {d.rationale}")


@app.command()
def replay(run_dir: Path, out: Path = typer.Option(Path("runs/replays"), "--out")) -> None:
    """Re-execute a run from its ledger and LLM cache; must reproduce its bundle_id."""
    try:
        matched, message = replay_audit(run_dir, out, build_target)
    except ValueError as e:
        fail(str(e))
    typer.secho(message, fg="green" if matched else "red")
    if not matched:
        raise typer.Exit(1)


@app.command()
def verify(
    run_dir: Path,
    pubkey: list[str] | None = typer.Option(None, "--pubkey", help="expected signer key(s)"),
    allow_redacted: Path | None = typer.Option(
        None,
        "--allow-redacted",
        help="file of sha256 digests of artifacts removed for publication",
    ),
) -> None:
    """Check ledger hash chain, signatures, artifacts and the bundle envelope."""
    skip: list[str] = []
    if allow_redacted is not None:
        try:
            skip = allow_redacted.read_text(encoding="utf-8").split()
        except OSError as e:
            fail(f"cannot read {allow_redacted}: {e}")
    rep = verify_run(run_dir, expected_pubkeys=pubkey or None, skip_artifacts=skip)
    if rep.ok:
        note = f", {rep.redacted} artifacts redacted" if rep.redacted else ""
        note = note.replace("1 artifacts", "1 artifact")
        typer.secho(f"OK  bundle {rep.bundle_id} ({rep.records} records{note})", fg="green")
        return
    typer.secho("VERIFICATION FAILED", fg="red", err=True)
    for p in rep.problems:
        typer.echo(f" - {p}", err=True)
    raise typer.Exit(1)


@app.command()
def render(run_dir: Path, regime: str = typer.Option("EU", "--regime")) -> None:
    """Print the clause table for one regulatory regime."""
    try:
        bundle = read_bundle(run_dir)
    except (FileNotFoundError, ValueError) as e:
        fail(f"cannot read bundle in {run_dir}: {e}")
    try:
        rows = render_view(bundle, load_catalog(), regime, policy_bundle_version())
    except VersionMismatchError as e:
        fail(str(e))
    typer.echo(render_markdown(rows, regime=regime, bundle=bundle))


review_app = typer.Typer(no_args_is_help=True, help="Human review queue for abstained controls")
waiver_app = typer.Typer(no_args_is_help=True, help="Time-limited waivers for failed controls")
app.add_typer(review_app, name="review")
app.add_typer(waiver_app, name="waiver")

DEFAULT_REVIEWER_KEY = Path.home() / ".maat" / "reviewer.pem"


def reviewer_key(path: Path | None) -> RunKey:
    path = path or DEFAULT_REVIEWER_KEY
    if path.exists():
        return RunKey.load_pem(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = RunKey.generate()
    key.save_pem(path)
    path.chmod(0o600)
    typer.echo(f"generated reviewer key {path} (public key {key.public_key_b64})")
    return key


@review_app.command("list")
def review_list(run_dir: Path) -> None:
    """List controls that abstained and wait for a human decision."""
    try:
        pending = pending_reviews(run_dir)
    except (FileNotFoundError, ValueError) as e:
        fail(f"cannot read bundle in {run_dir}: {e}")
    if not pending:
        typer.echo("no pending reviews")
    for d in pending:
        typer.echo(f"{d.clause_id:<14} {d.rationale}")


@review_app.command("decide")
def review_decide(
    run_dir: Path,
    control: str,
    label: str = typer.Option(..., "--label", help="S | P | N | NA"),
    reviewer: str = typer.Option(..., "--reviewer"),
    rationale: str = typer.Option(..., "--rationale"),
    key: Path | None = typer.Option(None, "--key", help="reviewer Ed25519 PEM key"),
) -> None:
    """Record a human verdict for CONTROL and re-seal the bundle as a new revision."""
    if label not in ("S", "P", "N", "NA"):
        fail(f"--label must be one of S, P, N, NA, got {label!r}")
    try:
        bundle = record_human_decision(
            run_dir, control, label, reviewer, rationale, reviewer_key(key), datetime.now(UTC)
        )
    except (FileNotFoundError, ValueError, KeyError, GateEngineError) as e:
        fail(str(e))
    d = next(x for x in bundle.decisions if x.clause_id == control)
    typer.echo(f"{control}: {d.outcome.value} (revision {bundle.header.revision})")


@waiver_app.command("add")
def waiver_add(
    run_dir: Path,
    control: str = typer.Option(..., "--control"),
    owner: str = typer.Option(..., "--owner"),
    scope: str = typer.Option(..., "--scope"),
    expiry: str = typer.Option(..., "--expiry", help="ISO-8601 with timezone"),
    compensation: list[str] = typer.Option([], "--compensation"),
    key: Path | None = typer.Option(None, "--key", help="reviewer Ed25519 PEM key"),
) -> None:
    """Waive a failed control until EXPIRY; re-seals the bundle as a new revision."""
    try:
        waiver = Waiver(
            id=f"W-{str(ULID())[-8:].lower()}",
            clause_id=control,
            owner=owner,
            scope=scope,
            expiry=expiry,
            compensations=compensation,
        )
        bundle = add_waiver(run_dir, waiver, reviewer_key(key), datetime.now(UTC))
    except (FileNotFoundError, ValueError, KeyError, GateEngineError) as e:
        fail(str(e))
    d = next(x for x in bundle.decisions if x.clause_id == control)
    typer.echo(
        f"{control}: {d.outcome.value} (revision {bundle.header.revision}, waiver {waiver.id})"
    )


@app.command()
def remediate(
    run_dir: Path,
    profile: Path = typer.Option(..., "--profile", "-p", help="system_profile.yaml"),
    apply: bool = typer.Option(False, "--apply", help="apply mitigations to a sandboxed snapshot"),
    key: Path | None = typer.Option(None, "--key", help="Ed25519 PEM key for the child run"),
    config: Path = typer.Option(Path("maat.toml"), "--config"),
    regime: str = typer.Option("EU", "--regime"),
) -> None:
    """Rank failed controls and propose mitigations; --apply mitigates a snapshot and re-tests."""
    try:
        prof = load_profile(profile)
        plans, manual = propose(run_dir, prof)
    except (ProfileError, FileNotFoundError, ValueError) as e:
        fail(str(e))
    if not plans:
        typer.echo("no automatic mitigation applies to the failed controls")
    for p in plans:
        typer.echo(
            f"{p.control_id:<14} score={p.severity_score:<5g} {p.mitigation_id}: {p.rationale}"
        )
    if manual:
        typer.echo(f"manual follow-up needed (no automatic mitigation): {', '.join(manual)}")
    if not apply or not plans:
        return
    if not prof.sandbox_allowed:
        fail("--apply needs profile.sandbox_allowed: true (mitigations touch a sandboxed snapshot)")
    try:
        result = remediate_run(
            run_dir,
            prof,
            apply=True,
            signer=reviewer_key(key),
            config=config,
            regime=regime,
            target_builder=build_target,
        )
    except (SandboxError, TargetError, GateEngineError, VersionMismatchError, ValueError) as e:
        fail(str(e))
    for note in result.notes:
        typer.echo(note)
    typer.echo(f"\nchild run: {result.child_dir}")
    typer.echo("control        clause                 before -> after   a_c")
    for r in result.rows:
        typer.echo(
            f"{r['control_id']:<14} {r['regime_clause']:<22} {r['before_outcome']} -> "
            f"{r['after_outcome']}   {r['before_a']} -> {r['after_a']}"
        )
    for k, v in result.summary.items():
        typer.echo(f"{k} = {v}")


@app.command()
def report(
    run_dir: Path,
    pdf: bool = typer.Option(False, "--pdf", help="also write report.pdf (needs pango)"),
) -> None:
    """Write a signed-bundle audit report (HTML, optionally PDF) into RUN_DIR."""
    try:
        ctx = report_context(run_dir, load_catalog(), policy_bundle_version())
    except (FileNotFoundError, ValueError) as e:
        fail(f"cannot read bundle in {run_dir}: {e}")
    except VersionMismatchError as e:
        fail(str(e))
    html = render_html(ctx)
    (run_dir / "report.html").write_text(html, encoding="utf-8")
    typer.echo(f"wrote {run_dir / 'report.html'} ({'VALID' if ctx['verify'].ok else 'INVALID'})")
    if pdf:
        try:
            render_pdf(html, run_dir / "report.pdf")
        except OSError as e:
            fail(
                f"PDF needs the pango library ({e}); on macOS run: brew install pango and set "
                "DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib"
            )
        typer.echo(f"wrote {run_dir / 'report.pdf'}")


mcp_app = typer.Typer(no_args_is_help=True, help="Serve MAAT tools to MCP clients")
app.add_typer(mcp_app, name="mcp")
AGENTS = ("risk", "fairness", "explainability", "compliance")


def open_mcp_run(prof, target, out: Path, signer: RunKey, agent: str, services=None):
    """Open a ledger-backed run for an MCP session. Returns (RunConfig, RunHandles)."""
    when = datetime.now(UTC)
    run_id = f"mcp-{when:%Y%m%d-%H%M%S}-{str(ULID())[-6:].lower()}"
    cfg = RunConfig(
        run_id=run_id,
        run_dir=Path(out) / run_id,
        signer=signer,
        as_of=when,
        services=services,
        meta={"planner": "mcp", "agent": agent, "run_id": run_id, "as_of": when.isoformat()},
    )
    handles = open_run(cfg)
    (cfg.run_dir / "profile.yaml").write_text(
        yaml.safe_dump(prof.model_dump(mode="json", exclude_none=True), sort_keys=False)
    )
    return cfg, handles


@mcp_app.command("serve")
def mcp_serve(
    agent: str = typer.Option(..., "--agent", help="risk | fairness | explainability | compliance"),
    profile: Path = typer.Option(..., "--profile", "-p"),
    out: Path = typer.Option(Path("runs/mcp"), "--out"),
    key: Path | None = typer.Option(None, "--key", help="Ed25519 PEM key (default: reviewer key)"),
    config: Path = typer.Option(Path("maat.toml"), "--config"),
) -> None:
    """Serve one agent's tools over MCP (stdio). Every call is recorded in a signed ledger."""
    if agent not in AGENTS:
        fail(f"--agent must be one of {', '.join(AGENTS)}, got {agent!r}")
    try:
        prof = load_profile(profile)
        target = build_target(prof)
        maat_cfg = load_config(config) if config.exists() else None
    except (ProfileError, TargetError, ConfigError) as e:
        fail(str(e))
    cfg_holder: dict = {}
    services = (
        default_services(
            maat_cfg,
            lambda: LLMCache(cfg_holder["cfg"].run_dir / "tool_cache.sqlite", maat_cfg.llm_mode),
        )
        if maat_cfg is not None
        else None
    )
    try:
        cfg, handles = open_mcp_run(prof, target, out, reviewer_key(key), agent, services)
    except RunError as e:
        fail(str(e))
    cfg_holder["cfg"] = cfg
    typer.echo(f"MCP run: {cfg.run_dir} (seal with: maat mcp seal {cfg.run_dir})", err=True)
    server = build_server(agent, lambda a: tool_context(cfg, handles, a, target, prof))
    try:
        server.run()
    finally:
        handles.ledger.close()


@mcp_app.command("seal")
def mcp_seal(
    run_dir: Path,
    key: Path | None = typer.Option(None, "--key", help="Ed25519 PEM key used when serving"),
) -> None:
    """Gate the controls evidenced so far in an MCP session and write the signed bundle."""
    try:
        meta = json.loads((run_dir / "run_meta.json").read_text())
        prof = load_profile(run_dir / "profile.yaml")
        target = build_target(prof)
        engine, catalog = OpaEngine(), load_catalog()
    except (FileNotFoundError, ValueError, ProfileError, TargetError, GateEngineError) as e:
        fail(f"cannot seal {run_dir}: {e}")
    signer = reviewer_key(key)
    ledger = Ledger(run_dir / "ledger.sqlite", meta["run_id"], signer)
    cfg = RunConfig(
        run_id=meta["run_id"],
        run_dir=run_dir,
        signer=signer,
        as_of=datetime.now(UTC),
        meta=meta,
    )
    handles = RunHandles(ledger=ledger, artifacts=ArtifactStore(run_dir / "artifacts", cfg.run_id))
    load_builtin_tools()
    records = ledger.records()
    evidenced = {r.tool.split("@", 1)[0] for r in records}
    applicable = applicable_controls(catalog, prof)
    controls = [c for c in applicable if any(e.tool in evidenced for e in c.evidence_edges)]
    latest = {}
    for r in records:
        name = r.tool.split("@", 1)[0]
        if r.evidence_type is EvidenceType.MEASURED or name not in latest:
            latest[name] = r
    try:
        decisions = gate_controls(controls, latest, prof, engine, cfg, waivers_from(records))
        status = "incomplete" if len(controls) < len(applicable) else None
        bundle = seal_run(
            profile=prof, target=target, catalog=catalog, engine=engine, config=cfg,
            handles=handles, controls=controls, decisions=decisions,
            registry=default_registry, status=status,
        )  # fmt: skip
    except (GateEngineError, ValueError) as e:
        ledger.close()
        fail(str(e))
    typer.echo(f"bundle: {bundle.header.bundle_id}")
    typer.echo(f"status: {bundle.status}")
    for d in bundle.decisions:
        typer.echo(f"{d.clause_id:<14} {d.outcome.value:<15} {d.rationale}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port"),
) -> None:
    """Run the MAAT HTTP API (v1). Configure with MAAT_API_* environment variables."""
    import uvicorn

    uvicorn.run("maat.api.app:create_app", factory=True, host=host, port=port)
