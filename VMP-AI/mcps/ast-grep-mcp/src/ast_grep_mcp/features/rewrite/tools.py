"""Rewrite feature MCP tool definitions."""

from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ast_grep_mcp.features.rewrite.service import (
    list_backups_impl,
    rewrite_code_impl,
    rollback_rewrite_impl,
)
from ast_grep_mcp.features.rewrite.zod_templates import (
    get_rules_by_category,
    get_zod_rule,
    list_import_rules,
    list_schema_rules,
)


def _register_rewrite_code(mcp: FastMCP) -> None:
    @mcp.tool()
    def rewrite_code(
        project_folder: str = Field(description="The absolute path to the project folder"),
        yaml_rule: str = Field(description="YAML rule with 'fix' field for code transformation"),
        dry_run: bool = Field(default=True, description="Preview changes without applying (default: true for safety)"),
        backup: bool = Field(default=True, description="Create backup before applying changes (default: true)"),
        max_file_size_mb: int = Field(default=0, description="Skip files larger than this (0 = unlimited)"),
        workers: int = Field(default=0, description="Number of worker threads (0 = auto)"),
    ) -> Dict[str, Any]:
        """
        Rewrite code using ast-grep fix rules. Apply automated code transformations safely.

        SAFETY FEATURES:
        - dry_run=True by default (preview before applying)
        - Automatic backups before changes
        - Returns diff preview or list of modified files

        ## General Usage

        Example: Replace var with const
        ```yaml
        id: replace-var-with-const
        language: javascript
        rule:
          pattern: var $NAME = $VAL
        fix: const $NAME = $VAL
        ```

        ## Zod Schema Validation Rules

        Enforce Zod best practices with these patterns:

        **Fix: Disallow z.any()**
        ```yaml
        id: no-any-schema
        language: typescript
        rule:
          pattern: z.any()
        fix: z.unknown().catch({})
        message: "Use z.unknown().catch({}) instead of z.any()"
        ```

        **Fix: Require Schema suffix**
        ```yaml
        id: require-schema-suffix
        language: typescript
        rule:
          pattern: const $NAME = z.object($$ARGS)
        fix: const $${NAME}Schema = z.object($$ARGS)
        message: "Schema variables must end with 'Schema' suffix"
        ```

        **Fix: Require error message in refine**
        ```yaml
        id: require-error-message
        language: typescript
        rule:
          pattern: $SCHEMA.refine($CB)
        fix: $SCHEMA.refine($CB, { message: "Validation failed" })
        message: "refine() must include error message"
        ```

        **Fix: Prefer z.enum() over literal union**
        ```yaml
        id: prefer-enum-over-literal-union
        language: typescript
        rule:
          pattern: z.union([z.literal($LIT1), z.literal($LIT2)])
        fix: z.enum([$LIT1, $LIT2])
        message: "Use z.enum() instead of union of literals"
        ```

        **Fix: Remove .optional() when .default() exists**
        ```yaml
        id: no-optional-and-default-together
        language: typescript
        rule:
          pattern: $SCHEMA.optional().default($VAL)
        fix: $SCHEMA.default($VAL)
        message: "Don't use both .optional() and .default()"
        ```

        ## Zod Import Rules

        Enforce namespace imports for tree-shaking:

        **Fix: Named import to namespace**
        ```yaml
        id: import-zod-namespace
        language: typescript
        rule:
          pattern: import { z } from "zod"
        fix: import * as z from "zod"
        message: "Use namespace import for better tree-shaking"
        ```

        **Fix: Default import to namespace**
        ```yaml
        id: import-zod-default-namespace
        language: typescript
        rule:
          pattern: import z from "zod"
        fix: import * as z from "zod"
        message: "Use namespace import for better tree-shaking"
        ```

        **Fix: Mixed imports to namespace + named**
        ```yaml
        id: import-zod-mixed-to-namespace
        language: typescript
        rule:
          pattern: import z, { $$EXPORTS } from "zod"
        fix: import * as z from "zod"; import { $$EXPORTS } from "zod"
        message: "Separate namespace and named imports"
        ```

        ## Tips

        - Use metavariables ($NAME, $$ARGS) to capture code patterns
        - stopBy: "neighbor" for relational rules to stop at immediate children only
        - Use "inside" and "has" constraints for context-aware matching
        - Test with dry_run=True first to preview changes
        - Use find_code_by_rule to locate matches before rewriting

        ## Available Rules

        Pre-built rules available in:
        - `rules/zod-validation-rules.yaml` - 10 Zod schema validation rules
        - `rules/import-zod-rules.yaml` - 7 Zod import enforcement rules

        Returns:
        - dry_run=True: Preview with diffs showing proposed changes
        - dry_run=False: backup_id and list of modified files
        """
        return rewrite_code_impl(project_folder, yaml_rule, dry_run, backup, max_file_size_mb, workers)


