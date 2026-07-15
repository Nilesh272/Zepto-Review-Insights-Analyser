#!/usr/bin/env bash
# Weekly Zepto pulse — runs the just-completed ISO week and appends to the local doc.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VENV="${PULSE_VENV:-$ROOT/.venv/bin/python}"
LEDGER="${PULSE_LEDGER:-$ROOT/.pulse/ledger.db}"
LOG_DIR="${PULSE_LOG_DIR:-$ROOT/.pulse/logs}"
mkdir -p "$(dirname "$LEDGER")" "$LOG_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/schedule-$STAMP.log"

{
  echo "=== pulse weekly run $STAMP ==="
  echo "cwd: $ROOT"
  "$VENV" -m pulse.cli --ledger "$LEDGER" schedule --product zepto 2>&1
  echo "=== done ==="
} >>"$LOG" 2>&1

# Optional: push the updated HTML to Vercel (set PULSE_VERCEL_DEPLOY=1).
if [[ "${PULSE_VERCEL_DEPLOY:-0}" == "1" ]]; then
  bash "$ROOT/scripts/deploy_vercel.sh" >>"$LOG" 2>&1 || echo "Vercel deploy failed (see log)" >>"$LOG"
fi

# Keep the last 20 log files (macOS-compatible).
ls -1t "$LOG_DIR"/schedule-*.log 2>/dev/null | tail -n +21 | xargs rm -f 2>/dev/null || true
