#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pytest==8.4.*",
# ]
# ///
"""
Pytest plugin for test file cleanup

This plugin adds cleanup commands to pytest for managing test files.
"""

import pytest
import sys
import os
from pathlib import Path

# Add the tests directory to the path so we can import test_utils
sys.path.insert(0, os.path.dirname(__file__))

from test_utils import cleanup_test_files, list_test_files, TEST_FILE_PREFIX

def pytest_addoption(parser):
    """Add command line options for cleanup"""
    group = parser.getgroup("test cleanup")
    group.addoption(
        "--cleanup-test-files",
        action="store_true",
        help="Clean up test files before running tests"
    )
    group.addoption(
        "--list-test-files",
        action="store_true",
        help="List test files without cleaning them"
    )

def pytest_configure(config):
    """Configure the plugin"""
    if config.option.list_test_files:
        test_files = list_test_files()
        if test_files:
            print(f"\nFound {len(test_files)} test files with prefix '{TEST_FILE_PREFIX}':")
            for file_path in test_files:
                print(f"  - {file_path}")
        else:
            print(f"\nNo test files found with prefix '{TEST_FILE_PREFIX}'.")
        pytest.exit("Listed test files")

def pytest_sessionstart(session):
    """Clean up test files at session start if requested"""
    if session.config.option.cleanup_test_files:
        print(f"\nCleaning up test files with prefix '{TEST_FILE_PREFIX}'...")
        removed_count = cleanup_test_files()
        print(f"Removed {removed_count} test files.")

def pytest_sessionfinish(session, exitstatus):
    """Clean up test files at session end"""
    # Always clean up at the end of the session
    removed_count = cleanup_test_files()
    if removed_count > 0:
        print(f"\nCleaned up {removed_count} test files after test session.") 