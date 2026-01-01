"""
FTP Server with Google Drive Backend
"""

import os
import io
import errno
import tempfile
import time
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.filesystems import AbstractedFS
from src.filesystem.gdrive_filesystem import GoogleDriveFileSystem


class GoogleDriveFTPFilesystem(AbstractedFS):
    """FTP filesystem implementation using Google Drive"""
    
    def __init__(self, root, cmd_channel, gdrive_fs):
        self.root = root
        self.cmd_channel = cmd_channel
        self.cwd = '/'
        self.gdrive_fs = gdrive_fs
        self._temp_files = {}
    
    def ftp2fs(self, ftppath):
        """Convert FTP path to filesystem path"""
        # Resolve relative paths against current working directory.
        if not ftppath.startswith('/'):
            ftppath = os.path.join(self.cwd, ftppath)
        ftppath = os.path.normpath(ftppath).replace('\\', '/')
        if not ftppath.startswith('/'):
            ftppath = '/' + ftppath
        return ftppath
    
    def fs2ftp(self, fspath):
        """Convert filesystem path to FTP path"""
        return fspath
    
    def validpath(self, path):
        """Check if path is valid"""
        return True
    
    def open(self, filename, mode):
        """Open a file"""
        fspath = self.ftp2fs(filename)
        
        if 'r' in mode:
            # Read mode - download from Google Drive
            file_content = self.gdrive_fs.read_file(fspath)
            if file_content is None:
                err = OSError(f"File not found: {filename}")
                err.errno = errno.ENOENT
                raise err
            return file_content
        elif 'w' in mode or 'a' in mode:
            # Write mode - create temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
            self._temp_files[temp_file.name] = fspath
            return temp_file
        else:
            err = OSError(f"Unsupported mode: {mode}")
            err.errno = errno.EINVAL
            raise err
    
    def close(self, filename, file_obj):
        """Close a file and upload if it was opened for writing"""
        file_obj.close()

    def handle_file_received(self, temp_path):
        """Upload a completed temp file to Google Drive."""
        fspath = self._temp_files.pop(temp_path, None)
        if not fspath:
            return

        success = self.gdrive_fs.write_file(fspath, temp_path)
        os.unlink(temp_path)

        if not success:
            err = OSError(f"Failed to upload file: {fspath}")
            err.errno = errno.EIO
            raise err
    
    def chdir(self, path):
        """Change current directory"""
        fspath = self.ftp2fs(path)
        
        # Handle root directory
        if fspath == '/' or fspath == '':
            self.cwd = '/'
            return
        
        # Normalize path to handle .. properly
        if not fspath.startswith('/'):
            fspath = '/' + fspath
        
        stats = self.gdrive_fs.get_file_stats(fspath)
        
        if stats and stats['isdir']:
            self.cwd = fspath
        elif stats is None:
            err = OSError(f"No such directory: {path}")
            err.errno = errno.ENOENT
            raise err
        else:
            err = OSError(f"Not a directory: {path}")
            err.errno = errno.ENOTDIR
            raise err
    
    def mkdir(self, path):
        """Create a directory"""
        fspath = self.ftp2fs(path)
        if not self.gdrive_fs.create_directory(fspath):
            err = OSError(f"Failed to create directory: {path}")
            err.errno = errno.EACCES
            raise err
    
    def listdir(self, path):
        """List directory contents"""
        fspath = self.ftp2fs(path)
        files = self.gdrive_fs.list_directory(fspath)
        return [f['name'] for f in files]
    
    def rmdir(self, path):
        """Remove a directory"""
        fspath = self.ftp2fs(path)
        if not self.gdrive_fs.delete_file(fspath):
            err = OSError(f"Failed to remove directory: {path}")
            err.errno = errno.EACCES
            raise err
    
    def remove(self, path):
        """Remove a file"""
        fspath = self.ftp2fs(path)
        if not self.gdrive_fs.delete_file(fspath):
            err = OSError(f"Failed to remove file: {path}")
            err.errno = errno.EACCES
            raise err
    
    def rename(self, src, dst):
        """Rename a file"""
        src_path = self.ftp2fs(src)
        dst_path = self.ftp2fs(dst)
        if not self.gdrive_fs.rename_file(src_path, dst_path):
            err = OSError(f"Failed to rename: {src} -> {dst}")
            err.errno = errno.EACCES
            raise err
    
    def stat(self, path):
        """Get file statistics"""
        fspath = self.ftp2fs(path)
        stats = self.gdrive_fs.get_file_stats(fspath)
        
        if not stats:
            err = OSError(f"File not found: {path}")
            err.errno = errno.ENOENT
            raise err
        
        # Create a stat result object
        class StatResult:
            def __init__(self, stats_dict):
                self.st_size = stats_dict['size']
                self.st_mtime = stats_dict['mtime']
                self.st_mode = 0o040755 if stats_dict['isdir'] else 0o100644
                self.st_ctime = stats_dict['mtime']
                self.st_atime = stats_dict['mtime']
                self.st_nlink = 1
                self.st_uid = 0
                self.st_gid = 0
        
        return StatResult(stats)
    
    def lstat(self, path):
        """Get file statistics (same as stat for our purposes)"""
        return self.stat(path)
    
    def isfile(self, path):
        """Check if path is a file"""
        try:
            stats = self.gdrive_fs.get_file_stats(self.ftp2fs(path))
            return stats and not stats['isdir']
        except:
            return False
    
    def isdir(self, path):
        """Check if path is a directory"""
        try:
            stats = self.gdrive_fs.get_file_stats(self.ftp2fs(path))
            return stats and stats['isdir']
        except:
            return False
    
    def islink(self, path):
        """Check if path is a symbolic link"""
        return False
    
    def lexists(self, path):
        """Check if path exists"""
        try:
            stats = self.gdrive_fs.get_file_stats(self.ftp2fs(path))
            return stats is not None
        except:
            return False
    
    def getcwd(self):
        """Get current working directory"""
        return self.cwd
    
    def get_user_by_uid(self, uid):
        """Get username by UID"""
        return "gdrive"
    
    def get_group_by_gid(self, gid):
        """Get group name by GID"""
        return "gdrive"
    
    def readlink(self, path):
        """Read symbolic link"""
        raise OSError("Symbolic links not supported")
    
    def getsize(self, path):
        """Get file size"""
        stats = self.stat(path)
        return stats.st_size
    
    def getmtime(self, path):
        """Get modification time"""
        stats = self.stat(path)
        return stats.st_mtime
    
    def utime(self, path, timeval):
        """Set access and modification times (Google Drive doesn't support this)"""
        # MFMT can be sent immediately after STOR; Google Drive may be eventually consistent.
        # Retry a few times, then succeed even if metadata isn't visible yet.
        fspath = self.ftp2fs(path)
        for _ in range(3):
            stats = self.gdrive_fs.get_file_stats(fspath)
            if stats:
                return True
            self.gdrive_fs.invalidate_cache(fspath)
            time.sleep(0.2)
        return True
    
    def chmod(self, path, mode):
        """Change file permissions (Google Drive doesn't support this)"""
        # Google Drive doesn't have Unix-style permissions
        # Just silently succeed to avoid errors
        pass


