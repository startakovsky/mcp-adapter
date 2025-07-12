#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pathlib",
# ]
# ///
"""
Cleanup script for test files

This script removes all test files with the pytest_ prefix from the latex-server
output and uploads directories.
"""

import sys
import os
from pathlib import Path

# Add the tests directory to the path so we can import test_utils
sys.path.insert(0, os.path.dirname(__file__))

from test_utils import cleanup_test_files, list_test_files, TEST_FILE_PREFIX, CLEANUP_CONFIG

def main():
    """Main cleanup function"""
    print(f"Cleaning up test files with prefix '{TEST_FILE_PREFIX}'...")
    print(f"Configuration: {CLEANUP_CONFIG}")
    
    # List files before cleanup
    test_files = list_test_files()
    if test_files:
        print(f"Found {len(test_files)} test files:")
        for file_path in test_files:
            print(f"  - {file_path}")
    else:
        print("No test files found.")
        return
    
    # Perform cleanup with current configuration
    removed_count = cleanup_test_files()
    
    print(f"\nCleanup complete: {removed_count} files removed.")
    
    # Verify cleanup
    remaining_files = list_test_files()
    if remaining_files:
        print(f"Warning: {len(remaining_files)} test files remain:")
        for file_path in remaining_files:
            print(f"  - {file_path}")
    else:
        print("All test files successfully removed.")

if __name__ == "__main__":
    main() 