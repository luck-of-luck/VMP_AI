"""README generation service.

This module provides functionality for auto-generating README.md sections
from code structure analysis.
"""

import json
import os
import re
import time
from typing import Dict, List, Optional, Tuple, cast

import sentry_sdk

from ast_grep_mcp.constants import ConversionFactors, FilePatterns, ReadmeDefaults, ReadmeSectionOrder
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.documentation import (
    ProjectInfo,
    ReadmeGenerationResult,
    ReadmeSection,
)

logger = get_logger(__name__)


# =============================================================================
# Project Analyzers
# =============================================================================


def _parse_json_metadata(file_path: str) -> Tuple[str, str]:
    """Parse name and version from JSON file."""
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return data.get("name", ""), data.get("version", "")
    except (json.JSONDecodeError, OSError):
        return "", ""


def _parse_toml_metadata(file_path: str) -> Tuple[str, str]:
    """Parse name and version from TOML-like file."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
        version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        return (name_match.group(1) if name_match else "", version_match.group(1) if version_match else "")
    except OSError:
        return "", ""


def _parse_go_mod(file_path: str) -> Tuple[str, str]:
    """Parse module name from go.mod."""
    try:
        with open(file_path, "r") as f:
            content = f.read()
        module_match = re.search(r"module\s+(\S+)", content)
        return module_match.group(1) if module_match else "", ""
    except OSError:
        return "", ""


def _detect_js_package_manager(project_folder: str) -> str:
    """Detect JavaScript package manager from lock files."""
    if os.path.exists(os.path.join(project_folder, "yarn.lock")):
        return "yarn"
    if os.path.exists(os.path.join(project_folder, "pnpm-lock.yaml")):
        return "pnpm"
    return "npm"


def _detect_python_package_manager(project_folder: str) -> str:
    """Detect Python package manager from lock files."""
    if os.path.exists(os.path.join(project_folder, "uv.lock")):
        return "uv"
    if os.path.exists(os.path.join(project_folder, "poetry.lock")):
        return "poetry"
    return "pip"


def _detect_package_manager(project_folder: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Detect package manager and project metadata.

    Args:
        project_folder: Project root

    Returns:
        Tuple of (package_manager, project_name, version)
    """
    j = os.path.join(project_folder, "package.json")
    if os.path.exists(j):
        name, version = _parse_json_metadata(j)
        return _detect_js_package_manager(project_folder), name, version

    pyproject = os.path.join(project_folder, "pyproject.toml")
    if os.path.exists(pyproject):
        name, version = _parse_toml_metadata(pyproject)
        return _detect_python_package_manager(project_folder), name, version

    setup_py = os.path.join(project_folder, "setup.py")
    if os.path.exists(setup_py):
        name, version = _parse_toml_metadata(setup_py)
        return "pip", name, version

    if os.path.exists(os.path.join(project_folder, "requirements.txt")):
        return "pip", "", ""

    cargo = os.path.join(project_folder, "Cargo.toml")
    if os.path.exists(cargo):
        name, version = _parse_toml_metadata(cargo)
        return "cargo", name, version

    go_mod = os.path.join(project_folder, "go.mod")
    if os.path.exists(go_mod):
        name, _ = _parse_go_mod(go_mod)
        return "go", name, ""

    return None, "", ""


_EXT_TO_LANG = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".swift": "swift",
    ".kt": "kotlin",
}


def _count_extensions(project_folder: str) -> Dict[str, int]:
    extensions: Dict[str, int] = {}
    for root, _, files in os.walk(project_folder):
        if any(skip in root for skip in FilePatterns.SKIP_DIR_NAMES):
            continue
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            extensions[ext] = extensions.get(ext, 0) + 1
    return extensions


def _detect_language(project_folder: str) -> str:
    """Detect primary programming language.

    Args:
        project_folder: Project root

    Returns:
        Primary language string
    """
    extensions = _count_extensions(project_folder)
    lang_counts: Dict[str, int] = {}
    for ext, count in extensions.items():
        lang = _EXT_TO_LANG.get(ext)
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + count
    return max(lang_counts, key=lambda k: lang_counts[k]) if lang_counts else "unknown"


