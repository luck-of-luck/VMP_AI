---
name: 9router-free
description: Use when working with free/`:free` AI models through 9Router on localhost:20128 — auditing which free models actually work, the GRATIS-CODING combo, interpreting 429 vs 404 on free tiers, or wiring a free model into opencode. Encodes measured free-tier failure signatures and the re-audit procedure.
license: MIT
metadata:
  measured_on: "2026-10-03"
  router_version: "0.5.40"
---

# Free models no 9Router

O 9Router é um **roteiro de LLM** (OpenAI/Claude-compatible) em
`http://localhost:20128`. Ele **não tem** conceito de agente, MCP ou skill —
configurar MCP dentro dele não existe. Isso vive no cliente (opencode,
claude-code). Confundir os dois é o erro mais comum aqui.

## O free tier apodrece. Meça, não acredite.

**Medido em 2026-10-03:** dos 11 modelos marcados `:free`, **só 5 responderam.**

| Modelo free | Estado medido |
|---|---|
| `nvidia/nemotron-3-ultra-550b-a55b:free` | OK 591ms |
| `nvidia/nemotron-3-super-120b-a12b:free` | OK 488ms |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | OK 488ms |
| `cohere/north-mini-code:free` | OK 378ms |
| `poolside/laguna-s-2.1:free` | OK 1191ms |
| `inclusionai/ling-3.0-flash:free` | **404** virou pago |
| `poolside/laguna-m.1:free` | **404** sem endpoint |
| `poolside/laguna-xs-2.1:free` | **429** |
| `google/gemma-4-26b-a4b-it:free` | **429** |
| `google/gemma-4-31b-it:free` | **429** |
| `nvidia/nemotron-3-nano-30b-a3b:free` | **429** |

O catálogo anuncia o que *existiu*. Trate a lista como hipótese, não fato.

## Como ler um 404 no free tier

O 404 do OpenRouter no free tier **não é bug de rota**. A mensagem diz o que
aconteceu:

```
404 "This model is unavailable for free. The paid version is available now
     - use this slug instead: nvidia/..."
```

O provedor **repromoveu** o modelo do tier gratuito. Repetir a chamada com o
mesmo id não resolve — não é rate limit, a porta fechou. Some da lista.

Já `410 Gone` é o provedor inteiro fora (foi o caso do `nvidia/*` direto, todos
os 8). E `404 page not found (reset after 29s)` num endpoint local é o proxy
local, não o modelo.

## O combo GRATIS-CODING

Criado no 9Router, `fallbackStrategy: round-robin`:

```
kr/claude-sonnet-4.5                                            (Kiro)  1834ms
kr/claude-sonnet-4                                              (Kiro)  1029ms
openrouter/nvidia/nemotron-3-ultra-550b-a55b:free                       568ms
openrouter/cohere/north-mini-code:free                                  402ms
openrouter/nvidia/nemotron-3-super-120b-a12b:free                       477ms
openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free           499ms
openrouter/poolside/laguna-s-2.1:free                                   721ms
```

**Por que 2 modelos do Kiro:** os 5 do OpenRouter dependem da **mesma
conexão**. Um `429` lá leva todos. O Kiro é uma conexão separada e carrega
**2 de 7 = 29% do round-robin**. É a redundância real do combo.

**round-robin, e não fusion:** `fusion` faz fan-out e multiplica latência e
cota. Em tier gratuito isso é contraproducente — o consumo de um `:free` é o
que gera o `429` que você está tentando evitar.

## O Kiro não é grátis — é creditado

A resposta traz `usage.kiro_credits` (medido `0.017475` por chamada). O README
do 9Router vende Kiro como "free Claude unlimited"; o dado observado é
**consumível**. Trate como grátis-com-cota-mensal, não como ilimitado. Ele
entra no combo pelo **roteamento independente**, não por custo zero.

## Bug do 9Router: variantes `thinking` e `agentic` do Kiro estão quebradas

Todas as 8 variações falham com `400 "Improperly formed request"` /
`REQUEST_BODY_INVALID`, de forma consistente:

```
kr/auto-thinking              400      kr/claude-sonnet-4.5-thinking           400
kr/claude-sonnet-4.5-agentic  400      kr/claude-sonnet-4-thinking-agentic     400
kr/claude-sonnet-4-agentic    400      kr/claude-sonnet-4.5-thinking-agentic   400
```

