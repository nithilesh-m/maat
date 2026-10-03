#!/usr/bin/env bash
set -euo pipefail
npx openapi-typescript ../docs/api/openapi-v1.json -o lib/api/schema.d.ts