# JS framework detection: (dep_key, framework_name)
_JS_FRAMEWORKS: List[Tuple[str, str]] = [
    ("react", "React"),
    ("next", "Next.js"),
    ("vue", "Vue.js"),
    ("angular", "Angular"),
    ("@angular/core", "Angular"),
    ("express", "Express"),
    ("fastify", "Fastify"),
    ("nestjs", "NestJS"),
    ("@nestjs/core", "NestJS"),
    ("electron", "Electron"),
]

# Python framework detection: (pattern, framework_name)
_PYTHON_FRAMEWORKS: List[Tuple[str, str]] = [
    ("django", "Django"),
    ("flask", "Flask"),
    ("fastapi", "FastAPI"),
    ("pytest", "pytest"),
    ("sqlalchemy", "SQLAlchemy"),
    ("pydantic", "Pydantic"),
]


def _detect_js_frameworks(project_folder: str) -> List[str]:
    """Detect JavaScript frameworks from package.json.

    Args:
        project_folder: Project root

    Returns:
        List of detected framework names
    """
    package_json = os.path.join(project_folder, "package.json")
    if not os.path.exists(package_json):
        return []

    try:
        with open(package_json, "r") as f:
            data = json.load(f)
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    except (json.JSONDecodeError, OSError):
        return []

    frameworks = []
    seen = set()  # Avoid duplicates like Angular appearing twice
    for dep_key, framework_name in _JS_FRAMEWORKS:
        if dep_key in deps and framework_name not in seen:
            frameworks.append(framework_name)
            seen.add(framework_name)
    return frameworks


def _read_file_lower(filepath: str) -> str:
    try:
        with open(filepath, "r") as f:
            return f.read().lower()
    except OSError:
        return ""


def _get_python_deps_content(project_folder: str) -> str:
    """Read Python dependency files content.

    Args:
        project_folder: Project root

    Returns:
        Combined lowercase content of dependency files
    """
    files = ["requirements.txt", "pyproject.toml"]
    parts = []
    for filename in files:
        filepath = os.path.join(project_folder, filename)
        if os.path.exists(filepath):
            parts.append(_read_file_lower(filepath))
    return "".join(parts)


def _detect_python_frameworks(project_folder: str) -> List[str]:
    """Detect Python frameworks from requirements.txt and pyproject.toml.

    Args:
        project_folder: Project root

    Returns:
        List of detected framework names
    """
    deps_content = _get_python_deps_content(project_folder)
    if not deps_content:
        return []

    return [name for pattern, name in _PYTHON_FRAMEWORKS if pattern in deps_content]


def _detect_frameworks(project_folder: str, language: str) -> List[str]:
    """Detect frameworks used in the project.

    Args:
        project_folder: Project root
        language: Primary language

    Returns:
        List of detected frameworks
    """
    frameworks = _detect_js_frameworks(project_folder)
    frameworks.extend(_detect_python_frameworks(project_folder))
    return frameworks


def _find_entry_points(project_folder: str, language: str) -> List[str]:
    """Find main entry point files.

    Args:
        project_folder: Project root
        language: Primary language

    Returns:
        List of entry point file paths
    """
    entry_points = []

    # Common entry point names
    common_names = {
        "python": ["main.py", "app.py", "__main__.py", "cli.py", "run.py"],
        "typescript": ["index.ts", "main.ts", "app.ts", "server.ts"],
        "javascript": ["index.js", "main.js", "app.js", "server.js"],
        "java": ["Main.java", "App.java", "Application.java"],
        "rust": ["main.rs", "lib.rs"],
        "go": ["main.go", "cmd/main.go"],
    }

    candidates = common_names.get(language, [])

    for candidate in candidates:
        full_path = os.path.join(project_folder, candidate)
        if os.path.exists(full_path):
            entry_points.append(candidate)
        # Check in src directory
        src_path = os.path.join(project_folder, "src", candidate)
        if os.path.exists(src_path):
            entry_points.append(os.path.join("src", candidate))

    return entry_points


