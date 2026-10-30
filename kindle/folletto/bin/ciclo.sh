#!/bin/sh
DIR=/mnt/us/extensions/folletto/bin
. "$DIR/config.sh"
# Spengo l'interfaccia del Kindle, così non ridisegna la libreria sopra il folletto.
# Per tornare al Kindle normale: tieni premuto il tasto di accensione finché si riavvia.
sleep 3
stop lab126_gui >/dev/null 2>&1 || stop framework >/dev/null 2>&1
sleep 2
eips -c
n=0
while true; do
  if wget -q -O /tmp/folletto.new "$URL" && [ -s /tmp/folletto.new ]; then
    mv /tmp/folletto.new /tmp/folletto.png
    # refresh completo ogni 5 giri per pulire le ombre dell'e-ink
    if [ $((n % 5)) -eq 0 ]; then eips -f -g /tmp/folletto.png; else eips -g /tmp/folletto.png; fi
  else
    eips 2 38 "Mac non raggiungibile, riprovo...  "
  fi
  n=$((n + 1))
  sleep "$INTERVALLO"
done
