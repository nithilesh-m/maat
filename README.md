# MAAT - Multi-Agent AI Audit and Trust Framework

Design: `docs/2026-10-03-maat-design.md` · Plan: `docs/plans/2026-10-03-maat-implementation-plan.md`

## Setup
```bash
brew install uv opa ollama
uv sync --all-groups
uv run pytest -q
```
Ollama-backed tests: `MAAT_OLLAMA_TESTS=1 uv run pytest -m ollama`.
