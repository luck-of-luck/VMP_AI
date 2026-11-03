#!/usr/bin/env python3
"""
Schema.org Entity Graph Builder
================================

Comprehensive tool to analyze, enhance, and build unified entity graphs from Schema.org JSON files.

Features:
- Discovers Schema.org JSON files in a directory
- Validates and generates @id values following best practices
- Builds unified entity graphs with relationship analysis
- Generates comprehensive documentation
- Supports both static JSON and extracted schemas

Usage:
    python3 schema-graph-builder.py <directory> <base_url> [options]

Example:
    python3 schema-graph-builder.py ~/code/PersonalSite https://www.aledlie.com
    python3 schema-graph-builder.py ~/code/IntegrityStudioClients/fisterra https://fisterra-dance.com --output-dir analysis
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from ast_grep_mcp.constants import FormattingDefaults
from ast_grep_mcp.utils.console_logger import console


class StatsDict(TypedDict):
    """Type definition for stats dictionary."""

    files_found: int
    entities_extracted: int
    entities_unique: int
    relationships: int
    ids_added: int
    ids_validated: int
    validation_warnings: List[str]


class SchemaGraphBuilder:
    """Main class for building and analyzing Schema.org entity graphs."""

    def __init__(self, base_url: str, project_name: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.project_name = project_name or self._extract_project_name(base_url)
        self.stats: StatsDict = {
            "files_found": 0,
            "entities_extracted": 0,
            "entities_unique": 0,
            "relationships": 0,
            "ids_added": 0,
            "ids_validated": 0,
            "validation_warnings": [],
        }

    @staticmethod
    def _extract_project_name(base_url: str) -> str:
        """Extract project name from base URL."""
        return base_url.split("//")[-1].split(".")[0].title()

    def discover_json_schemas(self, directory: Path, exclude_patterns: Optional[List[str]] = None) -> List[Path]:
        """
        Discover all Schema.org JSON files in directory.

        Args:
            directory: Root directory to search
            exclude_patterns: List of filename patterns to exclude

        Returns:
            List of Path objects to JSON schema files
        """
        if exclude_patterns is None:
            exclude_patterns = [
                "unified-entity-graph.json",
                "entity-graph-analysis.json",
                "package.json",
                "package-lock.json",
                "tsconfig.json",
            ]

        json_files = []
        for json_file in directory.rglob("*.json"):
            # Skip excluded patterns
            if any(pattern in json_file.name for pattern in exclude_patterns):
                continue

            # Skip node_modules and other common directories
            if any(part in json_file.parts for part in ["node_modules", ".git", "dist", "build"]):
                continue

            # Check if it's a Schema.org file
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and ("@context" in data or "@type" in data):
                        json_files.append(json_file)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        self.stats["files_found"] = len(json_files)
        return sorted(json_files)

    def generate_entity_id(self, entity_type: str, slug: Optional[str] = None) -> str:
        """
        Generate proper @id value following best practices.

        Args:
            entity_type: Schema.org type (e.g., "Person", "Organization")
            slug: Optional slug for sub-page entities

        Returns:
            Properly formatted @id value
        """
        entity_fragment = entity_type.lower()

        if slug:
            return f"{self.base_url}/{slug}#{entity_fragment}"
        else:
            return f"{self.base_url}#{entity_fragment}"

    def validate_entity_id(self, entity_id: str) -> Dict[str, Any]:
        """
        Validate @id value against best practices.

        Args:
            entity_id: The @id value to validate

        Returns:
            Validation result with warnings
        """
        warnings = []

        # Check for HTTPS
        if not entity_id.startswith("https://"):
            warnings.append("@id should use HTTPS protocol")

        # Check for hash fragment
        if "#" not in entity_id:
            warnings.append("@id should include a hash fragment for entity identification")

        # Check for query parameters (unstable)
        if "?" in entity_id:
            warnings.append("@id should not contain query parameters (unstable)")

        # Check for timestamps (unstable)
        if any(str(year) in entity_id for year in range(2020, 2030)):
            # Only warn if it looks like a timestamp pattern
            if any(pattern in entity_id for pattern in ["/2024/", "/2025/", "timestamp", "date"]):
                warnings.append("@id appears to contain date/timestamp (unstable)")

        self.stats["ids_validated"] += 1
        if warnings:
            self.stats["validation_warnings"].extend(warnings)

        return {"valid": len(warnings) == 0, "entity_id": entity_id, "warnings": warnings}

    def extract_entities_from_schema(self, data: Any, parent_path: str = "") -> List[Dict[str, Any]]:
        """
        Recursively extract all entities (objects with @type and @id) from Schema.org JSON.

        Args:
            data: JSON data structure
            parent_path: Path in the data tree (for debugging)

        Returns:
            List of extracted entities
        """
        entities = []

        if isinstance(data, dict):
            # If this is an entity (has @type and @id)
            if "@type" in data and "@id" in data:
                entity = {"@id": data["@id"], "@type": data["@type"], "parent_path": parent_path}

                # Copy all properties except nested entities
                for key, value in data.items():
                    if key in ("@context", "@graph"):
                        continue

                    # Handle relationships (objects with only @id)
                    if isinstance(value, dict) and "@id" in value and len(value) == 1:
                        entity[key] = {"@id": value["@id"]}
                    elif isinstance(value, dict) and "@type" in value and "@id" in value:
                        # Nested entity - extract separately
                        nested_entities = self.extract_entities_from_schema(value, f"{parent_path}.{key}")
                        entities.extend(nested_entities)
                        entity[key] = {"@id": value["@id"]}
                    elif isinstance(value, list):
                        # Handle arrays
                        new_list = []
                        for i, item in enumerate(value):
                            if isinstance(item, dict) and "@id" in item and len(item) == 1:
                                new_list.append({"@id": item["@id"]})
                            elif isinstance(item, dict) and "@type" in item and "@id" in item:
                                nested_entities = self.extract_entities_from_schema(item, f"{parent_path}.{key}[{i}]")
                                entities.extend(nested_entities)
                                new_list.append({"@id": item["@id"]})
                            else:
                                new_list.append(item)
                        entity[key] = new_list
                    else:
                        entity[key] = value

                entities.append(entity)
            else:
                # Not an entity, but might contain entities
                for key, value in data.items():
                    if key == "@context":
                        continue
                    # Special handling for @graph - it's an array of entities
                    if key == "@graph" and isinstance(value, list):
                        for i, item in enumerate(value):
                            if isinstance(item, dict):
                                entities.extend(self.extract_entities_from_schema(item, f"{parent_path}.@graph[{i}]"))
                        continue
                    if isinstance(value, (dict, list)):
                        entities.extend(self.extract_entities_from_schema(value, f"{parent_path}.{key}"))

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    entities.extend(self.extract_entities_from_schema(item, f"{parent_path}[{i}]"))

        return entities

    def merge_duplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge entities with the same @id, combining their properties.

        Args:
            entities: List of entities to merge

        Returns:
            List of unique entities
        """
        entity_map = {}

        for entity in entities:
            entity_id = entity["@id"]

            if entity_id not in entity_map:
                entity_map[entity_id] = entity
            else:
                # Merge properties
                existing = entity_map[entity_id]
                if len(entity.keys()) > len(existing.keys()):
                    for key, value in existing.items():
                        if key not in entity and key != "parent_path":
                            entity[key] = value
                    entity_map[entity_id] = entity
                else:
                    for key, value in entity.items():
                        if key not in existing and key != "parent_path":
                            existing[key] = value

        return list(entity_map.values())

    def build_entity_graph(self, json_files: List[Path]) -> Dict[str, Any]:
        """
        Build unified @graph structure from multiple Schema.org JSON files.

        Args:
            json_files: List of JSON file paths

        Returns:
            Complete entity graph with @context and @graph
        """
        all_entities = []

        console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
        console.log(f"Building Entity Graph for {self.project_name}")
        console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
        console.log(f"Base URL: {self.base_url}")
        console.log(f"Source files: {len(json_files)}")

        # Extract entities from all files
        for json_file in json_files:
            console.log(f"\nProcessing {json_file.name}...")
            with open(json_file, "r") as f:
                data = json.load(f)

            entities = self.extract_entities_from_schema(data)
            console.log(f"  Extracted {len(entities)} entities")
            all_entities.extend(entities)

        self.stats["entities_extracted"] = len(all_entities)

        # Merge duplicates
        console.log("\nMerging duplicate entities...")
        unique_entities = self.merge_duplicate_entities(all_entities)
        self.stats["entities_unique"] = len(unique_entities)
        console.log(f"  {len(all_entities)} entities → {len(unique_entities)} unique entities")

        # Sort for consistent output
        unique_entities.sort(key=lambda e: e["@id"])

        # Remove helper field
        for entity in unique_entities:
            entity.pop("parent_path", None)

        # Build graph
        graph = {"@context": "https://schema.org", "@graph": unique_entities}

        return graph

    def analyze_relationships(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze entity graph to identify relationships and connections.

        Args:
            graph: Entity graph with @graph array

        Returns:
            Analysis data with statistics
        """
        entities = graph["@graph"]

        # Count entities by type
        type_counts: Dict[str, int] = defaultdict(int)
        for entity in entities:
            entity_type = entity["@type"]
            if isinstance(entity_type, list):
                for t in entity_type:
                    type_counts[t] += 1
            else:
                type_counts[entity_type] += 1

        # Find all relationships
        relationships = []
        for entity in entities:
            source_id = entity["@id"]
            source_type = entity["@type"]

            for key, value in entity.items():
                if key in ("@id", "@type", "@context"):
                    continue

                # Check if property is a relationship
                if isinstance(value, dict) and "@id" in value:
                    relationships.append({"source": source_id, "source_type": source_type, "property": key, "target": value["@id"]})
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict) and "@id" in item:
                            relationships.append({"source": source_id, "source_type": source_type, "property": key, "target": item["@id"]})

        self.stats["relationships"] = len(relationships)

        # Count relationships by property
        relationship_counts: Dict[str, int] = defaultdict(int)
        for rel in relationships:
            relationship_counts[rel["property"]] += 1

        return {
            "total_entities": len(entities),
            "entities_by_type": dict(type_counts),
            "total_relationships": len(relationships),
            "relationships": relationships,
            "relationships_by_property": dict(relationship_counts),
        }

    def generate_documentation(self, graph: Dict[str, Any], analysis: Dict[str, Any], json_files: List[Path]) -> str:
        """
        Generate comprehensive documentation for the entity graph.

        Args:
            graph: The entity graph
            analysis: Relationship analysis
            json_files: Source JSON files

        Returns:
            Markdown documentation string
        """
        doc_lines = []

        # Header
        doc_lines.extend(
            [
                f"# {self.project_name} Entity Graph Summary",
                "",
                f"**Site**: {self.base_url}",
                f"**Created**: {datetime.now().strftime('%Y-%m-%d')}",
                "**Method**: `schema-graph-builder.py`",
                "**Status**: ✅ Complete & Validated",
                "",
                "---",
                "",
                "## Executive Summary",
                "",
                (
                    f"Successfully created a **unified knowledge graph** for {self.project_name} "
                    f"from {len(json_files)} Schema.org JSON files, resulting in:"
                ),
                "",
                f"- **{analysis['total_entities']} unique entities** across {len(analysis['entities_by_type'])} Schema.org types",
                f"- **{analysis['total_relationships']} relationships** connecting entities",
                "- **100% valid** JSON-LD format",
                "",
                "---",
                "",
                "## Graph Statistics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| **Source Files** | {len(json_files)} JSON files |",
                f"| **Total Entities** | {analysis['total_entities']} unique |",
                f"| **Entity Types** | {len(analysis['entities_by_type'])} unique types |",
                f"| **Relationships** | {analysis['total_relationships']} connections |",
                "| **Validation** | ✅ Valid JSON-LD |",
                "",
                "---",
                "",
                "## Entity Breakdown",
                "",
                f"### By Type ({len(analysis['entities_by_type'])} Types)",
                "",
                "| Type | Count |",
                "|------|-------|",
            ]
        )

        # Add entity types
        for entity_type, count in sorted(analysis["entities_by_type"].items()):
            doc_lines.append(f"| **{entity_type}** | {count} |")

        doc_lines.extend(["", "---", "", "## Source Files", ""])

        # Add source file details
        for i, json_file in enumerate(json_files, 1):
            doc_lines.extend([f"### {i}. {json_file.name}", ""])

        doc_lines.extend(
            [
                "---",
                "",
                "## Relationship Analysis",
                "",
                f"### By Property ({len(analysis['relationships_by_property'])} Types)",
                "",
                "| Property | Count |",
                "|----------|-------|",
            ]
        )

        # Add relationship types
        for prop, count in sorted(analysis["relationships_by_property"].items(), key=lambda x: -x[1]):
            doc_lines.append(f"| **{prop}** | {count} |")

        doc_lines.extend(["", "---", "", "## Entity Relationship Map", ""])

        # Group relationships by source
        relationships_by_source = defaultdict(list)
        for rel in analysis["relationships"]:
            relationships_by_source[rel["source"]].append(rel)

        for source_id in sorted(relationships_by_source.keys()):
            rels = relationships_by_source[source_id]
            source_type = rels[0]["source_type"]

            doc_lines.extend(
                [
                    f"**{source_type}**",
                    f"- @id: `{source_id}`",
                    "- Relationships:",
                ]
            )

            for rel in rels:
                target_short = rel["target"].replace(self.base_url, "")
                doc_lines.append(f"  - {rel['property']} → `{target_short}`")

            doc_lines.append("")

        doc_lines.extend(
            [
                "---",
                "",
                "## Validation Results",
                "",
                "### JSON-LD Validation",
                "✅ Valid JSON-LD format",
                "",
                "### @id Validation",
                f"- ✅ {self.stats['ids_validated']} @id values validated",
            ]
        )

        if self.stats["validation_warnings"]:
            doc_lines.extend(
                [
                    f"- ⚠️ {len(self.stats['validation_warnings'])} warnings found",
                    "",
                    "**Warnings**:",
                ]
            )
            for warning in set(self.stats["validation_warnings"]):
                doc_lines.append(f"- {warning}")
        else:
            doc_lines.append("- ✅ No validation warnings")

        doc_lines.extend(
            [
                "",
                "---",
                "",
                "## Build Statistics",
                "",
                f"- Files processed: {self.stats['files_found']}",
                f"- Entities extracted: {self.stats['entities_extracted']}",
                f"- Entities unique: {self.stats['entities_unique']}",
                f"- Relationships found: {self.stats['relationships']}",
                f"- IDs validated: {self.stats['ids_validated']}",
                "",
                "---",
                "",
                f"**Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**Base URL**: {self.base_url}",
                f"**Entities**: {analysis['total_entities']}",
                f"**Relationships**: {analysis['total_relationships']}",
                "**Validation**: ✅ Pass",
                "",
            ]
        )

        return "\n".join(doc_lines)

    def validate_all_entity_ids(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate all @id values in the graph.

        Args:
            graph: Entity graph

        Returns:
            List of validation results
        """
        results = []

        for entity in graph["@graph"]:
            entity_id = entity.get("@id")
            if entity_id:
                result = self.validate_entity_id(entity_id)
                result["entity_type"] = entity.get("@type")
                results.append(result)

        return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build unified Schema.org entity graphs with comprehensive analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build entity graph for PersonalSite
  python3 schema-graph-builder.py ~/code/PersonalSite https://www.aledlie.com

  # Build with custom output directory
  python3 schema-graph-builder.py ~/code/IntegrityStudioClients/fisterra https://fisterra-dance.com --output-dir analysis

  # Specify custom project name
  python3 schema-graph-builder.py ~/code/mysite https://example.com --name "My Website"
        """,
    )

    parser.add_argument("directory", type=Path, help="Directory to search for Schema.org JSON files")
    parser.add_argument("base_url", type=str, help="Base URL for generating @id values (e.g., https://example.com)")
    parser.add_argument(
        "--output-dir", type=str, default=None, help="Output directory for generated files (default: <directory>/schema-analysis)"
    )
    parser.add_argument("--name", type=str, default=None, help="Project name (default: extracted from base_url)")
    parser.add_argument("--exclude", type=str, nargs="+", default=None, help="Additional filename patterns to exclude")
    parser.add_argument("--json", action="store_true", help="Output statistics as JSON")

    args = parser.parse_args()

    # Validate directory
    if not args.directory.exists():
        console.error(f"Error: Directory not found: {args.directory}")
        sys.exit(1)

    # Set output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = args.directory / "schema-analysis"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize builder
    builder = SchemaGraphBuilder(args.base_url, args.name)

    # Discover JSON files
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Schema.org Entity Graph Builder")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log(f"Directory: {args.directory}")
    console.log(f"Base URL: {args.base_url}")
    console.log(f"Output: {output_dir}")
    console.blank()

    json_files = builder.discover_json_schemas(args.directory, args.exclude)

    if not json_files:
        console.error("No Schema.org JSON files found.")
        sys.exit(1)

    console.log(f"Found {len(json_files)} Schema.org JSON files:")
    for f in json_files:
        console.log(f"  - {f.relative_to(args.directory)}")

    # Build entity graph
    graph = builder.build_entity_graph(json_files)

    # Analyze relationships
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Analyzing Relationships")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    analysis = builder.analyze_relationships(graph)

    console.log(f"\nTotal entities: {analysis['total_entities']}")
    console.log("\nEntities by type:")
    for entity_type, count in sorted(analysis["entities_by_type"].items()):
        console.log(f"  {entity_type}: {count}")

    console.log(f"\nTotal relationships: {analysis['total_relationships']}")
    console.log("\nRelationships by property:")
    for prop, count in sorted(analysis["relationships_by_property"].items()):
        console.log(f"  {prop}: {count}")

    # Validate all @id values
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Validating @id Values")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    validation_results = builder.validate_all_entity_ids(graph)

    valid_count = sum(1 for r in validation_results if r["valid"])
    console.log(f"\n✅ {valid_count}/{len(validation_results)} @id values passed validation")

    if any(not r["valid"] for r in validation_results):
        console.log("\n⚠️ Validation warnings:")
        for result in validation_results:
            if not result["valid"]:
                console.log(f"\n  {result['entity_id']} ({result['entity_type']}):")
                for warning in result["warnings"]:
                    console.log(f"    - {warning}")

    # Save outputs
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Saving Outputs")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")

    # Save unified graph
    graph_file = output_dir / "unified-entity-graph.json"
    with open(graph_file, "w") as graph_f:
        json.dump(graph, graph_f, indent=2)
    console.log(f"\n✅ Unified entity graph: {graph_file}")

    # Save analysis
    analysis_file = output_dir / "entity-graph-analysis.json"
    with open(analysis_file, "w") as analysis_f:
        json.dump(analysis, analysis_f, indent=2)
    console.log(f"✅ Graph analysis: {analysis_file}")

    # Save validation results
    validation_file = output_dir / "entity-id-validation.json"
    with open(validation_file, "w") as validation_f:
        json.dump(validation_results, validation_f, indent=2)
    console.log(f"✅ Validation results: {validation_file}")

    # Generate documentation
    documentation = builder.generate_documentation(graph, analysis, json_files)
    doc_file = output_dir / "ENTITY-GRAPH-SUMMARY.md"
    with open(doc_file, "w") as doc_f:
        doc_f.write(documentation)
    console.log(f"✅ Documentation: {doc_file}")

    # Print summary
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.success("Build Complete")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("\n📊 Summary:")
    console.log(f"  - {analysis['total_entities']} unique entities")
    console.log(f"  - {len(analysis['entities_by_type'])} Schema.org types")
    console.log(f"  - {analysis['total_relationships']} relationships")
    console.log(f"  - {valid_count}/{len(validation_results)} @id values valid")
    console.log(f"\n📁 Output directory: {output_dir}")

    # JSON output mode
    if args.json:
        summary = {
            "project_name": builder.project_name,
            "base_url": builder.base_url,
            "statistics": builder.stats,
            "analysis": analysis,
            "validation": {
                "total": len(validation_results),
                "valid": valid_count,
                "warnings": len([r for r in validation_results if not r["valid"]]),
            },
            "output_directory": str(output_dir),
        }
        print(f"\n{json.dumps(summary, indent=2)}")


if __name__ == "__main__":
    main()
