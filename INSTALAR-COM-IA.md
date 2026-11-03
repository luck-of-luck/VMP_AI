# 🚀 VMP-AI — Instalar pedindo ajuda para OUTRA IA (PC fraco ou forte)

> Para quem está começando e o PC **não tem placa dedicada nem muita RAM**.
> O Ollama é **opcional, só para PCs fortes**. O padrão é **LITE** (nuvem grátis).

## 0) PROMPT PRONTO — cole numa outra IA (ChatGPT, Claude, Gemini, etc.)

```text
Me dê os comandos exatos, passo a passo, para instalar o VMP-AI no Windows 10/11
num PC FRACO (sem GPU dedicada, 4-8GB RAM), a partir do GitHub:

Repo: https://github.com/luck-of-luck/VMP-AI.git

Requisitos:
1) git clone do repo
2) setup em modo LITE (rápido, sem Ollama, sem baixar modelo pesado):
   setup.bat -lite   (ou: powershell -ExecutionPolicy Bypass -File setup.ps1 -Lite)
3) criar .env a partir de .env.example e preencher APENAS UMA chave grátis
   (CLINE_API_KEY em https://app.cline.bot OU OPENROUTER_API_KEY em https://openrouter.ai/keys)
4) instalar Node.js LTS + opencode (npm install -g opencode-ai) e garantir o
   Hermes Mode: opencode.jsonc já tem o bloco "hermes" -> bin/hermes.exe mcp serve
5) verificação final: hermes --version, opencode mcp list (tem que mostrar hermes),
   setup.ps1 -VerifyOnly

Se o PC for FORTE (16GB+ RAM, GPU), inclua no final a seção OPCIONAL:
setup.ps1 -WithOllama + ollama pull qwen2.5:14b + ollama serve.

Me devolva só comandos PowerShell prontos para colar, na ordem, sem enrolar.
```

## 1) Instalação LITE (PC fraco — recomendado)

```powershell
git clone https://github.com/luck-of-luck/VMP-AI.git
cd VMP-AI
.\setup.bat -lite
notepad .env   # preencha CLINE_API_KEY ou OPENROUTER_API_KEY, salve
.\Abrir-OpenCode.bat   # valida Hermes Mode (mostra hermes ✓ connected)
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -VerifyOnly
```

| Etapa | O que faz no LITE |
|-------|-------------------|
| 1 | Valida Python 3.11–3.13 (winget se faltar) |
| 2 | Instala `uv`, sync mínimo (`-Lite` usa só extra `mcp`) |
| 3 | Gera `bin\hermes.exe`, cria `.env` do `.env.example` |
| 4 | **PULA Ollama** (sem `ollama pull`, sem 8–20GB) |
| 5 | **[7] Garante OpenCode + Hermes Mode**: instala `opencode-ai` se `-WithOpenCode`, valida `opencode.jsonc` tem `"hermes"` + `opencode mcp list` |

## 2) Como sei que funcionou (checklist)

```powershell
.\hermes-agent\venv\Scripts\hermes.exe --version   # mostra versão
opencode mcp list                                   # tem que listar: hermes ✓ connected
powershell -File .\setup.ps1 -VerifyOnly           # Perfil: LITE (PC fraco)
```

- `Abrir-Hermes.bat` → CLI responde (usa Cline/OpenRouter :free, fallback automático).
- `Abrir-PROTON.bat` → interface PROTON v3 abre mesmo sem gateway (modo offline).
- Sem chave API e sem Ollama o agente **não responde** — o setup avisa em amarelo.

## 3) OPCIONAL — PC forte (Ollama local, offline, ilimitado)

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -WithOllama
ollama pull qwen2.5:14b    # PC modesto (~8GB) — NÃO baixe o 32b sem 16GB+ RAM
ollama serve               # geralmente já inicia sozinho
```

Só faça isso com **16GB+ RAM** (modelo 32b) ou **8GB** (modelo 14b). No PC fraco, **não instale**.

## 4) Problemas comuns (respostas curtas)

| Erro | Causa | Comando |
|------|-------|---------|
| `hermes.exe travou uv sync (erro 32)` | Hermes/Gateway aberto | Feche tudo, rode `setup.bat -lite` de novo |
| `opencode não reconhecido` | Sem Node | Instale Node LTS https://nodejs.org/ → `npm install -g opencode-ai` |
| `opencode mcp list` sem hermes | Primeira vez | Abra `opencode` uma vez na raiz (lê `opencode.jsonc`), depois `opencode mcp list` |
| `400 invalid_encrypted_content / was not issued` | Blob selado após troca de provider | Já corrigido: fallback desliga replay + retry sem blob (veja `agent/chat_completion_helpers.py`) |
| Python ausente | Sem PATH | `winget install Python.Python.3.12` → feche/reabra terminal → `setup.bat -lite` |

## 5) Arquivos de referência

- `setup.ps1 -Lite/-WithOllama/-WithOpenCode` · `setup.bat -lite` · `.env.example`
- `opencode.jsonc` (bloco `mcp.hermes` → `bin/hermes.exe mcp serve`)
- `config.yaml` (fallback termina em `ollama-local` — último, só PC forte)
- `proton/index.html` (PROTON v3 — buffer-arquivo, lab local, supervisor por IA)
