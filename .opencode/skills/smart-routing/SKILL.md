---
name: smart-routing
description: Use when token/rate-limit/credit exhausted or need intelligent multi-model fallback. Triggers on 429, quota, billing, fallback, tokens esgotados, trocar ia.
---

# Smart Routing — Troca Inteligente ao Esgotar Tokens

Use esta skill quando qualquer IA esgotar tokens, créditos, rate-limit (429), 402, 529/503 ou `context_length_exceeded`. Ela implementa a cadeia de fallback configurada em `opencode.jsonc:plugin/fallback-router.ts` e `hermes/config.yaml:fallback_model`.

## Cadeia (ordem = barato após forte)

1. `opencode/claude-sonnet-4-5` — primário (Zen, forte)
2. `openrouter/anthropic/claude-sonnet-4-5` — mesmo modelo via OpenRouter (outra conta)
3. `openrouter/google/gemini-3-flash` — rápido e barato (bom para 80% das tarefas)
4. `opencode/claude-haiku-4-5` — leve Zen
5. `github-copilot/gpt-4.1` — Copilot OAuth (`gho_***` já em `auth.json`)
6. `openrouter/meta-llama/llama-3.3-70b-instruct:free` — free tier, último recurso offline

> Esta cadeia espelha `config.yaml:fallback_model` — mantenha sincronizado.

## Quando usar

- Erro contém `429`, `rate limit`, `quota`, `credit`, `402`, `billing`, `exhausted`, `context length`, `overloaded`, `529`, `503`
- Usuário diz "trocar ia", "usar outra inteligência", "tokens acabaram"
- Modelo atual demorando ou retornando vazio repetidamente

## Procedimento (OpenCode)

1. Detecte o erro exato (`tool.execute.after` ou `event` com `isExhaustionError`)
2. Avise: `Modelo X esgotou (429), trocando para Y`
3. Troque via `/models` ou `client.session.update(sessionID, {model: next})`
4. Refaça a chamada **uma vez** no novo modelo; se falhar, vá para o próximo da cadeia
5. Nunca faça loop infinito no mesmo modelo; no máximo `FALLBACK_CHAIN.length` tentativas

Exemplo no TUI:
```
/models
# selecione openrouter/google/gemini-3-flash
refaça o prompt
```

## Procedimento (Hermes)

Hermes já faz isso **automaticamente** — `config.yaml:fallback_model` (ver `agent/agent_init.py:1564`).
Não precisa skill: basta ter as chaves no arquivo `.env`:
```
OPENROUTER_API_KEY=sk-or-v1-***
OPENCODE_ZEN_API_KEY=sk-***
COPILOT_GITHUB_TOKEN=gho_***
```
Ao esgotar, Hermes loga `🔄 Fallback chain (4): ... → ...` e tenta o próximo sem intervenção.

## Uso inteligente de múltiplas skills/ferramentas

- **Hermes**: não habilite todas as toolsets de uma vez (quebra prompt caching — `toolsets.py`). Use `hermes tools` (curses) e deixe `tool_search` (BM25) achar a tool certa. Instale skills sob demanda:
  ```bash
  hermes skills search github
  hermes skills install official/github/github-cli
  hermes skills install official/productivity/* 
  ```
  Skills são lazy-loaded via `/skills` — só as necessárias entram no prompt.

- **OpenCode**: skills em `~/.config/opencode/skills/*/SKILL.md` são carregadas se `description` bater com o prompt. Mantenha `description` curta (≤60c) e com keywords literais. Use:
  ```bash
  opencode mcp list                 # ver hermes, context7, grep
  # habilite grep/context7 só quando precisar (enabled: false -> true)
  ```

- **Regra geral**: ative `lsp: true` e `formatter: true` já estão ligados nos `opencode.jsonc`; adicione MCPs com `enabled: false` e ligue por demanda (`grep`, `sentry`). Evite 10+ MCPs simultâneos — cada um adiciona tokens em todo request (ver `docs/mcp-servers#cautions`).

## Verificação

```bash
# Hermes
hermes config | findstr Fallback
hermes mcp list                 # hermes mcp serve deve estar ok
hermes skills list | findstr opencode

# OpenCode (na raiz hermes)
opencode mcp list               # ✓ hermes connected
opencode --version              # 1.18.23
# teste fallback: force 429 simulando modelo inválido
opencode run --model openrouter/invalid-model "teste" 
# deve cair para próximo da cadeia e logar [fallback-router]
```
