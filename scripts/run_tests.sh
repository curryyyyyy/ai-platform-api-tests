#!/usr/bin/env bash
# 统一执行入口：跑测试并产出 Allure 原始结果与 JUnit XML，可选生成/打开 HTML 报告。
#
#   ./scripts/run_tests.sh -m contract                 只产出报告数据
#   ./scripts/run_tests.sh -m contract --report        额外生成静态 HTML
#   ./scripts/run_tests.sh -m contract --open          生成 HTML 并在浏览器打开
#   ./scripts/run_tests.sh -m contract --serve         用临时目录起服务并打开（不落盘 HTML）
#   ./scripts/run_tests.sh -m contract --no-clean      保留当前结果目录，用于趋势对比
#   ./scripts/run_tests.sh --no-skips -m "core and live"  将跳过视为门禁失败
#   FEISHU_WEBHOOK_URL=... ./scripts/run_tests.sh --notify-feishu -m contract
#                                                        本地发送本轮 JUnit 汇总
#   REPORT_KEEP=3 ./scripts/run_tests.sh -m contract   临时保留最近 3 次报告
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ALLURE_DIR="reports/allure"
JUNIT_DIR="reports/junit"
HTML_DIR="reports/allure-report"
REPORTS_ROOT="reports"
MODE="results"
CLEAN=1
REPORT_KEEP="${REPORT_KEEP:-5}"
FAIL_ON_SKIP=0
NOTIFY_FEISHU=0
PYTEST_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --report) MODE="report"; shift ;;
    --open) MODE="open"; shift ;;
    --serve) MODE="serve"; shift ;;
    --no-clean) CLEAN=0; shift ;;
    --no-skips) FAIL_ON_SKIP=1; shift ;;
    --notify-feishu) NOTIFY_FEISHU=1; shift ;;
    --keep) REPORT_KEEP="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) PYTEST_ARGS+=("$1"); shift ;;
  esac
done

if ! [[ "$REPORT_KEEP" =~ ^[1-9][0-9]*$ ]]; then
  echo "报告保留次数必须是大于 0 的整数，当前值: $REPORT_KEEP" >&2
  exit 2
fi

PYTEST="pytest"
if [ -x "$ROOT/.venv/bin/pytest" ]; then
  PYTEST="$ROOT/.venv/bin/pytest"
fi

PYTHON="python3"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

require_allure() {
  if ! command -v allure >/dev/null 2>&1; then
    echo "未检测到 allure 命令行，请先安装：brew install allure" >&2
    echo "（或用 npm i -g allure-commandline；安装后重跑本命令）" >&2
    exit 1
  fi
}

if [ "$MODE" != "results" ]; then
  require_allure
fi

mkdir -p "$JUNIT_DIR" "$ALLURE_DIR"
if [ "$CLEAN" -eq 1 ]; then
  rm -rf "${ALLURE_DIR:?}"/*
fi

ALLURE_FLAGS=(--alluredir="$ALLURE_DIR" --junitxml="$JUNIT_DIR/results.xml")
if [ "$CLEAN" -eq 1 ]; then
  ALLURE_FLAGS+=(--clean-alluredir)
fi

set +e
"$PYTEST" ${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"} "${ALLURE_FLAGS[@]}"
STATUS=$?
set -e

INCLUDE_HTML=0

echo
echo "Allure 原始结果: $ROOT/$ALLURE_DIR"
echo "JUnit XML:       $ROOT/$JUNIT_DIR/results.xml"

GATE_STATUS=0
if [ "$FAIL_ON_SKIP" -eq 1 ]; then
  GATE_ARGS=("$ROOT/$JUNIT_DIR/results.xml" --no-skips)
  if [ -n "${CORE_EXPECTED_TESTS:-}" ]; then
    GATE_ARGS+=(--expected-tests "$CORE_EXPECTED_TESTS")
  fi
  if ! "$PYTHON" "$ROOT/scripts/check_junit_gate.py" "${GATE_ARGS[@]}"; then
    GATE_STATUS=1
  fi
fi

case "$MODE" in
  report)
    allure generate "$ALLURE_DIR" --clean -o "$HTML_DIR"
    echo "静态报告:        $ROOT/$HTML_DIR/index.html"
    INCLUDE_HTML=1
    ;;
  open)
    allure generate "$ALLURE_DIR" --clean -o "$HTML_DIR"
    echo "静态报告:        $ROOT/$HTML_DIR/index.html"
    INCLUDE_HTML=1
    ;;
  serve)
    :
    ;;
  results)
    echo "查看报告:        ./scripts/run_tests.sh --open ${PYTEST_ARGS[*]-}"
    ;;
esac

ARCHIVE_ARGS=(
  --reports-root "$ROOT/$REPORTS_ROOT"
  --keep "$REPORT_KEEP"
)
if [ "$INCLUDE_HTML" -eq 1 ]; then
  ARCHIVE_ARGS+=(--include-html)
fi
if ! "$PYTHON" "$ROOT/scripts/report_history.py" "${ARCHIVE_ARGS[@]}"; then
  echo "警告：本轮报告归档失败，当前报告仍保留在 $ROOT/$ALLURE_DIR 和 $ROOT/$JUNIT_DIR" >&2
fi

if [ "$NOTIFY_FEISHU" -eq 1 ]; then
  if ! "$PYTHON" "$ROOT/scripts/notify_feishu.py" --reports-dir "$ROOT/$JUNIT_DIR"; then
    echo "警告：飞书通知发送失败，测试结果仍按原状态返回" >&2
  fi
fi

case "$MODE" in
  open) allure open "$HTML_DIR" ;;
  serve) allure serve "$ALLURE_DIR" ;;
esac

if [ "$STATUS" -eq 0 ] && [ "$GATE_STATUS" -ne 0 ]; then
  STATUS="$GATE_STATUS"
fi

exit "$STATUS"
