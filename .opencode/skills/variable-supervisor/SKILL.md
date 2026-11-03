---
name: variable-supervisor
description: Supervisiona adesão de variáveis globais entre Hermes e OpenCode. Use quando variáveis desincronizadas, env drift, fallback diverge.
---

# Variable Supervisor — Adesão Fluida

Supervisiona e sincroniza variáveis globais entre `HERMES_HOME/.env` (SSOT) e `opencode` (auth + provider env). Torna o sistema fluido: um segredo, um lugar.

## Quando usar

- `env drift`, `fallback diverge`, `variáveis globais`, `adesão`, `sync`
- Erro `401` no openrouter enquanto Hermes tem key válida
- `hermes mcp serve` falha por `HERMES_HOME` path stale

## Supervisão (3 camadas)

**Camada 0 — Observer** `hermes_cli/env_supervisor.py:validate_supervised_env`:
- Checa `OPENROUTER_API_KEY` prefixo `sk-or-`, `OPENCODE_ZEN_API_KEY`, `COPILOT_GITHUB_TOKEN`
- Compara `config.yaml:fallback_model` vs `plugins/fallback-router.ts:FALLBACK_CHAIN`
- Valida `mcp.hermes.command` existe e `permission.external_directory` protege `.env`

**Camada 1 — Sync automático** `sync.opencode_env:true` em `hermes/config.yaml:251`:
- `load_hermes_dotenv()` chama `sync_opencode_env()` após cada reload
- Copia `OPENROUTER_API_KEY, OPENCODE_ZEN_API_KEY, COPILOT_GITHUB_TOKEN, GH_TOKEN, GITHUB_TOKEN` para `~/.config/opencode/.env` e `~/.local/share/opencode/.env` (nunca em `opencode.jsonc`)
- Fallback chain sync: edite só `hermes/config.yaml:fallback_model`; rode `hermes cron run --now` para propagar (ou deixe o watcher fazer)

**Camada 2 — UX**
- `hermes doctor` reporta A1-A7 como `ConfigIssue`
- Cron `supervision-30m` valida a cada 30m e avisa no `gateway toast` se esgotado

## Comandos

```bash
# validar manualmente
python -c "from hermes_cli.env_supervisor import validate_supervised_env; print(validate_supervised_env())"

# forçar sync
python -c "from hermes_cli.env_supervisor import sync_opencode_env; print(sync_opencode_env())"

# ver sync
cat ~/.config/opencode/.env
cat $LOCALAPPDATA/hermes/.env

# checar MCP
opencode mcp list | grep hermes
```

## Pitfalls

- **Nunca** coloque segredo em `opencode.jsonc` — só em `.env` (gitignored, já protegido por `external_directory:deny`)
- Após editar `config.yaml:fallback_model`, edite também `fallback-router.ts` ou o validator vai alertar A4
- `HERMES_HOME` custom (`profiles/<name>` ou `/opt/data`) exige atualizar `opencode.jsonc:mcp.hermes.command` — o supervisor detecta A5

## Verificação

```bash
hermes memory status # holographic active
hermes curator status # 1d consolidate:on
opencode mcp list # ✓ hermes connected
```
