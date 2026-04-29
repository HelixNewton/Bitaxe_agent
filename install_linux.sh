#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python3}"
ENV_FILE="$SCRIPT_DIR/.env"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found at $PYTHON_BIN. Set PYTHON_BIN=/path/to/python3 and retry." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  echo "Created $ENV_FILE from .env.example. Edit MINER_URL before live control."
fi

touch "$SCRIPT_DIR/status.json" "$SCRIPT_DIR/learning.json"

controller_unit="$(mktemp)"
ui_unit="$(mktemp)"
trap 'rm -f "$controller_unit" "$ui_unit"' EXIT

cat >"$controller_unit" <<UNIT
[Unit]
Description=Bitaxe Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$PYTHON_BIN $SCRIPT_DIR/controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

cat >"$ui_unit" <<UNIT
[Unit]
Description=Bitaxe Agent UI
After=network-online.target bitaxe-agent.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$PYTHON_BIN $SCRIPT_DIR/ui_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

sudo install -m 0644 "$controller_unit" /etc/systemd/system/bitaxe-agent.service
sudo install -m 0644 "$ui_unit" /etc/systemd/system/bitaxe-agent-ui.service
sudo systemctl daemon-reload
sudo systemctl enable bitaxe-agent bitaxe-agent-ui
sudo systemctl restart bitaxe-agent bitaxe-agent-ui

echo "Installed services from $SCRIPT_DIR"
echo "Controller: sudo systemctl status bitaxe-agent --no-pager"
echo "Dashboard:  sudo systemctl status bitaxe-agent-ui --no-pager"
echo "Open:       http://127.0.0.1:8787/"
