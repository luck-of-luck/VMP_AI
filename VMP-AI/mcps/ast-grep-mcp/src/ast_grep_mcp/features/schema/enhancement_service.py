"""Enhancement service for Schema.org entity graph analysis.

This module implements the core logic for analyzing existing JSON-LD graphs
and suggesting enhancements based on Schema.org vocabulary, SEO best practices,
and Google Rich Results guidelines.
"""

import copy
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import sentry_sdk

from ast_grep_mcp.constants import ConversionFactors, FilePatterns, RegexCaptureGroups, SemanticVolumeDefaults, SEODefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.schema.client import SchemaOrgClient, get_schema_org_client
from ast_grep_mcp.features.schema.enhancement_rules import (
    ENTITY_SUGGESTIONS,
    get_property_example,
    get_property_priority,
    get_rich_results_for_property,
)
from ast_grep_mcp.models.schema_enhancement import (
    EnhancementPriority,
    EntityEnhancement,
    GraphEnhancementResult,
    MissingEntitySuggestion,
    PropertyEnhancement,
)

logger = get_logger("schema_enhancement")

LOW_PRIORITY_SORT_ORDER = 3
MIN_URL_PARTS_FOR_BASE_DOMAIN = 3

ENHANCEMENT_PRIORITY_ORDER = {
    EnhancementPriority.CRITICAL: 0,
    EnhancementPriority.HIGH: 1,
    EnhancementPriority.MEDIUM: 2,
    EnhancementPriority.LOW: LOW_PRIORITY_SORT_ORDER,
}


# =============================================================================
# Graph Loading Functions
# =============================================================================


def _load_graph_from_source(input_source: str, input_type: str) -> List[Dict[str, Any]]:
    """Load and parse JSON-LD graph from file or directory."""
    logger.info("load_graph_from_source", source=input_source, type=input_type)

    input_path = Path(input_source)
    if not input_path.exists():
        raise ValueError(f"Input source does not exist: {input_source}")

    entities: List[Dict[str, Any]] = []

    if input_type == "file":
        entities = _load_entities_from_file(input_path)
    elif input_type == "directory":
        entities = _load_entities_from_directory(input_path)
    else:
        raise ValueError(f"Invalid input_type: {input_type}. Must be 'file' or 'directory'")

    logger.info("load_complete", total_entities=len(entities))
    return entities