def _has_tests(project_folder: str) -> bool:
    return any(os.path.exists(os.path.join(project_folder, d)) for d in ("tests", "test", "__tests__", "spec"))


def _has_docs(project_folder: str) -> bool:
    return any(os.path.exists(os.path.join(project_folder, d)) for d in ("docs", "documentation"))


def _analyze_project(project_folder: str, language: str) -> ProjectInfo:
    """Analyze project structure and metadata.

    Args:
        project_folder: Project root
        language: Primary language (can be 'auto')

    Returns:
        ProjectInfo with analyzed data
    """
    if language == "auto" or not language:
        language = _detect_language(project_folder)

    package_manager, name, version = _detect_package_manager(project_folder)
    if not name:
        name = os.path.basename(project_folder)

    return ProjectInfo(
        name=name,
        version=version or None,
        description=_get_project_description(project_folder),
        language=language,
        package_manager=package_manager,
        entry_points=_find_entry_points(project_folder, language),
        frameworks=_detect_frameworks(project_folder, language),
        has_tests=_has_tests(project_folder),
        has_docs=_has_docs(project_folder),
        dependencies=_get_main_dependencies(project_folder, language),
    )


def _description_from_package_json(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
        return cast(str, data["description"]) if data.get("description") else None
    except (json.JSONDecodeError, OSError):
        return None


def _description_from_pyproject(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "r") as f:
            content = f.read()
        m = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
        return m.group(1) if m else None
    except OSError:
        return None


def _get_project_description(project_folder: str) -> Optional[str]:
    """Get project description from package files.

    Args:
        project_folder: Project root

    Returns:
        Description string or None
    """
    package_json = os.path.join(project_folder, "package.json")
    if os.path.exists(package_json):
        desc = _description_from_package_json(package_json)
        if desc:
            return desc

    pyproject = os.path.join(project_folder, "pyproject.toml")
    if os.path.exists(pyproject):
        return _description_from_pyproject(pyproject)

    return None


def _get_js_dependencies(project_folder: str, max_deps: int = ReadmeDefaults.MAX_DEPENDENCIES) -> List[str]:
    """Get JavaScript dependencies from package.json.

    Args:
        project_folder: Project root
        max_deps: Maximum dependencies to return

    Returns:
        List of dependency names
    """
    package_json = os.path.join(project_folder, "package.json")
    if not os.path.exists(package_json):
        return []

    try:
        with open(package_json, "r") as f:
            data = json.load(f)
        deps = data.get("dependencies", {})
        return list(deps.keys())[:max_deps]
    except (json.JSONDecodeError, OSError):
        return []


def _parse_requirement_line(line: str) -> str:
    line = line.strip()
    if not line or line.startswith("#"):
        return ""
    return re.split(r"[<>=!~\[]", line)[0].strip()


def _get_python_dependencies(project_folder: str, max_deps: int = ReadmeDefaults.MAX_DEPENDENCIES) -> List[str]:
    """Get Python dependencies from requirements.txt.

    Args:
        project_folder: Project root
        max_deps: Maximum dependencies to return

    Returns:
        List of dependency names
    """
    requirements = os.path.join(project_folder, "requirements.txt")
    if not os.path.exists(requirements):
        return []

    try:
        with open(requirements, "r") as f:
            lines = f.readlines()
    except OSError:
        return []

    dependencies = []
    for line in lines:
        pkg = _parse_requirement_line(line)
        if pkg:
            dependencies.append(pkg)
        if len(dependencies) >= max_deps:
            break
    return dependencies


def _get_main_dependencies(project_folder: str, language: str) -> List[str]:
    """Get main project dependencies.

    Args:
        project_folder: Project root
        language: Primary language

    Returns:
        List of main dependency names
    """
    dependencies = _get_js_dependencies(project_folder)
    dependencies.extend(_get_python_dependencies(project_folder, max_deps=ReadmeDefaults.MAX_DEPENDENCIES - len(dependencies)))
    return dependencies


# =============================================================================
# Section Generators
# =============================================================================


_PM_INSTALL_COMMANDS = {
    "npm": "npm install {name}",
    "yarn": "yarn add {name}",
    "pnpm": "pnpm add {name}",
    "pip": "pip install {name}",
    "uv": "uv add {name}",
    "poetry": "poetry add {name}",
    "cargo": "cargo add {name}",
    "go": "go get {name}",
}

_PM_SOURCE_COMMANDS = {
    "npm": "npm install",
    "yarn": "yarn install",
    "pnpm": "pnpm install",
    "pip": "uv sync  # or pip install -e .",
    "uv": "uv sync  # or pip install -e .",
    "poetry": "poetry install",
    "cargo": "cargo build --release",
    "go": "go build",
}


def _from_source_lines(name: str, pm: str) -> List[str]:
    lines = [
        "",
        "### From Source",
        "",
        "```bash",
        f"git clone https://github.com/your-username/{name}.git",
        f"cd {name}",
    ]
    src_cmd = _PM_SOURCE_COMMANDS.get(pm)
    if src_cmd:
        lines.append(src_cmd)
    lines.append("```")
    return lines


def _generate_installation_section(info: ProjectInfo) -> ReadmeSection:
    """Generate installation instructions section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with installation content
    """
    lines: List[str] = []

    if info.package_manager:
        tmpl = _PM_INSTALL_COMMANDS.get(info.package_manager, "")
        cmd = tmpl.format(name=info.name) if tmpl else ""
        if cmd:
            lines.extend(["```bash", cmd, "```"])
        else:
            lines.append(f"Install using {info.package_manager}.")
        lines.extend(_from_source_lines(info.name, info.package_manager))
    else:
        lines.extend(
            [
                "Clone the repository and install dependencies:",
                "",
                "```bash",
                f"git clone https://github.com/your-username/{info.name}.git",
                f"cd {info.name}",
                "# Install dependencies",
                "```",
            ]
        )

    return ReadmeSection(
        section_type="installation",
        title="Installation",
        content="\n".join(lines),
        order=ReadmeSectionOrder.INSTALLATION,
    )


def _usage_snippet(name: str, language: str) -> List[str]:
    n = name.replace("-", "_")
    if language == "python":
        return ["```python", f"from {n} import main", "", "# Example usage", "result = main()", "```"]
    if language in ("typescript", "javascript"):
        return ["```javascript", f'import {{ main }} from "{name}";', "", "// Example usage", "const result = main();", "```"]
    if language == "java":
        return ["```java", f"import com.example.{name.replace('-', '')}.Main;", "", "// Example usage", "Main.run();", "```"]
    if language == "rust":
        return ["```rust", f"use {n}::*;", "", "fn main() {", "    // Example usage", "}", "```"]
    if language == "go":
        return ["```go", f'import "{name}"', "", "func main() {", "    // Example usage", "}", "```"]
    return ["See examples below."]


def _cli_snippet(name: str, pm: Optional[str]) -> List[str]:
    if pm in ("npm", "yarn", "pnpm"):
        cmd = f"npx {name} --help"
    elif pm in ("pip", "uv", "poetry"):
        cmd = f"{name.replace('-', '_')} --help"
    else:
        cmd = f"./{name} --help"
    return ["", "### Command Line", "", "```bash", cmd, "```"]


def _generate_usage_section(info: ProjectInfo) -> ReadmeSection:
    """Generate usage examples section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with usage content
    """
    lines = _usage_snippet(info.name, info.language)

    if any("cli" in ep.lower() or "main" in ep.lower() for ep in info.entry_points):
        lines.extend(_cli_snippet(info.name, info.package_manager))

    return ReadmeSection(
        section_type="usage",
        title="Usage",
        content="\n".join(lines),
        order=ReadmeSectionOrder.USAGE,
    )


def _generate_features_section(info: ProjectInfo) -> ReadmeSection:
    """Generate features list section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with features content
    """
    lines = []

    # Generate generic features based on detected frameworks
    if info.frameworks:
        lines.append(f"Built with {', '.join(info.frameworks)}.")
        lines.append("")

    lines.append("- Feature 1: Description")
    lines.append("- Feature 2: Description")
    lines.append("- Feature 3: Description")

    if info.has_tests:
        lines.append("- Comprehensive test suite")

    if info.has_docs:
        lines.append("- Full documentation")

    return ReadmeSection(
        section_type="features",
        title="Features",
        content="\n".join(lines),
        order=ReadmeSectionOrder.FEATURES,
    )


def _generate_api_section(info: ProjectInfo) -> ReadmeSection:
    """Generate API reference section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with API content
    """
    lines = []

    lines.append("### Core Functions")
    lines.append("")
    lines.append("| Function | Description |")
    lines.append("|----------|-------------|")
    lines.append("| `main()` | Main entry point |")
    lines.append("| `configure()` | Configure settings |")
    lines.append("")
    lines.append("See the [full API documentation](docs/api.md) for details.")

    return ReadmeSection(
        section_type="api",
        title="API Reference",
        content="\n".join(lines),
        order=ReadmeSectionOrder.API_REFERENCE,
    )


def _generate_structure_section(info: ProjectInfo) -> ReadmeSection:
    """Generate project structure section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with structure content
    """
    lines = ["```"]

    # Generate basic structure
    lines.append(f"{info.name}/")

    if info.language == "python":
        lines.append("├── src/")
        lines.append(f"│   └── {info.name.replace('-', '_')}/")
        lines.append("│       ├── __init__.py")
        lines.append("│       └── main.py")
        if info.has_tests:
            lines.append("├── tests/")
            lines.append("│   └── test_main.py")
        lines.append("├── pyproject.toml")
        lines.append("└── README.md")
    elif info.language in ("typescript", "javascript"):
        lines.append("├── src/")
        lines.append("│   ├── index.ts")
        lines.append("│   └── lib/")
        if info.has_tests:
            lines.append("├── tests/")
            lines.append("│   └── index.test.ts")
        lines.append("├── package.json")
        lines.append("├── tsconfig.json")
        lines.append("└── README.md")
    else:
        lines.append("├── src/")
        lines.append("│   └── main.*")
        if info.has_tests:
            lines.append("├── tests/")
        lines.append("└── README.md")

    lines.append("```")

    return ReadmeSection(
        section_type="structure",
        title="Project Structure",
        content="\n".join(lines),
        order=ReadmeSectionOrder.PROJECT_STRUCTURE,
    )


_PM_DEV_SETUP: Dict[str, List[str]] = {
    "npm": ["npm install", "npm run test"],
    "yarn": ["yarn install", "yarn test"],
    "pnpm": ["pnpm install", "pnpm test"],
    "pip": ["uv sync", "uv run pytest"],
    "uv": ["uv sync", "uv run pytest"],
    "poetry": ["poetry install", "poetry run pytest"],
    "cargo": ["cargo build", "cargo test"],
    "go": ["go build ./...", "go test ./..."],
}

_CONTRIBUTING_STEPS = [
    "Contributions are welcome! Please follow these steps:",
    "",
    "1. Fork the repository",
    "2. Create a feature branch (`git checkout -b feature/amazing-feature`)",
    '3. Commit your changes (`git commit -m "Add amazing feature"`)',
    "4. Push to the branch (`git push origin feature/amazing-feature`)",
    "5. Open a Pull Request",
    "",
    "### Development Setup",
    "",
]


def _generate_contributing_section(info: ProjectInfo) -> ReadmeSection:
    """Generate contributing section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with contributing content
    """
    dev_cmds = _PM_DEV_SETUP.get(info.package_manager or "", ["# Install dependencies", "# Run tests"])
    lines = list(_CONTRIBUTING_STEPS) + ["```bash"] + dev_cmds + ["```"]

    return ReadmeSection(
        section_type="contributing",
        title="Contributing",
        content="\n".join(lines),
        order=ReadmeSectionOrder.CONTRIBUTING,
    )


def _generate_license_section(info: ProjectInfo) -> ReadmeSection:
    """Generate license section.

    Args:
        info: Project information

    Returns:
        ReadmeSection with license content
    """
    return ReadmeSection(
        section_type="license",
        title="License",
        content="This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.",
        order=ReadmeSectionOrder.LICENSE,
    )


def _generate_header(info: ProjectInfo) -> str:
    """Generate README header with title and badges.

    Args:
        info: Project information

    Returns:
        Header markdown string
    """
    lines = []

    # Title
    lines.append(f"# {info.name}")
    lines.append("")

    # Badges
    badges = []
    if info.version:
        badges.append(f"![Version](https://img.shields.io/badge/version-{info.version}-blue)")

    if info.language:
        lang_colors = {
            "python": "3776AB",
            "typescript": "3178C6",
            "javascript": "F7DF1E",
            "java": "ED8B00",
            "rust": "DEA584",
            "go": "00ADD8",
        }
        color = lang_colors.get(info.language, "gray")
        badges.append(f"![Language](https://img.shields.io/badge/{info.language}-{color})")

    if badges:
        lines.append(" ".join(badges))
        lines.append("")

    # Description
    if info.description:
        lines.append(info.description)
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Main Generator
# =============================================================================


_SECTION_GENERATORS = {
    "installation": _generate_installation_section,
    "usage": _generate_usage_section,
    "features": _generate_features_section,
    "api": _generate_api_section,
    "structure": _generate_structure_section,
    "contributing": _generate_contributing_section,
    "license": _generate_license_section,
}


def _build_sections(info: ProjectInfo, sections: List[str]) -> List[ReadmeSection]:
    keys = list(_SECTION_GENERATORS.keys()) if "all" in sections else [s for s in sections if s in _SECTION_GENERATORS]
    result = []
    for section_type in keys:
        try:
            result.append(_SECTION_GENERATORS[section_type](info))
        except Exception as e:
            logger.warning("section_generation_error", section=section_type, error=str(e))
            sentry_sdk.capture_exception(e)
    result.sort(key=lambda s: s.order)
    return result


def _build_full_readme(info: ProjectInfo, generated_sections: List[ReadmeSection]) -> str:
    parts = [_generate_header(info)]
    toc_lines = ["## Table of Contents", ""]
    for section in generated_sections:
        anchor = section.title.lower().replace(" ", "-")
        toc_lines.append(f"- [{section.title}](#{anchor})")
    toc_lines.append("")
    parts.append("\n".join(toc_lines))
    for section in generated_sections:
        parts.extend([f"## {section.title}", "", section.content, ""])
    return "\n".join(parts)


def generate_readme_sections_impl(
    project_folder: str,
    language: str = "auto",
    sections: Optional[List[str]] = None,
    include_examples: bool = True,
) -> ReadmeGenerationResult:
    """Generate README.md sections from code analysis.

    Args:
        project_folder: Root folder of the project
        language: Programming language (or 'auto' for detection)
        sections: Which sections to generate (or ['all'])
        include_examples: Whether to include code examples

    Returns:
        ReadmeGenerationResult with generated sections
    """
    start_time = time.time()
    if sections is None:
        sections = ["all"]

    logger.info("generate_readme_started", project_folder=project_folder, language=language, sections=sections)

    info = _analyze_project(project_folder, language)
    generated_sections = _build_sections(info, sections)
    full_readme = _build_full_readme(info, generated_sections)
    execution_time = int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)

    logger.info("generate_readme_completed", sections_generated=len(generated_sections), execution_time_ms=execution_time)

    return ReadmeGenerationResult(
        project_info=info,
        sections=generated_sections,
        full_readme=full_readme,
        execution_time_ms=execution_time,
    )
