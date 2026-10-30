#!/bin/bash
# Installa il folletto sul Mac e prepara la cartella da copiare sul Kindle.
#
# Uso:  bash install.sh [verticale|sinistra|destra]
#   verticale  Kindle in piedi (predefinito)
#   sinistra   Kindle in orizzontale, porta di ricarica a sinistra
#   destra     Kindle in orizzontale, porta di ricarica a destra
set -e
here="$(cd "$(dirname "$0")" && pwd)"
ORIENTAMENTO="${1:-verticale}"
PORT=8765
dest="$HOME/.claude/folletto"
plist="$HOME/Library/LaunchAgents/com.folletto.dashboard.plist"

case "$ORIENTAMENTO" in verticale|sinistra|destra) ;; *)
  echo "Orientamento sconosciuto: $ORIENTAMENTO (usa verticale, sinistra o destra)"; exit 1;;
esac

# 1. dipendenze ------------------------------------------------------------------
if ! command -v jq >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    echo "→ Installo jq…"; brew install jq
  else
    echo "Serve jq (o Homebrew per installarlo: https://brew.sh)."; exit 1
  fi
fi
if command -v brew >/dev/null 2>&1 && ! command -v icalBuddy >/dev/null 2>&1; then
  echo "→ Installo icalBuddy per la modalità meeting (facoltativo)…"
  brew install ical-buddy || echo "  icalBuddy non installato: la modalità meeting resterà spenta."
fi

# 2. status line di Claude Code ---------------------------------------------------
echo "→ Collego la status line di Claude Code…"
mkdir -p "$HOME/.claude"
cp "$here/mac/statusline.sh" "$HOME/.claude/statusline.sh"
chmod +x "$HOME/.claude/statusline.sh"
settings="$HOME/.claude/settings.json"
[ -s "$settings" ] || echo '{}' > "$settings"
cp "$settings" "$settings.backup-$(date +%Y%m%d%H%M%S)"
jq --arg cmd "$HOME/.claude/statusline.sh" '.statusLine = {type: "command", command: $cmd}' \
  "$settings" > "$settings.tmp" && mv "$settings.tmp" "$settings"

# 3. server della dashboard -------------------------------------------------------
echo "→ Installo la dashboard e la faccio partire a ogni accensione…"
mkdir -p "$dest"
cp "$here/mac/kindle_dash.py" "$dest/kindle_dash.py"
if [ ! -f "$dest/pensieri.txt" ]; then
  cat > "$dest/pensieri.txt" <<'FINE'
# I tuoi pensieri per il folletto: una frase per riga.
# Le righe che iniziano con # vengono ignorate. Non serve riavviare nulla.
FINE
fi
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.folletto.dashboard</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string><string>$dest/kindle_dash.py</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>KINDLE_DASH_PORT</key><string>$PORT</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$dest/errori.log</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)" "$plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"

# 4. cartella per il Kindle -------------------------------------------------------
ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -z "$ip" ]; then
  echo "Non trovo l'indirizzo del Mac sulla rete: sei collegato al Wi-Fi?"; exit 1
fi
echo "→ Preparo la cartella per il Kindle…"
ext="$HOME/Desktop/folletto"
mkdir -p "$HOME/Desktop"
rm -rf "$ext"
cp -R "$here/kindle/folletto" "$ext"
rm -f "$ext/bin/config.sh.example"
cat > "$ext/bin/config.sh" <<EOF
# Generato da install.sh. Se il Mac cambia indirizzo sulla rete, rilancia install.sh.
# ORIENTAMENTO: verticale | sinistra (porta di ricarica a sinistra) | destra
ORIENTAMENTO=$ORIENTAMENTO
URL="http://$ip:$PORT/dash.png?o=\$ORIENTAMENTO"
INTERVALLO=120   # secondi tra un aggiornamento e l'altro
EOF
chmod +x "$ext/bin/"*.sh

sleep 3
echo ""
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/dash.png" | grep -q 200; then
  echo "✓ La dashboard gira. Anteprima: http://localhost:$PORT/"
else
  echo "! La dashboard non risponde ancora: guarda $dest/errori.log"
fi
echo "✓ Cartella per il Kindle: $ext  →  copiala dentro 'extensions' sul Kindle"
echo "✓ I tuoi pensieri: $dest/pensieri.txt"
echo "  Il Kindle scaricherà: http://$ip:$PORT/dash.png?o=$ORIENTAMENTO"
echo "  Riavvia Claude Code e manda un messaggio per svegliare il folletto."