def _load_entities_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load entities from a single JSON file."""
    if not file_path.is_file():
        raise ValueError(f"Expected file but got directory: {file_path}")

    logger.debug("parsing_file", path=str(file_path))
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return _extract_entities_from_data(data)


_EXCLUDED_DIRS = frozenset(
    # Extract bare directory names from glob patterns like "**/node_modules/**"
    p.strip("*").strip("/")
    for p in FilePatterns.DEFAULT_EXCLUDE
    if p.startswith("**/") and p.endswith("/**")
) | {"bower_components", ".svn", ".hg", ".tox", ".pytest_cache", ".mypy_cache"}


def _filter_json_files(json_files: List[Path]) -> List[Path]:
    return [f for f in json_files if not any(excluded in f.parts for excluded in _EXCLUDED_DIRS)]


def _load_schema_file(json_file: Path, entities: List[Dict[str, Any]]) -> bool:
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not _is_schema_org_data(data):
            logger.debug("skipping_non_schema_file", file=str(json_file))
            return False
        extracted = _extract_entities_from_data(data)
        entities.extend(extracted)
        logger.debug("parsed_schema_file", file=str(json_file), entities=len(extracted))
        return True
    except json.JSONDecodeError as e:
        logger.debug("json_parse_error", file=str(json_file), error=str(e))
        return False
    except Exception as e:
        logger.debug("file_read_error", file=str(json_file), error=str(e))
        return False


def _load_entities_from_directory(dir_path: Path) -> List[Dict[str, Any]]:
    """Load entities from Schema.org JSON-LD files in a directory."""
    if not dir_path.is_dir():
        raise ValueError(f"Expected directory but got file: {dir_path}")

    logger.debug("scanning_directory", path=str(dir_path))
    json_files = _filter_json_files(list(dir_path.glob("**/*.json")))

    if not json_files:
        logger.warning("no_json_files_found", path=str(dir_path))
        return []

    logger.info("found_json_files_after_filtering", count=len(json_files))
    entities: List[Dict[str, Any]] = []
    schema_files_found = sum(1 for f in json_files if _load_schema_file(f, entities))

    logger.info("directory_scan_complete", total_files=len(json_files), schema_files=schema_files_found, entities_found=len(entities))
    return entities


def _context_is_schema_org(context: Any) -> bool:
    if isinstance(context, str):
        return "schema.org" in context.lower()
    if isinstance(context, list):
        return any("schema.org" in str(c).lower() for c in context)
    return False


def _is_schema_org_data(data: Any) -> bool:
    """Check if data appears to be Schema.org JSON-LD."""
    if isinstance(data, list):
        return any(_is_schema_org_data(item) for item in data[: SemanticVolumeDefaults.TOP_RESULTS_LIMIT])
    if not isinstance(data, dict):
        return False
    if _context_is_schema_org(data.get("@context", "")):
        return True
    return "@graph" in data or "@type" in data


def _is_valid_entity(item: Any) -> bool:
    """Check if item is a valid Schema.org entity (dict with @type)."""
    return isinstance(item, dict) and "@type" in item


def _extract_entities_from_list(items: List[Any]) -> List[Dict[str, Any]]:
    """Extract valid entities from a list."""
    return [item for item in items if _is_valid_entity(item)]


def _extract_entities_from_data(data: Any) -> List[Dict[str, Any]]:
    """Extract entities from parsed JSON-LD data.

    Only returns dict items that have @type (valid Schema.org entities).
    Filters out primitives, lists, and dicts without @type.
    """
    # Handle @graph container
    if isinstance(data, dict) and "@graph" in data:
        graph = data["@graph"]
        if isinstance(graph, list):
            return _extract_entities_from_list(graph)
        if _is_valid_entity(graph):
            return [graph]
        return []

    # Handle single entity
    if _is_valid_entity(data):
        return [data]

    # Handle array of entities
    if isinstance(data, list):
        return _extract_entities_from_list(data)

    return []


# =============================================================================
# Entity Analysis Functions
# =============================================================================


async def _analyze_entity(entity: Dict[str, Any], client: SchemaOrgClient) -> EntityEnhancement:
    """Analyze a single entity and suggest property enhancements.

    Args:
        entity: Entity dictionary from JSON-LD graph
        client: Initialized Schema.org client

    Returns:
        EntityEnhancement with suggested properties and scores
    """
    entity_id = entity.get("@id", "unknown")
    entity_type = _extract_entity_type(entity)

    if not entity_type:
        raise ValueError(f"Entity {entity_id} is missing @type field")

    logger.debug("analyzing_entity", entity_id=entity_id, entity_type=entity_type)

    existing_properties = [key for key in entity.keys() if not key.startswith("@")]
    suggested_properties = await _get_suggested_properties(entity_type, existing_properties, client)

    return EntityEnhancement(
        entity_id=entity_id,
        entity_type=entity_type,
        existing_properties=existing_properties,
        suggested_properties=suggested_properties,
        validation_issues=[],
        seo_score=0.0,
    )


def _extract_entity_type(entity: Dict[str, Any]) -> Optional[str]:
    """Extract the primary entity type from @type field."""
    entity_type_raw = entity.get("@type")
    if not entity_type_raw:
        return None
    if isinstance(entity_type_raw, list):
        first_type = entity_type_raw[0] if entity_type_raw else None
        return str(first_type) if first_type else None
    return str(entity_type_raw)


_NOTABLE_PRIORITIES = {EnhancementPriority.CRITICAL, EnhancementPriority.HIGH, EnhancementPriority.MEDIUM}


async def _get_suggested_properties(entity_type: str, existing_properties: List[str], client: SchemaOrgClient) -> List[PropertyEnhancement]:
    """Get suggested properties for an entity type."""
    try:
        all_properties = await client.get_type_properties(entity_type, include_inherited=True)
    except ValueError:
        logger.warning("type_not_found", entity_type=entity_type)
        all_properties = []

    prop_by_name = {p["name"]: p for p in all_properties}
    missing_names = prop_by_name.keys() - set(existing_properties)

    suggested = [
        e for name in missing_names if (e := _score_property(name, entity_type, prop_by_name[name])).priority in _NOTABLE_PRIORITIES
    ]
    suggested.sort(key=lambda p: ENHANCEMENT_PRIORITY_ORDER[p.priority])
    return suggested


def _score_property(property_name: str, entity_type: str, prop_details: Dict[str, Any]) -> PropertyEnhancement:
    """Score a property's importance and create enhancement suggestion."""
    priority = get_property_priority(entity_type, property_name)
    rich_results = get_rich_results_for_property(property_name)
    google_rich_result = rich_results[0] if rich_results else None

    reason = _build_property_reason(priority, google_rich_result)
    example_value = get_property_example(property_name)
    if example_value is None:
        expected_types = prop_details.get("expectedTypes", [])
        example_value = f"<{expected_types[0]}>" if expected_types else f"<{property_name}>"

    return PropertyEnhancement(
        property_name=property_name,
        expected_types=prop_details.get("expectedTypes", []),
        priority=priority,
        reason=reason,
        example_value=example_value,
        google_rich_result=google_rich_result,
    )


