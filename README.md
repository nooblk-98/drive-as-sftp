# Google Drive as SFTP Server

A Python application that creates an SFTP server interface for your Google Drive, allowing you to access and manage your Google Drive files using any SFTP client.

## Features

- Secure Google Drive authentication using OAuth2
- Browse Google Drive files and folders via SFTP
- Upload files to Google Drive through SFTP
- Download files from Google Drive through SFTP
- Rename and delete files/folders
- Create new folders

## Prerequisites

- Python 3.7 or higher
- Google Cloud account
- Google Drive API credentials

## Installation

Direct install:

```bash
curl -fsSL "https://raw.githubusercontent.com/nooblk-98/drive-as-ftp/refs/heads/main/scripts/install.sh" | sudo bash

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

Use the menu to edit settings (recommended):

```bash
drivesftp
# then choose: 6) Settings (.env)
```

## Usage

### Start the SFTP server

After installation, run the menu:

```bash
drivesftp
```

Menu options include start/stop, authenticate, status, logs, settings, update, reinstall, and uninstall.

### Connect with an SFTP client

You can use any SFTP client (FileZilla, WinSCP, command-line sftp, etc.) with these settings:

- **Host:** `localhost` (or your server IP)
- **Port:** `2121` (or the port you configured)
- **Username:** `admin` (or the username you configured)
- **Password:** `admin123` (or the password you configured)
- **Protocol:** SFTP

#### Example using command-line SFTP:

```bash
sftp -P 2121 admin@localhost
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
│   ├── server/                       # SFTP Server module
│   │   ├── __init__.py
│   │   └── sftp_server.py            # SFTP server implementation
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
2. **SFTP Server:** A custom SFTP server is created using `paramiko`
3. **Filesystem Bridge:** The filesystem wrapper translates SFTP operations to Google Drive API calls
4. **File Operations:** 
   - Downloads are streamed from Google Drive
   - Uploads use temporary files before uploading to Google Drive
   - Directory operations map to Google Drive folder operations

## Security Notes

⚠️ **Important Security Considerations:**

- SFTP runs over SSH and is encrypted in transit.
- For production use, consider:
  - Using SSH keys for authentication
  - Implementing strong passwords
  - Restricting access by IP address
  - Running behind a VPN or firewall
- Keep your `credentials.json` and `token.json` files secure
- Never commit these files to version control (they're in `.gitignore`)

## Limitations

- Google Docs, Sheets, and Slides cannot be downloaded directly (they're Google-native formats)
- Large file uploads/downloads may take time
- SFTP is encrypted, but Google Drive API rate limits still apply
- Rate limits apply based on Google Drive API quotas

## Troubleshooting

### "Credentials file not found" error
Make sure you've downloaded the OAuth credentials from Google Cloud Console and saved them as `credentials.json`.

### Authentication browser doesn't open
The application will print a URL in the console. Copy and paste it into your browser manually.

### "Permission denied" errors
Check that your Google Cloud project has the Google Drive API enabled and your OAuth consent screen is properly configured.

### SFTP connection refused
- Check that the port (default 2121) is not blocked by your firewall
- Verify the SFTP_HOST and SFTP_PORT settings in your `.env` file


## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is provided as-is for educational and personal use.

## Disclaimer

This is an unofficial project and is not affiliated with or endorsed by Google. Use at your own risk.
