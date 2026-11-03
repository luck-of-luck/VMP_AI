"""Post-validation logic for deduplication refactoring.

This module handles validation of files after refactoring changes
have been applied to ensure code correctness.
"""

import os
from typing import Any, Dict, List, Optional, Tuple

from ...constants import DisplayDefaults
from ...core.logging import get_logger
from ...utils.syntax_validation import suggest_syntax_fix
from .applicator_validator import ValidationResult


def _make_error(error_type: str, file_path: str, error: str, suggestion: str) -> Dict[str, Any]:
    return {"type": error_type, "file": file_path, "error": error, "suggestion": suggestion}


def _file_not_found_error(file_path: str) -> Dict[str, Any]:
    return _make_error(
        "file_not_found",
        file_path,
        f"Modified file not found: {file_path}",
        "File may have been deleted during operation",
    )


class RefactoringPostValidator:
    """Validates files after refactoring modifications."""

    def __init__(self) -> None:
        """Initialize the post-validator."""
        self.logger = get_logger("deduplication.post_validator")

    def validate_modified_files(self, modified_files: List[str], language: str) -> ValidationResult:
        """Validate files after modifications.

        Args:
            modified_files: List of modified file paths
            language: Programming language

        Returns:
            ValidationResult with validation status and errors
        """
        self.logger.info("post_validation_start", file_count=len(modified_files), language=language)

        errors: List[Dict[str, Any]] = []

        for file_path in modified_files:
            if not os.path.exists(file_path):
                errors.append(_file_not_found_error(file_path))
                continue
            errors.extend(self._validate_file_syntax(file_path, language))

        is_valid = len(errors) == 0
        self.logger.info("post_validation_complete", is_valid=is_valid, error_count=len(errors))

        return ValidationResult(is_valid=is_valid, errors=errors)

    def _validate_file_syntax(self, file_path: str, language: str) -> List[Dict[str, Any]]:
        """Validate file syntax after modifications.

        Args:
            file_path: Path to file to validate
            language: Programming language

        Returns:
            List of validation error dictionaries
        """
        try:
            from ..rewrite.service import validate_syntax

            result = validate_syntax(file_path, language)
        except Exception as e:
            self.logger.error("syntax_validation_exception", file=file_path, error=str(e))
            return [
                _make_error(
                    "validation_exception",
                    file_path,
                    f"Failed to validate syntax: {str(e)}",
                    "Check if the file is readable and well-formed",
                )
            ]

        if result["valid"]:
            return []

        self.logger.warning(
            "syntax_validation_failed",
            file=file_path,
            error=result.get("error", "")[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH],
        )
        return [
            _make_error(
                "syntax_error",
                file_path,
                result.get("error", "Unknown syntax error"),
                suggest_syntax_fix(result.get("error"), language, context="file"),
            )
        ]

    def _read_file_content(self, file_path: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        try:
            with open(file_path, "r") as f:
                return f.read(), None
        except Exception as e:
            return None, _make_error(
                "structure_check_failed",
                file_path,
                f"Failed to check file structure: {str(e)}",
                "Verify file is readable",
            )

