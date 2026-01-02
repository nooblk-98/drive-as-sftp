# Google Drive as SFTP Server

An SFTP server backed by Google Drive. Connect with any SFTP client and manage
files directly in your Drive.

## Features

- OAuth2 authentication for Google Drive
- Browse, upload, download, rename, delete, and create folders via SFTP
- Single-port SFTP (default `2121`)

## Prerequisites

- Python 3.7+
- Google Cloud account
- Google Drive API credentials

## Installation

Direct install (recommended):

```bash
curl -fsSL "https://raw.githubusercontent.com/nooblk-98/drive-as-ftp/refs/heads/main/scripts/install.sh" | sudo bash
```

Manual install:

```bash
git clone https://github.com/yourusername/drive-as-ftp.git
cd drive-as-ftp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you see `error: externally-managed-environment` (PEP 668), you must use a
virtual environment.

## Google Drive API setup

1. Go to https://console.cloud.google.com/
2. Create a project and enable **Google Drive API**
3. Create OAuth 2.0 credentials:
   - APIs & Services > Credentials
   - Create Credentials > OAuth client ID
   - Application type: Desktop app
4. Download the JSON and save it as `credentials.json`

## Configuration

Use the menu to edit settings (recommended):

```bash
drivesftp
# then choose: 6) Settings (.env)
```

Manual `.env` keys (if needed):

```
# SFTP Server Configuration
SFTP_HOST=0.0.0.0
SFTP_PORT=2121
SFTP_USERNAME=admin
SFTP_PASSWORD=admin123
SFTP_ROOT_PATH=/
SFTP_HOST_KEY=config/sftp_host_key

# Google Drive Settings
CREDENTIALS_FILE=credentials.json
TOKEN_FILE=token.json
OAUTH_CONSOLE=true

# Logging Settings
LOG_LEVEL=INFO
LOG_FILE=logs/sftp_server.log

# Performance Settings
CACHE_ENABLED=true
CACHE_TIMEOUT=60
```

## Usage

After installation, run the menu:

```bash
drivesftp
```

Menu options include start/stop, authenticate, status, logs, settings, update,
reinstall, and uninstall.

### Connect with an SFTP client

Use any SFTP client (FileZilla, WinSCP, or command-line `sftp`) with:

- Host: `your.server.ip`
- Port: `2121`
- Username: `admin`
- Password: `admin123`
- Protocol: SFTP

Example:

```bash
sftp -P 2121 admin@your.server.ip
```

## How it works

1. OAuth2 authenticates with Google Drive API
2. Paramiko provides the SFTP server
3. A filesystem bridge maps SFTP operations to Google Drive API calls

## Security notes

- SFTP runs over SSH and is encrypted in transit
- Use strong passwords or SSH keys for production
- Keep `credentials.json` and `token.json` private
- Never commit credentials to source control

## Limitations

- Google Docs/Sheets/Slides are not downloadable as files
- Large uploads can be slow due to Drive API limits

## Troubleshooting

### Credentials file not found
Make sure `credentials.json` exists in the app directory.

### Authentication browser doesn't open
Use console auth: keep `OAUTH_CONSOLE=true` and follow the printed URL.

### SFTP connection refused
- Check that port `2121` is open on your firewall/security group
- Verify `SFTP_HOST` and `SFTP_PORT` in `.env`

## License

Provided as-is for educational and personal use.

## Disclaimer

This is an unofficial project and is not affiliated with or endorsed by Google.
