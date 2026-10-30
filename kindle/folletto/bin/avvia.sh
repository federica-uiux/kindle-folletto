#!/bin/sh
DIR=/mnt/us/extensions/folletto/bin
[ -f /tmp/folletto.pid ] && kill "$(cat /tmp/folletto.pid)" 2>/dev/null
lipc-set-prop com.lab126.powerd preventScreenSaver 1
# setsid stacca il ciclo da KUAL, così sopravvive quando l'interfaccia si spegne
if command -v setsid >/dev/null 2>&1; then
  setsid sh "$DIR/ciclo.sh" >/dev/null 2>&1 < /dev/null &
else
  nohup sh "$DIR/ciclo.sh" >/dev/null 2>&1 < /dev/null &
fi
echo $! > /tmp/folletto.pid
