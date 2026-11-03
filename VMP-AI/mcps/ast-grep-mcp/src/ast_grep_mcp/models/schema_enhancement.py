"""Data models for Schema.org entity graph enhancement features."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EnhancementPriority(Enum):
    """Priority levels for Schema.org enhancements.

    Attributes:
        CRITICAL: Required for Google Rich Results
        HIGH: Strongly recommended for SEO
        MEDIUM: Improves discoverability
        LOW: Nice to have
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EnhancementCategory(Enum):
    """Categories of schema enhancement issues.

    Attributes:
        MISSING_PROPERTY: Entity is missing a recommended property
        MISSING_ENTITY: Graph is missing a recommended entity type
        INVALID_ID: Entity has an invalid or missing @id
        BROKEN_REFERENCE: Entity references a non-existent @id
    """

    MISSING_PROPERTY = "missing_property"
    MISSING_ENTITY = "missing_entity"
    INVALID_ID = "invalid_id"
    BROKEN_REFERENCE = "broken_reference"


@dataclass
class PropertyEnhancement:
    """Enhancement suggestion for a missing property.

    Attributes:
        property_name: Name of the property (e.g., "aggregateRating")
        expected_types: List of expected Schema.org types for the property
        priority: Priority level for adding this property
        reason: Human-readable explanation for why this property is recommended
        example_value: Example value showing proper structure
        google_rich_result: Name of Google Rich Result this enables (if any)
    """

    property_name: str
    expected_types: List[str]
    priority: EnhancementPriority
    reason: str
    example_value: Any
    google_rich_result: Optional[str] = None


@dataclass
class EntityEnhancement:
    """Enhancement suggestions for a single entity.

    Attributes:
        entity_id: The @id of the entity being analyzed
        entity_type: The @type of the entity (e.g., "Organization")
        existing_properties: List of properties the entity currently has
        suggested_properties: List of property enhancements recommended
        validation_issues: List of validation issues found (e.g., broken references)
        seo_score: SEO completeness score from 0.0 to 100.0
    """

    entity_id: str
    entity_type: str
    existing_properties: List[str]
    suggested_properties: List[PropertyEnhancement]
    validation_issues: List[str] = field(default_factory=list)
    seo_score: float = 0.0


@dataclass
class MissingEntitySuggestion:
    """Suggestion for a missing entity type in the graph.

    Attributes:
        entity_type: Schema.org type to add (e.g., "FAQPage")
        priority: Priority level for adding this entity
        reason: Human-readable explanation for why this entity is recommended
        example: Example structure for the entity with placeholder values
        google_rich_result: Name of Google Rich Result this enables (if any)
    """

    entity_type: str
    priority: EnhancementPriority
    reason: str
    example: Dict[str, Any]
    google_rich_result: Optional[str] = None


@dataclass
class GraphEnhancementResult:
    """Complete result of entity graph enhancement analysis.

    Attributes:
        original_graph: The original JSON-LD graph as parsed
        entity_enhancements: Enhancement suggestions for each entity
        missing_entities: Suggestions for missing entity types
        global_issues: Graph-level issues (e.g., no @context)
        overall_seo_score: Overall SEO completeness score from 0.0 to 100.0
        priority_summary: Count of suggestions by priority level
        enhanced_graph: Enhanced graph with all suggestions applied (if output_mode="enhanced")
        diff: Additions needed to enhance the graph (if output_mode="diff")
        execution_time_ms: Time taken to perform analysis in milliseconds
    """

    original_graph: List[Dict[str, Any]]
    entity_enhancements: List[EntityEnhancement]
    missing_entities: List[MissingEntitySuggestion]
    global_issues: List[str] = field(default_factory=list)
    overall_seo_score: float = 0.0
    priority_summary: Dict[str, int] = field(default_factory=dict)
    enhanced_graph: Optional[Dict[str, Any]] = None
    diff: Optional[Dict[str, Any]] = None
    execution_time_ms: int = 0