def _build_property_reason(priority: EnhancementPriority, google_rich_result: Optional[str]) -> str:
    """Build human-readable reason for property suggestion."""
    reasons = {
        EnhancementPriority.CRITICAL: (
            f"Critical for {google_rich_result}" if google_rich_result else "Critical for Schema.org compliance"
        ),
        EnhancementPriority.HIGH: (
            f"Strongly recommended for {google_rich_result}" if google_rich_result else "Strongly recommended for SEO"
        ),
        EnhancementPriority.MEDIUM: "Improves discoverability and user experience",
        EnhancementPriority.LOW: "Nice to have for completeness",
    }
    return reasons.get(priority, "")


# =============================================================================
# Reference Validation Functions
# =============================================================================


def _validate_entity_references(entity: Dict[str, Any], all_ids: Set[str]) -> List[str]:
    """Validate that all @id references in an entity exist in the graph."""
    issues: List[str] = []
    entity_id = entity.get("@id", "unknown")
    references = _find_id_references(entity)

    for ref_id, json_path in references:
        if ref_id not in all_ids:
            issues.append(f"Broken reference at {json_path}: @id '{ref_id}' not found in graph")

    if issues:
        logger.warning("validation_issues_found", entity_id=entity_id, issue_count=len(issues))

    return issues


def _find_id_references_dict(obj: Dict[str, Any], path: str) -> List[tuple[str, str]]:
    if "@id" in obj and len(obj) == 1:
        return [(obj["@id"], path)]
    refs: List[tuple[str, str]] = []
    for key, value in obj.items():
        if key != "@id":
            refs.extend(_find_id_references(value, f"{path}.{key}" if path else key))
    return refs


def _find_id_references(obj: Any, path: str = "") -> List[tuple[str, str]]:
    """Find all @id references in a nested structure."""
    if isinstance(obj, dict):
        return _find_id_references_dict(obj, path)
    if isinstance(obj, list):
        refs: List[tuple[str, str]] = []
        for i, item in enumerate(obj):
            refs.extend(_find_id_references(item, f"{path}[{i}]"))
        return refs
    return []


# =============================================================================
# Missing Entity Detection Functions
# =============================================================================


def _eval_condition(condition: str, entity_types: Set[str], type_counts: Dict[str, int]) -> bool:
    if condition.startswith("NOT has:"):
        return condition.replace("NOT has:", "").strip() not in entity_types
    if condition.startswith("has:"):
        return condition.replace("has:", "").strip() in entity_types
    if "count:" in condition and ">" in condition:
        match = re.match(r"count:(\w+)>(\d+)", condition)
        if not match:
            return False
        entity_type = match.group(RegexCaptureGroups.FIRST)
        threshold = int(match.group(RegexCaptureGroups.SECOND))
        return type_counts.get(entity_type, 0) > threshold
    return False


