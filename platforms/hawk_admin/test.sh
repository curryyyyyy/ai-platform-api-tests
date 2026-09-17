#!/usr/bin/env bash
# Validate the committed platform contract before executing its tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi
validate_runtime=1
marker_expression=""
previous=""
for argument in "$@"; do
  if [[ "$previous" == "-m" || "$previous" == "--markers" ]]; then
    marker_expression="$argument"
    break
  fi
  previous="$argument"
done
if [[ "$marker_expression" == *"not live"* && "$marker_expression" != *"and live"* ]] \
  || [[ "$marker_expression" == *contract* && "$marker_expression" != *live* ]]; then
  validate_runtime=0
fi
if [ "$validate_runtime" -eq 1 ]; then
  "$PYTHON" "$ROOT/scripts/validate_runtime.py" --platform hawk_admin
fi
exec "$ROOT/scripts/run_tests.sh" "$ROOT/tests/hawk_admin" "$@"
