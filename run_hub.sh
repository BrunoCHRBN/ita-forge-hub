#!/usr/bin/env bash
cd "$(dirname "$0")"

# 1. Puxa silenciosamente novas provas/imagens que o GitHub Actions já salvou no repositório
git pull --rebase --autostash >/dev/null 2>&1 &

# 2. Inicia o servidor Python na porta 8420 apenas se ainda não estiver rodando
if ! ss -tulpn | grep -q ":8420 "; then
  python -m http.server 8420 --bind 127.0.0.1 >/dev/null 2>&1 &
  SERVER_PID=$!
  trap "kill $SERVER_PID 2>/dev/null" EXIT
fi

URL="http://127.0.0.1:8420"

# 3. Abre em modo WebApp limpo (ideal para o tiling do Hyprland)
if command -v brave >/dev/null 2>&1; then
  brave --app="$URL"
elif command -v chromium >/dev/null 2>&1; then
  chromium --app="$URL"
elif command -v google-chrome-stable >/dev/null 2>&1; then
  google-chrome-stable --app="$URL"
elif command -v firefox >/dev/null 2>&1; then
  firefox --new-window "$URL"
else
  xdg-open "$URL"
fi
