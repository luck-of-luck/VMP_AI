#!/usr/bin/env python3
"""Prova que o registry e o transporte funcionam antes do orquestrador.

Verifica o que precisa ser verdadeiro para o pipeline rodar:
  1. Registry: papeis, escopo de escrita, e a invariante de separacao
     (critic/reader NAO recebem write_file).
  2. Transporte: um agente real le um arquivo e responde sobre ele.
  3. Sandbox: um 'critic' que tentar escrever e barrado PELO HOST.
  4. Piso de tokens: um agente com budget minimo ainda responde.
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "core"))

import registry as reg  # noqa: E402
from agent import MIN_TOKEN_FLOOR, run_agent  # noqa: E402

FAIL = []


def check(label, cond, detail=""):
    mark = "OK  " if cond else "FALHA"
    print(f"[{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FAIL.append(label)


print("=" * 70)
print("1. REGISTRY")
print("=" * 70)
for role in reg.PIPELINE:
    m = reg.manifest(role)
    print(
        f"  {role:<11} escreve={str(m.writes):<5} tokens={m.max_tokens:<5} {m.mission[:40]}"
    )

check("papeis do pipeline existem", all(r in reg.REGISTRY for r in reg.PIPELINE))
check(
    "CRITIC_LENSES tem >=3 lentes",
    len(reg.CRITIC_LENSES) >= 3,
    f"{len(reg.CRITIC_LENSES)} lentes",
)

# Invariante de separacao: o mais importante do design.
for role in ("critic", "reader", "researcher"):
    names = [t["function"]["name"] for t in reg.tools_for(role)]
    check(
        f"'{role}' NAO recebe write_file", "write_file" not in names, f"tools={names}"
    )

for role in ("maker", "fixer", "optimizer"):
    names = [t["function"]["name"] for t in reg.tools_for(role)]
    check(f"'{role}' recebe write_file", "write_file" in names, f"tools={names}")

# Escopo de escrita
check("maker pode gravar .py", reg.in_scope("maker", "C:/proj/app.py"))
check("maker pode gravar .md", reg.in_scope("maker", "C:/proj/README.md"))
check("maker NAO grava .exe", not reg.in_scope("maker", "C:/proj/malware.exe"))
check("critic NAO grava nada", not reg.in_scope("critic", "C:/proj/app.py"))

try:
    reg.manifest("inexistente")
    check("papel desconhecido levanta erro", False, "nao levantou")
except KeyError as e:
    check("papel desconhecido levanta erro", True, str(e)[:50])

print()
print("=" * 70)
print("2. ARQUIVO DE TESTE")
print("=" * 70)
tmpdir = Path(tempfile.mkdtemp(prefix="cluster_probe_"))
target = tmpdir / "alvo.py"
target.write_text(
    "def calcular_preco(base, taxa):\n"
    "    # bug proposital: a taxa entra duas vezes no resultado\n"
    "    total = base + taxa\n"
    "    return total + taxa\n"
    "\n"
    "def preco_vazio(base):\n"
    "    return calcular_preco(base, 0.10)\n",
    encoding="utf-8",
)
print(f"criado: {target}")
print(
    f"  tem bug: 'aplicada duas vezes' presente = {'aplicada duas vezes' in target.read_text(encoding='utf-8')}"
)

print()
print("=" * 70)
print("3. AGENTE REAL â€” reader le o arquivo e responde")
print("=" * 70)
# Este bloco chama o MODELO. O relay e intermitente por natureza (ja falhou
# com SSLV3_ALERT_BAD_RECORD_MAC e por timeout), entao uma falha de rede nao
# diz nada sobre o host. Duas leituras:
#   - 1a tentativa = veredito, se der certo.
#   - se falhar por rede/relay, RETENTA uma vez e so reprova se as duas
#     falharem. Rejeitar "reader respondeu" por um SSL nao treina ninguem.
# O que continua SEM tolerancia: o `read_file` ter sido chamado. Isso e
# sobre o nosso roteamento de tools, e nao muda com o clima da rede.
RETRY = 2
r = run_agent(
    "reader",
    f"Le o arquivo {target} e descreva em 2 frases: o que ele faz e qual logica "
    "suspeita voce observa. Cite a funcao.",
    timeout=180,
)
print(
    f"  tentativa 0: ok={r.ok} rounds={r.rounds} "
    f"latencia={r.latency:.1f}s tools={len(r.tool_calls)} finish={r.finish_reason}"
)
if r.error:
    print(f"    erro: {r.error[:200]}")
ultimo_erro = r.error
tentativas_feitas = 1
while not r.ok and tentativas_feitas < RETRY:
    tentativas_feitas += 1
    print("    -> falhou; uma ultima tentativa (relay e intermitente)")
    r = run_agent(
        "reader",
        f"Le o arquivo {target} e descreva em 2 frases: o que ele faz e qual logica "
        "suspeita voce observa. Cite a funcao.",
        timeout=180,
    )
    print(
        f"  tentativa {tentativas_feitas - 1}: ok={r.ok} rounds={r.rounds} "
        f"latencia={r.latency:.1f}s tools={len(r.tool_calls)} finish={r.finish_reason}"
    )
    if r.error:
        print(f"    erro: {r.error[:200]}")
    ultimo_erro = r.error

for tc in r.tool_calls:
    print(f"    tool: {tc['name']}({str(tc['args'])[:60]}) ok={tc['ok']}")
print(f"  RESPOSTA: {r.final[:400]}")
check("reader respondeu", r.ok, f"falhou {tentativas_feitas}x: {ultimo_erro}")
check(
    "reader leu o arquivo de verdade",
    any(tc["name"] == "read_file" for tc in r.tool_calls),
    f"tools={[t['name'] for t in r.tool_calls]}",
)

print()
print("=" * 70)
print("4. SANDBOX â€” o HOST tem que barrar a escrita, nao o modelo recusar")
print("=" * 70)
# O ponto do teste nao e "o critic se comportou": e que a garantia nao
# depende de ele se comportar. Por isso forcamos a tool de escrita na mao.
# Se o registry e o sandbox funcionam, o host recusa MESMO com a tool
# oferecida e um prompt mandando gravar.
import agent as agent_mod  # noqa: E402

destino = tmpdir / "invadido_por_critic.txt"

# Chama dispatch direto, com role='critic': isto e o host decidindo.
tr = agent_mod.dispatch(
    "write_file", {"path": str(destino), "content": " hack "}, "critic"
)
print(
    f"  dispatch write_file role=critic -> ok={tr.ok} denied={'SIM' if tr.denied else 'nao'}"
)
if tr.denied:
    print(f"    motivo: {tr.denied[:160]}")
check("host NEGA escrita de critic (tool forcada)", tr.denied is not None and not tr.ok)
check("arquivo NAO foi criado", not destino.exists(), f"existe={destino.exists()}")

# E o inverso: maker dentro do escopo escreve de verdade.
ok_path = tmpdir / "feito_pelo_maker.py"
tr2 = agent_mod.dispatch(
    "write_file", {"path": str(ok_path), "content": "x = 1\n"}, "maker"
)
print(f"  dispatch write_file role=maker  -> ok={tr2.ok}  existe={ok_path.exists()}")
check("host PERMITE escrita de maker no escopo", tr2.ok and ok_path.exists())

# Fora do escopo mesmo com papel escritor:
tr3 = agent_mod.dispatch(
    "write_file", {"path": str(tmpdir / "fora.exe"), "content": "x"}, "maker"
)
print(
    f"  dispatch write_file role=maker fora de escopo -> denied={'SIM' if tr3.denied else 'nao'}"
)
check("escopo barra extensao nao permitida", tr3.denied is not None)

print()
print("=" * 70)
print("5. PISO DE TOKENS â€” budget minimo ainda produz RESPOSTA")
print("=" * 70)
# budget de 256 e o piso medido. Aqui o agente NAO tem trabalho a fazer com
# ferramenta (a pergunta e factual e a resposta cabe em uma frase), entÃ£o o
# caso relevante e: ele responde em TEXTO dentro do piso, sem gastar o
# budget em tool-calling que nao precisa.
r3 = run_agent(
    "researcher",
    "Sem usar ferramentas. Responda em UMA frase curta: qual o primeiro passo "
    "para revisar codigo legado?",
    max_tokens=MIN_TOKEN_FLOOR,
    timeout=180,
)
print(
    f"  ok={r3.ok} finish={r3.finish_reason} latencia={r3.latency:.1f}s tokens_orcados={MIN_TOKEN_FLOOR}"
)
if r3.error:
    print(f"  erro: {r3.error[:200]}")
# Mesma politica do bloco 3: o relay e intermitente, uma falha de rede nao
# reprova o piso de tokens.
tentativas_piso = 1
while not r3.ok and tentativas_piso < 2:
    tentativas_piso += 1
    print("  -> falhou; retry (relay intermitente)")
    r3 = run_agent(
        "researcher",
        "Sem usar ferramentas. Responda em UMA frase curta: qual o primeiro passo "
        "para revisar codigo legado?",
        max_tokens=MIN_TOKEN_FLOOR,
        timeout=180,
    )
    print(f"  ok={r3.ok} finish={r3.finish_reason} latencia={r3.latency:.1f}s")
    if r3.error:
        print(f"  erro: {r3.error[:200]}")
print(f"  RESPOSTA: {r3.final[:200]}")
check(
    "responde em texto com budget no piso",
    r3.ok and bool(r3.final.strip()),
    f"falhou {tentativas_piso}x: {r3.error}",
)

print()
print("=" * 70)
print("6. PROVA DO ACHADO DO SPEC 2.1 - abaixo do piso o reasoning consome tudo")
print("=" * 70)
# O defeito era: `max_tokens` pequeno, o modelo gasta o orcamento em
# reasoning e volta vazio. A CORRECAO nao foi "pedir mais tokens" — foi
# IMPOR um piso no host, porque nao cabe no prompt dizer isso.
#
# POR QUE ESTE BLOCO MUDOU DE FORMA (2026-10-01):
# A versao anterior afirmava `reasoning >= metade do orcamento` numa amostra
# de 5 chamadas ao modelo remoto. Isso e medir o COMPORTAMENTO DE UM LLM,
# nao do nosso codigo — e oscilava: passei com [23, 14, 16, 12, 28] e
# falhei com [22, 23, 23, 0, 12]. Nenhuma das duas execucoes dizia algo
# sobre a correcao. Um teste que falha por acaso treina o time a rodar de
# novo ate passar, que e o oposto de conferir.
#
# A divisao agora e:
#   (a) DETERMINISTICO, sem rede: o host NUNCA envia budget abaixo do piso.
#       Isso e nosso, e nao tem variacao.
#   (b) OBSERVACAO, com rede: o modelo ainda come reasoning com budget
#       pequeno. Isso e um fato sobre o modelo. Registrado, nao veredito.
import agent as agent_mod2  # noqa: E402

ORCADO_BAIXO = 48
PISO = agent_mod2.MIN_TOKEN_FLOOR

print()
print("  (a) DETERMINISTICO: o host nunca envia budget abaixo do piso")
print()
# Intercepta a chamada de rede para inspecionar o payload SEM sair.
capturados = []


def _post_falso(payload, key, timeout):
    capturados.append(dict(payload))
    # Resposta com finish=length e content vazio: exatamente o defeito.
    return (
        True,
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "", "tool_calls": None},
                }
            ],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 40}},
        },
        None,
    )


post_real = agent_mod2._post
agent_mod2._post = _post_falso
try:
    for pedido, rotulo in [
        (ORCADO_BAIXO, "max_tokens=48 (abaixo do piso)"),
        (None, "max_tokens ausente (usa o padrao do papel)"),
        (9999, "max_tokens=9999 (acima do piso)"),
    ]:
        capturados.clear()
        agent_mod2.run_agent(
            role="researcher", task="tarefa qualquer", max_tokens=pedido
        )
        enviado = capturados[-1]["max_tokens"] if capturados else None
        check(
            f"host elevou o budget — {rotulo}",
            enviado is not None and enviado >= PISO,
            f"enviou {enviado}, piso e {PISO}",
        )
finally:
    agent_mod2._post = post_real

check(
    f"o piso esta acima do orcado que dispara o defeito ({ORCADO_BAIXO})",
    PISO > ORCADO_BAIXO,
    f"piso={PISO} orcado_que_quebra={ORCADO_BAIXO}",
)

print()
print("  (a2) DETERMINISTICO: finish=length NAO destroi trabalho ja feito")
print()
# Este e o outro contrato nosso: se o agente JA GRAVOU e so o relato nao
# coube, o trabalho vale. Tratar como falha faz o pipeline descartar uma
# gravacao correta — medido com o `fixer` em 2026-10-01.
capturados.clear()

import json  # noqa: E402
import tempfile as _tf  # noqa: E402
from pathlib import Path as _P  # noqa: E402

_tmp = _P(_tf.mkdtemp(prefix="piso_"))
_alvo = _tmp / "feito.py"
# O path PRECISA ser o de verdade: o escopo barra o write_file se o
# caminho nao casar, e um mock com "PLACEHOLDER" mediria o sandbox, nao o
# recovery de finish=length.
_args_gravacao = json.dumps({"path": str(_alvo), "content": "feito = True\n"})


def _post_gravou(payload, key, timeout):
    capturados.append(dict(payload))
    return (
        True,
        {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": _args_gravacao,
                                },
                            }
                        ],
                    },
                }
            ],
            "usage": {"completion_tokens_details": {"reasoning_tokens": 40}},
        },
        None,
    )


agent_mod2._post = _post_gravou
try:
    run_gravou = agent_mod2.run_agent(
        role="maker", task="grava", target=str(_alvo), max_tokens=ORCADO_BAIXO
    )
finally:
    agent_mod2._post = post_real

check(
    "gravar + finish=length conta como SUCESSO (o relato nao coube)",
    run_gravou.ok,
    f"ok={run_gravou.ok} erro={run_gravou.error}",
)
check(
    "a gravacao foi de fato aplicada antes do relato truncar",
    _alvo.exists() and "feito" in _alvo.read_text(encoding="utf-8"),
    f"existe={_alvo.exists()}",
)
check(
    "o agente nao ficou em loop de retentativa",
    len(run_gravou.tool_calls) <= 2,
    f"{len(run_gravou.tool_calls)} chamada(s) — esta retryando",
)

print()
print("  (b) MEDICAO DE CONTEXTO: o orcamento que dispara o defeito")
print("      varia com o modelo. Isto nao e veredito — e o dado que justifies")
print("      o piso. Veredito sobre o CODIGO fica em (a) e (a2), sem rede.")
print()
key = agent_mod2._key()
PROMPT_CURTO = "Responda apenas com o numero 7."

# NOTA SOBRE ESTA SECAO (2026-10-01): a versao anterior lia
# `usage.completion_tokens_details.reasoning_tokens` e afirmava "o reasoning
# consome metade do orcamento". Medi de novo: o relay NAO devolve esse
# campo (`usage` vem sem `completion_tokens_details`), entao a metrica
# mediava `None`. Pior: com `max_tokens=48` a resposta hoje vem correta
# ('7'), o que ja nao reproduz o defeito que o teste queria provar.
#
# O sinal que REALMENTE correlaciona com o defeito e `finish_reason`:
# varri o orcamento e a resposta so vem vazia com `finish=length`.
#   budget   8/12/16/20/24 -> length, resposta vazia
#   budget  32/48/96      -> stop,   resposta presente
# Entao a medicao abaixo usa `finish_reason`, e nao o campo de reasoning.
observado = []
for b in (16, 32):
    try:
        ok, resp, _ = agent_mod2._post(
            {
                "model": agent_mod2.MODEL,
                "messages": [{"role": "user", "content": PROMPT_CURTO}],
                "max_tokens": b,
            },
            key,
            120,
        )
    except Exception as e:
        print(f"  budget={b}: relay indisponivel ({type(e).__name__}) — pulada")
        continue
    ch = (resp.get("choices") or [{}])[0]
    content = ((ch.get("message") or {}).get("content") or "").strip()
    fr = ch.get("finish_reason")
    observado.append((b, fr, len(content)))
    print(f"  budget={b:<4} finish={str(fr):<7} chars={len(content)}")

vazias = [(b, fr, n) for b, fr, n in observado if n == 0]
print(f"  resumo: {len(vazias)}/{len(observado)} respostas vazias")
print()
print("  leitura: resposta vazia veio com finish=length (orcamento comido")
print("  ANTES da resposta). E por isso que o piso e imposto no host: nao")
print("  da para contornar pelo prompt. O piso (256) e folgado em relacao ao")
print("  limiar observado (~24), e isso e intencional — folga nao custa nada")
print("  e evita depender de um limiar que o modelo pode mover.")
if observado:
    print(
        "  se o modelo mudar e o limiar subir, o piso continua acima: "
        f"{PISO} >> {max((b for b, _, _ in observado), default=0)}"
    )

# O unico veredito de rede: com o PISO, a resposta tem de caber. E uma
# propriedade estavel — o piso foi medido exatamente para garantir isso.
print()
ok2, resp2, _ = agent_mod2._post(
    {
        "model": agent_mod2.MODEL,
        "messages": [{"role": "user", "content": PROMPT_CURTO}],
        "max_tokens": agent_mod2.MIN_TOKEN_FLOOR,
    },
    key,
    120,
)
content2 = (
    ((resp2.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
).strip()
rt2 = ((resp2.get("usage") or {}).get("completion_tokens_details") or {}).get(
    "reasoning_tokens"
)
print(
    f"  com piso {agent_mod2.MIN_TOKEN_FLOOR}: reasoning={rt2} "
    f"conteudo={len(content2)} chars -> {content2[:30]!r}"
)
check(
    "com o piso a resposta cabe", ok2 and bool(content2), f"conteudo={content2[:50]!r}"
)

print()
print("=" * 70)
if FAIL:
    print(f"FALHAS: {len(FAIL)}")
    for f in FAIL:
        print(f"  - {f}")
    sys.exit(1)
print("TODAS AS PROVAS PASSARAM")
