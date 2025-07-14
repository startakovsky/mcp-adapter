#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = []
# ///
"""
Cleanup script for file server shared_files directory
"""

import os
import glob
from pathlib import Path

def cleanup_shared_files():
    """Clean up all files in the file server shared_files directory"""
    shared_files_path = Path(__file__).parent.parent / "file-server" / "shared_files"
    
    if not shared_files_path.exists():
        print(f"Directory {shared_files_path} does not exist")
        return
    
    files_deleted = 0
    
    # Delete all files except metadata.json
    for file_path in shared_files_path.glob("*"):
        if file_path.is_file() and file_path.name != "metadata.json":
            try:
                file_path.unlink()
                files_deleted += 1
                print(f"Deleted: {file_path.name}")
            except Exception as e:
                print(f"Error deleting {file_path.name}: {e}")
    
    # Reset metadata.json to empty object
    metadata_file = shared_files_path / "metadata.json"
    try:
        with open(metadata_file, 'w') as f:
            f.write("{}")
        print("Reset metadata.json")
    except Exception as e:
        print(f"Error resetting metadata.json: {e}")
    
    print(f"\nCleaned up {files_deleted} files from shared_files directory")

if __name__ == "__main__":
    cleanup_shared_files()