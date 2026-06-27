#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

: "${HTTP_SHELL_TOKEN:=change-me-to-a-complex-token}"
: "${HTTP_SHELL_HOST:=127.0.0.1}"
: "${HTTP_SHELL_PORT:=8080}"

python3 ./http_shell.py \
  --host "$HTTP_SHELL_HOST" \
  --port "$HTTP_SHELL_PORT" \
  --token "$HTTP_SHELL_TOKEN"
