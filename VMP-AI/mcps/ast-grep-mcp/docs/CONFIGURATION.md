# Configuration Guide

This document describes configuration options for the ast-grep MCP server, including ast-grep configuration (`sgconfig.yaml`) and Sentry/Doppler integration.

## Table of Contents

1. [ast-grep Configuration](#ast-grep-configuration)
2. [Sentry Error Tracking](#sentry-error-tracking)
3. [Doppler Secret Management](#doppler-secret-management)
4. [Complete Configuration Examples](#complete-configuration-examples)

## ast-grep Configuration

The ast-grep MCP server supports custom configuration via a `sgconfig.yaml` file. This file allows you to customize ast-grep behavior, including:

- Defining custom languages
- Specifying rule directories
- Configuring test directories
- Setting language-to-file extension mappings

## Providing the Configuration File

You can provide the configuration file in two ways (in order of precedence):

1. **Command-line argument**: `--config /path/to/sgconfig.yaml`
2. **Environment variable**: `AST_GREP_CONFIG=/path/to/sgconfig.yaml`

The configuration file is validated on startup. If validation fails, the server will exit with a descriptive error message.

## Configuration Structure

### Top-Level Fields

```yaml
# Optional: Directories containing ast-grep rules
ruleDirs:
  - rules
  - custom-rules

# Optional: Directories containing test files
testDirs:
  - tests

# Optional: Custom language definitions
customLanguages:
  mylang:
    extensions:
      - .ml
      - .mli
    languageId: mylang
    expandoChar: _

# Optional: Language-to-glob mappings
languageGlobs:
  - extensions: [.proto]
    language: protobuf
```

### Field Descriptions

#### `ruleDirs` (optional)

Type: `List[str]`

Directories containing ast-grep rule files (`.yml` or `.yaml` files). Paths are relative to the configuration file location.

**Validation:**
- Must not be an empty list if specified
- Each directory path should exist (not enforced by validation, but recommended)

**Example:**
```yaml
ruleDirs:
  - rules
  - security-rules
  - refactoring-rules
```

#### `testDirs` (optional)

Type: `List[str]`

Directories containing test files for your ast-grep rules. Used by ast-grep's testing framework.

**Validation:**
- Must not be an empty list if specified

**Example:**
```yaml
testDirs:
  - tests
  - rule-tests
```

#### `customLanguages` (optional)

Type: `Dict[str, CustomLanguageConfig]`

Define custom languages with tree-sitter grammars. Each language has:

- **`extensions`** (required): List of file extensions (must start with `.`)
- **`languageId`** (optional): Language identifier
- **`expandoChar`** (optional): Character used for meta-variable expansion

**Validation:**
- Dictionary must not be empty if specified
- Each language must have at least one extension
- All extensions must start with a dot (`.`)

**Example:**
```yaml
customLanguages:
  # Custom language for Protocol Buffers
  protobuf:
    extensions:
      - .proto
    languageId: proto

  # Custom language for Terraform
  terraform:
    extensions:
      - .tf
      - .tfvars
    languageId: hcl
```

#### `languageGlobs` (optional)

Type: `List[Dict[str, Any]]`

Map file extensions to languages. Useful for associating non-standard extensions with existing languages.

**Example:**
```yaml
languageGlobs:
  - extensions: [.proto]
    language: protobuf
  - extensions: [.mjs, .cjs]
    language: javascript
```

## Complete Example

Here's a complete example configuration:

```yaml
# sgconfig.yaml - Complete example

ruleDirs:
  - rules
  - custom-rules
  - security

testDirs:
  - tests
  - rule-tests

customLanguages:
  # Add support for GraphQL
  graphql:
    extensions:
      - .graphql
      - .gql
    languageId: graphql

  # Add support for Solidity
  solidity:
    extensions:
      - .sol
    languageId: solidity

languageGlobs:
  # Map .mjs and .cjs to JavaScript
  - extensions: [.mjs, .cjs]
    language: javascript

  # Map .tsx and .jsx to TypeScript/JavaScript
  - extensions: [.tsx]
    language: tsx
  - extensions: [.jsx]
    language: jsx
```

## Validation

The server validates the configuration file on startup using Pydantic models. Common validation errors include:

### Empty Lists or Dictionaries

**Error:**
```
Configuration error in '/path/to/sgconfig.yaml': Validation failed: Directory list cannot be empty if specified
```

**Fix:**
Remove the empty field or add at least one item:
```yaml
# Wrong
ruleDirs: []

# Right - remove the field
# ruleDirs not specified

# Right - add items
ruleDirs:
  - rules
```

### Invalid File Extensions

**Error:**
```
Configuration error in '/path/to/sgconfig.yaml': Validation failed: Extension 'txt' must start with a dot (e.g., '.myext')
```

**Fix:**
Add a dot prefix to all extensions:
```yaml
# Wrong
customLanguages:
  mylang:
    extensions:
      - txt

# Right
customLanguages:
  mylang:
    extensions:
      - .txt
```

### Empty Extensions List

**Error:**
```
Configuration error in '/path/to/sgconfig.yaml': Validation failed: extensions list cannot be empty
```

**Fix:**
Add at least one extension:
```yaml
# Wrong
customLanguages:
  mylang:
    extensions: []

# Right
customLanguages:
  mylang:
    extensions:
      - .ml
```

### YAML Syntax Errors

**Error:**
```
Configuration error in '/path/to/sgconfig.yaml': YAML parsing failed: ...
```

**Fix:**
Check YAML syntax. Common issues:
- Incorrect indentation (use spaces, not tabs)
- Missing colons or hyphens
- Unclosed quotes or brackets

### File Not Found

**Error:**
```
Configuration error in '/path/to/sgconfig.yaml': File does not exist
```

**Fix:**
- Verify the path is correct
- Use absolute paths or paths relative to your working directory
- Check file permissions

## Testing Your Configuration

You can test your configuration by running the server with the `--config` flag:

```bash
uv run main.py --config /path/to/sgconfig.yaml
```

If validation succeeds, the server will start normally. If validation fails, you'll see a descriptive error message.

## Additional Resources

- [ast-grep Configuration Documentation](https://ast-grep.github.io/guide/project/project-config.html)
- [ast-grep Custom Language Guide](https://ast-grep.github.io/advanced/custom-language.html)
- [tree-sitter Language Support](https://tree-sitter.github.io/tree-sitter/)

## Schema Reference

### CustomLanguageConfig

```python
class CustomLanguageConfig:
    extensions: List[str]         # Required, must start with '.'
    languageId: Optional[str]     # Optional language identifier
    expandoChar: Optional[str]    # Optional expansion character
```

### AstGrepConfig

```python
class AstGrepConfig:
    ruleDirs: Optional[List[str]]                              # Rule directories
    testDirs: Optional[List[str]]                              # Test directories
    customLanguages: Optional[Dict[str, CustomLanguageConfig]] # Custom languages
    languageGlobs: Optional[List[Dict[str, Any]]]             # Language mappings
```

All fields are optional, but if provided, they must follow the validation rules described above.

---

## Sentry Error Tracking

The MCP server supports optional Sentry integration for error tracking and performance monitoring.

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SENTRY_DSN` | No | None | Sentry project DSN (format: `https://key@sentry.io/project-id`) |
| `SENTRY_ENVIRONMENT` | No | `"development"` | Environment name (`development`, `staging`, `production`) |

### Setup Methods

#### Method 1: Doppler (Recommended)

```bash
# Set secrets in Doppler
doppler secrets set SENTRY_DSN="https://your-key@sentry.io/project-id" --project bottleneck --config dev
doppler secrets set SENTRY_ENVIRONMENT="development" --project bottleneck --config dev

# Run server
doppler run --project bottleneck --config dev -- uv run main.py
```

#### Method 2: Environment Variables

**macOS/Linux:**
```bash
export SENTRY_DSN="https://your-key@sentry.io/project-id"
export SENTRY_ENVIRONMENT="production"
uv run main.py
```

**Windows (PowerShell):**
```powershell
$env:SENTRY_DSN = "https://your-key@sentry.io/project-id"
$env:SENTRY_ENVIRONMENT = "production"
uv run main.py
```

#### Method 3: MCP Client Configuration

Add to `.cursor-mcp/settings.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/path/to/ast-grep-mcp", "run", "main.py"],
      "env": {
        "SENTRY_DSN": "https://your-key@sentry.io/project-id",
        "SENTRY_ENVIRONMENT": "production"
      }
    }
  }
}
```

### Configuration Details

Located in `src/ast_grep_mcp/core/sentry.py`:

```python
def init_sentry(service_name: str = "ast-grep-mcp") -> None:
    """Initialize Sentry with Anthropic AI integration and service tagging."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return

    sentry_env = os.getenv("SENTRY_ENVIRONMENT", "development")
    is_dev = sentry_env == "development"

    sentry_sdk.init(
        dsn=dsn,
        environment=sentry_env,
        integrations=[AnthropicIntegration(include_prompts=True)],
        traces_sample_rate=1.0 if is_dev else SentryDefaults.PRODUCTION_TRACES_SAMPLE_RATE,
        profiles_sample_rate=1.0 if is_dev else SentryDefaults.PRODUCTION_PROFILES_SAMPLE_RATE,
        send_default_pii=True,
        attach_stacktrace=True,
        before_send=_make_tag_event(service_name),
    )

    sentry_sdk.set_tag("service", service_name)
```

### Customizing Sampling Rates

Edit `main.py` to adjust sampling per environment:

```python
# Conservative production sampling (1%)
traces_sample_rate = 0.01 if environment == "production" else 1.0

# Moderate production sampling (10%)
traces_sample_rate = 0.1 if environment == "production" else 1.0

# Aggressive production sampling (50%)
traces_sample_rate = 0.5 if environment == "production" else 1.0
```

Or use environment variable (requires code change):

```python
traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "1.0" if environment == "development" else "0.1"))
```

Then set via Doppler:

```bash
doppler secrets set SENTRY_TRACES_SAMPLE_RATE="0.05" --project bottleneck --config prd
```

### Testing Sentry Integration

Use the built-in test tool:

```python
# Via MCP client (Cursor/Claude)
test_sentry_integration()
```

Returns:

```json
{
  "sentry_enabled": true,
  "configuration": {
    "dsn_configured": true,
    "environment": "development",
    "traces_sample_rate": 1.0
  },
  "test_result": "success",
  "message": "Test error captured successfully. Check your Sentry dashboard."
}
```

### What Gets Tracked

**Errors:**
- ast-grep subprocess failures
- YAML parsing errors
- File operation errors (backup/restore)
- Schema.org API failures
- Code validation errors

**Performance:**
- Tool execution time
- Subprocess execution spans
- HTTP request spans
- Batch parallel operation spans

**AI Interactions** (if using Anthropic SDK):
- Prompts and responses
- Token usage
- Model information

See [SENTRY-INTEGRATION.md](./SENTRY-INTEGRATION.md) for detailed documentation.

---

## Doppler Secret Management

Doppler provides centralized, secure secret management with team collaboration and audit logging.

### Project Structure

This project is configured with:

- **Project**: `bottleneck`
- **Default Config**: `dev`
- **Configuration File**: `.doppler.yaml`

### Installation

**macOS:**
```bash
brew install dopplerhq/cli/doppler
```

**Linux:**
```bash
curl -Ls https://cli.doppler.com/install.sh | sh
```

**Windows:**
```powershell
scoop install doppler
```

### Authentication

```bash
# Login (opens browser)
doppler login

# Verify authentication
doppler me
```

### Managing Secrets

```bash
# View all secrets
doppler secrets --project bottleneck --config dev

# Get specific secret (plaintext)
doppler secrets get SENTRY_DSN --project bottleneck --config dev --plain

# Set secret
doppler secrets set SENTRY_DSN="https://key@sentry.io/123" --project bottleneck --config dev

# Delete secret
doppler secrets delete OLD_SECRET --project bottleneck --config dev
```

### Running with Doppler

**Manual execution:**
```bash
# Full command
doppler run --project bottleneck --config dev -- uv run main.py

# Shorter (uses .doppler.yaml)
doppler run -- uv run main.py
```

**MCP client configuration:**

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": [
        "run",
        "--project", "bottleneck",
        "--config", "dev",
        "--command",
        "uv --directory /absolute/path/to/ast-grep-mcp run main.py"
      ]
    }
  }
}
```

### Multiple Environments

Create separate configs for different environments:

```bash
# Create staging config
doppler configs create stg --project bottleneck

# Set staging-specific secrets
doppler secrets set SENTRY_DSN="https://stg-key@sentry.io/stg-id" --project bottleneck --config stg
doppler secrets set SENTRY_ENVIRONMENT="staging" --project bottleneck --config stg

# Create production config
doppler configs create prd --project bottleneck

# Set production secrets
doppler secrets set SENTRY_DSN="https://prd-key@sentry.io/prd-id" --project bottleneck --config prd
doppler secrets set SENTRY_ENVIRONMENT="production" --project bottleneck --config prd
```

Use different configs in MCP client:

```json
{
  "mcpServers": {
    "ast-grep-dev": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "dev", "--command", "uv --directory /path run main.py"]
    },
    "ast-grep-prod": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "prd", "--command", "uv --directory /path run main.py"]
    }
  }
}
```

### Team Collaboration

**Invite team members:**

1. Go to [Doppler Dashboard](https://dashboard.doppler.com/)
2. Select project → Team → Invite Member
3. Set role (Admin, Developer, Read-only)

**Role-based access:**

| Role | Permissions |
|------|------------|
| Owner | Full access, delete project |
| Admin | Manage secrets, configs, members |
| Developer | Read/write secrets |
| Read-only | View secrets only |

**Audit logging:**

View who accessed secrets in Project Settings → Audit Logs.

### Migration

If you're currently using manual environment variables, follow the Doppler setup steps in [docs/README.md](README.md#configuration) and mirror your existing values into Doppler secrets.

---

## Complete Configuration Examples

### Example 1: Local Development (No Monitoring)

**MCP Client** (`.cursor-mcp/settings.json`):
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/Users/me/code/ast-grep-mcp", "run", "main.py"],
      "env": {}
    }
  }
}
```

