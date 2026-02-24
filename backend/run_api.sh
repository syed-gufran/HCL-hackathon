#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -x "../venv/bin/python3.14" ]; then
  exec ../venv/bin/python3.14 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
elif [ -x "venv/bin/python3.14" ]; then
  exec venv/bin/python3.14 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
else
  exec python3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
fi
