"""
LaTeX Server Core Unit Tests - Simplified

Tests core LaTeX server utility functions directly without FastMCP complexity.
"""

import pytest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the server module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../latex-server'))
import server


class TestSanitizeFilename:
    """Test filename sanitization function"""
    
    def test_sanitize_filename_valid(self):
        """Test sanitization of valid filename"""
        result = server.sanitize_filename("valid_file-name.tex")
        assert result == "valid_file-name.tex"
    
    def test_sanitize_filename_none(self):
        """Test sanitization of None input"""
        result = server.sanitize_filename(None)
        assert result == ""
    
    def test_sanitize_filename_empty(self):
        """Test sanitization of empty string"""
        result = server.sanitize_filename("")
        assert result == ""
    
    def test_sanitize_filename_directory_traversal(self):
        """Test prevention of directory traversal"""
        result = server.sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result
        assert result == "______etc_passwd"
    
    def test_sanitize_filename_special_chars(self):
        """Test removal of special characters"""
        result = server.sanitize_filename("file@#$%^&*()name.tex")
        assert result == "file_________name.tex"
    
    def test_sanitize_filename_long_name(self):
        """Test truncation of long filenames"""
        long_name = "a" * 150 + ".tex"
        result = server.sanitize_filename(long_name)
        assert len(result) <= 100
    
    def test_sanitize_filename_hidden_file(self):
        """Test handling of hidden files (starting with dot)"""
        result = server.sanitize_filename(".hidden_file.tex")
        assert result == "hidden_file.tex"
    
    def test_sanitize_filename_spaces_and_dots(self):
        """Test removal of leading/trailing spaces and dots"""
        result = server.sanitize_filename("  ..filename..  ")
        assert result == "___filename___"


class TestExtractPackages:
    """Test LaTeX package extraction function"""
    
    def test_extract_packages_single(self):
        """Test extraction of single package"""
        content = r"\usepackage{amsmath}"
        packages = server.extract_packages(content)
        assert packages == ["amsmath"]
    
    def test_extract_packages_multiple_lines(self):
        """Test extraction from multiple lines"""
        content = r"""
        \usepackage{amsmath}
        \usepackage{graphicx}
        \usepackage{hyperref}
        """
        packages = server.extract_packages(content)
        assert set(packages) == {"amsmath", "graphicx", "hyperref"}
    
    def test_extract_packages_multiple_per_line(self):
        """Test extraction of multiple packages in one line"""
        content = r"\usepackage{amsmath,graphicx,hyperref}"
        packages = server.extract_packages(content)
        assert set(packages) == {"amsmath", "graphicx", "hyperref"}
    
    def test_extract_packages_with_options(self):
        """Test extraction with package options"""
        content = r"\usepackage[utf8]{inputenc}"
        packages = server.extract_packages(content)
        assert packages == ["inputenc"]
    
    def test_extract_packages_none(self):
        """Test extraction with no packages"""
        content = r"""
        \documentclass{article}
        \begin{document}
        Hello World
        \end{document}
        """
        packages = server.extract_packages(content)
        assert packages == []
    
    def test_extract_packages_malformed(self):
        """Test extraction with malformed package declarations"""
        content = r"""
        \usepackage{amsmath
        \usepackage{}
        \usepackage
        """
        packages = server.extract_packages(content)
        # Should handle gracefully and extract what it can
        assert isinstance(packages, list)


class TestPydanticModels:
    """Test Pydantic models for requests (simplified set)"""
    
    def test_template_request_valid(self):
        """Test valid template request"""
        request = server.TemplateRequest(
            template_name="basic_resume",
            variables={"name": "John Doe", "email": "john@example.com"},
            filename="resume.pdf"
        )
        assert request.template_name == "basic_resume"
        assert request.variables["name"] == "John Doe"
        assert request.filename == "resume.pdf"
    
    def test_file_upload_request_valid(self):
        """Test valid file upload request"""
        request = server.FileUploadRequest(
            content=r"\documentclass{article}\begin{document}Hello\end{document}",
            filename="upload.tex"
        )
        assert request.content is not None
        assert request.filename == "upload.tex"
    
    def test_file_compile_request_valid(self):
        """Test valid file compile request"""
        request = server.FileCompileRequest(
            file_id="test-file-123",
            compiler="xelatex",
            output_filename="output.pdf"
        )
        assert request.file_id == "test-file-123"
        assert request.compiler == "xelatex"
        assert request.output_filename == "output.pdf"


class TestValidationLogic:
    """Test LaTeX validation logic components (still used for package extraction)"""
    
    def test_extract_packages_function(self):
        """Test package extraction function directly"""
        content = r"""
        \documentclass{article}
        \usepackage{amsmath}
        \usepackage{graphicx}
        \begin{document}
        Hello, \LaTeX!
        \end{document}
        """
        
        packages = server.extract_packages(content)
        assert "amsmath" in packages
        assert "graphicx" in packages
        assert isinstance(packages, list)


if __name__ == "__main__":
    pytest.main([__file__])