def _register_rollback_rewrite(mcp: FastMCP) -> None:
    @mcp.tool()
    def rollback_rewrite(
        backup_id: str = Field(description="The backup ID from a previous rewrite operation"),
        project_folder: str = Field(description="The absolute path to the project folder"),
    ) -> Dict[str, Any]:
        """
        Restore files from a backup created during rewrite operations.

        Use this to undo changes from rewrite_code when:
        - Syntax validation fails
        - Changes had unintended effects
        - You need to restore previous state

        Get available backup_ids using list_backups().

        Returns:
        - success: Whether restoration was successful
        - restored_files: List of restored file paths
        - errors: Any errors encountered (if restoration failed)
        """
        return rollback_rewrite_impl(backup_id, project_folder)


def _register_list_backups(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_backups(project_folder: str = Field(description="The absolute path to the project folder")) -> List[Dict[str, Any]]:
        """
        List all available backups in the project.

        Shows backups created by rewrite_code and apply_deduplication operations.
        Backups are stored in .ast-grep-backups/ directory.

        Returns list of backups with:
        - backup_id: Unique identifier (use with rollback_rewrite)
        - timestamp: When backup was created
        - file_count: Number of files in backup
        - size_bytes: Total backup size
        - backup_type: 'standard' or 'deduplication'
        """
        return list_backups_impl(project_folder)


def _register_get_zod_rule(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_zod_rewrite_rule(
        rule_id: str = Field(description="Zod rule ID (e.g., 'no-any-schema', 'import-zod-named-to-namespace')"),
    ) -> Dict[str, str]:
        """
        Get a pre-built Zod rewrite rule by ID.

        Returns a complete YAML rule string that can be passed directly to rewrite_code().
        Use list_zod_rewrite_rules() to discover available rule IDs.

        Returns:
        - rule_id: The requested rule ID
        - yaml_rule: YAML rule string ready for rewrite_code(yaml_rule=...)
        """
        try:
            yaml_rule = get_zod_rule(rule_id)
        except KeyError as exc:
            return {"error": str(exc)}
        return {"rule_id": rule_id, "yaml_rule": yaml_rule}


def _register_list_zod_rules(mcp: FastMCP) -> None:
    @mcp.tool()
    def list_zod_rewrite_rules(
        category: str = Field(default="all", description="'schema', 'import', or 'all'"),
    ) -> Dict[str, Any]:
        """
        List pre-built Zod rewrite rules by category.

        Categories:
        - 'schema': Zod schema validation rules (e.g., no-any-schema, require-schema-suffix)
        - 'import': Zod import namespace rules (e.g., import-zod-named-to-namespace)
        - 'all': Both schema and import rules

        Returns:
        - category: The requested category
        - rules: Dict of rule_id -> description (for 'all', includes both groups)
        """
        if category not in ("schema", "import", "all"):
            return {"error": f"Invalid category: {category}. Use 'schema', 'import', or 'all'"}
        if category == "schema":
            rules: Dict[str, Any] = list_schema_rules()
        elif category == "import":
            rules = list_import_rules()
        else:
            rules = {"schema": list_schema_rules(), "import": list_import_rules()}
        return {"category": category, "rules": rules, "count": len(get_rules_by_category(category))}  # type: ignore[arg-type]


def register_rewrite_tools(mcp: FastMCP) -> None:
    """Register rewrite-related MCP tools.

    Args:
        mcp: FastMCP instance to register tools with
    """
    _register_rewrite_code(mcp)
    _register_rollback_rewrite(mcp)
    _register_list_backups(mcp)
    _register_get_zod_rule(mcp)
    _register_list_zod_rules(mcp)
