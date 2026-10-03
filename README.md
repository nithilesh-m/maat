# MAAT: Multi-Agent AI Audit and Trust Framework

MAAT audits an AI system against regulatory-style controls and produces **evidence you can verify
without trusting MAAT**. Its guiding rule: *tools measure, LLMs reason.* Every number comes from a
deterministic tool (Presidio, SHAP, Fairlearn, schemathesis, prompt-injection probes, ...). LLM agents
only plan, interpret and explain, and every claim they make is recorded next to the evidence behind it.

The result of an audit is a signed, tamper-evident **evidence bundle** plus a per-regime clause view,
findings, remediation advice and a report.

## Contents

- [How it works](#how-it-works)
- [Features](#features)
- [Quick start](#quick-start)
- [Command line](#command-line)
- [HTTP API](#http-api)
- [Web console](#web-console)
- [Running a demo on one local model](#running-a-demo-on-one-local-model)
- [Configuration](#configuration)
- [MCP server](#mcp-server)
- [Experiments](#experiments)
- [Development](#development)
- [Docker](#docker)
- [Repository layout](#repository-layout)
- [Limitations](#limitations)

## How it works

```
 system_profile.yaml ──► planner ──► specialist agents ──► tools (measure)
                                          │                    │
                                          ▼                    ▼
                                  evidence ledger  ◄──  tool results / artifacts
                                          │
                                          ▼
                       Rego/OPA threshold gates ──► judge panel ──► control decisions
                                          │                              │
                                          ▼                              ▼
                              signed DSSE bundle            human review / waivers
                                          │
                       ┌──────────────────┼───────────────────┐
                       ▼                  ▼                   ▼
                 regime views        remediation          signed report
                 (CC / AS / MER)    (+ held-out re-test)   (HTML / PDF)
```

1. **Profile.** You describe the system under audit (`system_profile.yaml`): its endpoint, data,
   risk tier and which controls apply.
2. **Plan and measure.** A planner picks controls from the catalog (48 controls). Specialist agents
   call deterministic tools; each call is logged with its inputs, outputs and artifact hashes.
3. **Evidence ledger.** An append-only SQLite ledger. Each record is canonicalised (RFC 8785),
   hashed (SHA-256), chained to the previous record and signed with Ed25519.
4. **Gates.** Rego policies (run by OPA) turn measurements into pass/fail against thresholds. Gates
   decide, not the LLM.
5. **Judge panel.** Where a control needs interpretation, a panel of judge models votes. A
   cross-family rule requires judges from different model families, so a model never grades its own
   family. Disagreement becomes an *abstain*, which goes to the human review queue.
6. **Bundle.** The run is sealed as a DSSE envelope carrying an in-toto statement and a Merkle root
   over the ledger and artifacts. Anyone can re-check it with `maat verify`.
7. **After the audit.** Review and waivers create new bundle *revisions* (history is never
   rewritten). Remediation ranks failed controls, proposes mitigations, applies them to a sandbox
   snapshot and re-tests on held-out data. Replay re-executes a run from its ledger and LLM cache
   and must reproduce the same bundle id.

## Features

- **Tamper-evident evidence**: hash-chained ledger, Ed25519 signatures, DSSE / in-toto bundles.
- **Deterministic gates**: OPA/Rego thresholds with their own policy tests.
- **Cross-family judge panel** with explicit abstention and a human review queue.
- **Regime views (C2AT)**: the same evidence rendered as CC, AS and MER clause tables.
- **Remediation loop**: ranked mitigations, sandboxed apply, held-out re-test and a measured delta.
- **Replay** that must reproduce the original bundle id.
- **Signed reports** (HTML, optionally PDF).
- **FastAPI service** with SSE live events, role-based tokens and a frozen v1 OpenAPI contract.
- **Web console** (Next.js) with a home page, live run view, findings, evidence records,
  remediation, review queue, bundle verification and run comparison.
- **MCP server** exposing MAAT tools to MCP clients.
- **Experiment harness**: baselines, ablations, resumable run matrix, bootstrap CIs and a freeze
  manifest for reproducible results.

## Quick start

Requirements: Python 3.12, [uv](https://docs.astral.sh/uv/), [OPA](https://www.openpolicyagent.org/),
[Ollama](https://ollama.com/) for live LLM runs, and Node 22 for the web console.

```bash
brew install uv opa ollama        # macOS; use your package manager elsewhere
uv sync --all-groups
uv run pytest -q                  # full test suite
```

Ollama-backed tests are opt-in:

```bash
MAAT_OLLAMA_TESTS=1 uv run pytest -m ollama
```

## Command line

```bash
uv run maat --help
```

| Command | What it does |
| --- | --- |
| `maat audit` | Audit the system in a profile (agent planner by default, or `--planner static`). |
| `maat verify <run_dir>` | Check the hash chain, signatures, artifacts and bundle envelope. |
| `maat replay <run_dir>` | Re-execute a run from its ledger and LLM cache. It must reproduce the bundle id. |
| `maat render` | Print the clause table for one regulatory regime. |
| `maat remediate` | Rank failed controls and propose mitigations. `--apply` mitigates a snapshot and re-tests. |
| `maat report <run_dir>` | Write a signed audit report into the run directory. |
| `maat review` | Human review queue for abstained controls. |
| `maat waiver` | Time-limited waivers for failed controls. |
| `maat serve` | Run the HTTP API. |
| `maat mcp` | Serve MAAT tools to MCP clients. |

A run without any LLM (static planner, deterministic tools only):

```bash
uv run maat audit --profile examples/profiles/t1_seeded.yaml --planner static --out runs
uv run maat verify runs/<run-id>
```

Useful `audit` options: `--config` (model config, default `maat.toml`), `--llm-mode live|record|replay`,
`--key` (Ed25519 PEM; an ephemeral key is used by default), `--as-of` (audit timestamp) and
`--auto-approve` (accept the suggested tier and ERS).

Example profiles live in `examples/profiles/` (clean and deliberately-defective "seeded" variants of
three test-bed systems).

## HTTP API

```bash
cp api_users.example.toml users.toml      # then put a SHA-256 of each token in the file
export MAAT_API_USERS_FILE=users.toml
export MAAT_API_RUNS_DIR=runs
export MAAT_API_ALLOW_ORIGINS=http://localhost:3000
uv run maat serve --port 8080
```

Tokens are sent as `Authorization: Bearer <token>`. Roles are `viewer`, `reviewer` and `admin`.
Generate a token hash with:

```bash
python -c "import hashlib; print(hashlib.sha256(b'my-token').hexdigest())"
```

The v1 contract is frozen in `docs/api/openapi-v1.json`; a schema change needs a deliberate
re-export (`uv run python scripts/export_openapi.py > docs/api/openapi-v1.json`). Live run progress
streams over Server-Sent Events.

Settings are read from `MAAT_API_*` environment variables:

| Variable | Meaning |
| --- | --- |
| `MAAT_API_RUNS_DIR` | Where run folders are stored. |
| `MAAT_API_USERS_FILE` | Token registry (TOML). |
| `MAAT_API_MAAT_CONFIG` | Model/runtime config (default `maat.toml`). |
| `MAAT_API_ALLOW_ORIGINS` | Comma-separated CORS origins. |
| `MAAT_API_ALLOW_SAME_FAMILY_JUDGES` | `true` lets a single model family judge (demos only). |
| `MAAT_API_SCREEN` | `prompt_guard` (default) or `none` to skip the injection screen. |
| `MAAT_API_ALLOWED_AUTH_ENV` | Environment variables a profile may reference for target auth. |

## Web console

```bash
cd web
npm ci
echo "NEXT_PUBLIC_MAAT_API=http://127.0.0.1:8080" > .env.local
npm run dev                   # http://localhost:3000
```

Pages: home (`/`), sign-in, runs list, new audit, run detail (live, clauses, findings, evidence
records, remediation, bundle), review queue, bundle verification (upload a zipped run folder) and run
comparison. The sign-in page asks for an API token, which is kept in the browser tab only.

Scripts: `npm run lint`, `npm run typecheck`, `npm test` (Vitest), `npm run e2e` (Playwright) and
`npm run gen:api` (regenerate the typed client from the OpenAPI file).

Stack: Next.js 16, React 19, Tailwind 4, shadcn on base-ui, TanStack Query, Recharts, framer-motion.

## Running a demo on one local model

The default config uses several models so the cross-family judge rule is meaningful. For a laptop demo,
`maat.demo.toml` runs everything on a single small model (`llama3.2:3b`) and the target under audit is
a deliberately defective RAG bot on the same model.

```bash
ollama serve &
ollama pull llama3.2:3b && ollama pull nomic-embed-text

export MAAT_API_MAAT_CONFIG=maat.demo.toml
export MAAT_API_ALLOW_SAME_FAMILY_JUDGES=true   # one model family only
export MAAT_API_SCREEN=none                     # skip the optional transformers injection screen
uv run python scripts/seed_demo_runs.py         # optional: pre-built sample runs
uv run maat serve --port 8090
```

Use `examples/profiles/demo_llama_seeded.yaml` as the system profile. A full audit takes a few
minutes on a laptop. With a single model family the judge panel is not independent, so treat demo
results as a walkthrough, not as evidence.

## Configuration

`maat.toml` selects model profiles (orchestrator, specialists, judges, tool model, guard, embeddings),
Ollama settings (temperature, seed, `num_predict`, keep-alive, timeout) and per-agent budgets. The
default profile uses judges from different families; `[models.same-family]` exists for ablations.
Generation uses `temperature = 0` and a fixed seed so runs are replayable.

## MCP server

```bash
uv run maat mcp
```

Exposes MAAT audit, verify and render tools to MCP clients such as Claude Desktop.

## Experiments

`experiments/` holds the evaluation harness for the research questions:

| Script | Purpose |
| --- | --- |
| `run_matrix.py` | Resumable run matrix over baselines and ablations (`--final` guards the final split). |
| `analyze_rq1.py` | RQ1: detection quality against seeded defects. |
| `analyze_rq2.py` | RQ2: judge-panel stability under perturbation. |
| `run_rq3.py` | RQ3: remediation effect with held-out re-tests. |
| `run_rq4.py` | RQ4: evidence quality, tamper detection, replay determinism and cost. |
| `analyze_all.py`, `plots.py` | Aggregate tables and figures with bootstrap confidence intervals. |
| `freeze.py` | SHA-256 freeze manifest of the inputs and results. |

Configs are in `experiments/configs/`. `scripts/package_release.py` builds a sanitised release
archive; `maat verify --allow-redacted` still verifies a bundle after sensitive artifacts are removed.
The matrix has so far been exercised with stubbed models; no full Ollama experiment results are
included.

## Development

CI (`.github/workflows/ci.yml`) runs the same checks:

```bash
uv run ruff check . && uv run ruff format --check .
opa test src/maat/gates/policies src/maat/gates/policies_test -v
uv run pytest -q

cd web
npm run gen:api && git diff --exit-code lib/api/schema.d.ts
npm run typecheck && npm run lint && npm test
```

Python 3.12 with strict typing and Pydantic models; the CLI is Typer, the API is FastAPI, agents use
LangGraph.

## Docker

```bash
docker build -t maat .
docker run -p 8080:8080 -v $PWD/data:/data -e MAAT_API_USERS_FILE=/data/users.toml maat
```

The image installs OPA, runs `maat serve` on port 8080 and reaches Ollama on the host
(`OLLAMA_HOST=http://host.docker.internal:11434`).

## Repository layout

```
src/maat/
  evidence/      ledger, hashing, signing, bundle build and verify
  tools/         deterministic measurement tools
  gates/         Rego policies and thresholds
  agents/        planner, specialists and judge panel (LangGraph)
  llm/           Ollama client, cache and record/replay
  catalog/       the 48-control catalog and regime mappings
  review/        human review queue and waivers
  remediation/   mitigation ranking, apply and re-test
  report/        signed report rendering
  api/           FastAPI app, auth, SSE, worker
  mcp/           MCP server
  eval/          evaluation metrics used by experiments
  baselines/     LLM-only baseline
  service.py     shared audit / replay / remediate logic
  cli.py         the `maat` command
testbed/         sample systems under audit (RAG bot, tabular credit, ...)
examples/        example system profiles
experiments/     research experiments and analysis
scripts/         seed, export and release helpers
web/             Next.js console
tests/           Python tests
```

## Limitations

- The regime mappings in the catalog have not been independently reviewed.
- Same-family judging (demo mode) removes the independence guarantee.
- Small local models give noisy interpretations; deterministic gates and the review queue exist for
  that reason.
- The API has no "who am I" endpoint yet, so the console probes the token's role.
