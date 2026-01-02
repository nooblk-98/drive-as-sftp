#!/usr/bin/env bash
set -euo pipefail

APP_NAME="driveftp"
APP_DIR="${APP_DIR:-/opt/drive-as-ftp}"
SERVICE_USER="${SERVICE_USER:-driveftp}"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
MENU_BIN="/usr/local/bin/${APP_NAME}"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo bash scripts/install.sh"
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemd is required for this installer."
  exit 1
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd -r -s /usr/sbin/nologin -d "$APP_DIR" "$SERVICE_USER"
fi

mkdir -p "$APP_DIR" "$APP_DIR/logs"

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude .git \
    --exclude .venv \
    --exclude logs \
    --exclude token.json \
    --exclude credentials.json \
    ./ "$APP_DIR/"
else
  tar --exclude='.git' --exclude='.venv' --exclude='logs' \
      --exclude='token.json' --exclude='credentials.json' -cf - . \
    | tar -xf - -C "$APP_DIR"
fi

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Drive-as-FTP server
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$VENV_DIR/bin/python $APP_DIR/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > "$MENU_BIN" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

APP_NAME="driveftp"
APP_DIR="/opt/drive-as-ftp"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
VENV_DIR="$APP_DIR/.venv"
SERVICE_USER="driveftp"

run_root() {
  if [[ $EUID -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

run_as_service_user() {
  if [[ $EUID -eq 0 ]]; then
    su -s /bin/bash -c "$*" "$SERVICE_USER"
  else
    sudo -u "$SERVICE_USER" bash -c "$*"
  fi
}

while true; do
  echo ""
  echo "DriveFTP menu"
  echo "1) Start service"
  echo "2) Stop service"
  echo "3) Authenticate (console)"
  echo "4) Status"
  echo "5) Logs (tail)"
  echo "6) Settings (.env)"
  echo "0) Exit"
  echo -n "Select: "
  read -r choice

  case "$choice" in
    1)
      run_root systemctl start "$APP_NAME"
      ;;
    2)
      run_root systemctl stop "$APP_NAME"
      ;;
    3)
      if [[ ! -f "$SERVICE_FILE" ]]; then
        echo "Service not installed. Run scripts/install.sh first."
        continue
      fi
      if [[ ! -f "$APP_DIR/credentials.json" ]]; then
        echo "Missing credentials.json in $APP_DIR"
        continue
      fi
      if [[ -f "$APP_DIR/token.json" ]]; then
        echo "Removing existing token.json"
        run_root rm -f "$APP_DIR/token.json"
      fi
      run_as_service_user "cd $APP_DIR && OAUTH_CONSOLE=true $VENV_DIR/bin/python main.py"
      ;;
    4)
      run_root systemctl status "$APP_NAME" --no-pager
      ;;
    5)
      run_root journalctl -u "$APP_NAME" -f
      ;;
    6)
      run_root "${EDITOR:-nano}" "$APP_DIR/.env"
      ;;
    0)
      exit 0
      ;;
    *)
      echo "Invalid option"
      ;;
  esac

done
EOF

chmod 0755 "$MENU_BIN"
chown -R "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

systemctl daemon-reload
systemctl enable "$APP_NAME"

echo "Installed. Use: $APP_NAME"
