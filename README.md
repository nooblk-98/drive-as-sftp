# Google Drive as FTP Server

A Python application that creates an FTP server interface for your Google Drive, allowing you to access and manage your Google Drive files using any FTP client.

## Features

- 🔐 Secure Google Drive authentication using OAuth2
- 📁 Browse Google Drive files and folders via FTP
- ⬆️ Upload files to Google Drive through FTP
- ⬇️ Download files from Google Drive through FTP
- ✏️ Rename and delete files/folders
- 📂 Create new folders
- 🔄 Standard FTP operations (LIST, RETR, STOR, DELE, etc.)

## Prerequisites

- Python 3.7 or higher
- Google Cloud account
- Google Drive API credentials

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/drive-as-ftp.git
cd drive-as-ftp
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

If you see `error: externally-managed-environment` (PEP 668), install inside a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up Google Drive API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google Drive API**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"
4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Select "Desktop app" as the application type
   - Download the credentials JSON file
5. Save the downloaded file as `credentials.json` in the project directory

### 4. Configure the application

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and configure your settings:
   ```
   # FTP Server Configuration
   FTP_HOST=0.0.0.0
   FTP_PORT=2121
   FTP_USERNAME=admin
   FTP_PASSWORD=admin123
   FTP_MAX_CONNECTIONS=256
   FTP_MAX_CONNECTIONS_PER_IP=5

   # Google Drive Settings
   CREDENTIALS_FILE=credentials.json
   TOKEN_FILE=token.json
   OAUTH_CONSOLE=true

   # Logging Settings
   LOG_LEVEL=INFO
   LOG_FILE=logs/ftp_server.log

   # Performance Settings
   CACHE_ENABLED=true
   CACHE_TIMEOUT=60
   ```

## Usage

### Start the FTP server

```bash
python main.py
```

On the first run, a browser window will open asking you to authorize the application to access your Google Drive. After authorization, a `token.json` file will be created for future sessions.

If you're running on a remote server, keep `OAUTH_CONSOLE=true` so the app prints an authorization URL and prompts for the code in the terminal.

## Install as a Linux service (systemd)

This installs the app under `/opt/drive-as-ftp`, creates a `driveftp` system user, and registers a `driveftp` service.

```bash
sudo bash scripts/install.sh
```

Direct install:

```bash
curl -fsSL https://raw.githubusercontent.com/nooblk-98/drive-as-ftp/refs/heads/main/scripts/install.sh | sudo bash
```

Copy your `credentials.json` into `/opt/drive-as-ftp` before using the Authenticate menu option.

After installation, run the menu:

```bash
driveftp
```

Menu options include start/stop, authenticate, status, logs, settings, update, reinstall, and uninstall.

### Connect with an FTP client

You can use any FTP client (FileZilla, WinSCP, command-line ftp, etc.) with these settings:

- **Host:** `localhost` (or your server IP)
- **Port:** `2121` (or the port you configured)
- **Username:** `admin` (or the username you configured)
- **Password:** `admin123` (or the password you configured)
- **Protocol:** FTP (not FTPS or SFTP)

#### Example using command-line FTP:

```bash
ftp localhost 2121
# Enter username and password when prompted
```

#### Example using FileZilla:

1. Open FileZilla
2. Enter the connection details in the Quickconnect bar
3. Click "Quickconnect"

## Project Structure

```
drive-as-ftp/
├── main.py                           # Main application entry point
├── src/                              # Source code directory
│   ├── __init__.py                   # Package initialization
│   ├── auth/                         # Authentication module
│   │   ├── __init__.py
│   │   └── gdrive_auth.py           # Google Drive OAuth2 authentication
│   ├── filesystem/                   # Filesystem module
│   │   ├── __init__.py
│   │   └── gdrive_filesystem.py     # Google Drive filesystem operations
│   ├── server/                       # FTP Server module
│   │   ├── __init__.py
│   │   └── ftp_server.py            # FTP server implementation
│   └── utils/                        # Utility modules
│       ├── __init__.py
│       ├── config.py                # Configuration management
│       └── logger.py                # Logging utilities
├── config/                           # Configuration directory
├── logs/                             # Log files directory
├── requirements.txt                  # Python dependencies
├── .env.example                     # Environment variables template
├── .gitignore                       # Git ignore rules
└── README.md                        # This file
```

## How It Works

1. **Authentication:** The application uses OAuth2 to authenticate with Google Drive API
2. **FTP Server:** A custom FTP server is created using `pyftpdlib`
3. **Filesystem Bridge:** The `GoogleDriveFTPFilesystem` class translates FTP operations to Google Drive API calls
4. **File Operations:** 
   - Downloads are streamed from Google Drive
   - Uploads use temporary files before uploading to Google Drive
   - Directory operations map to Google Drive folder operations

## Security Notes

⚠️ **Important Security Considerations:**

- The default FTP protocol is **not encrypted**. Data is transmitted in plain text.
- For production use, consider:
  - Using FTPS (FTP over SSL/TLS)
  - Implementing strong passwords
  - Restricting access by IP address
  - Running behind a VPN or firewall
- Keep your `credentials.json` and `token.json` files secure
- Never commit these files to version control (they're in `.gitignore`)

## Limitations

- Google Docs, Sheets, and Slides cannot be downloaded directly (they're Google-native formats)
- Large file uploads/downloads may take time
- FTP connections are not encrypted by default
- Rate limits apply based on Google Drive API quotas

## Troubleshooting

### "Credentials file not found" error
Make sure you've downloaded the OAuth credentials from Google Cloud Console and saved them as `credentials.json`.

### Authentication browser doesn't open
The application will print a URL in the console. Copy and paste it into your browser manually.

### "Permission denied" errors
Check that your Google Cloud project has the Google Drive API enabled and your OAuth consent screen is properly configured.

### FTP connection refused
- Check that the port (default 2121) is not blocked by your firewall
- Verify the FTP_HOST and FTP_PORT settings in your `.env` file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This is an unofficial project and is not affiliated with or endorsed by Google. Use at your own risk.
