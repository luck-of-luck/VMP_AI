"""Data models for ast-grep MCP server."""

# Condense models
# Config models
# Complexity models
from ast_grep_mcp.models.complexity import (
    ComplexityMetrics,
    ComplexityThresholds,
    FunctionComplexity,
)
from ast_grep_mcp.models.condense import (
    CondenseResult,
    LanguageCondenseStats,
)
from ast_grep_mcp.models.config import (
    AstGrepConfig,
    CustomLanguageConfig,
)

# Deduplication models
from ast_grep_mcp.models.deduplication import (
    AlignmentResult,
    AlignmentSegment,
    DiffPreview,
    DiffTree,
    DiffTreeNode,
    EnhancedDuplicationCandidate,
    FileDiff,
    FunctionTemplate,
    ParameterInfo,
    ParameterType,
    VariationCategory,
    VariationSeverity,
)

# Standards models
from ast_grep_mcp.models.standards import (
    EnforcementResult,
    FixBatchResult,
    FixResult,
    FixValidation,
    LintingRule,
    RuleExecutionContext,
    RuleSet,
    RuleStorageError,
    RuleTemplate,
    RuleValidationError,
    RuleValidationResult,
    RuleViolation,
    SecurityIssue,
    SecurityScanResult,
)

__all__ = [
    # Condense
    "CondenseResult",
    "LanguageCondenseStats",
    # Config
    "AstGrepConfig",
    "CustomLanguageConfig",
    # Deduplication
    "AlignmentResult",
    "AlignmentSegment",
    "DiffPreview",
    "DiffTree",
    "DiffTreeNode",
    "EnhancedDuplicationCandidate",
    "FileDiff",
    "FunctionTemplate",
    "ParameterInfo",
    "ParameterType",
    "VariationCategory",
    "VariationSeverity",
    # Complexity
    "ComplexityMetrics",
    "ComplexityThresholds",
    "FunctionComplexity",
    # Standards
    "EnforcementResult",
    "FixBatchResult",
    "FixResult",
    "FixValidation",
    "LintingRule",
    "RuleExecutionContext",
    "RuleSet",
    "RuleStorageError",
    "RuleTemplate",
    "RuleValidationError",
    "RuleValidationResult",
    "RuleViolation",
    "SecurityIssue",
    "SecurityScanResult",
]
