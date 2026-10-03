import io
import zipfile

import pytest

from tests.api.test_auth_store import H, app_with

pytestmark = pytest.mark.opa


def test_views_scores_decisions(run):
    c, rid, _ = run
    v = c.get(f"/api/v1/runs/{rid}/views/EU", headers=H("v")).json()
    assert any(r["control_id"] == "VG-SEC-01" for r in v["rows"]) and 0 <= v["cc"] <= 1
    assert "EU" in c.get(f"/api/v1/runs/{rid}/scores", headers=H("v")).json()["regimes"]
    assert c.get(f"/api/v1/runs/{rid}/verify", headers=H("v")).json()["ok"] is True


def test_records_and_404(run):
    c, rid, _ = run
    recs = c.get(f"/api/v1/runs/{rid}/records", headers=H("v")).json()
    assert recs and c.get(f"/api/v1/records/{rid}/nope", headers=H("v")).status_code == 404


def test_verify_upload_rejects_zip_slip(run):
    c, _, _ = run
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../evil.txt", "x")
    r = c.post(
        "/api/v1/verify",
        headers=H("v"),
        files={"file": ("run.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400


def test_findings_decisions_bundle_and_report(run):
    c, rid, _ = run
    d = c.get(f"/api/v1/runs/{rid}/decisions", headers=H("v")).json()
    assert any(x["clause_id"] == "VG-SEC-01" and x["outcome"] == "block" for x in d)
    assert c.get(f"/api/v1/runs/{rid}/findings", headers=H("v")).json() == []
    env = c.get(f"/api/v1/runs/{rid}/bundle", headers=H("v")).json()
    assert env["payloadType"] == "application/vnd.in-toto+json"
    html = c.get(f"/api/v1/runs/{rid}/report.html", headers=H("v"))
    assert html.status_code == 200 and "VALID" in html.text
    assert html.headers["content-type"].startswith("text/html")


def test_records_filter_and_pagination(run):
    c, rid, _ = run
    all_recs = c.get(f"/api/v1/runs/{rid}/records", headers=H("v")).json()
    assert len(all_recs) >= 2
    page = c.get(f"/api/v1/runs/{rid}/records?limit=1&offset=1", headers=H("v")).json()
    assert [r["id"] for r in page] == [all_recs[1]["id"]]
    only = c.get(f"/api/v1/runs/{rid}/records?type=gap", headers=H("v")).json()
    assert only and all(r["evidence_type"] == "gap" for r in only)
    one = c.get(f"/api/v1/records/{rid}/{all_recs[0]['id']}", headers=H("v")).json()
    assert one["id"] == all_recs[0]["id"]


def test_artifact_access_rules_and_path_safety(run):
    c, rid, _ = run
    recs = c.get(f"/api/v1/runs/{rid}/records", headers=H("v")).json()
    art = next(a for r in recs for a in r["artifacts"])
    ok = c.get(f"/api/v1/artifacts/{rid}/{art['sha256']}", headers=H("v"))
    assert ok.status_code == 200 and ok.content
    assert c.get(f"/api/v1/artifacts/{rid}/..", headers=H("v")).status_code in (400, 404)
    assert c.get(f"/api/v1/artifacts/{rid}/not-a-digest", headers=H("v")).status_code == 400
    assert c.get(f"/api/v1/artifacts/{rid}/sha256:{'0' * 64}", headers=H("v")).status_code == 404


def test_sensitive_artifacts_need_reviewer_and_flag(tmp_path):
    from maat.evidence.artifacts import ArtifactStore
    from maat.evidence.ledger import Ledger
    from maat.evidence.signing import RunKey
    from maat.schemas.evidence import EvidenceDraft
    from tests.fakes import AS_OF, SEED, seq_ids

    c = app_with(tmp_path)
    run_dir = tmp_path / "runs" / "run-s"
    run_dir.mkdir(parents=True)
    ref = ArtifactStore(run_dir / "artifacts", "run-s").put_bytes(b"secret", "risk", "s", True)
    led = Ledger(run_dir / "ledger.sqlite", "run-s", RunKey.from_seed(SEED), seq_ids())
    led.append(
        EvidenceDraft(
            run_id="run-s", agent="risk", tool="t@1", evidence_type="measured", target_ref="t",
            artifacts=[ref], started_at=AS_OF, ended_at=AS_OF,
        )
    )  # fmt: skip
    led.close()
    c.app.state.store.create("run-s", run_dir, "p.yaml", "static", "r")
    url = f"/api/v1/artifacts/run-s/{ref.sha256}"
    assert c.get(url, headers=H("v")).status_code == 403
    assert c.get(url + "?include_sensitive=true", headers=H("v")).status_code == 403
    assert c.get(url + "?include_sensitive=true", headers=H("r")).content == b"secret"
    assert c.get(url, headers=H("r")).status_code == 403


def test_unsealed_run_is_409_on_bundle_endpoints(tmp_path):
    c = app_with(tmp_path)
    (tmp_path / "runs" / "run-u").mkdir(parents=True)
    c.app.state.store.create("run-u", tmp_path / "runs" / "run-u", "p.yaml", "static", "r")
    for path in ("decisions", "findings", "views/EU", "scores", "bundle", "report.html"):
        r = c.get(f"/api/v1/runs/run-u/{path}", headers=H("v"))
        assert r.status_code == 409 and r.json()["detail"] == "run not sealed yet", path


def test_verify_upload_accepts_valid_zip_and_flags_tampering(run, tmp_path):
    c, rid, base = run
    src = base / "runs" / rid

    def zipped(mutate=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for f in src.rglob("*"):
                if f.is_file() and f.name != "events.jsonl":
                    data = f.read_bytes()
                    if mutate and f.name == "bundle.dsse.json":
                        data = mutate(data)
                    z.writestr(str(f.relative_to(src)), data)
        return buf.getvalue()

    ok = c.post(
        "/api/v1/verify", headers=H("v"), files={"file": ("r.zip", zipped(), "application/zip")}
    )
    assert ok.status_code == 200 and ok.json()["ok"] is True
    bad = c.post(
        "/api/v1/verify",
        headers=H("v"),
        files={"file": ("r.zip", zipped(lambda b: b"{}"), "application/zip")},
    )
    assert bad.status_code == 200 and bad.json()["ok"] is False and bad.json()["problems"]


def test_verify_upload_rejects_absolute_paths_and_oversized_archives(run):
    c, _, _ = run
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("/etc/evil.txt", "x")
    r = c.post(
        "/api/v1/verify",
        headers=H("v"),
        files={"file": ("r.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400
    r = c.post(
        "/api/v1/verify", headers=H("v"), files={"file": ("r.zip", b"not a zip", "application/zip")}
    )
    assert r.status_code == 400


def test_verify_upload_rejects_oversized_archive(run, monkeypatch):
    import maat.api.routers.evidence as ev

    monkeypatch.setattr(ev, "MAX_UNZIPPED_BYTES", 10)
    c, _, _ = run
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("big.txt", "x" * 100)
    r = c.post(
        "/api/v1/verify",
        headers=H("v"),
        files={"file": ("r.zip", buf.getvalue(), "application/zip")},
    )
    assert r.status_code == 400 and "too large" in r.json()["detail"]


def test_verify_upload_accepts_run_nested_under_one_folder(run):
    c, rid, base = run
    src = base / "runs" / rid
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for f in src.rglob("*"):
            if f.is_file() and f.name != "events.jsonl":
                z.writestr(f"{rid}/{f.relative_to(src)}", f.read_bytes())
    r = c.post("/api/v1/verify", headers=H("v"), files={"file": ("r.zip", buf.getvalue())})
    assert r.status_code == 200 and r.json()["ok"] is True