def _parse_suggestion_rule(rule: str, entity_types: Set[str], type_counts: Dict[str, int]) -> bool:
    """Parse and evaluate entity suggestion rules."""
    return all(_eval_condition(c.strip(), entity_types, type_counts) for c in rule.split(" AND "))


def _suggest_missing_entities(existing_entities: List[Dict[str, Any]], _client: SchemaOrgClient) -> List[MissingEntitySuggestion]:
    """Suggest missing entity types based on graph composition."""
    entity_types: Set[str] = set()
    type_counts: Dict[str, int] = {}

    for entity in existing_entities:
        entity_type_value = entity.get("@type")
        if entity_type_value:
            types = entity_type_value if isinstance(entity_type_value, list) else [entity_type_value]
            for etype in types:
                if not isinstance(etype, str):
                    continue
                entity_types.add(etype)
                type_counts[etype] = type_counts.get(etype, 0) + 1

    suggestions: List[MissingEntitySuggestion] = []

    for rule, config in ENTITY_SUGGESTIONS.items():
        if _parse_suggestion_rule(rule, entity_types, type_counts):
            suggestion = MissingEntitySuggestion(
                entity_type=config["suggest"],
                priority=config["priority"],
                reason=config["reason"],
                example=_generate_example_entity(config["suggest"]),
                google_rich_result=config.get("google_rich_result"),
            )
            suggestions.append(suggestion)

    suggestions.sort(key=lambda s: ENHANCEMENT_PRIORITY_ORDER.get(s.priority, SEODefaults.DEFAULT_PRIORITY_ORDER))

    return suggestions


_EXAMPLE_ENTITY_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "FAQPage": {
        "mainEntity": [
            {
                "@type": "Question",
                "name": "What is your most frequently asked question?",
                "acceptedAnswer": {"@type": "Answer", "text": "This is the answer to the question."},
            }
        ]
    },
    "BreadcrumbList": {
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home"},
            {"@type": "ListItem", "position": 2, "name": "Category"},
        ]
    },
    "Review": {
        "reviewRating": {"@type": "Rating", "ratingValue": "5", "bestRating": "5"},
        "author": {"@type": "Person", "name": "Reviewer Name"},
        "reviewBody": "This is an example review.",
        "datePublished": "2025-01-01",
    },
}

_WEBSITE_EXAMPLE_TEMPLATE: Dict[str, Any] = {
    "name": "Example Website",
    "potentialAction": {
        "@type": "SearchAction",
        "query-input": "required name=search_term_string",
    },
}


def _generate_example_entity(entity_type: str, base_url: str = "https://example.com") -> Dict[str, Any]:
    """Generate example JSON-LD structure for an entity type."""
    base_structure: Dict[str, Any] = {"@type": entity_type, "@id": f"{base_url}#{entity_type.lower()}"}
    if entity_type == "WebSite":
        template = {**_WEBSITE_EXAMPLE_TEMPLATE, "url": base_url}
        template["potentialAction"] = {
            **_WEBSITE_EXAMPLE_TEMPLATE["potentialAction"],
            "target": {"@type": "EntryPoint", "urlTemplate": f"{base_url}/search?q={{search_term_string}}"},
        }
    elif entity_type == "BreadcrumbList":
        tmpl = _EXAMPLE_ENTITY_TEMPLATES["BreadcrumbList"]
        items = [
            {**tmpl["itemListElement"][0], "item": base_url},
            {**tmpl["itemListElement"][1], "item": f"{base_url}/category"},
        ]
        template = {"itemListElement": items}
    else:
        template = _EXAMPLE_ENTITY_TEMPLATES.get(
            entity_type, {"name": f"Example {entity_type}", "description": f"Placeholder for {entity_type} entity"}
        )
    base_structure.update(template)
    return base_structure


# =============================================================================
# SEO Scoring Functions
# =============================================================================


