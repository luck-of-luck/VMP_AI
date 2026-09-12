<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1A1A2E,50:16213E,100:0F3460&height=220&section=header&text=VMP--AI&fontSize=72&fontColor=FFFFFF&fontAlignY=34&desc=Hermes%20Agent%20%C2%B7%20Local-First%20%C2%B7%20CROWORK%20%C2%B7%20Fallback%20Inteligente&descSize=16&descAlignY=58&animation=fadeIn" width="100%" />

<div align="center">

[![Typing SVG](https://readme-typing-svg.herokuapp.com?font=Fira+Code&weight=600&size=20&duration=2800&pause=700&color=FF6B35&center=true&vCenter=true&width=880&lines=Agente+IA+Aut%C3%B4nomo+%2B+Mem%C3%B3ria+%2B+Skills;%2B+CROWORK+%E2%80%94+sala+compartilhada+transcript%2BPTY;%2B+Fallback+Sagrado%3A+OmniRoute+%E2%86%92+InferX+%E2%86%92+Z.AI+%E2%86%92+Ollama;Clone+%26+Use%3A+setup.bat+%E2%86%92+.env+%E2%86%92+Abrir-Hermes.bat)](https://git.io/typing-svg)

<p>
  <a href="LICENSE"><img src="https://img.shields.io/badge/Licença-MIT-0F3460?style=for-the-badge" /></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.11–3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" /></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img src="https://img.shields.io/badge/Base-NousResearch%2Fhermes--agent-8A2BE2?style=for-the-badge" /></a>
  <a href="hermes-agent/skills/crowork/SKILL.md"><img src="https://img.shields.io/badge/CROWORK-ativo-FF6B35?style=for-the-badge&logo=webrtc&logoColor=white" /></a>
  <img src="https://img.shields.io/badge/OmniRoute-3.8.48-00C853?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Book4_Ultra-U7_155H_%2B_RTX4050-1428A0?style=flat-square&logo=samsung&logoColor=white" />
</p>

<p>
  <img src="https://skillicons.dev/icons?i=python,ts,js,react,tailwind,docker,git,github,linux,vscode&theme=dark" /><br>
  <img src="https://img.shields.io/badge/Hermes-Agente-0F3460?style=flat-square" /> <img src="https://img.shields.io/badge/OpenCode-MCP-007ACC?style=flat-square&logo=visualstudiocode&logoColor=white" /> <img src="https://img.shields.io/badge/OmniRoute-Router-0F3460?style=flat-square" /> <img src="https://img.shields.io/badge/CROWORK-sala_compartilhada-FF6B35?style=flat-square" /> <img src="https://img.shields.io/badge/N8N-automações-EA4B71?style=flat-square&logo=n8n&logoColor=white" />
</p>

</div>

> **Agente de IA autônomo, local-first e pronto para produção.** Baseado no [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research), com **CROWORK colaborativo**, **fallback inteligente com IAs grátis** (OmniRoute • InferX • Z.AI • Nvidia • Ollama) e fluxo **clone & use**.

---

## 🎨 Arquitetura Visual — VMP-AI

```mermaid
flowchart TB
    subgraph Core["🧠 Hermes Core (Python 3.11+)"]
        A[run_agent.py<br/>AIAgent loop]
        B[model_tools.py<br/>+ registry]
        C[hermes_state.py<br/>SQLite + FTS5]
        D[toolsets.py<br/>narrow waist]
    end
    subgraph Interfaces["🖥️ Interfaces — Todas Ativas"]
        TUI["TUI Ink<br/>hermes --tui"]
        CLI["CLI<br/>hermes / crowork / kanban"]
        WEB["Web Dashboard<br/>/cowork, /chat"]
        DESKTOP["Desktop Electron<br/>hermes-crowork"]
        GW["Gateway<br/>Telegram/Discord/Slack/WA"]
    end
    subgraph VMP["⚡ VMP-AI Extras"]
        OCODE["OpenCode MCP<br/>bin/hermes.exe mcp serve"]
        CROWORK["CROWORK<br/>plugins/crowork<br/>skills/crowork"]
        OMNI["OmniRoute 20128<br/>combos grátis"]
        N8N["n8n MCP<br/>workflows"]
    end
    A --> TUI & CLI & WEB & DESKTOP & GW
    B --> CROWORK
    D --> OCODE
    OCODE <--> A
    CROWORK <--> GW
    OMNI --> A
    N8N --> A
    style CROWORK fill:#FF6B35,stroke:#0F3460,color:#fff
    style OMNI fill:#00C853,stroke:#0F3460,color:#fff
    style A fill:#0F3460,stroke:#FF6B35,color:#fff
```

```mermaid
mindmap
  root((VMP-AI))
    CROWORK
      CLI hermes crowork
      TUI /crowork
      Web /cowork
      Desktop hermes-crowork
      Tools crowork_*
      Skill crowork
    Fallback Sagrado
      OmniRoute combos
      InferX DeepSeek V4 Flash
      Z.AI GLM 5.2
      Nvidia NIM
      OpenRouter :free
      Ollama local
    Skills 80+
      vortex
      github
      opencode
      research
    Gateway
      Telegram
      Discord
      WhatsApp
      Slack
```

---

## 👥 CROWORK — Sala Colaborativa (nativo e permanente)

> **Uma sala = um transcript + um PTY espelhado + presença ao vivo.** Crie `ampliagro-sprint` e todos veem o mesmo chat e terminal.

```mermaid
flowchart LR
    U1[Você<br/>TUI] <--> ROOM[(Sala<br/>ampliagro-sprint<br/>HERMES_HOME/crowork/*.json)]
    U2[Coworker<br/>Desktop] <--> ROOM
    U3[Agente<br/>opencode] <--> ROOM
    U4[Telegram<br/>Gateway] <--> ROOM
    ROOM <--> PTY[PTY Espelhado<br/>pty_bridge.py]
    PTY <--> TR[Transcript<br/>SessionDB]
    style ROOM fill:#FF6B35,stroke:#0F3460,color:#fff
    style PTY fill:#0F3460,stroke:#FF6B35,color:#fff
```

**Todas as interfaces (já instaladas):**

| Interface | Comando | Arquivo |
|---|---|---|
| **CLI** | `hermes crowork create/join/list/status/share` (aliases `crow`, `cw`) | `hermes_cli/crowork.py` |
| **TUI** | `/crowork create sala-01` | `hermes_cli/commands.py` |
| **Web** | `/cowork` → Cowork Board | `web/src/pages/CoworkPage.tsx` |
| **Desktop** | painel `hermes-crowork` | `apps/desktop/src/plugins/hermes-crowork/` |
| **Tools** | `crowork_create`, `crowork_join`, ... | `plugins/crowork/` |
| **Skill** | `crowork` | `skills/crowork/SKILL.md` |

**Auto-start:** `Iniciar.ps1` + `Abrir-Hermes.bat` + `Abrir-Hermes-TUI.bat` criam/entram em `ampliagro-sprint` automaticamente. Dados em `HERMES_HOME/crowork/`.

---

## ⚡ Fallback Inteligente — IAs Grátis (Robson Vibe Coding)

```mermaid
flowchart LR
    REQ[Prompt] --> OMNI[OmniRoute<br/>fogueteiros-coding<br/>teste-um<br/>:20128]
    OMNI -->|fail 429/quota| INFERX[InferX<br/>DeepSeek V4 Flash<br/>1M ctx]
    INFERX -->|fail| ZAI[Z.AI<br/>GLM 5.2]
    ZAI -->|fail| NVIDIA[Nvidia NIM<br/>Llama 3.1 8B]
    NVIDIA -->|fail| CLINE[Cline<br/>minimax/m2.5]
    CLINE -->|fail| OR[OpenRouter<br/>:free]
    OR -->|fail| LOCAL[Ollama<br/>qwen2.5-coder:32b<br/>100% offline]
    style OMNI fill:#00C853,stroke:#fff,color:#fff
    style LOCAL fill:#0F3460,stroke:#FF6B35,color:#fff
```

**Vídeos que viraram código (canal Robson Oliveira — Vibe Coding):**

| Vídeo | O que virou `config.yaml` |
|---|---|
| `6pEmC9aAkQU` Hermes + OmniRoute | `providers.omniroute → 20128/v1`, combos `fogueteiros-coding` |
| `SciHyoqtUmk` DeepSeek V4 Flash InferX | `providers.inferx → api.inferx.net/v1` |
| `1QH-cKRuyuM` GLM 5.2 Z.AI | `providers.zai → api.z.ai/paas/v4` |
| `bOuC3RHpBak` Nvidia NIM grátis | `providers.nvidia → integrate.api.nvidia.com/v1` |

> Nunca trava em `429/402/quota` — troca e avisa: *“Modelo X esgotou, trocando para Y”*.

---

## 🧱 Estrutura do repositório

```
VMP-AI/
├─ hermes-agent/          # código-fonte do Hermes Agent (upstream, MIT)
│  ├─ skills/             # 16 categorias, 80+ skills (vortex, github, opencode...)
│  ├─ plugins/crowork/    # ★ CROWORK (6 tools)
│  └─ opencode.jsonc      # config opencode upstream (usa ../bin/hermes.exe)
├─ .opencode/
│  └─ skills/vortex-hermes/ # BRIDGE VMP-AI: opencode + Hermes (este repo)
├─ proton/                # PROTON — JARVIS app (RTX + neon + fluid, index.html)
├─ crowork/               # ★ salas compartilhadas (ampliagro-sprint.json)
├─ config.yaml            # fallback inteligente (OmniRoute → InferX → Z.AI → Ollama)
├─ opencode.jsonc         # CONFIG PRINCIPAL — Hermes MCP + omniroute/inferx/zai/nvidia + crowork
├─ setup.bat / setup.ps1  # instalador 1-clique (valida 10 checks)
├─ Iniciar.ps1            # launcher interativo + Ensure-Crowork
├─ Abrir-Hermes.bat       # CLI + auto CROWORK
├─ Abrir-Hermes-TUI.bat   # TUI + auto CROWORK
├─ Abrir-OpenCode.bat     # OpenCode na raiz + CROWORK
└─ SOUL.md                # persona + CROWORK nativo
```

> 🔒 **Privacy-first:** segredos, sessões, memórias, bancos de dados e caches **não** são versionados (veja `.gitignore`).

---

## ✅ Pré-requisitos

- Windows 10/11 com **PowerShell 5.1+** (nativo) — ou WSL2/Linux
- Conexão na **primeira execução** (para baixar Python, `uv` e dependências)
- (Opcional, para OpenCode) **Node.js + npm**

---

## 🚀 Instalação — *clone & use*

**Opção A — Duplo-clique (recomendado):**
```powershell
git clone https://github.com/luck-of-luck/VMP-AI.git
cd VMP-AI
# Duplo-clique em setup.bat  (ou: powershell -ExecutionPolicy Bypass -File setup.ps1)
# Edite .env e preencha PELO MENOS UMA: OMNIROUTE_API_KEY, INFERX_API_KEY, CLINE_API_KEY ou OPENROUTER_API_KEY
# 100% offline: instale Ollama (https://ollama.com) e pule chave
# Pronto! Abrir-Hermes.bat  (já entra em crowork/ampliagro-sprint)
```

**Opção B — Terminal:**
```powershell
git clone https://github.com/luck-of-luck/VMP-AI.git
cd VMP-AI
powershell -ExecutionPolicy Bypass -File .\setup.ps1
notepad .env
.\Abrir-Hermes.bat
```

| Etapa | O que faz |
|-------|-----------|
| 1 | Valida / instala **Python 3.11–3.13** |
| 2 | Instala **uv** (Astral) |
| 3 | `uv sync` + gera `bin\` (hermes, hermes-acp) |
| 4 | Cria `.env` + wizard de chaves |
| 5 | Verifica **Node/opencode** e **Ollama/LM Studio** (grátis) |
| 6 | **CROWORK** — cria `crowork/ampliagro-sprint.json` |

> `setup.bat -Extras "messaging,mcp"` / `setup.ps1 -WithN8nMCP`.

---

## 🖥️ Primeiros passos (com CROWORK)

```powershell
# CLI já no crowork
.\Abrir-Hermes.bat
/crowork status ampliagro-sprint
/crowork share ampliagro-sprint  # envia no WhatsApp

# TUI
.\Abrir-Hermes-TUI.bat  # já faz crowork join ampliagro-sprint

# Launcher interativo
powershell -File Iniciar.ps1  # 1) OpenCode RAIZ (já com crowork)
```

### OpenCode + Hermes — editor IA com skills e MCP

```powershell
npm install -g opencode-ai
opencode                     # TUI (ou: Abrir-OpenCode.bat)
opencode mcp list            # hermes ✓ connected
```

**`opencode.jsonc` já vem com:**
- **MCP `hermes`** (`bin/hermes.exe mcp serve`) — 80+ skills + `crowork_*`
- **Providers:** `omniroute`, `inferx`, `zai`, `nvidia`, `cline`, `openrouter`, `ollama-local`, `lmstudio-local`
- **Instructions:** `SOUL.md` + `hermes-agent/AGENTS.md` + `skills/crowork/SKILL.md`

---

## 🧠 Esquema inteligente + visão de tela

- **Modelo principal:** **OmniRoute combo** → **InferX DeepSeek V4 Flash** → **MiniMax M2.5 via Cline** (1M ctx)
- **Leitura de tela:** `auxiliary.vision` via `cline/openai/gpt-4o` → `browser_vision`
- **Contextos enormes:** `context_file_max_chars: 400k`, `tool_output: 150k`

## 🔌 Todas as IAs do seu PC (fallback)

| Ordem | IA | Chave |
|------|-----|-----------|
| 1-2 | **OmniRoute combos** (`fogueteiros-coding`, `teste-um`) | `OMNIROUTE_API_KEY` |
| 3 | **InferX DeepSeek V4 Flash** (1M) | `INFERX_API_KEY` |
| 4 | **Z.AI GLM 5.2** | `ZAI_API_KEY` |
| 5 | **Nvidia NIM** (Llama/GLM) | `NVIDIA_API_KEY` |
| 6-8 | **Cline** (minimax/deepseek/ClinePass) | `CLINE_API_KEY` |
| 9 | **Copilot** (gpt-4.1) | `GH_TOKEN` |
| 10-11 | **Claude / Kimi** | `ANTHROPIC_API_KEY` / `KIMI_API_KEY` |
| 12-15 | **OpenRouter :free** (auto-router) | `OPENROUTER_API_KEY` |
| 16 | **LM Studio** `:1234` | app local |
| 17-20 | **Ollama** `qwen2.5-coder:32b` | `ollama serve` (offline) |

```bash
# Delegar para outros CLIs:
claude -p "implemente X"
opencode run "implemente X"
# ou dentro do crowork:
hermes crowork share ampliagro-sprint
```

---

## ⚙️ Configuração

| Arquivo | Finalidade |
|---------|-----------|
| `.env` | Chaves API (`OMNIROUTE`, `INFERX`, `ZAI`, `NVIDIA`, `CLINE`, `OPENROUTER`...) |
| `config.yaml` | Modelos + fallback + memória + crowork |
| `opencode.jsonc` | MCP Hermes ↔ OpenCode + providers espelhados |
| `SOUL.md` | Persona + CROWORK nativo e permanente |
| `crowork/*.json` | Salas compartilhadas (`ampliagro-sprint.json`) |

---

## 🧭 Comandos úteis

| Comando | Ação |
|---------|------|
| `hermes crowork create <sala> [tópico]` | Cria sala (aliases `crow`, `cw`) |
| `hermes crowork join <sala>` | Entra (espelha transcript/PTY) |
| `hermes crowork list/status/share` | Gerencia salas |
| `/crowork` | No chat TUI |
| `/cowork` | No Web Dashboard |
| `hermes --tui` | TUI completa |
| `omniroute serve` | Inicia router local (20128) |
| `hermes mcp serve` | Servidor MCP |
| `hermes gateway setup` | Telegram/Discord/WA |

---

## 🔐 Privacidade & segurança

- `.gitignore` robusto: `.env`, `auth.json`, `crowork/*.json` privados **não** entram no Git (salas são locais por `HERMES_HOME`).
- Roda **localmente** — você controla chaves e dados.
- Aprovação `smart` para comandos destrutivos.

---

## 📊 Stack Visual

<div align="center">
<img src="https://skillicons.dev/icons?i=python,ts,js,react,tailwind,postgres,redis,docker,git,github,linux,vscode,nodejs&theme=dark" />
<br>
<img src="https://img.shields.io/badge/PROTON-JARVIS-FF6B35?style=for-the-badge" /> <img src="https://img.shields.io/badge/Ampliagro_OS-Bento-0F3460?style=for-the-badge" /> <img src="https://img.shields.io/badge/Book4_Ultra-Offline_First-1428A0?style=for-the-badge" />
</div>

---

## 🛟 Solução de problemas

- **Antivírus acusa `uv.exe`:** falso positivo (Rust Astral). Exclua `bin\`.
- **`hermes` não reconhecido:** `setup.bat` ou `hermes-agent\venv\Scripts\hermes.exe`.
- **`setup.bat` pisca:** `powershell -ExecutionPolicy Bypass -File setup.ps1`.
- **OmniRoute não conecta:** `omniroute serve --daemon` + cheque `http://localhost:20128`, `OMNIROUTE_API_KEY` em `.env`.
- **CROWORK não aparece:** `hermes tools list | findstr crowork` → deve estar `✓ enabled`. Reinicie Hermes após editar `toolsets.py`.
- **Sem chave API?** `ollama pull qwen2.5-coder:32b` → 100% offline.

---

## 📜 Licença & créditos

- Este repo: **MIT** © 2026 VMP-AI ([LICENSE](LICENSE)).
- `hermes-agent/`: **MIT** © Nous Research — [repositório oficial](https://github.com/NousResearch/hermes-agent).

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0F3460,50:16213E,100:1A1A2E&height=120&section=footer&text=VMP--AI+%C2%B7+CROWORK+%C2%B7+Fallback+Sagrado&fontSize=18&fontColor=FF6B35" width="100%" />
