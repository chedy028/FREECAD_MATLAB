"""Test security utilities"""

import pytest
from pathlib import Path
from agent.security import SecurityValidator


def test_validate_path_allowed():
    """Test path validation - allowed path"""
    validator = SecurityValidator(
        allowed_base_paths=["runs", "cad_templates"],
        blocked_extensions=[".exe"],
        sandbox_enabled=True,
    )
    
    # Should not raise
    validator.validate_path("runs/test/file.json")


def test_validate_path_blocked():
    """Test path validation - blocked path"""
    validator = SecurityValidator(
        allowed_base_paths=["runs"],
        blocked_extensions=[".exe"],
        sandbox_enabled=True,
    )
    
    with pytest.raises(ValueError, match="outside allowed base paths"):
        validator.validate_path("/etc/passwd")


def test_validate_path_blocked_extension():
    """Test path validation - blocked extension"""
    validator = SecurityValidator(
        allowed_base_paths=["runs"],
        blocked_extensions=[".exe", ".dll"],
        sandbox_enabled=True,
    )
    
    with pytest.raises(ValueError, match="blocked for security"):
        validator.validate_path("runs/malware.exe")


def test_sanitize_filename():
    """Test filename sanitization"""
    validator = SecurityValidator(
        allowed_base_paths=["runs"],
        blocked_extensions=[],
    )
    
    # Path traversal attempt
    assert validator.sanitize_filename("../../etc/passwd") == "_.._etc_passwd"
    
    # Spaces and special chars
    assert validator.sanitize_filename("my file (v2).txt") == "my_file__v2_.txt"
    
    # Safe filename
    assert validator.sanitize_filename("geometry_v1.step") == "geometry_v1.step"


def test_validate_template():
    """Test template validation"""
    validator = SecurityValidator(
        allowed_base_paths=["runs"],
        blocked_extensions=[],
    )
    
    allowed = ["parametric_enclosure_v1", "parametric_bracket_v1"]
    
    # Should not raise
    validator.validate_template_name("parametric_enclosure_v1", allowed)
    
    # Should raise
    with pytest.raises(ValueError, match="not in allowlist"):
        validator.validate_template_name("malicious_template", allowed)

