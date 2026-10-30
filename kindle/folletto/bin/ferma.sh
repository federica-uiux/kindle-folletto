#!/bin/sh
[ -f /tmp/folletto.pid ] && kill "$(cat /tmp/folletto.pid)" 2>/dev/null
rm -f /tmp/folletto.pid
lipc-set-prop com.lab126.powerd preventScreenSaver 0
start lab126_gui >/dev/null 2>&1 || start framework >/dev/null 2>&1
lipc-set-prop com.lab126.appmgrd start app://com.lab126.booklet.home 2>/dev/null
