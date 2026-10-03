import hashlib
import json
import tempfile
from pathlib import Path

import schemathesis

from maat.api.app import create_app
from maat.api.settings import ApiSettings


def test_openapi_frozen(tmp_path):
    """API v1 is frozen: a schema change needs a deliberate re-export, noted in docs/api/README.md.

    Re-export with: uv run python scripts/export_openapi.py > docs/api/openapi-v1.json
    """
    live = create_app(ApiSettings(runs_dir=tmp_path)).openapi()
    assert json.loads(Path("docs/api/openapi-v1.json").read_text()) == json.loads(
        json.dumps(live, sort_keys=True)
    )


_WORK = Path(tempfile.mkdtemp(prefix="maat-contract-"))
_USERS = _WORK / "users.toml"
_USERS.write_text(
    f'[[users]]\nname="v"\nrole="viewer"\ntoken_sha256="{hashlib.sha256(b"viewer").hexdigest()}"\n'
)
_APP = create_app(ApiSettings(runs_dir=_WORK / "runs", users_file=_USERS))
schema = schemathesis.openapi.from_asgi("/openapi.json", _APP)


@schema.parametrize()
def test_no_server_errors_with_invalid_token(case):
    case.headers = {"Authorization": "Bearer invalid"}
    assert case.call().status_code < 500


@schema.include(method="GET").parametrize()
def test_no_server_errors_on_reads_as_viewer(case):
    case.headers = {"Authorization": "Bearer viewer"}
    assert case.call().status_code < 500


@schema.include(path="/api/v1/verify").parametrize()
def test_verify_upload_never_5xx(case):
    case.headers = {"Authorization": "Bearer viewer"}
    assert case.call().status_code < 500
