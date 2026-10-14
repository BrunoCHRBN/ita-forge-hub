#!/usr/bin/env bash
cd "$(dirname "$0")"

# Puxa atualizações do GitHub silenciosamente
git pull --rebase --autostash >/dev/null 2>&1 &

# Mantém o servidor vivo em background na porta 8420
if ! ss -tulpn | grep -q ":8420 "; then
  nohup python -m http.server 8420 --bind 127.0.0.1 >/dev/null 2>&1 &
  sleep 0.4
fi

URL="http://127.0.0.1:8420"

if command -v brave >/dev/null 2>&1; then
  brave --app="$URL" &
elif command -v chromium >/dev/null 2>&1; then
  chromium --app="$URL" &
elif command -v google-chrome-stable >/dev/null 2>&1; then
  google-chrome-stable --app="$URL" &
elif command -v firefox >/dev/null 2>&1; then
  firefox --new-window "$URL" &
else
  xdg-open "$URL" &
fi