def _calculate_entity_seo_score(entity_enhancement: EntityEnhancement) -> float:
    """Calculate SEO completeness score for a single entity."""
    PRIORITY_WEIGHTS = {
        EnhancementPriority.CRITICAL: SEODefaults.ENTITY_PENALTY_CRITICAL,
        EnhancementPriority.HIGH: SEODefaults.ENTITY_PENALTY_HIGH,
        EnhancementPriority.MEDIUM: SEODefaults.ENTITY_PENALTY_MEDIUM,
        EnhancementPriority.LOW: SEODefaults.ENTITY_PENALTY_LOW,
    }

    score = SEODefaults.BASE_SCORE
    for suggestion in entity_enhancement.suggested_properties:
        score += PRIORITY_WEIGHTS.get(suggestion.priority, 0)

    if not entity_enhancement.validation_issues:
        score += SEODefaults.BONUS_INCREMENT

    return max(0.0, min(SEODefaults.BASE_SCORE, score))


def _calculate_overall_seo_score(
    entity_enhancements: List[EntityEnhancement],
    missing_entities: List[MissingEntitySuggestion],
) -> float:
    """Calculate overall SEO completeness score for the entire graph."""
    MISSING_ENTITY_PENALTIES = {
        EnhancementPriority.CRITICAL: SEODefaults.MISSING_PENALTY_CRITICAL,
        EnhancementPriority.HIGH: SEODefaults.MISSING_PENALTY_HIGH,
        EnhancementPriority.MEDIUM: SEODefaults.MISSING_PENALTY_MEDIUM,
        EnhancementPriority.LOW: SEODefaults.MISSING_PENALTY_LOW,
    }

    if entity_enhancements:
        avg_entity_score = sum(e.seo_score for e in entity_enhancements) / len(entity_enhancements)
    else:
        avg_entity_score = SEODefaults.FALLBACK_AVG_ENTITY_SCORE

    overall_score = avg_entity_score
    for missing_entity in missing_entities:
        overall_score += MISSING_ENTITY_PENALTIES.get(missing_entity.priority, 0)

    return max(0.0, min(SEODefaults.BASE_SCORE, overall_score))


def _build_priority_summary(
    entity_enhancements: List[EntityEnhancement],
    missing_entities: List[MissingEntitySuggestion],
) -> Dict[str, int]:
    """Build summary of enhancement suggestions by priority level."""
    priority_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for entity in entity_enhancements:
        for suggestion in entity.suggested_properties:
            priority_counts[suggestion.priority.value] += 1

    for missing_entity in missing_entities:
        priority_counts[missing_entity.priority.value] += 1

    return priority_counts


_VALID_SCHEMA_CONTEXTS = ("https://schema.org", "http://schema.org")


def _validate_context(graph_data: Dict[str, Any]) -> List[str]:
    context = graph_data.get("@context")
    if not context:
        return ["Missing @context - should be 'https://schema.org' or similar"]
    if isinstance(context, str) and not any(context.startswith(v) for v in _VALID_SCHEMA_CONTEXTS):
        return [f"Invalid @context '{context}' - should be 'https://schema.org'"]
    return []


def _validate_graph_root(graph_data: Dict[str, Any]) -> List[str]:
    if "@graph" not in graph_data and "@type" not in graph_data:
        return ["Missing @graph array or single entity with @type"]
    if "@graph" not in graph_data:
        return []
    graph = graph_data["@graph"]
    if not isinstance(graph, list):
        return ["@graph should be an array of entities"]
    if len(graph) == 0:
        return ["Graph contains no entities"]
    return []


def _validate_graph_structure(graph_data: Dict[str, Any]) -> List[str]:
    """Validate the structure of a Schema.org JSON-LD graph."""
    return _validate_context(graph_data) + _validate_graph_root(graph_data)


# =============================================================================
# Output Generation Functions
# =============================================================================


def _apply_property_enhancements(target_entity: Dict[str, Any], enhancement: "EntityEnhancement") -> None:
    for prop in enhancement.suggested_properties:
        if prop.property_name not in target_entity:
            target_entity[prop.property_name] = prop.example_value


