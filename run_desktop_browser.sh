#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export DISPLAY=:99
export QT_QPA_PLATFORM=xcb

Xvfb :99 -screen 0 1440x900x24 >/tmp/neuroshield_xvfb.log 2>&1 &
Xvfb_PID=$!

sleep 2

python app.py >/tmp/neuroshield_app.log 2>&1 &
APP_PID=$!

x11vnc -display :99 -shared -forever -noxdamage -rfbport 5900 -localhost >/tmp/neuroshield_x11vnc.log 2>&1 &
X11VNC_PID=$!

websockify --web /usr/share/novnc/ 6080 localhost:5900 >/tmp/neuroshield_websockify.log 2>&1 &
WEBSOCKIFY_PID=$!

printf 'Xvfb PID: %s\n' "$Xvfb_PID"
printf 'App PID: %s\n' "$APP_PID"
printf 'x11vnc PID: %s\n' "$X11VNC_PID"
printf 'websockify PID: %s\n' "$WEBSOCKIFY_PID"
printf 'Open: http://localhost:6080/vnc.html\n'

wait "$APP_PID"
kill "$X11VNC_PID" "$WEBSOCKIFY_PID" "$Xvfb_PID" 2>/dev/null || true
