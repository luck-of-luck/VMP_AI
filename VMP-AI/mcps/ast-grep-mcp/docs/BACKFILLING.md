# Telemetry Backfilling

Reconstruct missing OTEL plugin spans from agent-cache invocation logs so that new skills inherit usage history from the agents they wrap.

## Problem

When a new skill wraps an existing agent (e.g., `/review` wraps `code-reviewer`), the skill auditor scores its telemetry dimensions at 0 because no `plugin.name` spans exist yet. The agent has hundreds of invocations with full telemetry, but the skill has none.

## Solution

`scripts/backfill-skill-spans.py` reads agent-cache logs, resolves trace context, and appends `hook:plugin-pre-tool` / `hook:plugin-post-tool` spans to the OTEL trace JSONL files. Each backfilled span links to the original agent invocation via `agent.linked_type`.

## Usage

```bash
# Dry run (default) -- prints spans to stdout, writes nothing
python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review

# Write spans to trace files
python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review --write

# Filter to specific sessions
python3 scripts/backfill-skill-spans.py --skill review --agent code-reviewer --category review --sessions 7477d8dc,a3e2e2a5
```

## Data Sources

| Source | Location | Content |
|--------|----------|---------|
| Agent cache | `~/.claude/agent-cache/<session>/agent-invocations.log` | STARTED/COMPLETED records with timestamps and output size |
| Trace context | `~/.claude/telemetry/trace-ctx/<session>.json` | `traceId`, `spanId`, `timestamp` linking sessions to OTEL traces |
| Trace spans | `~/.claude/telemetry/traces-YYYY-MM-DD.jsonl` | OTEL spans (append target) |

## Agent Cache Format

```
# STARTED (6 tab-separated fields)
2026-03-08T09:07:55.069Z	code-reviewer	review	active	STARTED	NEW,FG

# COMPLETED (4 tab-separated fields)
2026-03-08T09:08:50.123Z	code-reviewer	COMPLETED	5843bytes
```

## Backfilled Span Format

Two spans per invocation:

**Pre-tool** (near-instant at invocation start):
```json
{
  "traceId": "<from trace-ctx>",
  "spanId": "<random hex16>",
  "name": "hook:plugin-pre-tool",
  "kind": 0,
  "startTime": [epoch_s, ns],
  "endTime": [epoch_s, ns + 8ms],
  "duration": [0, 8000000],
  "status": {"code": 1},
  "attributes": {
    "hook.name": "plugin-pre-tool",
    "hook.type": "plugin",
    "session.id": "<session-uuid>",
    "hook.trigger": "PreToolUse",
    "plugin.name": "<skill-name>",
    "plugin.full_name": "<skill-name>",
    "plugin.category": "<skill-category>",
    "plugin.source_type": "active",
    "plugin.has_args": true,
    "agent.linked_type": "<agent-name>",
    "backfill.source": "backfill:agent-span-recovery",
    "backfill.timestamp": "<ISO-8601>"
  },
  "events": [],
  "links": [],
  "resource": {"serviceName": "claude-code-hooks", "serviceVersion": "1.0.0"}
}
```

**Post-tool** (full invocation duration):
```json
{
  "name": "hook:plugin-post-tool",
  "duration": [seconds, nanoseconds],
  "attributes": {
    "hook.trigger": "PostToolUse",
    "agent.output_bytes": 5843,
    "agent.completion_status": "COMPLETED"
  }
}
```

## Idempotency

Spans are tagged with `backfill.source: "backfill:agent-span-recovery"` and `plugin.name`. Before appending, the script checks each target trace file for existing backfilled spans matching the same skill and session. Duplicate sessions are skipped.

Re-running `--write` after a successful backfill produces zero new spans.

## Recovery Tiers

| Tier | Sources Available | Fidelity |
|------|-------------------|----------|
| ~90% | agent-cache + transcript + trace-ctx | Full: timestamps, duration, output size, trace linkage |
| ~50% | agent-cache + trace-ctx (no transcript) | Partial: timing and linkage, no output content |
| ~20% | agent-cache only (no trace-ctx) | Skipped: no traceId to link spans into |

Sessions without trace-ctx files (pre-OTEL hooks era) are skipped with a warning.

## Example: /review Skill Backfill (2026-03-08)

```
Source:     code-reviewer agent
Target:     /review skill
Invocations found:  579 across 259 sessions
With trace-ctx:     261 invocations (45%)
Spans written:      522 (261 x 2 pre/post)
Trace files:        16 (2026-02-17 through 2026-03-08)
Skipped (no ctx):   318 invocations
```

## Limitations

- Sessions before OTEL hooks were enabled have no trace-ctx and cannot be backfilled
- Output content (the actual review text) is not stored in spans; only byte count is preserved
- Backfilled spans have `kind: 0` (INTERNAL) and `status.code: 1` (OK) regardless of original outcome
- The `COMPLETED_WITH_ERROR_MENTIONS` status is preserved in `agent.completion_status` but `status.code` is always OK
