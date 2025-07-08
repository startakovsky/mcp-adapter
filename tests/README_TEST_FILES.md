# Test File Management

This document describes the test file management system implemented to ensure clean test execution and easy cleanup of test-generated files.

## Overview

The test system uses a consistent prefix (`pytest_`) for all test-generated files, making them easy to identify and clean up. This includes:

- LaTeX source files (`.tex`)
- Compiled PDF files (`.pdf`)
- Uploaded files in the uploads directory
- Output files in the output directory

## Components

### 1. Test Utilities (`test_utils.py`)

Core utilities for managing test files:

- `get_test_filename(base_name, extension)`: Generate filenames with the test prefix
- `cleanup_test_files(directories)`: Remove all test files with the prefix
- `cleanup_test_files_by_pattern(pattern, directories)`: Remove test files matching a pattern
- `list_test_files(directories)`: List all test files with the prefix
- `ensure_test_directories()`: Ensure test directories exist

### 2. Pytest Fixtures (`conftest.py`)

Automatic cleanup fixtures:

- `cleanup_test_files_fixture`: Automatically cleans up before and after each test
- `test_filename`: Fixture to generate test filenames with proper prefix

### 3. Pytest Plugin (`pytest_cleanup_plugin.py`)

Command-line options for pytest:

- `--cleanup-test-files`: Clean up test files before running tests
- `--list-test-files`: List test files without cleaning them

### 4. Standalone Cleanup Script (`cleanup_test_files.py`)

Manual cleanup script that can be run independently.

## Usage

### In Tests

Use the `test_filename` fixture to generate proper test filenames:

```python
@pytest.mark.asyncio
async def test_upload_file(self, sample_latex_document: str, test_filename):
    async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
        result = await gateway_helper.call_tool(
            "latex_upload_latex_file",
            {
                "content": sample_latex_document,
                "filename": test_filename("my_test", "tex")  # Generates "pytest_my_test.tex"
            }
        )
```

### Command Line

List test files:
```bash
cd tests
uv run pytest --list-test-files
```

Clean up before running tests:
```bash
cd tests
uv run pytest --cleanup-test-files
```

### Manual Cleanup

Run the standalone cleanup script:
```bash
cd tests
uv run cleanup_test_files.py
```

### Python API

```python
from test_utils import cleanup_test_files, list_test_files

# List test files
files = list_test_files()
print(f"Found {len(files)} test files")

# Clean up all test files
removed = cleanup_test_files()
print(f"Removed {removed} files")
```

## File Locations

Test files are stored in:

- `latex-server/output/`: Compiled PDF files
- `latex-server/uploads/`: Uploaded LaTeX source files

## Automatic Cleanup

The system provides automatic cleanup through:

1. **Per-test cleanup**: Each test automatically cleans up before and after execution
2. **Session cleanup**: All test files are cleaned up at the end of the pytest session
3. **Manual triggers**: Command-line options and standalone scripts

## Best Practices

1. **Always use the test_filename fixture** for generating filenames in tests
2. **Don't hardcode filenames** - use the utility functions
3. **Run cleanup before committing** to ensure no test files are left behind
4. **Use descriptive base names** for test files to make debugging easier

## Configuration

The test prefix can be modified by changing the `TEST_FILE_PREFIX` constant in `test_utils.py`. The default is `"pytest_"`.

## Troubleshooting

### Files not being cleaned up

1. Check that files use the correct prefix
2. Verify the cleanup directories exist
3. Check file permissions
4. Run manual cleanup script

### Test failures due to file conflicts

1. Ensure each test uses unique filenames
2. Use the test_filename fixture consistently
3. Add test-specific identifiers to filenames

### Performance issues

1. The cleanup is designed to be fast for typical test scenarios
2. For large numbers of files, consider using pattern-based cleanup
3. Monitor the number of test files being generated 