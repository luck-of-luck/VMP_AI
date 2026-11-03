#!/usr/bin/env python3
"""Prova a corrida de escrita parcial (achado do comite de revisao).

ACHADO (2026-10-01, lente de concorrencia e recursos):
    "O arquivo e truncado e escrito diretamente. Assim, leitores podem
     observar conteudo parcial e escritas simultaneas podem perder
     atualizacoes."

Este teste FAZ a corrida de verdade: enquanto o `write_file` escreve um
arquivo grande, um leitor le o mesmo caminho repetidamente e verifica se ja
viu conteudo pela METADE. Se vir, a leitura parcial e real e a escrita nao e
atomica.

Antes da correcao: espera-se ver estado parcial.
Depois: nunca — ou o arquivo esta velho, ou o novo, nunca os dois.

Nao e teste de "o codigo esta bonito". E teste de "a barreira segura".
"""

import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "core"))

import agent as agent_mod  # noqa: E402

FALHAS = []


def check(label, cond, detail=""):
    marca = "OK   " if cond else "FALHA"
    print(f"[{marca}] {label}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FALHAS.append(label)


# Conteudo grande o bastante para a escrita levar tempo mensuravel, e com
# marcadores no inicio e no fim para distinguir "velho" de "novo".
NOVO_INICIO = "#<<NOVO>>"
NOVO_FIM = "#<<FIM_NOVO>>"
VELHO = "#<<VELHO>>\n" + ("x" * 400_000)
NOVO = NOVO_INICIO + "\n" + ("y" * 400_000) + "\n" + NOVO_FIM + "\n"


def corrida(alvo: Path, *, rotulos: int = 60) -> dict:
    """Escreve o arquivo novo enquanto N leitores leem o mesmo caminho.

    Os leitores abrem e FECHAM a cada iteracao (`read_text`), que e o
    comportamento real do `read_file` do cluster. Nao se segura o handle:
    esse caso esta no bloco 5, que mede o limite do SO.
    """
    visto_velho = 0
    visto_novo = 0
    visto_PARCIAL = 0
    erros = 0
    para = threading.Event()

    def leitor():
        nonlocal visto_velho, visto_novo, visto_PARCIAL, erros
        while not para.is_set():
            try:
                txt = alvo.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                continue
            except Exception:
                erros += 1
                continue
            if NOVO_FIM in txt:
                visto_novo += 1
            elif "VELHO" in txt:
                visto_velho += 1
            else:
                # Nao e o velho inteiro nem o novo inteiro: estado MEIO.
                visto_PARCIAL += 1
            time.sleep(0.001)

    alvo.write_text(VELHO, encoding="utf-8")

    threads = [threading.Thread(target=leitor, daemon=True) for _ in range(4)]
    for t in threads:
        t.start()
    time.sleep(0.05)

    r = agent_mod.dispatch(
        "write_file",
        {"path": str(alvo), "content": NOVO},
        "maker",
        raiz=str(alvo.parent),
    )
    time.sleep(0.05)
    para.set()
    for t in threads:
        t.join(timeout=2)

    return {
        "ok": r.ok,
        "velho": visto_velho,
        "novo": visto_novo,
        "PARCIAL": visto_PARCIAL,
        "erros": erros,
    }


print("=" * 74)
print("1. CORRIDA DE LEITURA DURANTE A ESCRITA")
print("=" * 74)

tmp = Path(tempfile.mkdtemp(prefix="corrida_"))

# Varias rodadas: a corrida e uma janela de tempo, entao uma unica medicao
# pode passar por sorte. Cinco rodadas reduzem isso.
resultados = []
for i in range(5):
    alvo = tmp / f"alvo_{i}.py"
    res = corrida(alvo)
    resultados.append(res)
    print(
        f"  rodada {i}: ok={res['ok']} "
        f"velho={res['velho']} novo={res['novo']} "
        f"PARCIAL={res['PARCIAL']} erros={res['erros']}"
    )

total_parcial = sum(r["PARCIAL"] for r in resultados)
total_leituras = sum(r["velho"] + r["novo"] + r["PARCIAL"] for r in resultados)
falhas_escrita = [i for i, r in enumerate(resultados) if not r["ok"]]
viram_novo = sum(r["novo"] for r in resultados)
print()
print(f"  leituras totais: {total_leituras}")
print(f"  leituras PARCIAIS (estado invalido): {total_parcial}")

# ESTA ASSERCAO VEIO DEPOIS DE UMA FALHA REAL DESTE TESTE.
#
# Na primeira versao da escrita atomica, TODAS as rodadas deram
# `ok=False` - e a contagem de parciais ficou 0. O teste reportava
# "NENHUMA ESCADA" quando, na verdade, nenhuma escrita tinha acontecido:
# os leitores liam o arquivo velho a noite toda porque o `os.replace`
# falhava com `WinError 5` no Windows (ver `_substituir_com_retry`).
#
# Ou seja: "0 leituras parciais" e um resultado VERDADE E COMPLETAMENTE
# VAZIO se a escrita falhou. Sozinha, a metrica nao prova nada. Por isso a
# checagem de sucesso da escrita vem ANTES e e obrigatoria.
check(
    "a ESCRITA FUNCIONOU em todas as rodadas (sem isso o resto e vazio)",
    not falhas_escrita,
    f"falhou nas rodadas {falhas_escrita} - '0 parciais' seria mentira",
)
check(
    "os leitores viram o conteudo NOVO (a troca aconteceu)",
    viram_novo > 0,
    f"{viram_novo} leituras viram o novo",
)
check(
    "NENHUMA leitura parcial (escrita e atomica)",
    total_parcial == 0,
    f"{total_parcial} de {total_leituras} leituras viraram estado invalido",
)
check(
    "as leituras ocorrem de verdade (sanidade do teste)",
    total_leituras > 0,
    f"{total_leituras} leituras - se 0, o teste nao provaria nada",
)

print()
print("=" * 74)
print("2. O ARQUIVO FINAL ESTA CORRETO E INTEIRO")
print("=" * 74)
alvo = tmp / "alvo_0.py"
txt = alvo.read_text(encoding="utf-8")
check("marcador novo no inicio", NOVO_INICIO in txt)
check("marcador novo no fim", NOVO_FIM in txt)
check("conteudo completo", len(txt) > 400_000, f"{len(txt)} chars")
check("conteudo velho nao sobrou", "VELHO" not in txt)
check("abre como Python valido", compile(txt, str(alvo), "exec") is not None)

print()
print("=" * 74)
print("3. SEM ESCOPO, A ESCRITA NAO DEIXA LIXO (temp fica limpo)")
print("=" * 74)
tmp2 = Path(tempfile.mkdtemp(prefix="lixo_"))
alvo2 = tmp2 / "a.py"
agent_mod.dispatch(
    "write_file", {"path": str(alvo2), "content": "x = 1\n"}, "maker", raiz=str(tmp2)
)
restantes = sorted(p.name for p in tmp2.iterdir())
print(f"  arquivos em {tmp2.name}: {restantes}")
check(
    "so o arquivo alvo existe (nenhum temporario orfao)",
    restantes == ["a.py"],
    f"encontrados: {restantes}",
)

# Falha no meio da escrita tem que nao corromper o original.
print()
print("=" * 74)
print("4. FALHA NA ESCRITA NAO CORROMPE O ARQUIVO ORIGINAL")
print("=" * 74)
tmp3 = Path(tempfile.mkdtemp(prefix="falha_"))
alvo3 = tmp3 / "b.py"
original = "# conteudo bom\nvalor = 42\n"
alvo3.write_text(original, encoding="utf-8")

# Forca uma falha: passar um caminho cujo diretorio e um ARQUIVO.
arquivo_bloqueio = tmp3 / "bloqueio"
arquivo_bloqueio.write_text("sou um arquivo, nao um diretorio\n", encoding="utf-8")
r = agent_mod.dispatch(
    "write_file",
    {"path": str(arquivo_bloqueio / "sub.py"), "content": "novo"},
    "maker",
    raiz=str(tmp3),
)
print(f"  escrita em caminho invalido -> ok={r.ok}  {r.output[:80]}")
check("falhou de forma limpa", not r.ok, f"ok={r.ok}")
check(
    "o arquivo bloqueador nao foi alterado",
    arquivo_bloqueio.read_text(encoding="utf-8")
    == "sou um arquivo, nao um diretorio\n",
    "conteudo foi corrompido",
)

print()
print("=" * 74)
print("5. HANDLE RETIDO DE VERDADE — o limite do SISTEMA, nao do codigo")
print("=" * 74)
# MEDIDO: no Windows, NENHUMA API substitui um arquivo cujo handle esta
# aberto e retido. Testei as tres:
#   - os.replace                  -> WinError 5
#   - MoveFileExW(MRE|COPY_ALLOWED) -> WinError 5
#   - MoveFileExW(MRE apenas)     -> WinError 5
# So funciona depois que o handle fecha. E restricao do SO: enquanto alguem
# segura o arquivo, nao existe troca possivel, atomica ou nao.
#
# Entao o comportamento CORRETO nao e "gravar assim mesmo" — seria voltar a
# truncar o destino, que e o defeito que estamos corrigindo. E falhar limpo,
# preservando o original intacto. E o que este teste exige.
tmp5 = Path(tempfile.mkdtemp(prefix="handle_"))
alvo5 = tmp5 / "segurado.py"
ORIGINAL5 = "conteudo original\n"
alvo5.write_text(ORIGINAL5, encoding="utf-8")

fh = open(alvo5, "r", encoding="utf-8")
fh.read(5)
print("  handle aberto por um 'leitor' e MANTIDO aberto")
r5 = agent_mod.dispatch(
    "write_file",
    {"path": str(alvo5), "content": "conteudo novo\n"},
    "maker",
    raiz=str(tmp5),
)
print(f"  -> ok={r5.ok}")
print(f"     {r5.output[:110]}")
fh.close()

check(
    "handle retido: a escrita NAO e silenciosamente corrompida (falha limpa)",
    not r5.ok,
    f"ok={r5.ok} - se gravou, so porque truncou um arquivo com handle aberto",
)
check(
    "handle retido: o conteudo ORIGINAL foi preservado intacto",
    alvo5.read_text(encoding="utf-8") == ORIGINAL5,
    f"virou {alvo5.read_text(encoding='utf-8')!r} - arquivo corrompido",
)
orfaos5 = sorted(p.name for p in tmp5.iterdir())
print(f"  arquivos em {tmp5.name}: {orfaos5}")
check(
    "handle retido: nenhum temporario orfao ficou para tras",
    orfaos5 == ["segurado.py"],
    f"encontrados: {orfaos5}",
)

# E assim que o handle fecha, a MESMA escrita tem que funcionar.
print()
print("  --- apos o handle fechar, a mesma escrita funciona ---")
r5b = agent_mod.dispatch(
    "write_file",
    {"path": str(alvo5), "content": "conteudo novo\n"},
    "maker",
    raiz=str(tmp5),
)
print(f"  -> ok={r5b.ok}")
check(
    "apos o handle fechar, a escrita passa normalmente",
    r5b.ok and alvo5.read_text(encoding="utf-8") == "conteudo novo\n",
    f"ok={r5b.ok} conteudo={alvo5.read_text(encoding='utf-8')!r}",
)

print()
print("=" * 74)
print("6. LEITOR SOLTO (abre e fecha a cada leitura) — o caso comum")
print("=" * 74)
tmp6 = Path(tempfile.mkdtemp(prefix="soltas_"))
alvo6 = tmp6 / "solta.py"
alvo6.write_text("velho\n", encoding="utf-8")
ok6 = 0
for i in range(12):
    # abre, le, fecha: e o que read_text() faz
    alvo6.read_text(encoding="utf-8")
    r6 = agent_mod.dispatch(
        "write_file",
        {"path": str(alvo6), "content": f"geracao {i}\n"},
        "maker",
        raiz=str(tmp6),
    )
    if r6.ok:
        ok6 += 1
print(f"  escritas bem-sucedidas: {ok6}/12")
check("todas as escritas com leitor efemero passaram", ok6 == 12, f"{ok6}/12")

print()
print("=" * 74)
if FALHAS:
    print(f"CORRIDAS / FALHAS: {len(FALHAS)}")
    for f in FALHAS:
        print(f"  - {f}")
    sys.exit(1)
print("A ESCRITA E ATOMICA: nenhum leitor viu estado invalido")
