# Repomix Command-Line Cheat Sheet

A concise command-line cheat sheet for Repomix, the tool used to pack codebases for AI consumption.

## Basic Usage

- `npx repomix` — Packs the current directory using default settings.
- `repomix path/to/dir` — Packs a specific local directory.
- `repomix --init` — Generates a `repomix.config.json` file in the current directory.
- `repomix --copy` — Automatically copies the generated output to your clipboard.

## Output Formats & Style

- `--style <format>` — Set output format: `xml` (default), `markdown`, `json`, or `plain`.
- `-o, --output <file>` — Specify a custom output filename (default: `repomix-output.xml`).
- `--stdout` — Writes packed output directly to the terminal instead of a file.
- `--split-output <size>` — Splits large output into multiple files (e.g., `--split-output 2mb`).

## File Selection & Filtering

- `--include "src/**/*.ts"` — Only include files matching specific glob patterns.
- `--ignore "tests/**,*.log"` — Exclude specific files or directories.
- `--stdin` — Pipe a list of files from other commands (e.g., `git ls-files | repomix --stdin`).
- `--no-files` — Generates metadata and directory structure without file contents.

## Compression & Token Management

- `--compress` — Intelligent code structure extraction using Tree-sitter to reduce token count.
- `--remove-comments` — Strips code comments to save space.
- `--remove-empty-lines` — Removes blank lines from all files.
- `--token-count-tree [N]` — Displays a file tree showing token counts for files over N tokens.

## Remote Repositories

- `--remote <url>` — Pack a remote GitHub repository directly.
- `--remote-branch <name>` — Specify a branch, tag, or commit hash for remote packing.

## Advanced Options

- `--output-show-line-numbers` — Adds line numbers to the output for easier referencing.
- `--instruction-file-path <path>` — Includes custom AI instructions from a text file.
- `--verbose` — Enables detailed debug logging.
- `--quiet` — Suppresses all console output except for errors.

---

## Is `--compress` Lossless?

No, the `--compress` flag is **lossy**.

It uses Tree-sitter to intelligently parse your code and extract only the "essential" structures while removing implementation details (function bodies, internal logic, etc.) to reduce token counts by roughly 70%.

### What is Lost vs. Preserved

- **Lost:** Detailed function bodies, internal logic, local variable assignments, and granular implementation details.
- **Preserved:** Function and method signatures, class structures, interface/type definitions, imports, and exports.

### When to Use It

- **Architectural Overview:** Use it when you want an AI to understand the "what" (API surface and structure) without getting bogged down in the "how" (detailed code).
- **Context Limits:** Use it for very large codebases that would otherwise exceed an LLM's context window.

> **Pro Tip:** If you need the AI to actually refactor or debug specific logic, do **not** use `--compress`, as the logic it needs to see will be stripped out and replaced with placeholders like `pass`.

---

## Compression Configuration

Compression is controlled by a single boolean — there are no granular knobs for what gets kept or removed. Enable it in your config or via CLI:

```json
{
  "output": {
    "compress": true
  }
}
```

Or on the command line: `repomix --compress`

The Tree-sitter-based compression preserves function/method signatures, class structures, interface/type definitions, imports, and exports. It removes function bodies, loop/conditional internals, and local variable assignments. There is no way to selectively keep or remove specific categories — it is all-or-nothing.

> **Note:** Compression is marked as experimental by the Repomix team and may gain more granular controls in the future. See [Feature Request #561](https://github.com/yamadashy/repomix/issues/561) and [#516](https://github.com/yamadashy/repomix/issues/516) for open discussions on selective compression.

### Future Granularity (Tracked)

Granular compression controls (e.g., `keep_signatures`, `keep_interfaces`, `keep_docstrings`, per-directory compression modes) do not exist in the current repomix API but are being discussed upstream. Potential configuration might include per-category toggles for what the Tree-sitter extractor preserves vs. strips, and include/exclude patterns specific to the `--compress` pass. This is tracked in [docs/BACKLOG.md](../BACKLOG.md) for integration when upstream support lands.

### Pro Tips for Compression

- **Selective inclusion:** Use `--include` to compress only certain directories while leaving others out entirely, rather than trying to control what the compressor keeps.
- **Combine with other reductions:** `--compress --remove-comments --remove-empty-lines` stacks all three for maximum token reduction.

---

## Full Configuration Template

This configuration combines compression with layered ignore rules to ensure the AI receives a structural overview while skipping irrelevant files.

Save this as `repomix.config.json` in your project root:

```json
{
  "$schema": "https://repomix.com/schemas/latest/schema.json",
  "output": {
    "filePath": "packed-codebase.xml",
    "style": "xml",
    "compress": true,
    "removeComments": true,
    "removeEmptyLines": true,
    "showLineNumbers": false,
    "topFilesLength": 10
  },
  "ignore": {
    "useGitignore": true,
    "useDefaultPatterns": true,
    "customPatterns": [
      "**/tests/**",
      "**/docs/**",
      "package-lock.json",
      "yarn.lock",
      "*.log",
      "dist/**/*",
      "build/**/*"
    ]
  },
  "security": {
    "enableSecurityCheck": true
  }
}
```

### Why This Setup Works

- **Layered Filtering:** It respects your `.gitignore` and built-in defaults (like `node_modules`), while `customPatterns` lets you prune project-specific noise like lockfiles or test suites.
- **Structural Compression:** With `compress: true`, the AI sees the entire project structure and API surface without wasting tokens on the actual logic inside functions.
- **Security Built-in:** The `enableSecurityCheck` ensures Secretlint runs automatically to prevent accidental exposure of API keys or credentials in the packed file.
