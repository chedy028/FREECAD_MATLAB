"""Security utilities and validation"""

import os
from pathlib import Path
from typing import List, Optional


class SecurityValidator:
    """Validate paths and operations for security"""

    def __init__(
        self,
        allowed_base_paths: List[str],
        blocked_extensions: List[str],
        max_file_size_mb: int = 500,
        sandbox_enabled: bool = True,
    ):
        self.allowed_base_paths = [Path(p).resolve() for p in allowed_base_paths]
        self.blocked_extensions = [ext.lower() for ext in blocked_extensions]
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.sandbox_enabled = sandbox_enabled

    def validate_path(self, path: str) -> None:
        """
        Validate that a path is safe to access.
        
        Raises ValueError if path is not allowed.
        """
        if not self.sandbox_enabled:
            return

        path_obj = Path(path).resolve()

        # Check if path is under allowed base paths
        is_allowed = any(
            str(path_obj).startswith(str(base)) for base in self.allowed_base_paths
        )

        if not is_allowed:
            raise ValueError(
                f"Path '{path}' is outside allowed base paths: {self.allowed_base_paths}"
            )

        # Check extension
        ext = path_obj.suffix.lower()
        if ext in self.blocked_extensions:
            raise ValueError(f"File extension '{ext}' is blocked for security reasons")

    def validate_file_size(self, path: str) -> None:
        """
        Validate file size.
        
        Raises ValueError if file is too large.
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            return  # File doesn't exist yet (will be created)

        size = path_obj.stat().st_size
        
        if size > self.max_file_size_bytes:
            raise ValueError(
                f"File size ({size} bytes) exceeds limit ({self.max_file_size_bytes} bytes)"
            )

    def validate_template_name(self, template: str, allowed: List[str]) -> None:
        """
        Validate template name against allowlist.
        
        Raises ValueError if template is not allowed.
        """
        if template not in allowed:
            raise ValueError(
                f"Template '{template}' not in allowlist: {allowed}"
            )

    def validate_entrypoint(self, entrypoint: str, allowed: List[str]) -> None:
        """
        Validate MATLAB entrypoint against allowlist.
        
        Raises ValueError if entrypoint is not allowed.
        """
        if entrypoint not in allowed:
            raise ValueError(
                f"Entrypoint '{entrypoint}' not in allowlist: {allowed}"
            )

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal.
        
        Removes any path separators and special characters.
        """
        # Remove path separators
        filename = filename.replace("/", "_").replace("\\", "_")
        
        # Remove parent directory references
        filename = filename.replace("..", "_")
        
        # Remove any other potentially dangerous characters
        safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
        filename = "".join(c if c in safe_chars else "_" for c in filename)
        
        return filename


def create_security_validator_from_config(config) -> SecurityValidator:
    """Create SecurityValidator from config"""
    return SecurityValidator(
        allowed_base_paths=config.security.allowed_base_paths,
        blocked_extensions=config.security.blocked_extensions,
        max_file_size_mb=config.security.max_file_size_mb,
        sandbox_enabled=config.security.sandbox_enabled,
    )

