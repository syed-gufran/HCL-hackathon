#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec venv/bin/python3.14 -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