def _append_missing_entities(
    graph: List[Dict[str, Any]],
    missing_entities: List[MissingEntitySuggestion],
    base_url: str,
) -> None:
    entity_counter = 1
    for missing in missing_entities:
        new_entity = copy.deepcopy(missing.example)
        if "@id" not in new_entity:
            new_entity["@id"] = f"{base_url}#{missing.entity_type.lower()}-{entity_counter}"
            entity_counter += 1
        graph.append(new_entity)


def _generate_enhanced_graph(
    original_graph: List[Dict[str, Any]],
    entity_enhancements: List[EntityEnhancement],
    missing_entities: List[MissingEntitySuggestion],
    base_url: str = "https://example.com",
) -> Dict[str, Any]:
    """Generate enhanced JSON-LD graph with all suggestions applied."""
    enhanced_graph_array = copy.deepcopy(original_graph)
    entity_map = {e.get("@id"): e for e in enhanced_graph_array}
    for enhancement in entity_enhancements:
        target = entity_map.get(enhancement.entity_id)
        if target is not None:
            _apply_property_enhancements(target, enhancement)
    _append_missing_entities(enhanced_graph_array, missing_entities, base_url)
    return {"@context": "https://schema.org", "@graph": enhanced_graph_array}


def _generate_diff(
    original_graph: List[Dict[str, Any]],
    entity_enhancements: List[EntityEnhancement],
    missing_entities: List[MissingEntitySuggestion],
) -> Dict[str, Any]:
    """Generate diff showing only additions needed to enhance the graph."""
    property_additions: Dict[str, Dict[str, Any]] = {}
    total_properties = 0

    for enhancement in entity_enhancements:
        if enhancement.suggested_properties:
            entity_props = {prop.property_name: prop.example_value for prop in enhancement.suggested_properties}
            property_additions[enhancement.entity_id] = entity_props
            total_properties += len(entity_props)

    new_entities = [copy.deepcopy(m.example) for m in missing_entities]

    return {
        "property_additions": property_additions,
        "new_entities": new_entities,
        "summary": {
            "properties_to_add": total_properties,
            "entities_to_add": len(new_entities),
        },
    }


def _serialize_property(prop: PropertyEnhancement) -> Dict[str, Any]:
    prop_dict = asdict(prop)
    prop_dict["priority"] = prop.priority.value
    return prop_dict


def _serialize_entity(entity: EntityEnhancement) -> Dict[str, Any]:
    return {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "existing_properties": entity.existing_properties,
        "suggested_properties": [_serialize_property(p) for p in entity.suggested_properties],
        "validation_issues": entity.validation_issues,
        "seo_score": entity.seo_score,
    }


def _serialize_missing(missing: MissingEntitySuggestion) -> Dict[str, Any]:
    missing_dict = asdict(missing)
    missing_dict["priority"] = missing.priority.value
    return missing_dict


def _apply_output_mode(output: Dict[str, Any], result: GraphEnhancementResult, output_mode: str) -> None:
    if output_mode == "enhanced" and result.enhanced_graph is not None:
        output["enhanced_graph"] = result.enhanced_graph
        output["original_graph_size"] = len(result.original_graph)
    elif output_mode == "diff" and result.diff is not None:
        output["diff"] = result.diff
        output["original_graph_size"] = len(result.original_graph)


def _format_result_for_output(result: GraphEnhancementResult, output_mode: str) -> Dict[str, Any]:
    """Format GraphEnhancementResult for JSON serialization."""
    output: Dict[str, Any] = {
        "entity_enhancements": [_serialize_entity(e) for e in result.entity_enhancements],
        "missing_entities": [_serialize_missing(m) for m in result.missing_entities],
        "overall_seo_score": result.overall_seo_score,
        "priority_summary": result.priority_summary,
        "execution_time_ms": result.execution_time_ms,
    }
    if result.global_issues:
        output["global_issues"] = result.global_issues
    _apply_output_mode(output, result, output_mode)
    return output


# =============================================================================
# Main Orchestration Function
# =============================================================================


