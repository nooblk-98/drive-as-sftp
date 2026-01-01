"""
Google Drive Filesystem for FTP
Implements filesystem operations for Google Drive
"""

import os
import io
import stat
import time
from datetime import datetime
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError


class GoogleDriveFileSystem:
    """Provides filesystem-like interface to Google Drive"""
    
    def __init__(self, service, cache_timeout=30):
        self.service = service
        self._path_cache = {}  # Cache for path -> file_info
        self._dir_cache = {}   # Cache for directory listings
        self._cache_timeout = cache_timeout
    
    def _is_cache_valid(self, cache_time):
        """Check if cache entry is still valid"""
        return (time.time() - cache_time) < self._cache_timeout
    
    def _get_cached_path(self, path):
        """Get cached file info by path"""
        if path in self._path_cache:
            file_info, cache_time = self._path_cache[path]
            if self._is_cache_valid(cache_time):
                return file_info
        return None
    
    def _cache_path(self, path, file_info):
        """Cache file info for a path"""
        self._path_cache[path] = (file_info, time.time())
    
    def _get_cached_dir(self, path):
        """Get cached directory listing"""
        if path in self._dir_cache:
            files, cache_time = self._dir_cache[path]
            if self._is_cache_valid(cache_time):
                return files
        return None
    
    def _cache_dir(self, path, files):
        """Cache directory listing"""
        self._dir_cache[path] = (files, time.time())
    
    def invalidate_cache(self, path=None):
        """Invalidate cache for a specific path or all cache"""
        if path:
            self._path_cache.pop(path, None)
            self._dir_cache.pop(path, None)
            # Also invalidate parent directory listing
            parent = '/'.join(path.rstrip('/').split('/')[:-1]) or '/'
            self._dir_cache.pop(parent, None)
        else:
            self._path_cache.clear()
            self._dir_cache.clear()
    
    def _escape_query_value(self, value):
        """Escape special characters for Google Drive API query"""
        # Escape backslashes first, then single quotes
        value = value.replace('\\', '\\\\')
        value = value.replace("'", "\\'")
        return value
    
    def _get_file_by_path(self, path):
        """Get file/folder by path"""
        # Check cache first
        cached = self._get_cached_path(path)
        if cached:
            return cached
        
        if path == '/' or path == '':
            root_info = {'id': 'root', 'name': '/', 'mimeType': 'application/vnd.google-apps.folder'}
            self._cache_path(path, root_info)
            return root_info
        
        parts = path.strip('/').split('/')
        parent_id = 'root'
        current_path = ''
        
        for part in parts:
            current_path = current_path + '/' + part if current_path else '/' + part
            
            # Check if this path segment is cached
            cached = self._get_cached_path(current_path)
            if cached:
                parent_id = cached['id']
                file_info = cached
                continue
            
            escaped_part = self._escape_query_value(part)
            query = f"name='{escaped_part}' and '{parent_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime, createdTime)"
            ).execute()
            
            files = results.get('files', [])
            if not files:
                return None
            
            file_info = files[0]
            parent_id = file_info['id']
            
            # Cache this path segment
            self._cache_path(current_path, file_info)
        
        return file_info
    
    def _get_file_by_id(self, file_id):
        """Get file metadata by ID"""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, size, modifiedTime, createdTime, parents"
            ).execute()
            return file
        except HttpError:
            return None
    
    def list_directory(self, path):
        """List files in a directory"""
        # Check cache first
        cached = self._get_cached_dir(path)
        if cached is not None:
            return cached
        
        file_info = self._get_file_by_path(path)
        if not file_info:
            return []
        
        if file_info['mimeType'] != 'application/vnd.google-apps.folder':
            return []
        
        query = f"'{file_info['id']}' in parents and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType, size, modifiedTime, createdTime)",
            pageSize=1000
        ).execute()
        
        files = results.get('files', [])
        
        # Cache the directory listing
        self._cache_dir(path, files)
        
        # Also cache individual file paths
        for file in files:
            file_path = path.rstrip('/') + '/' + file['name']
            self._cache_path(file_path, file)
        
        return files
    
    def get_file_stats(self, path):
        """Get file statistics (size, mtime, etc.)"""
        file_info = self._get_file_by_path(path)
        if not file_info:
            return None
        
        is_dir = file_info['mimeType'] == 'application/vnd.google-apps.folder'
        size = int(file_info.get('size', 0)) if not is_dir else 0
        
        # Parse modification time
        mtime_str = file_info.get('modifiedTime', file_info.get('createdTime'))
        if mtime_str:
            mtime = datetime.fromisoformat(mtime_str.replace('Z', '+00:00')).timestamp()
        else:
            mtime = time.time()
        
        return {
            'size': size,
            'mtime': mtime,
            'isdir': is_dir,
            'name': file_info['name'],
            'id': file_info['id']
        }
    
    def read_file(self, path):
        """Read file content"""
        file_info = self._get_file_by_path(path)
        if not file_info or file_info['mimeType'] == 'application/vnd.google-apps.folder':
            return None
        
        request = self.service.files().get_media(fileId=file_info['id'])
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        return fh
    
    def write_file(self, path, file_obj):
        """Write file content"""
        parts = path.strip('/').split('/')
        filename = parts[-1]
        parent_path = '/' + '/'.join(parts[:-1]) if len(parts) > 1 else '/'
        
        # Get parent folder
        parent_info = self._get_file_by_path(parent_path)
        if not parent_info:
            return False
        
        # Check if file exists
        existing_file = self._get_file_by_path(path)
        
        file_metadata = {'name': filename}
        media = MediaFileUpload(file_obj, resumable=True)
        
        try:
            if existing_file:
                # Update existing file
                self.service.files().update(
                    fileId=existing_file['id'],
                    media_body=media
                ).execute()
            else:
                # Create new file
                file_metadata['parents'] = [parent_info['id']]
                self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
            
            # Invalidate cache for this path and parent directory
            self.invalidate_cache(path)
            return True
        except HttpError as e:
            print(f"Error writing file: {e}")
            return False
    
    def delete_file(self, path):
        """Delete a file"""
        file_info = self._get_file_by_path(path)
        if not file_info:
            return False
        
        try:
            self.service.files().delete(fileId=file_info['id']).execute()
            # Invalidate cache for this path and parent directory
            self.invalidate_cache(path)
            return True
        except HttpError:
            return False
    
    def create_directory(self, path):
        """Create a directory"""
        parts = path.strip('/').split('/')
        dirname = parts[-1]
        parent_path = '/' + '/'.join(parts[:-1]) if len(parts) > 1 else '/'
        
        parent_info = self._get_file_by_path(parent_path)
        if not parent_info:
            return False
        
        file_metadata = {
            'name': dirname,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_info['id']]
        }
        
        try:
            self.service.files().create(body=file_metadata, fields='id').execute()
            # Invalidate cache for parent directory
            self.invalidate_cache(path)
            return True
        except HttpError:
            return False
    
    def rename_file(self, old_path, new_path):
        """Rename a file"""
        file_info = self._get_file_by_path(old_path)
        if not file_info:
            return False
        
        new_name = new_path.strip('/').split('/')[-1]
        
        try:
            self.service.files().update(
                fileId=file_info['id'],
                body={'name': new_name}
            ).execute()
            # Invalidate cache for both old and new paths
            self.invalidate_cache(old_path)
            self.invalidate_cache(new_path)
            return True
        except HttpError:
            return False
