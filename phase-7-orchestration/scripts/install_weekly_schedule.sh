#!/usr/bin/env bash
# Install a macOS launchd job that runs the Zepto weekly pulse every Monday at 9:00 AM local time.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_SRC="$ROOT/scripts/com.zepto.pulse.weekly.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.zepto.pulse.weekly.plist"
RUN_SCRIPT="$ROOT/scripts/run_weekly.sh"

chmod +x "$RUN_SCRIPT"

# Remove the previous Spotify schedule if present.
launchctl bootout "gui/$(id -u)/com.spotify.pulse.weekly" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.spotify.pulse.weekly.plist"

# Substitute the project root into the plist template.
sed "s|__PULSE_ROOT__|$ROOT|g" "$PLIST_SRC" >"$PLIST_DST"

launchctl bootout "gui/$(id -u)/com.zepto.pulse.weekly" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.zepto.pulse.weekly"
launchctl kickstart -k "gui/$(id -u)/com.zepto.pulse.weekly" 2>/dev/null || true

echo "Installed weekly Zepto schedule → $PLIST_DST"
echo "Runs every Monday 9:00 AM (local time) + Vercel auto-deploy."
echo "Logs: $ROOT/.pulse/logs/"
echo ""
echo "To uninstall:"
echo "  launchctl bootout gui/$(id -u)/com.zepto.pulse.weekly"
echo "  rm $PLIST_DST"
