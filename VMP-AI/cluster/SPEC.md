# CLUSTER IA - Especificacao e veredito das capacidades

> Toda afirmacao neste documento foi **medida**, nao suposta.
> Reproduza com `python VMP-AI/cluster/probe_model.py`, `probe_capacity.py`,
> `probe_limits.py`, `test_core.py`, `test_pipeline_e2e.py`.
> Data da medicao: **2026-10-01**.

## 1. O que e

Um cluster de agentes `space-bunny-free` (relay OpenCode Zen) que trabalham em
conjunto sobre um mesmo projeto, cada um com um **papel** distinto, em uma
**ordem** definida, entregando o resultado um ao outro.

Nao e "varios chats abertos". E um sistema onde:

- cada agente tem um **papel declarado** e um **escopo** do que pode tocar;
- existe uma **ordem de trabalho** e criterio de **handoff**;
- um agente **nao pode** fazer o trabalho de outro papel (o revisor nao edita);
- o orquestrador e **soberano**: decide quando rodar, quem espera quem, e quando
  parar. O modelo nao decide a topologia.

### Prova de que funciona

`test_pipeline_e2e.py` roda o pipeline inteiro sobre um arquivo com 3 defeitos
plantados (logica, recurso, seguranca) e **verifica por comportamento**, nao por
elogio. Ultima execucao completa:

```
researcher  OK  55s      reader      OK  48s      maker      OK  11s
critic#1    OK 108s      critic#2    OK 145s      critic#3   OK  23s
fixer       OK 158s      optimizer  OK 103s
exit=0   9 agentes   565s   6/6 papeis
```

Os 3 defeitos foram corrigidos e o arquivo final **importa e executa**
(verificado: `media([])` levanta `ZeroDivisionError` com mensagem, `somar_ate([])`
devolve 0, `primeiro([])` devolve None).

## 2. Veredito medido do modelo

| Capacidade | Resultado | Como foi medida |
|---|---|---|
| Inferencia basica | OK 1.9s | prompt "reply PONG" |
| **Tool-calling** | OK emite `tool_calls` valido | mandou chamar `read_file`; chamou |
| **Loop de ferramentas** | OK 2+ round-trips | leu arquivo real e descreveu |
| **JSON estrito** | OK parseavel | `json.loads` do output passou |
| Contexto de entrada | OK ate **300.000 chars** (~75k tokens) | ramp 2k->300k, todos aceitos |
| Leitura de codigo real | OK acerta `def` correto | 1a funcao de `run_agent.py` (426k chars) |
| Concorrencia | OK **10/10 simultaneos, 0x 429** | ondas de 3/5/8/10 |
| Durabilidade | OK **30/30 em 3 ondas** | 3 ondas de 10 |
| Latencia | mediana **1.8s**, p-max **12.2s** | 15 chamadas + ondas |
| Reasoning | varia **0 -> orcamento inteiro** | via `finish_reason=length` + resposta vazia (o relay nao expoe `reasoning_tokens`) |

## 3. Os 6 defeitos encontrados na construcao

Esta e a secao mais importante do documento. Cada um destes custou uma rodada
de depuracao e **nao e obvio**: todos se manifestam como "o modelo e burro" ou
como falha de rede, e nenhum deles e culpa do modelo.

### 3.1 O cluster produzia codigo QUEBRADO com `ok=True` (o mais grave)

O pipeline completou **6/6 papeis, todos `ok=True`**, e o resultado foi
`SyntaxError: unterminated triple-quoted string literal` na linha 11: o `fixer`
truncou a gravacao no meio de uma docstring, e o `optimizer` leu o arquivo
truncado e "corrigiu" em cima dele.

`acted()` verificava **ACAO** (o agente gravou?). Nada verificava **RESULTADO**
(o arquivo esta valido?). Um cluster de agentes sem essa segunda verificacao
produz codigo quebrado com orgulho - e o `ok=True` no handoff mente ativamente.

**Correcao:** `verify.py` vira o criterio de aceite. Apos cada papel QUE GRAVA,
o arquivo precisa continuar compilando; se nao continua, a etapa e FALHA, o
pipeline PARA, e a versao boa e restaurada do snapshot (o conteudo quebrado
fica em `_alvo_quebrado.py` para inspecao). O codigo de retorno passa a
refletir o resultado: `0` = rodou e ficou valido, `1` = etapa falhou,
`2` = rodou mas o resultado e invalido.

