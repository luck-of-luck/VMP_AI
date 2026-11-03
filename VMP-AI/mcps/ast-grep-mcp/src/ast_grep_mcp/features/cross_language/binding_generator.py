"""API binding generation implementation.

This module provides functionality to generate API client bindings
for multiple programming languages from API specifications.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

from ast_grep_mcp.constants import ConversionFactors
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.cross_language import (
    BINDING_LANGUAGES,
    ApiEndpoint,
    BindingGenerationResult,
    BindingStyle,
    GeneratedBinding,
)

logger = get_logger(__name__)


# =============================================================================
# Type Mappings
# =============================================================================

OPENAPI_TO_PYTHON = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "List",
    "object": "Dict[str, Any]",
}

OPENAPI_TO_TYPESCRIPT = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "array": "Array<unknown>",
    "object": "Record<string, unknown>",
}


# =============================================================================
# Name Converters
# =============================================================================


def _to_camel_case(name: str) -> str:
    """Convert snake_case or kebab-case to camelCase."""
    parts = re.split(r"[-_]", name)
    return parts[0].lower() + "".join(word.capitalize() for word in parts[1:])


def _to_pascal_case(name: str) -> str:
    """Convert snake_case or kebab-case to PascalCase."""
    parts = re.split(r"[-_]", name)
    return "".join(word.capitalize() for word in parts)


# =============================================================================
# OpenAPI Parsing Helpers
# =============================================================================


def _parse_parameter(param: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a single OpenAPI parameter."""
    return {
        "name": param.get("name", ""),
        "in": param.get("in", "query"),
        "type": param.get("schema", {}).get("type", "string"),
        "required": param.get("required", False),
        "description": param.get("description", ""),
    }


