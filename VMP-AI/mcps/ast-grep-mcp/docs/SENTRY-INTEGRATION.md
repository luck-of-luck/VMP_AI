# Sentry Integration Guide

This document provides comprehensive guidance on using Sentry error tracking with the ast-grep-mcp server.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Setup](#setup)
  - [Option 1: Doppler (Recommended)](#option-1-doppler-recommended)
  - [Option 2: Manual Configuration](#option-2-manual-configuration)
- [What Gets Tracked](#what-gets-tracked)
- [Configuration Options](#configuration-options)
- [Testing Your Setup](#testing-your-setup)
- [Viewing Events in Sentry](#viewing-events-in-sentry)
- [Performance Monitoring](#performance-monitoring)
- [AI Monitoring (Anthropic SDK)](#ai-monitoring-anthropic-sdk)
- [Privacy Considerations](#privacy-considerations)
- [Cost Management](#cost-management)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The ast-grep-mcp server includes comprehensive Sentry integration for production error tracking, performance monitoring, and AI agent interaction analysis. This integration helps you:

- **Debug production issues** with full context and stack traces
- **Monitor performance** of code searches and rewrites
- **Track AI interactions** to understand agent behavior
- **Identify bottlenecks** in large codebase operations
- **Prevent regressions** by catching errors early

## Features

### Error Tracking

All 55 MCP tools include automatic error capture:

- **Code Search Tools**: ast-grep subprocess failures, YAML parsing errors, pattern matching errors
- **Code Rewrite Tools**: Backup failures, syntax validation errors, rollback failures
- **Schema.org Tools**: HTTP fetch failures, JSON parsing errors, validation errors
- **Batch Operations**: Parallel execution failures, query deduplication errors
- **Security Scanner**: Vulnerability detection errors, pattern matching failures
- **Quality Tools**: Report generation errors, auto-fix validation failures

### Performance Monitoring

Every tool execution is tracked as a Sentry transaction with:

- **Tool name** and **parameters** as transaction tags
- **Execution time** measurements
- **Subprocess spans** for ast-grep CLI operations
- **HTTP spans** for Schema.org API calls
- **Batch operation spans** for parallel query execution

### Rich Context

Every error includes:

- Tool name and parameters
- Execution time before failure
- Full stack trace
- Environment (development/production)
- Service tag (`service:ast-grep-mcp`)
- Custom tags for specific error types

## Setup

### Option 1: Doppler (Recommended)

Doppler provides secure, centralized secret management with team collaboration and audit logging.

#### 1. Install Doppler CLI

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

#### 2. Authenticate

```bash
doppler login
```

This opens a browser for authentication.

#### 3. Verify Project Configuration

```bash
# List available projects
doppler projects

# Check secrets for this project
doppler secrets --project bottleneck --config dev
```

You should see `SENTRY_DSN` and `SENTRY_ENVIRONMENT` in the output.

#### 4. Configure Sentry DSN

If `SENTRY_DSN` is not set:

```bash
# Get your Sentry DSN from: https://sentry.io/settings/[org]/projects/[project]/keys/
doppler secrets set SENTRY_DSN="https://your-key@sentry.io/project-id" --project bottleneck --config dev
```

#### 5. Configure MCP Client

**Cursor** (`.cursor-mcp/settings.json`):
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

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):
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

#### 6. Test the Setup

```bash
# Test Doppler can run the server
doppler run --project bottleneck --config dev -- uv run main.py

# You should see: "Sentry initialized with DSN" in the logs
```

### Option 2: Manual Configuration

For simple setups or local development without Doppler.

#### 1. Get Your Sentry DSN

1. Go to [Sentry.io](https://sentry.io/)
2. Navigate to **Settings** → **Projects** → **[Your Project]** → **Client Keys (DSN)**
3. Copy the DSN (format: `https://key@sentry.io/project-id`)

#### 2. Set Environment Variables

**macOS/Linux:**
```bash
export SENTRY_DSN="https://your-key@sentry.io/project-id"
export SENTRY_ENVIRONMENT="production"  # or "development"
```

**Windows (PowerShell):**
```powershell
$env:SENTRY_DSN = "https://your-key@sentry.io/project-id"
$env:SENTRY_ENVIRONMENT = "production"
```

#### 3. Configure MCP Client

Add environment variables to your MCP client configuration:

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ast-grep-mcp", "run", "main.py"],
      "env": {
        "SENTRY_DSN": "https://your-key@sentry.io/project-id",
        "SENTRY_ENVIRONMENT": "production"
      }
    }
  }
}
```

## What Gets Tracked

### Errors Captured

| Error Type | Example Scenarios |
|------------|------------------|
| **Subprocess Errors** | ast-grep binary not found, invalid YAML rules, pattern syntax errors |
| **File Operation Errors** | Permission denied, file not found, backup creation failures |
| **Validation Errors** | Python syntax errors after rewrite, TypeScript compilation failures |
| **HTTP Errors** | Schema.org API timeouts, network failures, JSON parsing errors |
| **Cache Errors** | LRU cache eviction failures, TTL expiration issues |
| **Batch Errors** | Parallel execution failures, query deduplication errors |

### Performance Traces

Every tool execution creates a transaction with these spans:

```
Transaction: find_code (2.5s)
├─ Span: run_ast_grep (2.3s)
│  └─ Subprocess: ast-grep --json=stream (2.2s)
└─ Span: format_results (0.2s)
```

Example tools with performance tracking:

- **find_code**: Pattern matching execution time
- **rewrite_code**: Backup creation, ast-grep fix, syntax validation
- **batch_search**: Parallel query execution, deduplication
- **search_schemas**: HTTP fetch, JSON parsing, indexing
- **detect_security_issues**: Security scan execution time, vulnerability counts
- **apply_standards_fixes**: Auto-fix application time, validation passes
- **generate_quality_report**: Report generation time, metric collection

### AI Monitoring (If Using Anthropic SDK)

When `sendDefaultPii: true` is enabled, Sentry captures:

- AI prompts sent to Claude
- Claude responses
- Token usage (input/output tokens)
- Model name and version
- Conversation context

**Privacy Note**: This feature captures actual user prompts and AI responses. Ensure compliance with your data privacy policies before enabling in production.

## Configuration Options

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SENTRY_DSN` | Sentry project DSN | None (disabled) | `https://key@sentry.io/123` |
| `SENTRY_ENVIRONMENT` | Environment name | `"development"` | `"production"`, `"staging"` |

### Code Configuration

Located in `main.py` in the `init_sentry()` function:

```python
def init_sentry() -> None:
    """Initialize Sentry error tracking with Anthropic AI integration."""
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if not sentry_dsn:
        logger.info("Sentry DSN not configured, error tracking disabled")
        return

    environment = os.environ.get("SENTRY_ENVIRONMENT", "development")

    # Sampling rates
    traces_sample_rate = 1.0 if environment == "development" else 0.1

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=True,  # Enable AI monitoring
        integrations=[AnthropicIntegration()],
    )
```

### Customizing Sampling Rates

To reduce costs in production, adjust `traces_sample_rate`:

```python
# Development: Track 100% of transactions
traces_sample_rate = 1.0

# Production: Track 10% of transactions
traces_sample_rate = 0.1

# High-traffic production: Track 1% of transactions
traces_sample_rate = 0.01
```

## Testing Your Setup

### Using the test_sentry_integration Tool

The MCP server includes a built-in testing tool:

```
test_sentry_integration()
```

**Expected Output:**

```json
{
  "sentry_enabled": true,
  "configuration": {
    "dsn_configured": true,
    "environment": "development",
    "traces_sample_rate": 1.0
  },
  "test_result": "success",
  "message": "Test error captured successfully. Check your Sentry dashboard at https://sentry.io/organizations/your-org/issues/",
  "dashboard_url": "https://sentry.io/organizations/your-org/issues/",
  "instructions": [
    "1. Go to your Sentry dashboard",
    "2. Look for error: 'Test error from ast-grep-mcp'",
    "3. Verify error context includes tool name and timestamp",
    "4. Check transaction trace for performance data"
  ]
}
```

### Manual Testing

**Step 1**: Trigger a test error:

```bash
# Run a search with invalid YAML to trigger an error
# The error will be captured and sent to Sentry
```

**Step 2**: Check Sentry dashboard:

1. Go to https://sentry.io/organizations/[your-org]/issues/
2. Look for recent errors from `service:ast-grep-mcp`
3. Click on an error to see full details

**Step 3**: Verify performance traces:

1. Go to https://sentry.io/organizations/[your-org]/performance/
2. Filter by `service:ast-grep-mcp`
3. View transaction traces and spans

## Viewing Events in Sentry

### Issues Dashboard

Filter errors by service:

1. Go to **Issues** in Sentry
2. Add filter: `service:ast-grep-mcp`
3. View recent errors with full context

### Performance Dashboard

View transaction traces:

1. Go to **Performance** in Sentry
2. Filter by `service:ast-grep-mcp`
3. Click on a transaction to see detailed spans
4. Analyze slow operations

### Custom Queries

Create custom queries in **Discover**:

```sql
-- Find all errors from specific tools
service:ast-grep-mcp AND tool_name:rewrite_code

-- Find slow operations (>5 seconds)
service:ast-grep-mcp AND transaction.duration:>5000

-- Find all subprocess errors
service:ast-grep-mcp AND error.type:SubprocessError
```

## Performance Monitoring

### Transaction Structure

Every tool execution creates a transaction:

```
Transaction: rewrite_code
├─ Tags:
│  ├─ tool_name: rewrite_code
│  ├─ dry_run: false
│  ├─ language: python
│  └─ service: ast-grep-mcp
├─ Spans:
│  ├─ create_backup (0.5s)
│  ├─ run_ast_grep (2.0s)
│  │  └─ subprocess: ast-grep (1.9s)
│  └─ validate_syntax (0.3s)
└─ Duration: 2.8s
```

### Analyzing Slow Operations

**Find bottlenecks:**

1. Go to **Performance** → **Summary**
2. Sort by **P95** (95th percentile duration)
3. Click on slow transactions
4. Analyze span waterfall

**Common bottlenecks:**

- Large codebase searches: Optimize with `max_results` or `--paths` filters
- Parallel batch operations: Reduce worker count
- Syntax validation: Skip validation for trusted inputs

## AI Monitoring (Anthropic SDK)

When `sendDefaultPii: true` is enabled, Sentry captures AI interactions.

### What Gets Captured

```python
# Example AI interaction trace
Transaction: ai_prompt
├─ Span: anthropic_api_call
│  ├─ Prompt: "Find all console.log statements"
│  ├─ Response: "Here's the ast-grep rule..."
│  ├─ Input Tokens: 150
│  ├─ Output Tokens: 300
│  └─ Model: claude-sonnet-4
└─ Duration: 1.2s
```

### Viewing AI Traces

1. Go to **Performance** in Sentry
2. Filter by `service:ast-grep-mcp`
3. Look for transactions with `anthropic_api_call` spans
4. View full prompt/response context

### Privacy Considerations

**AI monitoring captures:**
- User prompts (may contain sensitive code or data)
- AI responses (may contain proprietary logic)
- File paths and project structure

**Recommendations:**
- Use separate Sentry project for AI monitoring
- Enable only in development/staging
- Configure data scrubbing rules for sensitive patterns
- Review captured data regularly

## Privacy Considerations

### Personal Identifiable Information (PII)

The integration includes `send_default_pii: true` to enable AI monitoring. This means:

**What gets captured:**
- File paths (may include usernames or organization names)
- Code snippets in error contexts
- YAML rule definitions
- AI prompts and responses

**What does NOT get captured:**
- File contents (unless in error context)
- Environment variables (except those explicitly logged)
- Credentials or API keys

### Compliance Recommendations

1. **Review your data privacy policies** before enabling Sentry in production
2. **Configure data scrubbing** in Sentry project settings:
   - Scrub API keys, tokens, passwords
   - Redact sensitive file paths
   - Filter proprietary code patterns
3. **Use separate Sentry projects** for different sensitivity levels:
   - `ast-grep-mcp-public` (scrubbed data)
   - `ast-grep-mcp-internal` (full context)
4. **Enable audit logging** in Doppler to track secret access
5. **Set retention policies** to auto-delete events after 30/60/90 days

## Cost Management

Sentry pricing is based on events and transactions. Here's how to optimize costs:

### 1. Adjust Sampling Rates

**Development:**
```python
traces_sample_rate = 1.0  # 100% - see everything
```

**Production:**
```python
traces_sample_rate = 0.1  # 10% - balance cost vs visibility
```

**High-traffic production:**
```python
traces_sample_rate = 0.01  # 1% - minimal cost
```

### 2. Use Error Filtering

Configure in Sentry project settings → **Inbound Filters**:

- Ignore known errors (e.g., "file not found" from user input)
- Filter by error type
- Filter by environment

### 3. Transaction Filtering

Add custom filtering in `init_sentry()`:

```python
def traces_sampler(sampling_context):
    # Sample 100% of errors
    if sampling_context.get("parent_sampled") is False:
        return 1.0

    # Sample 10% of successful operations
    return 0.1

sentry_sdk.init(
    dsn=sentry_dsn,
    traces_sampler=traces_sampler,  # Instead of traces_sample_rate
)
```

### 4. Monitor Quota Usage

1. Go to **Settings** → **Subscription**
2. View **Events** and **Transactions** usage
3. Set up alerts for 80% quota usage
4. Adjust sampling rates if approaching limits

## Troubleshooting

### Sentry Not Initializing

**Symptom**: No "Sentry initialized" message in logs

**Causes:**
1. `SENTRY_DSN` not set
2. Invalid DSN format
3. Doppler not injecting environment variables

**Solutions:**

```bash
# Check if DSN is set
echo $SENTRY_DSN

# Test Doppler secret injection
doppler run --project bottleneck --config dev -- env | grep SENTRY

# Verify DSN format (should be: https://key@sentry.io/project-id)
doppler secrets get SENTRY_DSN --project bottleneck --config dev --plain
```

### Errors Not Appearing in Sentry

**Symptom**: `test_sentry_integration()` succeeds but errors don't show up

**Causes:**
1. Network connectivity issues
2. Sentry project quota exceeded
3. Inbound filters blocking events
4. Wrong Sentry project

**Solutions:**

```bash
# Check network connectivity
curl -I https://sentry.io

# Check Sentry project settings
# Go to: https://sentry.io/settings/[org]/projects/[project]/

# Verify DSN points to correct project
doppler secrets get SENTRY_DSN --project bottleneck --config dev --plain

# Check quota usage
# Go to: https://sentry.io/settings/[org]/subscription/
```

### Doppler Not Injecting Secrets

**Symptom**: Server starts but Sentry shows "DSN not configured"

**Causes:**
1. Doppler not authenticated
2. Wrong project/config specified
3. `.doppler.yaml` missing or incorrect

**Solutions:**

```bash
# Check Doppler authentication
doppler me

# Verify project configuration
cat .doppler.yaml

# Should show:
# setup:
#   project: bottleneck
#   config: dev

# Test secret injection manually
doppler run --project bottleneck --config dev -- env | grep SENTRY

# If empty, verify secrets exist
doppler secrets --project bottleneck --config dev | grep SENTRY
```

### High Event Volume / Cost

**Symptom**: Sentry quota exceeded or high bill

**Solutions:**

1. **Reduce sampling rate:**
   ```python
   traces_sample_rate = 0.1  # Change from 1.0 to 0.1
   ```

2. **Add inbound filters** (Sentry dashboard):
   - Filter by error message pattern
   - Ignore specific error types
   - Filter by environment

3. **Use dynamic sampling:**
   ```python
   def traces_sampler(sampling_context):
       # High sampling for errors
       if sampling_context.get("parent_sampled") is False:
           return 1.0

       # Low sampling for successful operations
       operation = sampling_context.get("transaction_context", {}).get("op")
       if operation in ["find_code", "batch_search"]:
           return 0.05  # 5% for high-volume operations

       return 0.1  # 10% for other operations
   ```

### AI Monitoring Not Working

**Symptom**: No AI interactions in Sentry

**Causes:**
1. `send_default_pii` disabled
2. Anthropic SDK not installed
3. No AI interactions happening

**Solutions:**

```bash
# Verify Anthropic integration is installed
uv run python -c "import sentry_sdk; print(sentry_sdk.integrations.anthropic)"

# Check sentry-sdk version includes Anthropic
uv run pip show sentry-sdk | grep Version
# Should be >= 2.0.0

# Verify sendDefaultPii is enabled
# Check main.py: send_default_pii=True
```

## Best Practices

### 1. Use Environment-Specific Configurations

```bash
# Development: Full visibility
doppler secrets set SENTRY_ENVIRONMENT="development" --project bottleneck --config dev
doppler secrets set SENTRY_TRACES_SAMPLE_RATE="1.0" --project bottleneck --config dev

# Production: Balanced cost vs visibility
doppler secrets set SENTRY_ENVIRONMENT="production" --project bottleneck --config prd
doppler secrets set SENTRY_TRACES_SAMPLE_RATE="0.1" --project bottleneck --config prd
```

### 2. Tag Errors for Better Filtering

The integration already tags all events with:
- `service:ast-grep-mcp`
- `tool_name:[tool_name]`
- Environment (development/production)

Add custom tags in your code:

```python
with sentry_sdk.configure_scope() as scope:
    scope.set_tag("project_type", "monorepo")
    scope.set_tag("codebase_size", "large")
```

### 3. Set Up Alerts

Configure in Sentry → **Alerts**:

- **High error rate**: Alert when errors spike
- **Performance regression**: Alert when P95 > 5s
- **Quota usage**: Alert at 80% of quota
- **New error types**: Alert on first occurrence

### 4. Regular Review

Weekly:
- Review top 10 errors
- Check performance regressions
- Analyze slow operations

Monthly:
- Review quota usage
- Adjust sampling rates
- Update inbound filters
- Archive resolved issues

### 5. Separate Projects for Different Use Cases

Recommended Sentry projects:

1. **ast-grep-mcp-dev**: Development with 100% sampling
2. **ast-grep-mcp-prod**: Production with 10% sampling
3. **ast-grep-mcp-ai**: AI monitoring with full PII capture (internal only)

### 6. Use Source Maps for Better Stack Traces

(Future enhancement - not yet implemented)

### 7. Document Your Setup

Keep a team wiki/doc with:
- Sentry project URLs
- Doppler project/config names
- Sampling rate decisions
- Alert escalation procedures
- Privacy policy compliance notes

## Additional Resources

- [Sentry Python SDK Documentation](https://docs.sentry.io/platforms/python/)
- [Sentry Performance Monitoring](https://docs.sentry.io/product/performance/)
- [Doppler Documentation](https://docs.doppler.com/)
- [Anthropic SDK Integration](https://docs.sentry.io/platforms/python/integrations/anthropic/)

## Support

For issues with this integration:
1. Check this documentation
2. Run `test_sentry_integration()` for diagnostic info
3. Review [KNOWN_ISSUES.md](./KNOWN_ISSUES.md)
4. Open an issue on GitHub with diagnostic output
