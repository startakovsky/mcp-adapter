#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pathlib",
# ]
# ///
"""
Examples of using the modular cleanup configuration

This file demonstrates different ways to configure the cleanup system.
"""

import sys
import os
from pathlib import Path

# Add the tests directory to the path so we can import test_utils
sys.path.insert(0, os.path.dirname(__file__))

from test_utils import cleanup_test_files, CLEANUP_CONFIG, CLEANUP_PATTERNS

def example_minimal_cleanup():
    """Example: Only clean up files with test prefix"""
    config = {
        "use_test_prefix": True,
        "use_latex_uploads": False,
        "use_latex_outputs": False,
        "use_test_outputs": False,
        "use_reuse_outputs": False,
    }
    
    print("Minimal cleanup - only test prefix files:")
    removed = cleanup_test_files(config=config)
    print(f"Removed {removed} files")

def example_latex_only_cleanup():
    """Example: Clean up LaTeX server files but not test prefix files"""
    config = {
        "use_test_prefix": False,
        "use_latex_uploads": True,
        "use_latex_outputs": True,
        "use_test_outputs": False,
        "use_reuse_outputs": False,
    }
    
    print("LaTeX-only cleanup:")
    removed = cleanup_test_files(config=config)
    print(f"Removed {removed} files")

def example_selective_cleanup():
    """Example: Clean up specific patterns only"""
    config = {
        "use_test_prefix": True,
        "use_latex_uploads": True,
        "use_latex_outputs": False,
        "use_test_outputs": True,
        "use_reuse_outputs": False,
    }
    
    print("Selective cleanup - test prefix + uploads + test outputs:")
    removed = cleanup_test_files(config=config)
    print(f"Removed {removed} files")

def example_full_cleanup():
    """Example: Clean up everything (default behavior)"""
    print("Full cleanup (default configuration):")
    removed = cleanup_test_files()
    print(f"Removed {removed} files")

def show_configuration():
    """Show current configuration and available patterns"""
    print("Current cleanup configuration:")
    for key, value in CLEANUP_CONFIG.items():
        print(f"  {key}: {value}")
    
    print("\nAvailable cleanup patterns:")
    for key, pattern in CLEANUP_PATTERNS.items():
        print(f"  {key}: {pattern}")

if __name__ == "__main__":
    show_configuration()
    print("\n" + "="*50)
    
    # Run examples
    example_minimal_cleanup()
    print()
    example_latex_only_cleanup()
    print()
    example_selective_cleanup()
    print()
    example_full_cleanup() 