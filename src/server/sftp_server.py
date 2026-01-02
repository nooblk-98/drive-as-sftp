"""
SFTP Server with Google Drive Backend
"""

import os
import stat
import time
import socket
import posixpath
import tempfile
import threading
import paramiko
from datetime import datetime
from src.filesystem.gdrive_filesystem import GoogleDriveFileSystem


class _DriveSFTPHandle(paramiko.SFTPHandle):
    def __init__(self, flags, gdrive_fs, path, read_file=None, temp_file=None):
        super().__init__(flags)
        self.gdrive_fs = gdrive_fs
        self.path = path
        self.readfile = read_file
        self.writefile = temp_file
        self._temp_file = temp_file

    def close(self):
        if self._temp_file:
            self._temp_file.flush()
            self._temp_file.close()
            success = self.gdrive_fs.write_file(self.path, self._temp_file.name)
            try:
                os.unlink(self._temp_file.name)
            except FileNotFoundError:
                pass
            if not success:
                return paramiko.SFTP_FAILURE
        if self.readfile:
            self.readfile.close()
        return paramiko.SFTP_OK


class _GoogleDriveSFTPInterface(paramiko.SFTPServerInterface):
    def __init__(self, server, gdrive_fs):
        super().__init__(server)
        self.gdrive_fs = gdrive_fs

    def _normalize(self, path):
        if not path:
            return '/'
        path = path.replace('\\', '/')
        if not path.startswith('/'):
            path = '/' + path
        return posixpath.normpath(path)

    def _attrs_from_stats(self, stats_dict, name=None):
        attrs = paramiko.SFTPAttributes()
        attrs.filename = name
        is_dir = stats_dict['isdir']
        attrs.st_size = stats_dict['size']
        attrs.st_mode = (stat.S_IFDIR | 0o755) if is_dir else (stat.S_IFREG | 0o644)
        attrs.st_mtime = int(stats_dict['mtime'])
        attrs.st_atime = int(stats_dict['mtime'])
        return attrs

    def _attrs_from_info(self, info):
        is_dir = info.get('mimeType') == 'application/vnd.google-apps.folder'
        size = int(info.get('size', 0)) if not is_dir else 0
        mtime_str = info.get('modifiedTime', info.get('createdTime'))
        if mtime_str:
            mtime = datetime.fromisoformat(mtime_str.replace('Z', '+00:00')).timestamp()
        else:
            mtime = time.time()
        return self._attrs_from_stats(
            {'isdir': is_dir, 'size': size, 'mtime': mtime},
            name=info.get('name')
        )

    def list_folder(self, path):
        path = self._normalize(path)
        stats = self.gdrive_fs.get_file_stats(path)
        if not stats or not stats['isdir']:
            return paramiko.SFTP_NO_SUCH_FILE
        files = self.gdrive_fs.list_directory(path)
        return [self._attrs_from_info(info) for info in files]

    def stat(self, path):
        path = self._normalize(path)
        stats = self.gdrive_fs.get_file_stats(path)
        if not stats:
            return paramiko.SFTP_NO_SUCH_FILE
        return self._attrs_from_stats(stats)

    def lstat(self, path):
        return self.stat(path)

    def open(self, path, flags, attr):
        path = self._normalize(path)
        write_flags = flags & (
            os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        )
        if write_flags:
            temp_file = tempfile.NamedTemporaryFile(mode='w+b', delete=False)
            return _DriveSFTPHandle(flags, self.gdrive_fs, path, temp_file=temp_file)
        file_obj = self.gdrive_fs.read_file(path)
        if file_obj is None:
            return paramiko.SFTP_NO_SUCH_FILE
        return _DriveSFTPHandle(flags, self.gdrive_fs, path, read_file=file_obj)

    def remove(self, path):
        path = self._normalize(path)
        return paramiko.SFTP_OK if self.gdrive_fs.delete_file(path) else paramiko.SFTP_FAILURE

    def rename(self, oldpath, newpath):
        oldpath = self._normalize(oldpath)
        newpath = self._normalize(newpath)
        return paramiko.SFTP_OK if self.gdrive_fs.rename_file(oldpath, newpath) else paramiko.SFTP_FAILURE

    def mkdir(self, path, attr):
        path = self._normalize(path)
        return paramiko.SFTP_OK if self.gdrive_fs.create_directory(path) else paramiko.SFTP_FAILURE

    def rmdir(self, path):
        path = self._normalize(path)
        return paramiko.SFTP_OK if self.gdrive_fs.delete_file(path) else paramiko.SFTP_FAILURE

    def setstat(self, path, attr):
        # Ignore chmod/utime requests to avoid client errors.
        return paramiko.SFTP_OK

    def fsetstat(self, handle, attr):
        # Ignore chmod/utime requests to avoid client errors.
        return paramiko.SFTP_OK

    def chmod(self, path, mode):
        return paramiko.SFTP_OK

    def chown(self, path, uid, gid):
        return paramiko.SFTP_OK

    def utime(self, path, times):
        return paramiko.SFTP_OK


class _PasswordAuthServer(paramiko.ServerInterface):
    def __init__(self, username, password, gdrive_fs):
        self.username = username
        self.password = password
        self.gdrive_fs = gdrive_fs

    def check_auth_password(self, username, password):
        if username == self.username and password == self.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return 'password'

    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED


class SFTPServer:
    def __init__(self, host, port, username, password, gdrive_service, cache_timeout=30, root_path='/', host_key_path='config/sftp_host_key'):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.host_key_path = host_key_path
        self.gdrive_fs = GoogleDriveFileSystem(gdrive_service, cache_timeout=cache_timeout, root_path=root_path)
        self._sock = None
        self._stop_event = threading.Event()

    def _load_or_create_host_key(self):
        key_path = self.host_key_path
        key_dir = os.path.dirname(key_path)
        if key_dir:
            os.makedirs(key_dir, exist_ok=True)
        if os.path.exists(key_path):
            return paramiko.RSAKey.from_private_key_file(key_path)
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(key_path)
        try:
            os.chmod(key_path, 0o600)
        except OSError:
            pass
        return key

    def _handle_client(self, client_sock):
        transport = None
        try:
            transport = paramiko.Transport(client_sock)
            transport.add_server_key(self._load_or_create_host_key())
            server = _PasswordAuthServer(self.username, self.password, self.gdrive_fs)
            transport.set_subsystem_handler('sftp', paramiko.SFTPServer, _GoogleDriveSFTPInterface, self.gdrive_fs)
            transport.start_server(server=server)
            while transport.is_active() and not self._stop_event.is_set():
                time.sleep(0.2)
        finally:
            if transport:
                transport.close()
            client_sock.close()

    def serve_forever(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(100)
        while not self._stop_event.is_set():
            try:
                client, _addr = self._sock.accept()
            except OSError:
                continue
            t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
            t.start()

    def close_all(self):
        self._stop_event.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass


def create_sftp_server(host, port, username, password, gdrive_service, cache_timeout=30, root_path='/', host_key_path='config/sftp_host_key'):
    return SFTPServer(host, port, username, password, gdrive_service, cache_timeout=cache_timeout, root_path=root_path, host_key_path=host_key_path)
