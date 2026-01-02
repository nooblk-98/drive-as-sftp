#!/usr/bin/env bash
set -euo pipefail

APP_NAME="driveftp"
APP_DIR="${APP_DIR:-/opt/drive-as-ftp}"
SERVICE_USER="${SERVICE_USER:-driveftp}"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
MENU_BIN="/usr/local/bin/${APP_NAME}"
REPO_URL="${REPO_URL:-https://github.com/nooblk-98/drive-as-ftp.git}"

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

if [[ -f "./requirements.txt" ]]; then
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
else
  if ! command -v git >/dev/null 2>&1; then
    echo "git is required for direct install. Install git and re-run."
    exit 1
  fi
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" pull --ff-only
  else
    rm -rf "$APP_DIR"
    git clone "$REPO_URL" "$APP_DIR"
  fi
fi

if [[ ! -f "$APP_DIR/requirements.txt" ]]; then
  echo "requirements.txt not found in $APP_DIR. Clone or copy failed."
  exit 1
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

auth_only() {
  run_as_service_user "cd $APP_DIR && OAUTH_CONSOLE=true $VENV_DIR/bin/python - <<'PY'\nfrom src.auth import GoogleDriveAuth\nfrom src.utils.config import Config\ncfg = Config()\nauth = GoogleDriveAuth(cfg.credentials_file, cfg.token_file)\nauth.authenticate()\nprint('Authentication complete')\nPY"
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
  echo "7) Update app"
  echo "8) Reinstall service"
  echo "9) Uninstall"
  echo "0) Exit"
  echo -n "Select: "
  read -r choice

  case "$choice" in
    1)
      if [[ ! -f "$APP_DIR/.env" && -f "$APP_DIR/.env.example" ]]; then
        run_root cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        run_root chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
      fi
      if [[ ! -f "$APP_DIR/.env" ]]; then
        echo "Missing $APP_DIR/.env. Create it or copy from .env.example."
        continue
      fi
      if [[ ! -f "$APP_DIR/credentials.json" ]]; then
        echo "Missing credentials.json in $APP_DIR."
        echo "Paste the full credentials.json content now, then press Ctrl-D."
        run_root bash -c "cat > \"$APP_DIR/credentials.json\""
        run_root chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/credentials.json"
      fi
      if [[ ! -s "$APP_DIR/credentials.json" ]]; then
        echo "credentials.json is empty. Start aborted."
        continue
      fi
      if [[ ! -f "$APP_DIR/token.json" ]]; then
        echo "No token.json found. Starting console authentication..."
        auth_only
      fi
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
      auth_only
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
    7)
      if [[ ! -d "$APP_DIR/.git" ]]; then
        echo "No git repo in $APP_DIR. Update requires git."
        continue
      fi
      run_as_service_user "cd $APP_DIR && git pull --ff-only"
      run_root systemctl restart "$APP_NAME"
      ;;
    8)
      if [[ ! -x "$APP_DIR/scripts/install.sh" ]]; then
        echo "Installer not found at $APP_DIR/scripts/install.sh"
        continue
      fi
      run_root bash "$APP_DIR/scripts/install.sh"
      ;;
    9)
      read -r -p "Uninstall service and remove $APP_DIR? [y/N] " confirm
      if [[ "${confirm:-N}" != "y" && "${confirm:-N}" != "Y" ]]; then
        continue
      fi
      run_root systemctl stop "$APP_NAME" || true
      run_root systemctl disable "$APP_NAME" || true
      run_root rm -f "$SERVICE_FILE"
      run_root systemctl daemon-reload
      run_root rm -f "/usr/local/bin/$APP_NAME"
      run_root rm -rf "$APP_DIR"
      echo "Uninstalled."
      exit 0
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
