#!/usr/bin/env bash
# Deploy the Zepto pulse HTML report to Vercel (static hosting).
#
# One-time setup:
#   npm i -g vercel          # or: npx vercel (no global install)
#   vercel login
#   cd phase-7-orchestration && vercel link   # link to a Vercel project
#
# Manual deploy:
#   bash scripts/deploy_vercel.sh
#
# Auto-deploy after weekly run (optional):
#   export PULSE_VERCEL_DEPLOY=1
#   bash scripts/run_weekly.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DOC="out/docs/zepto-weekly-pulse.html"
if [[ ! -f "$DOC" ]]; then
  echo "error: $DOC not found — run the pulse first:" >&2
  echo "  python -m pulse.cli run --product zepto --week 2026-W28" >&2
  exit 1
fi

# Root URL serves the review-collection dashboard (falls back to the weekly report).
if [[ -f "$ROOT/out/docs/dashboard.html" ]]; then
  cp "$ROOT/out/docs/dashboard.html" "$ROOT/out/docs/index.html"
else
  cp "$DOC" "$ROOT/out/docs/index.html"
fi

DEPLOY_DIR="$ROOT/out/docs"
cd "$DEPLOY_DIR"

if command -v npx >/dev/null 2>&1; then
  VERCEL=(npx --yes vercel@latest)
elif command -v vercel >/dev/null 2>&1; then
  VERCEL=(vercel)
else
  echo "error: install Node.js/npx or the Vercel CLI — npm i -g vercel@latest" >&2
  exit 1
fi

echo "Deploying $DEPLOY_DIR → Vercel (production)…"
SCOPE_ARGS=()
# Default team scope (override with VERCEL_SCOPE=your-team).
SCOPE="${VERCEL_SCOPE:-nikhilt27s-projects}"
if [[ -n "$SCOPE" ]]; then
  SCOPE_ARGS=(--scope "$SCOPE")
fi
"${VERCEL[@]}" deploy --prod --yes "${SCOPE_ARGS[@]}"

echo "Done. Open the production URL shown above (or your Vercel dashboard)."
