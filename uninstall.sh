#!/bin/bash
# Rimuove il folletto dal Mac. Sul Kindle basta cancellare extensions/folletto.
plist="$HOME/Library/LaunchAgents/com.folletto.dashboard.plist"
launchctl bootout "gui/$(id -u)" "$plist" 2>/dev/null || true
rm -f "$plist"

settings="$HOME/.claude/settings.json"
if [ -s "$settings" ] && command -v jq >/dev/null 2>&1 \
   && jq -e '.statusLine.command | tostring | test("statusline.sh")' "$settings" >/dev/null 2>&1; then
  jq 'del(.statusLine)' "$settings" > "$settings.tmp" && mv "$settings.tmp" "$settings"
fi
rm -f "$HOME/.claude/statusline.sh" "$HOME/.claude/usage-state.json"

echo "Folletto rimosso. I tuoi pensieri restano in ~/.claude/folletto/pensieri.txt"
echo "(cancella la cartella ~/.claude/folletto se non ti servono più)."