def _parse_request_body(operation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse request body from operation."""
    if "requestBody" not in operation:
        return None
    content = operation["requestBody"].get("content", {})
    if "application/json" in content:
        return cast(Dict[str, Any], content["application/json"].get("schema", {}))
    return None


def _parse_responses(operation: Dict[str, Any]) -> Dict[str, Any]:
    """Parse responses from operation."""
    responses = {}
    for status, response in operation.get("responses", {}).items():
        content = response.get("content", {})
        schema = content.get("application/json", {}).get("schema") if "application/json" in content else None
        responses[status] = {
            "description": response.get("description", ""),
            "schema": schema,
        }
    return responses


def _parse_operation(path: str, method: str, operation: Dict[str, Any]) -> Optional[ApiEndpoint]:
    """Parse a single API operation into an endpoint."""
    if method.lower() not in ["get", "post", "put", "delete", "patch"]:
        return None
    if not isinstance(operation, dict):
        return None

    parameters = [_parse_parameter(p) for p in operation.get("parameters", [])]

    return ApiEndpoint(
        path=path,
        method=method.upper(),
        operation_id=operation.get("operationId", f"{method}_{path.replace('/', '_')}"),
        summary=operation.get("summary", ""),
        description=operation.get("description", ""),
        parameters=parameters,
        request_body=_parse_request_body(operation),
        responses=_parse_responses(operation),
        tags=operation.get("tags", []),
    )


def _parse_openapi_spec(spec: Dict[str, Any]) -> Tuple[str, str, str, List[ApiEndpoint]]:
    """Parse an OpenAPI specification."""
    info = spec.get("info", {})
    api_name = info.get("title", "API")
    version = info.get("version", "1.0.0")

    servers = spec.get("servers", [])
    base_url = servers[0].get("url", "") if servers else ""

    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            endpoint = _parse_operation(path, method, operation)
            if endpoint:
                endpoints.append(endpoint)

    return api_name, version, base_url, endpoints


def _load_api_spec(file_path: str) -> Tuple[str, str, str, List[ApiEndpoint]]:
    """Load and parse an API specification file."""
    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"API spec file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    spec = _parse_spec_content(content, path.suffix)

    if "openapi" in spec or "swagger" in spec:
        return _parse_openapi_spec(spec)
    raise ValueError("Unsupported API specification format")


def _parse_spec_content(content: str, suffix: str) -> Dict[str, Any]:
    """Parse spec content based on file extension."""
    if suffix == ".json":
        return cast(Dict[str, Any], json.loads(content))
    if suffix in [".yaml", ".yml"]:
        try:
            import yaml

            return cast(Dict[str, Any], yaml.safe_load(content))
        except ImportError:
            raise ValueError("PyYAML is required to parse YAML files")
    # Try JSON as fallback
    try:
        return cast(Dict[str, Any], json.loads(content))
    except json.JSONDecodeError:
        raise ValueError(f"Unsupported API spec format: {suffix}")


# =============================================================================
# Parameter Processing Helpers
# =============================================================================


def _classify_parameters(
    parameters: List[Dict[str, Any]],
    type_converter: Callable[[str], str],
) -> Tuple[List[Tuple[str, str, bool]], List[str], List[Tuple[str, str]]]:
    """Classify parameters into params list, path params, and query params.

    Returns:
        Tuple of (param_strings, path_params, query_params)
    """
    params = []
    path_params = []
    query_params = []

    for param in parameters:
        param_name = _to_camel_case(param["name"])
        param_type = type_converter(param.get("type", "string"))

        if param.get("required"):
            params.append((param_name, param_type, True))
        else:
            params.append((param_name, param_type, False))

        if param.get("in") == "path":
            path_params.append(param["name"])
        elif param.get("in") == "query":
            query_params.append((param["name"], param_name))

    return params, path_params, query_params


# =============================================================================
# Python Binding Generator
# =============================================================================


def _python_param_string(params: List[Tuple[str, str, bool]], has_body: bool) -> str:
    """Build Python parameter string."""
    param_strs = ["self"]
    for name, type_str, required in params:
        if required:
            param_strs.append(f"{name}: {type_str}")
        else:
            param_strs.append(f"{name}: Optional[{type_str}] = None")
    if has_body:
        param_strs.append("body: Dict[str, Any]")
    return ", ".join(param_strs)


def _python_method_body(
    endpoint: ApiEndpoint,
    path_params: List[str],
    query_params: List[Tuple[str, str]],
) -> List[str]:
    """Generate Python method body lines."""
    lines = []

    # Build URL with path params
    path = endpoint.path
    for pp in path_params:
        path = path.replace("{" + pp + "}", "{" + _to_camel_case(pp) + "}")
    lines.append(f'        url = f"{{self.base_url}}{path}"')

    # Query params
    if query_params:
        lines.append("        params = {}")
        for orig_name, camel_name in query_params:
            lines.append(f"        if {camel_name} is not None:")
            lines.append(f'            params["{orig_name}"] = {camel_name}')

    # Request call
    method_lower = endpoint.method.lower()
    args = ["url"]
    if endpoint.request_body:
        args.append("json=body")
    if query_params:
        args.append("params=params")

    lines.append(f"        response = self.session.{method_lower}({', '.join(args)})")
    lines.extend(
        [
            "        response.raise_for_status()",
            "        return response.json()",
        ]
    )
    return lines


def _python_type_converter(t: str) -> str:
    return OPENAPI_TO_PYTHON.get(t, "Any")


def _python_endpoint_lines(endpoint: ApiEndpoint) -> List[str]:
    """Generate lines for a single Python endpoint method."""
    method_name = _to_camel_case(endpoint.operation_id)
    params, path_params, query_params = _classify_parameters(endpoint.parameters, _python_type_converter)
    params_str = _python_param_string(params, bool(endpoint.request_body))
    lines = [
        f"    def {method_name}({params_str}) -> Dict[str, Any]:",
        '        """',
        f"        {endpoint.summary or endpoint.description or endpoint.operation_id}",
        "",
        f"        {endpoint.method} {endpoint.path}",
        '        """',
    ]
    lines.extend(_python_method_body(endpoint, path_params, query_params))
    lines.append("")
    return lines


def _generate_python_binding(
    api_name: str,
    base_url: str,
    endpoints: List[ApiEndpoint],
    style: BindingStyle,
) -> GeneratedBinding:
    """Generate Python API client binding."""
    lines = [
        '"""',
        f"Auto-generated API client for {api_name}",
        '"""',
        "from typing import Any, Dict, List, Optional",
        "",
        "import requests",
        "",
        "",
        f"class {_to_pascal_case(api_name)}Client:",
        f'    """Client for {api_name} API."""',
        "",
        "    def __init__(self, base_url: str = None, api_key: str = None):",
        f'        self.base_url = base_url or "{base_url}"',
        "        self.api_key = api_key",
        "        self.session = requests.Session()",
        "        if api_key:",
        '            self.session.headers["Authorization"] = f"Bearer {api_key}"',
        "",
    ]

    types_generated = [_to_camel_case(ep.operation_id) for ep in endpoints]
    for endpoint in endpoints:
        lines.extend(_python_endpoint_lines(endpoint))

    return GeneratedBinding(
        language="python",
        file_name=f"{_to_camel_case(api_name)}_client.py",
        code="\n".join(lines),
        imports=["requests"],
        dependencies=["requests>=2.28.0"],
        types_generated=types_generated,
    )


