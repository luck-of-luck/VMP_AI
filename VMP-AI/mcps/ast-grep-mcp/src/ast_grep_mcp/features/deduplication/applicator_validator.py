"""Validation logic for deduplication refactoring plans.

This module handles pre-validation of refactoring plans before
they are applied to ensure code quality and prevent syntax errors.
"""

from pathlib import Path
from typing import Any, Dict, List

from ...constants import DisplayDefaults
from ...core.logging import get_logger
from ...utils.syntax_validation import suggest_syntax_fix, validate_code_for_language


class ValidationResult:
    """Result of validation operation."""

    def __init__(self, is_valid: bool, errors: List[Dict[str, Any]]) -> None:
        """Initialize validation result.

        Args:
            is_valid: Whether validation passed
            errors: List of validation errors
        """
        self.is_valid = is_valid
        self.errors = errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {"passed": self.is_valid, "errors": self.errors}


class RefactoringPlanValidator:
    """Validates refactoring plans before application."""

    def __init__(self) -> None:
        """Initialize the validator."""
        self.logger = get_logger("deduplication.validator")

    def validate_plan(self, refactoring_plan: Dict[str, Any], group_id: int, project_folder: str) -> ValidationResult:
        """Validate refactoring plan completeness and correctness.

        Args:
            refactoring_plan: The refactoring plan to validate
            group_id: Duplication group ID
            project_folder: Project root folder

        Returns:
            ValidationResult with validation status and errors
        """
        self.logger.info("validate_plan_start", group_id=group_id)
        errors: List[Dict[str, Any]] = []

        # Validate required fields
        errors.extend(self._validate_required_fields(refactoring_plan))

        # Validate generated code syntax (file existence checked during orchestration)
        errors.extend(self._validate_code_syntax(refactoring_plan))

        is_valid = len(errors) == 0
        self.logger.info("validate_plan_complete", is_valid=is_valid, error_count=len(errors))

        return ValidationResult(is_valid=is_valid, errors=errors)

    def _validate_required_fields(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check plan has all required fields.

        Args:
            plan: Refactoring plan to validate

        Returns:
            List of error dictionaries
        """
        required_fields = ["generated_code", "files_affected", "language"]
        return [
            {
                "type": "missing_field",
                "field": field,
                "error": f"Missing required field: {field}",
                "suggestion": f"Add '{field}' to the refactoring plan",
            }
            for field in required_fields
            if field not in plan
        ]

    def _resolve_file_path(self, file_path: str, project_folder: str) -> Path:
        full_path = Path(file_path)
        if not full_path.is_absolute():
            full_path = Path(project_folder) / file_path
        return full_path

    def _check_file_error(self, file_path: str, full_path: Path) -> Dict[str, Any] | None:
        if not full_path.exists():
            return {
                "type": "file_not_found",
                "file": str(file_path),
                "error": f"File not found: {file_path}",
                "suggestion": "Verify the file path is correct",
            }
        if not full_path.is_file():
            return {
                "type": "not_a_file",
                "file": str(file_path),
                "error": f"Path is not a file: {file_path}",
                "suggestion": "Ensure the path points to a file, not a directory",
            }
        return None

    def _check_extracted_function(self, code: str, language: str) -> List[Dict[str, Any]]:
        if not code:
            return []
        is_valid, error_msg = validate_code_for_language(code, language)
        if is_valid:
            return []
        return [
            {
                "type": "extracted_function",
                "file": "extracted function",
                "error": error_msg,
                "code_preview": code[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH],
                "suggestion": suggest_syntax_fix(error_msg, language, context="code"),
            }
        ]

    def _check_replacement_syntax(self, file_path: str, new_content: str, language: str) -> Dict[str, Any] | None:
        is_valid, error_msg = validate_code_for_language(new_content, language)
        if is_valid:
            return None
        return {
            "type": "replacement_code",
            "file": file_path,
            "error": error_msg,
            "suggestion": suggest_syntax_fix(error_msg, language, context="code"),
        }

    def _check_replacements(self, replacements: Dict[str, Any], language: str) -> List[Dict[str, Any]]:
        errors = []
        for file_path, replacement in replacements.items():
            new_content = replacement.get("new_content", "")
            if not new_content:
                continue
            error = self._check_replacement_syntax(file_path, new_content, language)
            if error:
                errors.append(error)
        return errors

    def _validate_code_syntax(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Pre-validate generated code syntax.

        Args:
            plan: Refactoring plan with generated code

        Returns:
            List of error dictionaries
        """
        language = plan.get("language", "python")
        generated_code = plan.get("generated_code", {})
        errors = self._check_extracted_function(generated_code.get("extracted_function", ""), language)
        errors.extend(self._check_replacements(generated_code.get("replacements", {}), language))
        return errors
