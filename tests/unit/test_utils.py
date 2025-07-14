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
Test utilities for managing test files and cleanup
"""

import os
import glob
import shutil
import uuid
import time
from pathlib import Path
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Test file configuration
TEST_FILE_PREFIX = "pytest"

# Additional cleanup patterns for different file types
CLEANUP_PATTERNS = {
    "latex_uploads": "*.tex",  # All .tex files in uploads
    "latex_outputs": "compiled_*.pdf",  # Compiled PDFs
    "test_outputs": "*_output_*.pdf",  # Test output PDFs
    "reuse_outputs": "reuse_output_*.pdf",  # Reuse test PDFs
    "double_extensions": "*.pdf.pdf",  # Files with double extensions
    "all_pdfs": "*.pdf",  # All PDF files (fallback)
    "file_server_test_files": "test_*",  # Test files in file-server
    "file_server_leak_files": "leak_test_*",  # Leak test files
    "file_server_uuid_files": "[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]-*",  # UUID files
    "file_server_concurrent_files": "concurrent_*",  # Concurrent test files
    "file_server_rapid_files": "rapid_*",  # Rapid test files
    "file_server_timeout_files": "timeout_test_*",  # Timeout test files
}

# Configuration for which cleanup patterns to use
CLEANUP_CONFIG = {
    "use_test_prefix": True,  # Always use the test prefix
    "use_latex_uploads": True,  # Clean up all .tex files in uploads
    "use_latex_outputs": True,  # Clean up compiled_*.pdf files
    "use_test_outputs": True,  # Clean up test output files
    "use_reuse_outputs": True,  # Clean up reuse output files
    "use_double_extensions": True,  # Clean up files with double extensions
    "use_all_pdfs": False,  # Clean up all PDF files (use with caution)
    "use_file_server_test_files": True,  # Clean up test files in file-server
    "use_file_server_leak_files": True,  # Clean up leak test files
    "use_file_server_uuid_files": True,  # Clean up UUID files
    "use_file_server_concurrent_files": True,  # Clean up concurrent test files
    "use_file_server_rapid_files": True,  # Clean up rapid test files
    "use_file_server_timeout_files": True,  # Clean up timeout test files
    "reset_file_server_metadata": True,  # Reset metadata.json to empty
}

def get_test_filename(base_name: str, extension: str = "", descriptor: str = "") -> str:
    """
    Generate a test filename with the standard prefix, descriptor, and unique identifier
    
    Args:
        base_name: Base name for the file
        extension: File extension (without dot)
        descriptor: Optional descriptor to identify the test type/purpose
    
    Returns:
        Filename with test prefix, descriptor, and unique identifier
    """
    if extension and not extension.startswith('.'):
        extension = '.' + extension
    
    # Generate a short unique identifier (first 8 chars of UUID)
    unique_id = str(uuid.uuid4())[:8]
    
    # Build filename components
    parts = [TEST_FILE_PREFIX]
    
    if descriptor:
        parts.append(descriptor)
    
    parts.append(base_name)
    parts.append(unique_id)
    
    # Join with underscores and add extension
    filename = "_".join(parts) + extension
    
    return filename

def cleanup_test_files(
    directories: Optional[List[str]] = None,
    config: Optional[Dict[str, bool]] = None
) -> int:
    """
    Clean up test files based on configuration
    
    Args:
        directories: List of directories to clean (defaults to latex-server/output and latex-server/uploads)
        config: Configuration dict to override CLEANUP_CONFIG defaults
    
    Returns:
        Number of files removed
    """
    if directories is None:
        # Default directories to clean (relative to project root)
        directories = [
            "../latex-server/output",
            "../latex-server/uploads",
            "../file-server/shared_files"
        ]
    
    if config is None:
        config = CLEANUP_CONFIG.copy()
    
    removed_count = 0
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
        
        files_to_remove = []
        
        # Always clean up files with test prefix if enabled
        if config.get("use_test_prefix", True):
            pattern = str(dir_path / f"{TEST_FILE_PREFIX}*")
            files_to_remove.extend(glob.glob(pattern))
        
        # Clean up additional patterns based on configuration
        if "uploads" in str(dir_path):
            if config.get("use_latex_uploads", False):
                pattern = str(dir_path / CLEANUP_PATTERNS["latex_uploads"])
                files_to_remove.extend(glob.glob(pattern))
        
        if "output" in str(dir_path):
            if config.get("use_latex_outputs", False):
                pattern = str(dir_path / CLEANUP_PATTERNS["latex_outputs"])
                files_to_remove.extend(glob.glob(pattern))
            
            if config.get("use_test_outputs", False):
                pattern = str(dir_path / CLEANUP_PATTERNS["test_outputs"])
                files_to_remove.extend(glob.glob(pattern))
            
            if config.get("use_reuse_outputs", False):
                pattern = str(dir_path / CLEANUP_PATTERNS["reuse_outputs"])
                files_to_remove.extend(glob.glob(pattern))
        
        # Clean up file-server artifacts
        if "shared_files" in str(dir_path):
            file_server_patterns = [
                "file_server_test_files",
                "file_server_leak_files", 
                "file_server_uuid_files",
                "file_server_concurrent_files",
                "file_server_rapid_files",
                "file_server_timeout_files"
            ]
            
            for pattern_name in file_server_patterns:
                if config.get(f"use_{pattern_name}", False):
                    pattern = str(dir_path / CLEANUP_PATTERNS[pattern_name])
                    files_to_remove.extend(glob.glob(pattern))
            
            # Reset metadata.json if requested
            if config.get("reset_file_server_metadata", False):
                metadata_path = dir_path / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'w') as f:
                            f.write('{}')
                        logger.debug(f"Reset metadata.json to empty: {metadata_path}")
                    except OSError as e:
                        logger.warning(f"Failed to reset metadata.json: {e}")
        
        # Remove all identified files
        for file_path in files_to_remove:
            try:
                os.remove(file_path)
                removed_count += 1
                logger.debug(f"Removed file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove file {file_path}: {e}")
    
    return removed_count

def cleanup_test_files_by_pattern(pattern: str, directories: Optional[List[str]] = None) -> int:
    """
    Clean up test files matching a specific pattern
    
    Args:
        pattern: Glob pattern to match (will be prefixed with TEST_FILE_PREFIX)
        directories: List of directories to clean
    
    Returns:
        Number of files removed
    """
    if directories is None:
        directories = [
            "../latex-server/output",
            "../latex-server/uploads",
            "../file-server/shared_files"
        ]
    
    removed_count = 0
    full_pattern = f"{TEST_FILE_PREFIX}{pattern}"
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
            
        # Find files matching pattern
        search_pattern = str(dir_path / full_pattern)
        matching_files = glob.glob(search_pattern)
        
        for file_path in matching_files:
            try:
                os.remove(file_path)
                removed_count += 1
                logger.debug(f"Removed test file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove test file {file_path}: {e}")
    
    return removed_count

def list_test_files(directories: Optional[List[str]] = None) -> List[str]:
    """
    List all test files with the test prefix
    
    Args:
        directories: List of directories to search
    
    Returns:
        List of test file paths
    """
    if directories is None:
        directories = [
            "../latex-server/output",
            "../latex-server/uploads",
            "../file-server/shared_files"
        ]
    
    test_files = []
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            continue
            
        # Find all files with test prefix
        pattern = str(dir_path / f"{TEST_FILE_PREFIX}*")
        files = glob.glob(pattern)
        test_files.extend(files)
    
    return test_files

def ensure_test_directories():
    """Ensure test directories exist"""
    directories = [
        "../latex-server/output",
        "../latex-server/uploads",
        "../file-server/shared_files"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True) 