**Features:**
- No error tracking
- No secret management
- Minimal overhead
- Good for: Local development, testing

### Example 2: Development with Sentry (Manual)

**MCP Client**:
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/Users/me/code/ast-grep-mcp", "run", "main.py"],
      "env": {
        "SENTRY_DSN": "https://dev-key@sentry.io/dev-project",
        "SENTRY_ENVIRONMENT": "development"
      }
    }
  }
}
```

**Features:**
- Error tracking enabled
- 100% trace sampling
- Manual credential management
- Good for: Solo developers, simple projects

### Example 3: Team Development with Doppler

**MCP Client**:
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": [
        "run",
        "--project", "bottleneck",
        "--config", "dev",
        "--command",
        "uv --directory /Users/me/code/ast-grep-mcp run main.py"
      ]
    }
  }
}
```

**Doppler Secrets** (`bottleneck/dev`):
```bash
SENTRY_DSN=https://dev-key@sentry.io/dev-project
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=1.0
```

**Features:**
- Centralized secret management
- Team collaboration
- Audit logging
- Easy environment switching
- Good for: Teams, multiple environments

### Example 4: Production Deployment

**MCP Client**:
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": [
        "run",
        "--project", "bottleneck",
        "--config", "prd",
        "--command",
        "uv --directory /opt/ast-grep-mcp run main.py"
      ]
    }
  }
}
```

**Doppler Secrets** (`bottleneck/prd`):
```bash
SENTRY_DSN=https://prd-key@sentry.io/prd-project
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% sampling
```

**Features:**
- Production error tracking
- Cost-optimized sampling (10%)
- Secure credential rotation
- Separate Sentry project
- Good for: Production deployments, high traffic

### Example 5: Multi-Environment Setup

**MCP Client**:
```json
{
  "mcpServers": {
    "ast-grep-dev": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "dev", "--command", "uv --directory /path run main.py"]
    },
    "ast-grep-stg": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "stg", "--command", "uv --directory /path run main.py"]
    },
    "ast-grep-prd": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "prd", "--command", "uv --directory /path run main.py"]
    }
  }
}
```

**Doppler Configs:**

| Config | SENTRY_ENVIRONMENT | Trace Sampling | Use Case |
|--------|-------------------|----------------|----------|
| `dev` | development | 100% | Local development, full visibility |
| `stg` | staging | 50% | Pre-production testing |
| `prd` | production | 10% | Production deployment |

**Good for:** Large teams, CI/CD pipelines, staged deployments

### Example 6: Custom ast-grep Configuration

**MCP Client**:
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": [
        "run",
        "--project", "bottleneck",
        "--config", "dev",
        "--command",
        "uv --directory /path run main.py --config /path/to/sgconfig.yaml"
      ]
    }
  }
}
```

