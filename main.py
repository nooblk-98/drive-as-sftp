"""
Google Drive as FTP Server
Main application entry point
"""

import sys
from src.auth import GoogleDriveAuth
from src.server import create_ftp_server
from src.utils import Config, setup_logger


def main():
    """Main function to start the FTP server"""
    print("=" * 60)
    print("Google Drive as FTP Server")
    print("=" * 60)
    print()
    
    # Load configuration
    config = Config()
    
    # Setup logger
    logger = setup_logger(
        name='gdrive-ftp',
        log_file=config.log_file,
        log_level=config.log_level
    )
    
    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  ✗ {error}")
        print()
        print("Please follow these steps:")
        print("1. Go to Google Cloud Console (https://console.cloud.google.com/)")
        print("2. Create a new project or select an existing one")
        print("3. Enable Google Drive API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download the credentials JSON file")
        print(f"6. Save it as '{config.credentials_file}' in this directory")
        print()
        sys.exit(1)
    
    # Display configuration
    config.display()
    print()
    
    # Authenticate with Google Drive
    logger.info("Authenticating with Google Drive...")
    print("Authenticating with Google Drive...")
    try:
        auth = GoogleDriveAuth(config.credentials_file, config.token_file)
        gdrive_service = auth.authenticate()
        logger.info("Successfully authenticated with Google Drive")
        print("✓ Successfully authenticated with Google Drive")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        print(f"✗ Authentication failed: {e}")
        sys.exit(1)
    
    # Create and start FTP server
    logger.info(f"Starting FTP server on {config.ftp_host}:{config.ftp_port}...")
    print(f"\nStarting FTP server on {config.ftp_host}:{config.ftp_port}...")
    try:
        server = create_ftp_server(
            config.ftp_host,
            config.ftp_port,
            config.ftp_username,
            config.ftp_password,
            gdrive_service,
            cache_timeout=config.cache_timeout,
            root_path=config.ftp_root_path
        )
        
        # Set server limits
        server.max_cons = config.ftp_max_connections
        server.max_cons_per_ip = config.ftp_max_connections_per_ip
        
        logger.info("FTP server started successfully")
        print("✓ FTP server started successfully!")
        print(f"\nYou can now connect to the FTP server:")
        print(f"  Host: {config.ftp_host if config.ftp_host != '0.0.0.0' else 'localhost'}")
        print(f"  Port: {config.ftp_port}")
        print(f"  Username: {config.ftp_username}")
        print(f"  Password: {config.ftp_password}")
        print(f"\nLogs are being written to: {config.log_file}")
        print("\nPress Ctrl+C to stop the server")
        print("=" * 60)
        
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        logger.info("Server shutdown requested")
        server.close_all()
        print("Server stopped.")
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        print(f"✗ Failed to start server: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
