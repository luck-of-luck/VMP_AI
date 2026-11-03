# schema

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "schema",
  "description": "Directory containing 6 code files with 1 classes and 75 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "1 class definitions",
    "75 function definitions"
  ]
}
</script>

## Overview

This directory contains 6 code file(s) with extracted schemas.

## Files and Schemas

### `client.py` (python)

**Classes:**
- `SchemaOrgClient` - Line 23
  - Client for fetching and querying Schema.org vocabulary.
  - Methods: __init__, _index_item, _validate_and_index_data, _normalize_to_array, _extract_super_types (+22 more)

**Functions:**
- `get_schema_org_client() -> <ast.Constant object at 0x106365190>` - Line 15

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `httpx`, `sentry_sdk`, `typing`

### `enhancement_rules.py` (python)

**Functions:**
- `get_property_priority(entity_type, property_name) -> EnhancementPriority` - Line 204
- `get_rich_results_for_property(property_name) -> List[...]` - Line 221
- `get_rich_results_for_entity(entity_type) -> List[...]` - Line 233
- `get_all_properties_for_entity(entity_type) -> Dict[...]` - Line 245
- `get_property_example(property_name) -> Any` - Line 257
- `get_entity_suggestions() -> Dict[...]` - Line 269

**Key Imports:** `ast_grep_mcp.models.schema_enhancement`, `typing`

### `enhancement_service.py` (python)

**Functions:**
- `_load_graph_from_source(input_source, input_type) -> List[...]` - Line 53
- `_load_entities_from_file(file_path) -> List[...]` - Line 74
- `_filter_json_files(json_files) -> List[...]` - Line 94
- `_load_schema_file(json_file, entities) -> bool` - Line 98
- `_load_entities_from_directory(dir_path) -> List[...]` - Line 117
- `_context_is_schema_org(context) -> bool` - Line 137
- `_is_schema_org_data(data) -> bool` - Line 145
- `_is_valid_entity(item) -> bool` - Line 156
- `_extract_entities_from_list(items) -> List[...]` - Line 161
- `_extract_entities_from_data(data) -> List[...]` - Line 166
- ... and 28 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.schema.client`, `ast_grep_mcp.features.schema.enhancement_rules`, `ast_grep_mcp.models.schema_enhancement` (+8 more)

### `html_service.py` (python)

**Functions:**
- `_match_globs(file_path, project_folder, globs) -> bool` - Line 115
- `_run_rule(project_folder, yaml_rule, file_globs) -> List[...]` - Line 121
- `_has_liquid_tags(content) -> bool` - Line 141
- `_parse_jsonld_text(text) -> Optional[...]` - Line 146
- `_find_html_files(project_folder, globs) -> List[...]` - Line 155
- `_extract_jsonld_with_regex(file_path) -> List[...]` - Line 171
- `_extract_microdata_with_regex(file_path) -> List[...]` - Line 201
- `_extract_rdfa_with_regex(file_path) -> List[...]` - Line 224
- `detect_jsonld_in_html(project_folder, file_globs) -> Dict[...]` - Line 248
- `detect_microdata_in_html(project_folder, file_globs) -> Dict[...]` - Line 312
- ... and 2 more functions

**Key Imports:** `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.search.service`, `fnmatch`, `json`, `os` (+2 more)

### `markdown_service.py` (python)

**Functions:**
- `_extract_frontmatter(content) -> Optional[...]` - Line 69
- `_get_nested(data, dotted_path) -> Any` - Line 81
- `_find_schema_fields(frontmatter) -> Dict[...]` - Line 92
- `_collect_md_files(project_folder, file_globs) -> List[...]` - Line 108
- `extract_schema_from_frontmatter(project_folder, file_globs) -> Dict[...]` - Line 120
- `validate_frontmatter_schema(project_folder, file_globs) -> Dict[...]` - Line 172
- `suggest_frontmatter_enhancements(project_folder, file_globs) -> Dict[...]` - Line 233

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `pathlib`, `re`, `typing` (+1 more)

### `tools.py` (python)

**Functions:**
- `generate_entity_id_tool(base_url, entity_type, entity_slug) -> str` - Line 172
- `validate_entity_id_tool(entity_id) -> Dict[...]` - Line 208
- `_reg_get_search(mcp) -> <ast.Constant object at 0x10802fd00>` - Line 301
- `_reg_hierarchy_properties(mcp) -> <ast.Constant object at 0x10802fbb0>` - Line 318
- `_reg_example_entity_id(mcp) -> <ast.Constant object at 0x107f364f0>` - Line 333
- `_reg_validate_build(mcp) -> <ast.Constant object at 0x107f36730>` - Line 356
- `detect_structured_data_tool(project_folder, file_globs, formats) -> Dict[...]` - Line 373
- `validate_structured_data_tool(project_folder, file_globs) -> Dict[...]` - Line 415
- `_reg_enhance(mcp) -> <ast.Constant object at 0x1080462e0>` - Line 459
- `_reg_structured_data(mcp) -> <ast.Constant object at 0x107f88d90>` - Line 475
- ... and 1 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.schema.client`, `ast_grep_mcp.features.schema.enhancement_service`, `ast_grep_mcp.features.schema.html_service` (+6 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*