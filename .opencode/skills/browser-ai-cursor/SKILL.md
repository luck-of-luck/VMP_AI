---
name: browser-ai-cursor
description: Navegador da IA com cursor, digitação, visão e gravação via MCP hermes.
---

# Browser-for-the-AI (Cursor + Insert + Analyze + Record)

> Navegador controlado pela própria IA, exposto ao OpenCode via o servidor MCP `hermes`
> (`bin/hermes.exe mcp serve`). A IA tem um **cursor** (coordenadas da viewport), pode
> **inserir** dados (digitar/clicar), **analisar** a tela (visão) e **gravar** a sessão em vídeo.

## Quando Usar

- O usuário pede para a IA "abrir o site X", "navegar", "preencher formulário",
  "clicar em tal botão", "ver a tela", "gravar o que acontece na página".
- Você (a IA) precisa de controle fino por coordenadas (canvas, mapas, jogos,
  CAPTCHAs, overlays) onde os refs `@eN` do snapshot não bastam.
- Precisa registrar uma sessão de navegação em vídeo para revisão/QA.

## Pré-requisitos

- MCP `hermes` habilitado em `opencode.jsonc` (`"enabled": true`) e `bin/hermes.exe` presente.
- Backend de navegador disponível (Chrome/Edge local ou provedor cloud). Verifique com
  `opencode mcp list` → `hermes: connected`.
- Para `browser_vision`, um modelo de visão configurado (senão o Hermes retorna erro claro).

## Como Usar (fluxo completo)

As ferramentas ficam disponíveis como ferramentas do servidor MCP `hermes`
(`hermes_browser_navigate`, `hermes_browser_pointer`, `hermes_browser_record`, etc. —
confirme os nomes exatos com `opencode mcp list` / `mcp__hermes__*`).

1. **Abrir a página** → `browser_navigate(url)` (inicializa a sessão).
2. **Enxergar a tela** → `browser_vision(question, annotate=true)` para obter as
   coordenadas dos elementos, ou `browser_snapshot()` para a árvore de acessibilidade (refs `@eN`).
3. **Agir com o cursor** → `browser_pointer(action="click", x, y)` / `"move"` / `"hover"` /
   `"double_click"` / `"drag"` / `"type"`.
4. **Inserir dados** → `browser_type(ref, text)` (por ref) ou `browser_pointer(action="type", x, y, text)`.
5. **Gravar** → `browser_record(action="start")` … agir … `browser_record(action="stop")`
   (retorna o caminho do `.webm`; compartilhe com `MEDIA:<path>`).
6. **Verificar** → `browser_vision(...)` novamente para confirmar o resultado visual.

## Referência Rápida

| Necessidade | Ferramenta |
|-------------|-----------|
| Abrir página | `browser_navigate(url)` |
| Texto da página (refs) | `browser_snapshot(full=false)` |
| Ver a tela com IA | `browser_vision(question, annotate=true)` |
| Clicar por ref | `browser_click(ref)` |
| Digitar por ref | `browser_type(ref, text)` |
| **Cursor: mover** | `browser_pointer(action="move", x, y)` |
| **Cursor: clicar** | `browser_pointer(action="click", x, y)` |
| **Cursor: digitar** | `browser_pointer(action="type", x, y, text)` |
| **Cursor: arrastar** | `browser_pointer(action="drag", x, y, to_x, to_y)` |
| Scroll / voltar / tecla | `browser_scroll(direction)` / `browser_back()` / `browser_press(key)` |
| **Gravar tela** | `browser_record(action="start"/"stop"/"status")` |

Coordenadas são em **pixels CSS relativos ao canto superior esquerdo da viewport**
(`x=0,y=0` = topo esquerdo). Use `browser_vision(annotate=true)` para mapear as
posições antes de clicar.

## Pitfalls

- Chame `browser_navigate` **antes** de qualquer outra ferramenta de browser.
- `browser_pointer(action="move")` apenas **inspeciona** o elemento sob o cursor (não clica);
  para interagir use `"click"`/`"type"`/`"drag"`.
- `browser_record` não funciona no backend Camofox; use Chrome/Edge local ou provedor cloud.
- Gravações ficam em `<HERMES_HOME>/browser_recordings/` e expiram após 72h.
- Após editar `opencode.jsonc`, **reinicie o OpenCode** (config não hot-reload).

## Verificação

- `opencode mcp list` → `hermes: connected`.
- `opencode mcp invoke hermes tools` (ou equivalente) deve listar
  `browser_navigate`, `browser_pointer`, `browser_record`, `browser_vision`, etc.
