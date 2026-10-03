"""Print the deterministic OpenAPI document of API v1.

uv run python scripts/export_openapi.py > docs/api/openapi-v1.json
"""

import json
import sys
import tempfile
from pathlib import Path

from maat.api.app import create_app
from maat.api.settings import ApiSettings

with tempfile.TemporaryDirectory() as td:
    schema = create_app(ApiSettings(runs_dir=Path(td))).openapi()
sys.stdout.write(json.dumps(schema, indent=2, sort_keys=True) + "\n")
