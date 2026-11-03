---
name: hermes
description: Use when you need Hermes conversations, messaging channels or gateway state. Triggers on hermes, telegram, discord, slack, whatsapp.
---

# Hermes — Messaging Gateway Bridge

Hermes is installed as a local MCP server (`hermes mcp serve`). Use its tools to interact with Telegram, Discord, Slack, WhatsApp, Signal, Matrix and other platforms that Hermes bridges.

## When to Use

- User asks about Hermes conversations, messages, or channels: `hermes`, `telegram`, `discord`, `slack`, `gateway`
- Need to read message history, poll events, or send a message to a platform
- Need to list pending approvals (`permissions_list_open`) before dangerous actions

## Prerequisites

- Hermes binary installed at `%LOCALAPPDATA%/hermes/bin/hermes.exe` (Windows) or `bin/hermes.exe` — configured in `opencode.jsonc` as `mcp.hermes`
- Run `opencode mcp list` to verify `hermes` is connected; restart opencode after config changes

## How to Run

MCP tools are auto-available when the server is `enabled: true`. Prompt with explicit tool hint:

```
use the hermes tool to list conversations
use hermes messages_read for session_key "telegram:630898..."
```

## Quick Reference

Tools exposed by `mcp_serve.py:622` (MCPServer `hermes`):

| Tool | Purpose |
|------|---------|
| `hermes_conversations_list` | List active conversations (filter `platform`, `search`, `limit`) |
| `hermes_conversation_get` | Get one conversation by `session_key` |
| `hermes_messages_read` | Read recent messages (`session_key`, `limit`) |
| `hermes_attachments_fetch` | List non-text attachments (`session_key`, `message_id`) |
| `hermes_channels_list` | List sendable targets (`platform` filter) |
| `hermes_messages_send` | Send to `target` (`platform:chat_id`) |
| `hermes_events_poll` | Poll events since `after_cursor` |
| `hermes_events_wait` | Long-poll for next event |
| `hermes_permissions_list_open` | Pending approvals |
| `hermes_permissions_respond` | Respond `allow-once`/`allow-always`/`deny` |

## Procedure

1. **Discover:** `hermes_conversations_list` or `hermes_channels_list` to get `session_key` / `target`
2. **Read:** `hermes_messages_read` (limit 50, chronological)
3. **Act:** `hermes_messages_send` with `target: "telegram:123"` or `discord:#general`
4. **Poll:** `hermes_events_poll` / `hermes_events_wait` for live updates
5. **Gate:** check `hermes_permissions_list_open` before tool execution that needs approval

## Pitfalls

- `session_key` required for `messages_read` — get it from `conversations_list` first
- After editing `opencode.jsonc`, **restart opencode** (config not hot-reloaded)
- Hermes state lives at `%LOCALAPPDATA%\hermes` on Windows — not `~/.hermes`

## Verification

```bash
opencode mcp list                 # should show hermes: connected
opencode --version                # 1.18.23
bin/hermes.exe mcp serve --help
```
