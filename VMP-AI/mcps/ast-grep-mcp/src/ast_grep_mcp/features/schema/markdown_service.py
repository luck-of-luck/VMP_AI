"""Markdown frontmatter Schema.org extraction and validation.

Extracts YAML frontmatter from markdown files and detects Schema.org
structured data fields for validation and enhancement suggestions.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from ast_grep_mcp.constants import FilePatterns
from ast_grep_mcp.core.logging import get_logger

logger = get_logger("schema.markdown")

DEFAULT_MD_GLOBS = ["**/*.md", "**/*.mdx"]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# Keys that indicate Schema.org structured data in frontmatter
SCHEMA_KEYS: Set[str] = {
    "@type",
    "@context",
    "@id",
    "schema",
    "structured_data",
    "jsonld",
    "seo",
}

# Nested paths that commonly hold schema data (dot-separated)
SCHEMA_NESTED_PATHS: Set[str] = {
    "seo.schema",
    "seo.jsonld",
    "seo.structured_data",
}

# Schema.org types commonly found in frontmatter
COMMON_FRONTMATTER_TYPES: Set[str] = {
    "Article",
    "BlogPosting",
    "NewsArticle",
    "TechArticle",
    "HowTo",
    "FAQPage",
    "WebPage",
    "Product",
    "Recipe",
    "Event",
    "Course",
}

# Required properties per common type for suggestion purposes
TYPE_REQUIRED_PROPERTIES: Dict[str, List[str]] = {
    "Article": ["headline", "author", "datePublished"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished", "locationCreated"],
    "HowTo": ["name", "step"],
    "FAQPage": ["mainEntity"],
    "Product": ["name", "description"],
    "Recipe": ["name", "recipeIngredient", "recipeInstructions"],
    "Event": ["name", "startDate", "location"],
    "Course": ["name", "description", "provider"],
}


def _extract_frontmatter(content: str) -> Optional[Dict[str, Any]]:
    """Parse YAML frontmatter from markdown content."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else None
    except yaml.YAMLError:
        return None


def _get_nested(data: Dict[str, Any], dotted_path: str) -> Any:
    """Retrieve a value from a nested dict using a dot-separated path."""
    parts = dotted_path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _find_schema_fields(frontmatter: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Schema.org-related fields from frontmatter."""
    found: Dict[str, Any] = {}

    for key in SCHEMA_KEYS:
        if key in frontmatter:
            found[key] = frontmatter[key]

    for path in SCHEMA_NESTED_PATHS:
        value = _get_nested(frontmatter, path)
        if value is not None:
            found[path] = value

    return found


def _collect_md_files(project_folder: str, file_globs: Optional[List[str]] = None) -> List[Path]:
    """Collect markdown files from project folder."""
    root = Path(project_folder)
    globs = file_globs or DEFAULT_MD_GLOBS
    files: List[Path] = []
    for glob_pattern in globs:
        for path in root.glob(glob_pattern):
            if path.is_file() and not any(exc.strip("**/") in str(path) for exc in FilePatterns.DEFAULT_EXCLUDE):
                files.append(path)
    return sorted(files)


def extract_schema_from_frontmatter(
    project_folder: str,
    file_globs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Parse markdown frontmatter and extract Schema.org fields.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan (default: **/*.md, **/*.mdx)

    Returns:
        Dict with files containing schema data, files without, and extracted fields
    """
    files = _collect_md_files(project_folder, file_globs)

    with_schema: List[Dict[str, Any]] = []
    without_schema: List[str] = []
    no_frontmatter: List[str] = []

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        frontmatter = _extract_frontmatter(content)
        rel_path = str(file_path.relative_to(project_folder))

        if frontmatter is None:
            no_frontmatter.append(rel_path)
            continue

        schema_fields = _find_schema_fields(frontmatter)
        if schema_fields:
            with_schema.append(
                {
                    "file": rel_path,
                    "schema_fields": schema_fields,
                    "all_keys": set(frontmatter.keys()),
                }
            )
        else:
            without_schema.append(rel_path)

    return {
        "files_scanned": len(files),
        "with_schema": with_schema,
        "without_schema": without_schema,
        "no_frontmatter": no_frontmatter,
    }


def validate_frontmatter_schema(
    project_folder: str,
    file_globs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate Schema.org fields found in markdown frontmatter.

    Checks that @type values are recognized Schema.org types and that
    @context is properly set.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan

    Returns:
        Validation results with errors and warnings per file
    """
    extraction = extract_schema_from_frontmatter(project_folder, file_globs)
    validations: List[Dict[str, Any]] = []

    for entry in extraction["with_schema"]:
        file_path = entry["file"]
        fields = entry["schema_fields"]
        errors: List[str] = []
        warnings: List[str] = []

        schema_type = fields.get("@type")
        if schema_type and isinstance(schema_type, str):
            if schema_type not in COMMON_FRONTMATTER_TYPES:
                warnings.append(f"Unrecognized @type: {schema_type}")
        elif schema_type is None:
            # Check nested locations
            for path in SCHEMA_NESTED_PATHS:
                nested = fields.get(path)
                if isinstance(nested, dict) and "@type" in nested:
                    schema_type = nested["@type"]
                    break

        context = fields.get("@context")
        if context is None and "@type" in fields:
            warnings.append("@type present without @context")
        elif isinstance(context, str) and "schema.org" not in context:
            errors.append(f"@context does not reference schema.org: {context}")

        validations.append(
            {
                "file": file_path,
                "schema_type": schema_type,
                "errors": errors,
                "warnings": warnings,
                "valid": len(errors) == 0,
            }
        )

    return {
        "files_validated": len(validations),
        "validations": validations,
        "total_errors": sum(len(v["errors"]) for v in validations),
        "total_warnings": sum(len(v["warnings"]) for v in validations),
    }


def suggest_frontmatter_enhancements(
    project_folder: str,
    file_globs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Suggest missing Schema.org properties for markdown frontmatter.

    Based on the @type detected, suggests required and recommended properties
    that are missing from the frontmatter.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan

    Returns:
        Enhancement suggestions per file
    """
    extraction = extract_schema_from_frontmatter(project_folder, file_globs)
    suggestions: List[Dict[str, Any]] = []

    for entry in extraction["with_schema"]:
        file_path = entry["file"]
        fields = entry["schema_fields"]

        schema_type = fields.get("@type")
        if not isinstance(schema_type, str):
            continue

        required = TYPE_REQUIRED_PROPERTIES.get(schema_type, [])
        if not required:
            continue

        # Use full frontmatter keys, plus nested schema/structured_data dicts
        all_keys: Set[str] = entry.get("all_keys", set(fields.keys()))
        for nested_key in ("schema", "structured_data", "jsonld"):
            nested = fields.get(nested_key)
            if isinstance(nested, dict):
                all_keys.update(nested.keys())

        missing = [prop for prop in required if prop not in all_keys]
        if missing:
            suggestions.append(
                {
                    "file": file_path,
                    "schema_type": schema_type,
                    "missing_properties": missing,
                    "total_required": len(required),
                    "completeness": round(1 - len(missing) / len(required), 2),
                }
            )

    return {
        "files_with_suggestions": len(suggestions),
        "suggestions": suggestions,
    }
