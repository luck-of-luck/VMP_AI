"""Models for interactive pattern development functionality.

This module provides dataclasses for pattern development results,
including code analysis, pattern suggestions, and refinement guidance.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class SuggestionType(Enum):
    """Type of pattern suggestion."""

    EXACT = "exact"  # Matches exactly what was provided
    GENERALIZED = "generalized"  # With metavariables for flexibility
    STRUCTURAL = "structural"  # Based on node kind only


@dataclass
class PatternSuggestion:
    """A suggested pattern with explanation.

    Attributes:
        pattern: The suggested pattern string
        description: What this pattern matches
        type: Type of suggestion (exact, generalized, structural)
        confidence: How likely this pattern is correct (0.0-1.0)
        notes: Additional notes about usage
    """

    pattern: str
    description: str
    type: SuggestionType
    confidence: float
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pattern": self.pattern,
            "description": self.description,
            "type": self.type.value,
            "confidence": self.confidence,
            "notes": self.notes,
        }


@dataclass
class CodeAnalysis:
    """Analysis of the target code structure.

    Attributes:
        root_kind: The root AST node kind
        child_kinds: List of child node kinds
        identifiers: Identified identifier names
        literals: Identified literal values
        keywords: Language keywords found
        complexity: Simple/Medium/Complex based on AST depth
        ast_preview: Simplified AST structure preview
    """

    root_kind: str
    child_kinds: List[str]
    identifiers: List[str]
    literals: List[str]
    keywords: List[str]
    complexity: str  # "simple", "medium", "complex"
    ast_preview: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "root_kind": self.root_kind,
            "child_kinds": self.child_kinds,
            "identifiers": self.identifiers,
            "literals": self.literals,
            "keywords": self.keywords,
            "complexity": self.complexity,
            "ast_preview": self.ast_preview,
        }


@dataclass
class RefinementStep:
    """A step in the pattern refinement process.

    Attributes:
        action: What action to take
        pattern: The pattern after this step
        explanation: Why this step helps
        priority: Order to try (1 = first)
    """

    action: str
    pattern: str
    explanation: str
    priority: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "action": self.action,
            "pattern": self.pattern,
            "explanation": self.explanation,
            "priority": self.priority,
        }


@dataclass
class PatternDevelopResult:
    """Complete result of pattern development assistance.

    Attributes:
        code: The target code to match
        language: The programming language
        code_analysis: Analysis of the code structure
        suggested_patterns: List of pattern suggestions, ordered by recommendation
        best_pattern: The recommended pattern to start with
        pattern_matches: Whether the best pattern matches the code
        match_count: Number of matches if applicable
        refinement_steps: Steps to refine the pattern if needed
        yaml_rule_template: Ready-to-use YAML rule with the best pattern
        next_steps: Guidance on what to do next
        execution_time_ms: Time taken in milliseconds
    """

    code: str
    language: str
    code_analysis: CodeAnalysis
    suggested_patterns: List[PatternSuggestion]
    best_pattern: str
    pattern_matches: bool
    match_count: int
    refinement_steps: List[RefinementStep]
    yaml_rule_template: str
    next_steps: List[str]
    execution_time_ms: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "language": self.language,
            "code_analysis": self.code_analysis.to_dict(),
            "suggested_patterns": [p.to_dict() for p in self.suggested_patterns],
            "best_pattern": self.best_pattern,
            "pattern_matches": self.pattern_matches,
            "match_count": self.match_count,
            "refinement_steps": [s.to_dict() for s in self.refinement_steps],
            "yaml_rule_template": self.yaml_rule_template,
            "next_steps": self.next_steps,
            "execution_time_ms": self.execution_time_ms,
        }