### 3.2 `ast.parse` sozinho NAO detecta gravacao truncada

Achado dentro do achado. Ao testar o verificador contra o arquivo quebrado, ele
disse "sintaxe ok" - e estava errado. O arquivo terminava assim:

```python
def carregar(caminho):
    with open(caminho, "rb") as f:
        primeiros = f.readline()
        tamanho = int(...) or _tamanho_restante(f)
        ...
```

**`...` como statement e sintaticamente VALIDO em Python.** O arquivo passa no
`ast.parse`, passa em "sintaxe ok", e e codigo morto que ainda referencia nomes
inexistentes. O verificador agora tem tres camadas: parse, ausencia de `...`
solto, e "toda funcao tem corpo executavel" (nao so docstring).

O mesmo arquivo **tambem** tinha todas as funcoes com sintaxe valida enquanto
`media` tinha sido **removida por inteiro**. Por isso existe tambem a checagem
de **preservacao de assinaturas**: um agente pode "corrigir" um bug apagando um
parametro, e isso passa em toda verificacao de sintaxe do mundo.

### 3.3 Tolerancia a falha parcial nos paralelos

Com 3 criticos em paralelo, 2 produziram revisao valida e o terceiro esbarrou
em orcamento. O pipeline tratou a etapa inteira como falha e parou -
descartando trabalho bom.

**Correcao:** se pelo menos **metade** dos agentes de um papel paralelo
respondeu, a etapa vale (declarada com ressalva no handoff). Se **nenhum**
respondeu, e falha real e o pipeline para. O gate de qualidade existe para
pegar AUSENCIA de revisao, nao para descartar revisao parcial.

### 3.6 Teto de concorrencia do relay (medido 2026-10-01)

Isto define se um comite grande e uma onda ou uma cadeia. Medido com
`probe_fofa.ts` (orcamento 3000, o que funciona):

| agentes simultaneos | pergunta curta | lendo arquivo |
|---|---|---|
| 10 | 10/10 em 4,8 s | 10/10 em 83 s |
| 25 | 25/25 em 7,7 s | — |
| 50 | **50/50 em 14,9 s** | **50/50 em 33 s** |

`finish=stop` em todos, e a resposta de cada agente continha o numero pedido
(ordem correta), entao nao houve resposta trocada entre agentes.

**Conclusao: 50 e uma ONDA, nao cinco.** O relay nao estrangula por
concorrencia. A variacao real e de latencia (com arquivo, medi entre 33 s e
187 s em chamadas diferentes) — quem varia e o relay, nao o desenho.

Duas armadilhas desta medicao, ambas registradas porque custaram uma rodada:

- Com `max_tokens: 600` deu **0 respostas** em 10, 25 e 50 chamadas — sem
  erro, so `content` vazio. Era o defeito de 3.4 de novo (reasoning consome
  o orcamento). Orcamento pequeno nao mede concorrencia, mede o piso.
- `chamarRelay` devolve `{ ok, content, finish }` normalizado. Tratar como
  resposta OpenAI crua faz `choices[0]` vir `undefined` e a rajada inteira
  reportar 0 ok — "relay quebrado" com o relay saudavel.

### 3.4 `max_tokens` e o gargalo silencioso

O modelo pode gastar tokens em **reasoning antes de responder**, debitado do
mesmo orcamento. O sinal observavel nao e `finish_reason` sozinho, e sim:
**resposta vazia + `finish_reason=length`**.

Varri o orcamento com a pergunta `"Responda apenas com o numero 7."`
(medido 2026-10-01):

| `max_tokens` | `finish_reason` | resposta |
|---|---|---|
| 8, 12, 16, 20, 24 | `length` | **vazia** |
| 32, 48, 96 | `stop` | presente |

O limiar observado fica em ~24 tokens. **`MIN_TOKEN_FLOOR = 256` e folgado em
relacao a ele, de proposito**: folga nao custa nada e evita depender de um
limiar que o modelo pode mover.

**Correcao:** o piso e imposto no host (`agent.py`, `budget = max(
MIN_TOKEN_FLOOR, ...)`). Nao adianta pedir no prompt — o orcamento e um
parametro da chamada, e nao do texto.

Se o orcamento acabar DEPOIS da gravacao, com o relato ainda nao escrito, o
agente conta como **sucesso** (`acted(run)`): a gravacao e o trabalho. Medido
com o `fixer` em 2026-10-01 — tratar como falha fazia o pipeline descartar um
arquivo correto.

