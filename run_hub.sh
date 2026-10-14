#!/usr/bin/env bash
cd "$(dirname "$0")"
pkill -f "http.server 8420" 2>/dev/null || true
nohup ./.venv/bin/python -m http.server 8420 --bind 127.0.0.1 >/tmp/ita_hub.log 2>&1 &
sleep 0.5
xdg-open "http://127.0.0.1:8420" >/dev/null 2>&1 &
