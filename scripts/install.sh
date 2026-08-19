#!/usr/bin/env bash
# Install on Ubuntu/Debian VPS into /opt/tg-bitrix
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/tg-bitrix}"
SERVICE_USER="${SERVICE_USER:-ubuntu}"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash scripts/install.sh"
  exit 1
fi

apt-get update -y
apt-get install -y python3 python3-venv python3-pip

mkdir -p "$APP_DIR"
# Copy project files without wiping an existing .env / .venv
shopt -s dotglob nullglob
for item in "$REPO_DIR"/*; do
  base="$(basename "$item")"
  case "$base" in
    .git|.venv|__pycache__|.env) continue ;;
  esac
  rm -rf "$APP_DIR/$base"
  cp -a "$item" "$APP_DIR/"
done
shopt -u dotglob nullglob

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "Created $APP_DIR/.env — заполните TELEGRAM_BOT_TOKEN и CRM (BITRIX_WEBHOOK_URL и/или ESPO_URL+ESPO_API_KEY)"
fi

chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# Patch systemd user if needed
sed "s/User=ubuntu/User=$SERVICE_USER/" "$APP_DIR/systemd/tg-bitrix.service" \
  > /etc/systemd/system/tg-bitrix.service

systemctl daemon-reload
systemctl enable tg-bitrix.service

echo
echo "OK. Дальше:"
echo "  1) nano $APP_DIR/.env"
echo "  2) systemctl start tg-bitrix"
echo "  3) journalctl -u tg-bitrix -f"
