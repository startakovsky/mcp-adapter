#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pytest==8.4.*",
#     "pytest-asyncio==1.0.*",
# ]
# ///
"""
Main test configuration and fixtures for all tests
"""

import pytest
import sys
import os

# Add the tests directory to the path so we can import test_utils
sys.path.insert(0, os.path.dirname(__file__))

from unit.test_utils import (
    get_test_filename, 
    cleanup_test_files, 
    ensure_test_directories,
    TEST_FILE_PREFIX,
    CLEANUP_CONFIG
)

@pytest.fixture(autouse=True, scope="session")
def cleanup_session_artifacts():
    """Clean up test artifacts once per session (before and after all tests)"""
    # Clean up before all tests
    cleanup_test_files()
    ensure_test_directories()
    
    yield
    
    # Clean up after all tests - comprehensive cleanup
    import subprocess
    import os
    
    try:
        # Run the cleanup utility for file-server artifacts
        cleanup_script = os.path.join(os.path.dirname(__file__), "cleanup_shared_files.py")
        if os.path.exists(cleanup_script):
            subprocess.run(["uv", "run", cleanup_script], check=False, capture_output=True)
    except Exception:
        pass  # Don't fail tests due to cleanup issues
    
    # Standard test file cleanup
    cleanup_test_files()

@pytest.fixture(autouse=True)
def cleanup_test_files_fixture():
    """Automatically clean up test files before and after each test"""
    # Ensure test directories exist
    ensure_test_directories()
    
    # Clean up before test (light cleanup)
    cleanup_test_files()
    
    yield
    
    # Clean up after test (light cleanup)
    cleanup_test_files()

@pytest.fixture
def test_filename():
    """Fixture to generate test filenames with proper prefix, descriptor, and identifier"""
    def _get_test_filename(base_name: str, extension: str = "", descriptor: str = "") -> str:
        return get_test_filename(base_name, extension, descriptor)
    return _get_test_filename 