Só os modelos **sem** sufixo funcionam: `kr/auto`, `kr/claude-sonnet-4.5`,
`kr/claude-sonnet-4`. Não monte combo com as variantes.

## O 9Router não devolve JSON puro — dois formatos

Isso **quebra scripts** e não é óbvio. Ambos chegam com
`content-type: text/event-stream`, **mesmo sem `stream: true`**:

1. **Via OpenRouter:** um objeto `chat.completion` normal **com
   `data: [DONE]\n\n` colado no fim**. `JSON.parse` quebra perto do final
   ("Unexpected non-whitespace character after JSON").
2. **Via Kiro:** SSE de verdade, vários `data: {...}\n\n`.

Consequência: **veredito por `JSON.parse` é frágil.** Classifique pelo
**status HTTP**, que é o único sinal confiável. `audit-free-models.cjs` tem um
`readBody()` que lida com os dois — copie dele, não do zero.

## Vereditos NÃO são estáveis — meça duas vezes

Duas rodadas em minutos, mesmo host:

| Modelo | Rodada 1 | Rodada 2 |
|---|---|---|
| `nvidia/nemotron-3-nano-30b-a3b:free` | 404 "virou pago" | **429** |
| `poolside/laguna-m.1:free` | 404 "sem endpoint" | **429** |

**Uma falha isolada não prova que um modelo morreu.** Só `GONE` com o texto
*"use this slug instead"* indica que o provedor tirou o modelo do free.
Qualquer outro 404/429 é transiente. Reincidência é o que prova.

## Re-auditar (faça antes de confiar de novo)

O free tier muda sem aviso. O procedimento está em `audit-free-models.cjs`,
**nesta mesma pasta**:

```bash
node audit-free-models.cjs                 # só os :free
node audit-free-models.cjs --second-path   # inclui kiro/nvidia (conexões independentes)
```

Use `.cjs`, **não `.js`**: `~/.config/opencode/package.json` declara
`"type": "module"`, então um `.js` com `require` morre com
`require is not defined in ES module scope`.

Ele classifica em três, e a distinção é o que importa:

| Veredito | Código | Significado | Ação |
|---|---|---|---|
| `OK` | 200 | Vivo | Pode entrar em combo |
| `GONE` | 404 + "use this slug instead" | **Virou pago** | Remover do combo. Repetir não resolve. |
| `FAIL` | 429 / 410 / 404 genérico | Rate, provedor fora, ou **transiente** | **Re-executar antes de remover** |

Só `GONE` com aquele texto justifica remoção. Um `429` ou `404` genérico é
transiente — apagar o modelo por uma medição é como remover um caminho porque
choveu uma vez. Rode **duas vezes** antes de concluir qualquer coisa.

Se `better-sqlite3` não carregar, passe a chave na mão:
`NINEROUTER_KEY=sk-... node audit-free-models.cjs`.

## Configurar no opencode

`~/.config/opencode/opencode.json` (o arquivo **não** o `.jsonc` — ambos são
deep-merged, e o provider `9router` mora no `.json`):

```json
{
  "provider": {
    "9router": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://127.0.0.1:20128/v1",
        "apiKey": "sk-..."
      },
      "models": { "GRATIS-CODING": { "name": "GRATIS-CODING" } }
    }
  }
}
```

Confira com `opencode models 9router` — o que não aparecer ali não está
registrado. E `opencode debug config` mostra o **merged** real, que é o
único que vale.

## Limits que este skill impõe

- **O que está aqui foi medido em 2026-10-03** e pode estar velho hoje. A
  tabela é ponto de partida, não verdade permanente.
- `testStatus: active` no banco do 9Router **não garante que o modelo
  responda agora** — `openrouter` estava `active` com 429 em 4 modelos.
- `oc/space-bunny-free` responde (medido 200/1077ms) mas **não aparece em
  `/v1/models`**. Presença no catálogo não é pré-requisito para funcionar —
  e ausência não é prova de que está quebrado.
- Nada aqui foi testado com **imagem, tool-calling longo ou contexto grande**.
  Só texto curto. Não extrapole para multimodal.