def create_ftp_server(host, port, username, password, gdrive_service, cache_timeout=30, root_path='/'):
    """Create and configure FTP server"""
    
    # Create Google Drive filesystem with caching and root path
    gdrive_fs = GoogleDriveFileSystem(gdrive_service, cache_timeout=cache_timeout, root_path=root_path)
    
    # Create authorizer
    authorizer = DummyAuthorizer()
    # Add permissions including 'T' so clients don't get privilege errors on MFMT.
    authorizer.add_user(username, password, '/', perm='elradfmwMT')
    
    # Create custom filesystem class with Google Drive
    class CustomFilesystem(GoogleDriveFTPFilesystem):
        def __init__(self, root, cmd_channel):
            super().__init__(root, cmd_channel, gdrive_fs)
    
    # Create handler class
    class CustomHandler(FTPHandler):
        abstracted_fs = CustomFilesystem

        def ftp_MFMT(self, path, timeval=None):
            """Ignore MFMT to prevent client-side upload failures."""
            self.respond("213 Modify time not applied")
            return

        def on_file_received(self, file):
            try:
                self.fs.handle_file_received(file)
            except Exception as exc:
                self.log(f"Upload failed for {file}: {exc}")

        def on_incomplete_file_received(self, file):
            try:
                if os.path.exists(file):
                    os.unlink(file)
            except Exception as exc:
                self.log(f"Failed to cleanup temp file {file}: {exc}")
    
    CustomHandler.authorizer = authorizer
    
    # Create server
    server = FTPServer((host, port), CustomHandler)
    
    return server