# =============================================================================
# TypeScript Binding Generator
# =============================================================================


def _ts_param_string(params: List[Tuple[str, str, bool]], has_body: bool) -> str:
    """Build TypeScript parameter string."""
    param_strs = []
    for name, type_str, required in params:
        optional = "" if required else "?"
        param_strs.append(f"{name}{optional}: {type_str}")
    if has_body:
        param_strs.append("body: Record<string, unknown>")
    return ", ".join(param_strs)


def _ts_method_body(
    endpoint: ApiEndpoint,
    path_params: List[Tuple[str, str]],
    query_params: List[Tuple[str, str]],
) -> List[str]:
    """Generate TypeScript method body lines."""
    lines = []

    # Build path
    path = endpoint.path
    if path_params:
        for orig_name, camel_name in path_params:
            path = path.replace("{" + orig_name + "}", "${" + camel_name + "}")
        lines.append(f"    const path = `{path}`;")
    else:
        lines.append(f'    const path = "{path}";')

    # Query string
    url_expr = "${path}"
    if query_params:
        lines.append("    const params = new URLSearchParams();")
        for orig_name, camel_name in query_params:
            lines.append(f"    if ({camel_name} !== undefined) params.append('{orig_name}', String({camel_name}));")
        lines.append('    const queryString = params.toString() ? `?${params.toString()}` : "";')
        url_expr = "${path}${queryString}"

    # Request
    if endpoint.request_body:
        lines.append(f"    return this.request('{endpoint.method}', `{url_expr}`, {{ body: JSON.stringify(body) }});")
    else:
        lines.append(f"    return this.request('{endpoint.method}', `{url_expr}`);")

    return lines


def _ts_type_converter(t: str) -> str:
    return OPENAPI_TO_TYPESCRIPT.get(t, "unknown")


def _ts_endpoint_lines(endpoint: ApiEndpoint) -> List[str]:
    """Generate lines for a single TypeScript endpoint method."""
    method_name = _to_camel_case(endpoint.operation_id)
    params, path_params_raw, query_params = _classify_parameters(endpoint.parameters, _ts_type_converter)
    path_params = [(p, _to_camel_case(p)) for p in path_params_raw]
    params_str = _ts_param_string(params, bool(endpoint.request_body))
    lines = [
        "  /**",
        f"   * {endpoint.summary or endpoint.description or endpoint.operation_id}",
        f"   * {endpoint.method} {endpoint.path}",
        "   */",
        f"  async {method_name}({params_str}): Promise<unknown> {{",
    ]
    lines.extend(_ts_method_body(endpoint, path_params, query_params))
    lines.extend(["  }", ""])
    return lines


def _ts_class_header(api_name: str, base_url: str) -> List[str]:
    """Return the TypeScript class boilerplate header lines."""
    class_name = _to_pascal_case(api_name) + "Client"
    return [
        "/**",
        f" * Auto-generated API client for {api_name}",
        " */",
        "",
        "interface ApiClientOptions {",
        "  baseUrl?: string;",
        "  apiKey?: string;",
        "}",
        "",
        f"export class {class_name} {{",
        "  private baseUrl: string;",
        "  private apiKey?: string;",
        "",
        "  constructor(options: ApiClientOptions = {}) {",
        f'    this.baseUrl = options.baseUrl || "{base_url}";',
        "    this.apiKey = options.apiKey;",
        "  }",
        "",
        "  private async request<T>(method: string, path: string, options: RequestInit = {}): Promise<T> {",
        "    const headers: Record<string, string> = { 'Content-Type': 'application/json' };",
        "    if (this.apiKey) headers['Authorization'] = `Bearer ${this.apiKey}`;",
        "",
        "    const response = await fetch(`${this.baseUrl}${path}`, {",
        "      ...options, method, headers: { ...headers, ...options.headers },",
        "    });",
        "",
        "    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);",
        "    return response.json();",
        "  }",
        "",
    ]


def _generate_typescript_binding(
    api_name: str,
    base_url: str,
    endpoints: List[ApiEndpoint],
    style: BindingStyle,
) -> GeneratedBinding:
    """Generate TypeScript API client binding."""
    lines = _ts_class_header(api_name, base_url)
    types_generated = [_to_camel_case(ep.operation_id) for ep in endpoints]
    for endpoint in endpoints:
        lines.extend(_ts_endpoint_lines(endpoint))
    lines.append("}")

    return GeneratedBinding(
        language="typescript",
        file_name=f"{_to_camel_case(api_name)}Client.ts",
        code="\n".join(lines),
        imports=[],
        dependencies=[],
        types_generated=types_generated,
    )