def _empty_graph_result(start_time: float, output_mode: str) -> Dict[str, Any]:
    return _format_result_for_output(
        GraphEnhancementResult(
            original_graph=[],
            entity_enhancements=[],
            missing_entities=[],
            global_issues=["No entities found in input source"],
            overall_seo_score=0.0,
            priority_summary={"critical": 0, "high": 0, "medium": 0, "low": 0},
            execution_time_ms=int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND),
        ),
        output_mode,
    )


async def _analyze_entities(entities: List[Dict[str, Any]], client: SchemaOrgClient) -> List[EntityEnhancement]:
    all_ids: Set[str] = {str(e.get("@id")) for e in entities if e.get("@id")}
    entity_enhancements: List[EntityEnhancement] = []
    for entity in entities:
        try:
            enhancement = await _analyze_entity(entity, client)
            enhancement.validation_issues = _validate_entity_references(entity, all_ids)
            enhancement.seo_score = _calculate_entity_seo_score(enhancement)
            entity_enhancements.append(enhancement)
        except ValueError as e:
            logger.warning("entity_analysis_failed", error=str(e))
    return entity_enhancements


def _build_output_fields(
    entities: List[Dict[str, Any]],
    entity_enhancements: List[EntityEnhancement],
    missing_entities: List[MissingEntitySuggestion],
    output_mode: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    base_url = _extract_base_url(entities)
    if output_mode == "enhanced":
        return _generate_enhanced_graph(entities, entity_enhancements, missing_entities, base_url), None
    if output_mode == "diff":
        return None, _generate_diff(entities, entity_enhancements, missing_entities)
    return None, None


async def _build_graph_result(
    entities: List[Dict[str, Any]],
    client: SchemaOrgClient,
    output_mode: str,
    start_time: float,
) -> GraphEnhancementResult:
    entity_enhancements = await _analyze_entities(entities, client)
    missing_entities = _suggest_missing_entities(entities, client)
    overall_seo_score = _calculate_overall_seo_score(entity_enhancements, missing_entities)
    priority_summary = _build_priority_summary(entity_enhancements, missing_entities)
    enhanced_graph, diff = _build_output_fields(entities, entity_enhancements, missing_entities, output_mode)
    execution_time_ms = int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)
    logger.info(
        "analyze_entity_graph_complete",
        entity_count=len(entity_enhancements),
        missing_count=len(missing_entities),
        seo_score=overall_seo_score,
        execution_time_ms=execution_time_ms,
    )
    return GraphEnhancementResult(
        original_graph=entities,
        entity_enhancements=entity_enhancements,
        missing_entities=missing_entities,
        global_issues=[],
        overall_seo_score=overall_seo_score,
        priority_summary=priority_summary,
        enhanced_graph=enhanced_graph,
        diff=diff,
        execution_time_ms=execution_time_ms,
    )


async def analyze_entity_graph(input_source: str, input_type: str = "file", output_mode: str = "analysis") -> Dict[str, Any]:
    """Analyze existing JSON-LD graph and suggest enhancements."""
    start_time = time.time()
    logger.info("analyze_entity_graph_start", input_source=input_source, input_type=input_type, output_mode=output_mode)

    try:
        entities = _load_graph_from_source(input_source, input_type)
        if not entities:
            return _empty_graph_result(start_time, output_mode)
        client = get_schema_org_client()
        result = await _build_graph_result(entities, client, output_mode, start_time)
        return _format_result_for_output(result, output_mode)

    except Exception as e:
        logger.error("analyze_entity_graph_failed", error=str(e))
        sentry_sdk.capture_exception(e, extras={"input_source": input_source, "input_type": input_type})
        raise


def _extract_base_url(entities: List[Dict[str, Any]]) -> str:
    """Extract base URL from entity @id values."""
    for entity in entities:
        entity_id = entity.get("@id", "")
        if entity_id.startswith("http"):
            # Extract base URL (remove fragment and path after domain)
            parts = entity_id.split("#")[0].split("/")
            if len(parts) >= MIN_URL_PARTS_FOR_BASE_DOMAIN:
                return f"{parts[0]}//{parts[2]}"
    return "https://example.com"
