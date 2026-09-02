#!/usr/bin/env bash
set -euo pipefail

mkdir -p reports/allure reports/junit
pytest "$@" \
  --alluredir=reports/allure \
  --junitxml=reports/junit/results.xml