# =============================================================================
# JavaScript Binding Generator
# =============================================================================


def _js_param_string(params: List[Tuple[str, str, bool]], has_body: bool) -> str:
    """Build JavaScript parameter string (no types)."""
    names = [name for name, _, _ in params]
    if has_body:
        names.append("body")
    return ", ".join(names)


def _js_type_converter(t: str) -> str:
    return t


def _js_endpoint_lines(endpoint: ApiEndpoint) -> List[str]:
    """Generate lines for a single JavaScript endpoint method."""
    method_name = _to_camel_case(endpoint.operation_id)
    params, path_params_raw, query_params = _classify_parameters(endpoint.parameters, _js_type_converter)
    path_params = [(p, _to_camel_case(p)) for p in path_params_raw]
    params_str = _js_param_string(params, bool(endpoint.request_body))
    lines = [
        "  /**",
        f"   * {endpoint.summary or endpoint.description or endpoint.operation_id}",
        f"   * {endpoint.method} {endpoint.path}",
        "   */",
        f"  async {method_name}({params_str}) {{",
    ]
    lines.extend(_ts_method_body(endpoint, path_params, query_params))
    lines.extend(["  }", ""])
    return lines


def _generate_javascript_binding(
    api_name: str,
    base_url: str,
    endpoints: List[ApiEndpoint],
    style: BindingStyle,
) -> GeneratedBinding:
    """Generate JavaScript API client binding."""
    class_name = _to_pascal_case(api_name) + "Client"

    lines = [
        "/**",
        f" * Auto-generated API client for {api_name}",
        " */",
        "",
        f"class {class_name} {{",
        "  constructor(options = {}) {",
        f'    this.baseUrl = options.baseUrl || "{base_url}";',
        "    this.apiKey = options.apiKey;",
        "  }",
        "",
        "  async request(method, path, options = {}) {",
        "    const headers = { 'Content-Type': 'application/json' };",
        "    if (this.apiKey) headers['Authorization'] = `Bearer ${this.apiKey}`;",
        "",
        "    const response = await fetch(`${this.baseUrl}${path}`, {",
        "      ...options, method, headers: { ...headers, ...options.headers },",
        "    });",
        "",
        "    if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);",
        "    return response.json();",
        "  }",
        "",
    ]

    types_generated = [_to_camel_case(ep.operation_id) for ep in endpoints]
    for endpoint in endpoints:
        lines.extend(_js_endpoint_lines(endpoint))
    lines.extend(["}", "", f"module.exports = {{ {class_name} }};"])

    return GeneratedBinding(
        language="javascript",
        file_name=f"{_to_camel_case(api_name)}Client.js",
        code="\n".join(lines),
        imports=[],
        dependencies=[],
        types_generated=types_generated,
    )


# =============================================================================
# Main Implementation
# =============================================================================

GENERATORS = {
    "python": _generate_python_binding,
    "typescript": _generate_typescript_binding,
    "javascript": _generate_javascript_binding,
}


def generate_language_bindings_impl(
    api_definition_file: str,
    target_languages: Optional[List[str]] = None,
    binding_style: str = "native",
    include_types: bool = True,
) -> BindingGenerationResult:
    """Generate API client bindings for multiple languages."""
    start_time = time.time()

    if not target_languages:
        target_languages = ["python", "typescript", "javascript"]

    target_languages = [lang for lang in target_languages if lang in BINDING_LANGUAGES]

    if not target_languages:
        raise ValueError(f"No supported languages specified. Supported: {BINDING_LANGUAGES}")

    style = BindingStyle(binding_style)
    api_name, version, base_url, endpoints = _load_api_spec(api_definition_file)

    logger.info("api_spec_parsed", api_name=api_name, version=version, endpoints_count=len(endpoints))

    bindings = []
    warnings = []

    for lang in target_languages:
        generator = GENERATORS.get(lang)
        if not generator:
            warnings.append(f"No generator available for {lang}")
            continue
        try:
            bindings.append(generator(api_name, base_url, endpoints, style))
        except Exception as e:
            warnings.append(f"Failed to generate {lang} binding: {str(e)[:100]}")
            logger.warning("binding_generation_failed", language=lang, error=str(e)[:100])

    return BindingGenerationResult(
        api_name=api_name,
        api_version=version,
        base_url=base_url,
        endpoints_count=len(endpoints),
        bindings=bindings,
        warnings=warnings,
        execution_time_ms=int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND),
    )
