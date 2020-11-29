import io
import os
import random
import smb
from smb import SMBConnection, smb_constants

FORBIDDEN_DIR_NAMES = [".", "..", ".Thumbnails"]
ALLOWED_FILE_EXTENSIONS = [".jpg", ".png"]
MAX_FILE_SIZE_BYTES = 1024 * 1024 * 20  # 20 MB

def _matches_allowed_file(sf: smb.base.SharedFile) -> bool:
    """Predicate that checks if `sf` is a file we could possibly return."""
    return (
        not sf.isDirectory and 
        any(sf.filename.lower().endswith(ext) for ext in ALLOWED_FILE_EXTENSIONS) and
        sf.file_size < MAX_FILE_SIZE_BYTES
    )

def _matches_allowed_dir(sf: smb.base.SharedFile) -> bool:
    """Predicate that checks if `sf` is a directory we should explore."""
    return (
        sf.isDirectory and sf.filename not in FORBIDDEN_DIR_NAMES
    )

class NoFileError(Exception):
    pass

class SMBPicturePicker:
    """Traverses the directory tree on an SMB share and picks a random image file."""

    def __init__(self, username: str, password: str, server_name: str, server_ip: str, share: str):
        self.conn = SMBConnection.SMBConnection(
            username,
            password,
            'smb_picture_picker',  # Arbitrary name identifying this connection on the server.
            server_name
        )

        assert self.conn.connect(server_ip)

        self.smb_share = share
        self.random = random.SystemRandom()
    
    def pick(self, base_dir = '/', max_depth = 5) -> io.BytesIO:
        """Recursively goes through the directory tree to pick a random jpg file.
        
        Does not backtrack: will raise NoFileError if it's caught in a dead end with
        no matching files and no subdirectories to recurse into.
        """

        ls_response = self.conn.listPath(self.smb_share, base_dir)
        
        options = []
        if max_depth > 0:
            options = [x for x in ls_response if (
                _matches_allowed_dir(x) or _matches_allowed_file(x))]
        else:
            # At this depth we have to pick a real file
            options = [x for x in ls_response if _matches_allowed_file(x)]
        
        if len(options) > 0:
            choice = self.random.choice(options)
            if choice.isDirectory:
                return self.pick(
                    os.path.join(base_dir, choice.filename),
                    max_depth - 1
                )
            else:
                smb_filename = os.path.join(base_dir, choice.filename)
                f = io.BytesIO()
                file_attributes, file_size = self.conn.retrieveFile(
                    self.smb_share,
                    smb_filename,
                    f
                )
                f.seek(0)

                print(f"Name: {smb_filename}, size: {file_size} bytes")
                return f
        else:
            raise NoFileError(f"Couldn't pick a file under {base_dir}")