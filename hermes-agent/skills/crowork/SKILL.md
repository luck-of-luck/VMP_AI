---
name: crowork
description: Sala colaborativa CROWORK — sessões compartilhadas com transcript e PTY espelhados.
version: 1.0.0
author: VMP-AI / luck-of-luck
license: MIT
metadata:
  hermes:
    tags: [collaboration, crowork, cowork, presence, session, kanban, gateway, desktop, tui, web]
    category: productivity
---

# CROWORK — Sala Colaborativa

Modo **CROWORK** (com R) — evolução do cowork clássico: **uma sala = um transcript + um PTY + presença ao vivo**. Todos que `join` veem as mesmas mensagens e o mesmo terminal, com quem está digitando.

Use quando o usuário disser: `crowork`, `sala compartilhada`, `pair programming`, `sessão colaborativa`, `vamos codar juntos`, `/crowork`.

## Quando Usar

- Usuário quer codar/pairar com outra pessoa ou outro agente no mesmo contexto
- Precisa de PTY espelhado (um roda `hermes --tui` e o outro vê em tempo real)
- Quer quadro visual (Web Board) + TUI + Desktop sincronizados

## How to Run

**CLI (no terminal):**
```bash
hermes crowork create ampliagro-sprint "Sprint Agro 5.0 — offline sync"
hermes crowork join ampliagro-sprint
hermes crowork status ampliagro-sprint
hermes crowork share ampliagro-sprint  # copia e envia no WhatsApp/Discord
hermes crowork list
hermes crowork leave ampliagro-sprint
# aliases: crow, cw
hermes crow create sala-01
hermes cw join sala-01
```

**TUI (chat):**
```
/crowork create sala-01
/crowork join sala-01
/crowork status
/crowork share sala-01
/crowork list
```

**Tools (agente):**
Use `crowork_create`, `crowork_join`, `crowork_list`, `crowork_status`, `crowork_share`, `crowork_leave` — toolset `crowork`. Dados em `HERMES_HOME/crowork/*.json` (get_hermes_home()).

## Interfaces — Todas já instaladas

1. **CLI** → `hermes_cli/crowork.py` (subcomandos create/join/leave/list/status/share/invite)
2. **TUI** → `/crowork` via COMMAND_REGISTRY (hermes_cli/commands.py) — mesmo transcript, PTY via `pty_bridge.py`
3. **Web** → `web/src/pages/CoworkPage.tsx` + `web/src/lib/crowork.ts` (board com salas, presença, convite)
4. **Desktop** → `apps/desktop/src/plugins/hermes-crowork/` (painel lateral presença + chat por sala, nanostore)
5. **Gateway** → salas funcionam de qualquer plataforma (Telegram/Discord/Slack) — convite é só `hermes crowork join <sala>`

## Procedure

1. Crie a sala: `hermes crowork create <nome> [tópico]`
2. Compartilhe: `hermes crowork share <nome>` (cole no grupo)
3. Cada coworker: `hermes crowork join <nome>` ou `/crowork join <nome>` no TUI
4. Codem juntos — todo `terminal`, `read_file`, `patch` aparece para todos da sala
5. Acompanhe: `hermes crowork status <nome>` (membros ativos nos últimos 5min)

## Pitfalls

- Salas são por `HERMES_HOME` (perfil). Se coworkers usam `HERMES_HOME` diferentes (ex: perfis separados), usem o mesmo gateway/cloud backend ou exportem `HERMES_HOME` compartilhado.
- Presença expira em 5min sem `join`/`status`. Re-join renova.
- Não use `git push --force` em sala compartilhada sem combinar.
- Plugin auto-loaded (`kind: backend`) — já ativo, não precisa habilitar em `hermes tools`.

## Verification

```bash
hermes crowork create teste-crowork "verificação"
hermes crowork join teste-crowork
hermes crowork status teste-crowork
hermes crowork list
# deve listar teste-crowork com membros
```