### 3.5 O defeito e INTERMITENTE, nao deterministico

Isto e o que torna 3.1 tao traicoeiro. Medido: com `max_tokens=48`, a pergunta
`"7"` (1 char) **passou**; "Responda apenas com o numero 7" **falhou**. Mesmo
codigo, mesmo orcamento, resultados opostos - conforme o tamanho da pergunta.

Em producao isso aparece como "o agente as vezes responde vazio", que e o tipo
de bug que ninguem reproduz e todo mundo acha que e imagina.

### 3.6 `SSL: BAD_RECORD_MAC` vem do keep-alive do urllib

O erro aparecia de forma intermitente (6/6 falhas numa janela, 30/30 na seguinte)
sempre em ~0.4s - falha imediata de TLS, nao timeout. A causa: o `urllib`
reaproveita a conexao TLS e, ao reusar uma sessao apos uma resposta maior, o
relay responde com registro corrompido.

**Correcao:** `http.client` com conexao nova por requisicao. Medido: 0 falhas em
12 pares (antes: 3 falhas em 8). Custo: um handshake TLS por chamada -
irrelevante frente a derrubar o pipeline.

### 3.7 `read_file` em diretorio prendia o agente em laco

`read_file` devolvia o **conteudo** de um diretorio (24k chars de JSON de
handoff). O modelo pedia o diretorio, recebia o proprio artefato, e relia aquilo
repetidamente ate estourar `MAX_TOOL_ROUNDS`, sem nunca responder.

**Correcao:** `read_file` em diretorio recusa e manda usar `list_dir`. Mais uma
guarda contra chamada repetida identica (a 2a vez devolve "IGNORADO").

### 3.8 Papel escritor que "fala" em vez de agir - o mais perigoso

O `maker` devolveu o codigo corrigido **dentro de um bloco de texto** e nunca
chamou `write_file`. O arquivo ficou intacto. O pipeline seguiu para `critic`
como se o trabalho tivesse sido feito.

Este e o defeito que um cluster de agentes promete eliminar e nao eliminou: um
agente que **relata** trabalho em vez de **fazer** trabalho, com `ok=True`.

**Correcao, em tres camadas:**
1. `acted(run)` - so conta `write_file` bem-sucedido como entrega.
2. O orquestrador trata "respondeu mas nao gravou" como **falha**, e retenta uma
   vez com a tarefa reforçada.
3. O prompt do papel escritor diz explicitamente que a entrega e a gravacao.

### 3.9 Retry de transporte destruia trabalho ja feito

O `fixer` gravou o arquivo, a resposta esvaziou por orcamento, e o retry de
transporte **rodou a execucao inteira de novo** - o resultado final ficou sem a
correcao que ja estava no disco.

**Correcao:** se a execucao que falhou ja gravou, aceita-se como sucesso. A
gravacao e o trabalho; o relato e comentario. Vale nos dois niveis (dentro de
`run_agent` e no `run_agent_resilient`).

### 3.10 Erro sem mensagem (falha silenciosa)

Ao esgotar tentativas ainda pedindo ferramenta, o loop saia com `ok=False` e
`error=None`. O orquestrador reportava `motivo: ?` - a falha mais difícil de
diagnosticar que existe. Corrigido com mensagem explicita.

## 4. Limites assumidos (o que o cluster NAO faz)

- **Um unico provider, um unico token.** Sem failover interno. Se o
  `space-bunny-free` cair, todos os agentes caem junto. A resiliencia externa
  (o `fallback_model` do Hermes) existe fora do cluster.
- **Sem estado compartilhado real.** Agentes trocam mensagens por arquivo JSON.
  Um agente que "nasce" nao sabe o que o anterior pensou alem do handoff.
- **Sem garantia de qualidade por modelo.** O modelo e bom para ler, revisar,
  pesquisar e gerar. Para raciocinio profundo de arquitetura, um frontier pago
  continua superior. O cluster **amplifica**, nao substitui.
- **Custo zero != custo invisivel.** A cota free e recurso do fornecedor: pode
  mudar. O orquestrador trata 429 como sinal para reduzir paralelismo.
- **Latencia real: ~60-160s por papel.** Nao e instantaneo. Bom para revisao e
  refatoracao; ruim para laco interativo.

## 5. Papeis (registry)

