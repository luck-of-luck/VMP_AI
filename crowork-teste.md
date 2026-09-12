# 🧪 CROWORK Teste — ampliagro-sprint

**Sala:** `ampliagro-sprint` (id=ba35a1b2)  
**Data:** 2026-09-12  
**Criado via:** CROWORK (transcript + PTY espelhados)  
**Por:** VORTEX AI (Hermes) + opencode (VMP-AI)

## Objetivo
Verificar se o modo CROWORK espelha corretamente:
- ✅ Transcript compartilhado (esta mensagem aparece para todos que deram `join`)
- ✅ PTY espelhado (comandos no terminal aparecem para todos)
- ✅ Presença ao vivo (quem está ativo nos últimos 5min)
- ✅ Fallback VMP-AI com OmniRoute saudável

## Teste 1 — Presença
```bash
hermes crowork status ampliagro-sprint
# ou no TUI: /crowork status ampliagro-sprint
# ou via tool: crowork_status(room="ampliagro-sprint")
```

## Teste 2 — Arquivo compartilhado
Este arquivo foi criado **dentro do crowork** via:
```bash
# CLI
hermes crowork join ampliagro-sprint

# Depois, qualquer comando é espelhado:
echo "# teste" > crowork-teste.md
git add crowork-teste.md && git commit -m "test: crowork espelhado"
```

Todos que estão na sala veem o mesmo `terminal` e `read_file` em tempo real.

## Teste 3 — Fallback com OmniRoute
```
OmniRoute 3.8.48 healthy (http://localhost:20128)
Modelos: 45+ (nemotron-ultra 550b, minimax-m3, kimi-k2.5, gpt-5.4...)
Fallback: omniroute/fogueteiros-coding → inferx/deepseek-v4-flash → zai/glm-5.2 → nvidia → cline → openrouter:free → ollama
```

## Próximo passo
Segunda pessoa entra com:
```bash
hermes crowork join ampliagro-sprint
# ou TUI: /crowork join ampliagro-sprint
# ou Web: /cowork → selecionar ampliagro-sprint → Entrar
# ou Desktop: painel hermes-crowork → selecionar → Entrar
```

Convite universal: `hermes crowork join ampliagro-sprint`

---
*Gerado automaticamente pelo teste CROWORK — se você vê este arquivo, o espelhamento funcionou.*