**sgconfig.yaml**:
```yaml
ruleDirs:
  - rules
  - custom-rules

customLanguages:
  graphql:
    extensions:
      - .graphql
      - .gql
    languageId: graphql
```

**Features:**
- Custom ast-grep language support
- Doppler secret management
- Sentry error tracking
- Good for: Custom language projects, advanced ast-grep usage

---

## Configuration Validation

### Validate ast-grep Configuration

```bash
# Test config file syntax
cat sgconfig.yaml | python -c "import yaml; yaml.safe_load(open('sgconfig.yaml'))"

# Run server with config
uv run main.py --config sgconfig.yaml
```

### Validate Sentry Configuration

```bash
# Check environment variables
echo $SENTRY_DSN
echo $SENTRY_ENVIRONMENT

# Or with Doppler
doppler secrets get SENTRY_DSN --project bottleneck --config dev --plain

# Test Sentry integration
uv run main.py
# Look for: "Sentry initialized with DSN" in logs
```

### Validate Complete Setup

```bash
# 1. Test Doppler injection
doppler run --project bottleneck --config dev -- env | grep SENTRY

# 2. Test server startup
doppler run --project bottleneck --config dev -- uv run main.py

# 3. Use test tool via MCP client
test_sentry_integration()
```

---

## Additional Resources

- **ast-grep Configuration**: [ast-grep docs](https://ast-grep.github.io/guide/project/project-config.html)
- **Sentry Integration**: [SENTRY-INTEGRATION.md](./SENTRY-INTEGRATION.md)
- **Doppler Setup**: [docs/README.md](README.md#configuration)
- **Main Documentation**: [README.md](../README.md)
- **Development Guide**: [CLAUDE.md](../CLAUDE.md)
