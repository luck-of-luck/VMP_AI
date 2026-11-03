"""Configuration models for ast-grep MCP server."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CustomLanguageConfig(BaseModel):
    """Configuration for a custom language in sgconfig.yaml."""

    model_config = ConfigDict(populate_by_name=True)

    extensions: List[str]
    languageId: Optional[str] = None  # noqa: N815
    expandoChar: Optional[str] = None  # noqa: N815

    @field_validator("extensions")
    @classmethod
    def validate_extensions(cls, v: List[str]) -> List[str]:
        """Ensure extensions start with a dot."""
        if not v:
            raise ValueError("extensions list cannot be empty")
        for ext in v:
            if not ext.startswith("."):
                raise ValueError(f"Extension '{ext}' must start with a dot (e.g., '.myext')")
        return v


class AstGrepConfig(BaseModel):
    """Pydantic model for validating sgconfig.yaml structure."""

    model_config = ConfigDict(populate_by_name=True)

    ruleDirs: Optional[List[str]] = None  # noqa: N815
    testDirs: Optional[List[str]] = None  # noqa: N815
    customLanguages: Optional[Dict[str, CustomLanguageConfig]] = None  # noqa: N815
    languageGlobs: Optional[List[Dict[str, Any]]] = None  # noqa: N815

    @field_validator("ruleDirs", "testDirs")
    @classmethod
    def validate_dirs(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate directory lists are not empty if provided."""
        if v is not None and len(v) == 0:
            raise ValueError("Directory list cannot be empty if specified")
        return v

    @field_validator("customLanguages")
    @classmethod
    def validate_custom_languages(cls, v: Optional[Dict[str, CustomLanguageConfig]]) -> Optional[Dict[str, CustomLanguageConfig]]:
        """Validate custom languages dictionary."""
        if v is not None and len(v) == 0:
            raise ValueError("customLanguages cannot be empty if specified")
        return v
