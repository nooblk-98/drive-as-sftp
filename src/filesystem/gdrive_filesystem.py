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
    
    def __init__(self, service, cache_timeout=30, root_path='/'):
        self.service = service
        self._path_cache = {}  # Cache for path -> file_info
        self._dir_cache = {}   # Cache for directory listings
        self._cache_timeout = cache_timeout
        self.root_path = root_path.rstrip('/') if root_path != '/' else ''
        self._root_folder_id = None
    
    def _get_root_folder_id(self):
        """Get the folder ID for the configured root path"""
        if self._root_folder_id:
            return self._root_folder_id
        
        if not self.root_path:
            self._root_folder_id = 'root'
            return 'root'
        
        # Get the folder ID for the root path
        root_info = self._get_file_by_path_internal(self.root_path, use_root_offset=False)
        if root_info and root_info['mimeType'] == 'application/vnd.google-apps.folder':
            self._root_folder_id = root_info['id']
            return self._root_folder_id
        
        raise ValueError(f"Root path '{self.root_path}' not found or is not a folder")
    
    def _translate_path(self, path):
        """Translate FTP path to actual Google Drive path"""
        if not self.root_path:
            return path
        
        # Remove leading slash from path
        path = path.lstrip('/')
        
        # If empty, return root path
        if not path:
            return self.root_path
        
        # Combine root path with the requested path
        return self.root_path + '/' + path
    
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
            actual_path = self._translate_path(path)
            self._path_cache.pop(actual_path, None)
            self._dir_cache.pop(actual_path, None)
            # Also invalidate parent directory listing
            parent = '/'.join(actual_path.rstrip('/').split('/')[:-1]) or '/'
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
    
    def _get_file_by_path_internal(self, path, use_root_offset=True):
        """Internal method to get file/folder by path"""
        # Translate path if using root offset
        if use_root_offset:
            actual_path = self._translate_path(path)
        else:
            actual_path = path
        
        # Check cache first
        cached = self._get_cached_path(actual_path)
        if cached:
            return cached
        
        if actual_path == '/' or actual_path == '':
            root_info = {'id': 'root', 'name': '/', 'mimeType': 'application/vnd.google-apps.folder'}
            self._cache_path(actual_path, root_info)
            return root_info
        
        parts = actual_path.strip('/').split('/')
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
    
    def _get_file_by_path(self, path):
        """Get file/folder by path (public method with root offset)"""
        return self._get_file_by_path_internal(path, use_root_offset=True)
    
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
        actual_path = self._translate_path(path)
        # Check cache first
        cached = self._get_cached_dir(actual_path)
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
        self._cache_dir(actual_path, files)
        
        # Also cache individual file paths
        for file in files:
            file_path = actual_path.rstrip('/') + '/' + file['name']
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
    
    def write_file(self, path, file_obj_or_path):
        """Write file content"""
        import sys
        
        parts = path.strip('/').split('/')
        filename = parts[-1]
        parent_path = '/' + '/'.join(parts[:-1]) if len(parts) > 1 else '/'
        
        print(f"[DEBUG] write_file called: path={path}, parent_path={parent_path}", file=sys.stderr)
        
        # Get parent folder
        parent_info = self._get_file_by_path(parent_path)
        if not parent_info:
            print(f"[ERROR] Parent folder not found: {parent_path}", file=sys.stderr)
            return False
        
        print(f"[DEBUG] Parent folder ID: {parent_info['id']}", file=sys.stderr)
        
        # Check if file exists
        existing_file = self._get_file_by_path(path)
        
        file_metadata = {'name': filename}
        
        # Handle both file objects and file paths
        if isinstance(file_obj_or_path, str):
            # It's a file path
            print(f"[DEBUG] Uploading from file path: {file_obj_or_path}", file=sys.stderr)
            media = MediaFileUpload(file_obj_or_path, resumable=True)
        else:
            # It's a file object - use it directly
            file_path = file_obj_or_path.name if hasattr(file_obj_or_path, 'name') else str(file_obj_or_path)
            print(f"[DEBUG] Uploading from file object: {file_path}", file=sys.stderr)
            media = MediaFileUpload(file_path, resumable=True)
        
        def _get_local_size():
            if isinstance(file_obj_or_path, str):
                return os.path.getsize(file_obj_or_path)
            name = getattr(file_obj_or_path, 'name', None)
            if name and os.path.exists(name):
                return os.path.getsize(name)
            return 0

        try:
            if existing_file:
                # Update existing file and request metadata for cache.
                print(f"[DEBUG] Updating existing file ID: {existing_file['id']}", file=sys.stderr)
                updated = self.service.files().update(
                    fileId=existing_file['id'],
                    media_body=media,
                    fields="id, name, mimeType, size, modifiedTime, createdTime"
                ).execute()
                file_info = updated or existing_file
                print(f"[DEBUG] File updated successfully", file=sys.stderr)
            else:
                # Create new file and request metadata for cache.
                file_metadata['parents'] = [parent_info['id']]
                print(f"[DEBUG] Creating new file: {filename} in parent {parent_info['id']}", file=sys.stderr)
                file_info = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id, name, mimeType, size, modifiedTime, createdTime"
                ).execute()
                print(f"[DEBUG] File created successfully with ID: {file_info.get('id')}", file=sys.stderr)

            # Optimistically cache metadata so MFMT/stat won't fail immediately.
            now_iso = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
            size = _get_local_size()
            existing_id = existing_file['id'] if existing_file else None
            existing_mime = existing_file.get('mimeType') if existing_file else 'application/octet-stream'
            cached = {
                'id': file_info.get('id') if file_info else existing_id,
                'name': filename,
                'mimeType': file_info.get('mimeType') if file_info else existing_mime,
                'size': file_info.get('size', size) if file_info else size,
                'modifiedTime': file_info.get('modifiedTime', now_iso) if file_info else now_iso,
                'createdTime': file_info.get('createdTime', now_iso) if file_info else now_iso
            }
            if cached['id']:
                actual_path = self._translate_path(path)
                self._cache_path(actual_path, cached)

            # Invalidate parent directory listing so new file appears in listings.
            self.invalidate_cache(parent_path)
            print(f"[DEBUG] Upload completed successfully for {path}", file=sys.stderr)
            return True
        except HttpError as e:
            print(f"[ERROR] Error writing file {path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"[ERROR] Unexpected error writing file {path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
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