| Papel | Missao | Escreve? | Entrega |
|---|---|---|---|
| `researcher` | levantar fatos e riscos antes de codigo | nunca | relatorio de fatos e riscos |
| `reader` | mapear estrutura e contratos | nunca | mapa do codigo/contratos |
| `maker` | implementar a mudanca | so no escopo | arquivo gravado via write_file |
| `critic` | achar defeito no trabalho do outro | **nunca** | lista de defeitos priorizada |
| `fixer` | corrigir os defeitos apontados | so no escopo | diff corretivo |
| `optimizer` | melhorar legibilidade sem mudar comportamento | so no escopo | diff + justificativa |

**Invariante de separacao:** `critic`, `reader` e `researcher` nunca recebem a
tool de escrita. Um revisor que edita o proprio texto deixa de revisa-lo. Isso e
imposto pelo sandbox (`READ_ONLY` no registry), nao por confianca no prompt - e
**verificado por teste** (`test_core.py` secao 4: o host barra a escrita mesmo
com a tool forcada).

**Lentes do critic:** um unico critic tender a achar o mesmo defeito de cinco
formas. `CRITIC_LENSES` define 5 classes (correcao, seguranca, contrato,
concorrencia, manutenibilidade) para rodar em paralelo com olhares distintos.

## 6. Ordem de trabalho

```
        [researcher]   fatos, riscos, o que existe
              |
              v
        [reader]       estrutura, contratos, pontos de mudanca
              |
              v
        [maker]        implementa (VERIFICADO por acted())
              |
              v
        [critic] x3     aponta defeitos (paralelo, lentes distintas)
              |
              v
        [fixer]        corrige o que foi apontado
              |
              v
        [optimizer]    limpeza final
```

**Handoff** e um JSON por etapa em `runs/<run_id>/`. Cada agente le o handoff das
anteriores e escreve o seu.

**Gate de qualidade:** se uma etapa falha, o pipeline **para** e reporta. Nao
segue para `fixer` sem revisao concluida. Pular a revisao automaticamente e como
o modelo "confia em si mesmo": parece eficiente e introduz o defeito em
silencio.

## 7. Uso

```bash
cd %LOCALAPPDATA%\hermes  # ou a pasta clonada do repo

# pipeline completo (9 agentes)
python VMP-AI\cluster\orchestrator.py --alvo app.py --tarefa "corrija os defeitos"

# so a revisao (3 criticos em paralelo, para antes do fixer)
python VMP-AI\cluster\orchestrator.py --alvo app.py --tarefa "revise" --ate critic

# proveduras
python VMP-AI\cluster\test_core.py          # registry + sandbox + piso
python VMP-AI\cluster\test_pipeline_e2e.py  # pipeline completo
```

## 8. Arquivos

```
VMP-AI/cluster/
  SPEC.md                    este documento
  registry.py                papeis: manifest, escopo, tools permitidas
  core/agent.py              transporte: tool-calling + retry + sandbox
  orchestrator.py            ordem, handoff, gate de qualidade
  pool.py                    10 slots verificados (prontidao)
  cluster_cli.py             CLI: standby / run / status
  verify.py                  criterio de aceite: o arquivo esta valido?
  probe_model.py             capacidade: tool-calling, JSON, contexto
  probe_capacity.py          rampa de contexto + concorrencia
  probe_limits.py            max_tokens, latencia, durabilidade
  probe_ready.py             o que 'prontidao' pode significar aqui
  test_core.py               registry + sandbox + piso (rede)
  test_pipeline_e2e.py       pipeline completo end-to-end (rede)
  runs/                      artefatos por execucao
```

## 9. Proximos passos honestos

O que **nao** foi feito, e o que valeria a pena:

- **Git por papel.** Todo agente grava direto no arquivo de trabalho. Dois
  agentes com escopos sobrepostos no mesmo arquivo sobrescrevem. Um branch por
  papel resolveria.
- **Testes automaticos no pipeline.** Hoje eu verifico que os 3 bugs plantados
  sumiram. Falta o cluster rodar a suite do projeto e so aceitar o resultado se
  ela passar - sem isso, um "otimizador" pode passar a vida deixando codigo
  quebrado.
- **Deteccao de regressao entre papeis.** O `optimizer` nao sabe o que o `maker`
  fez de proposito. Sem registro de intencao, ele pode desfazer uma decisao
  deliberada achando que e limpeza.
- **Interface.** Hoje e CLI + artefatos em disco. A/web vem depois de o nucleo
  estar provado, nao antes.