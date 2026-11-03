#!/usr/bin/env python3
"""Prova a falha de escape de escopo achada pelo comite de revisao.

O comite (lente de seguranca, 2026-10-01) apontou: `in_scope` usa `fnmatch`,
que compara PADRAO DE TEXTO e nao caminho de disco. Um caminho com `..`
casa com o padrao e escapa do escopo autorizado.

Este teste FAZ o exploit de verdade: tenta gravar fora do escopo. Antes da
correcao ele deve falhar (isto e, mostrar a vulnerabilidade); depois, passar.

Nao e teste de "o codigo esta bom". E teste de "a barreira segura".
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "core"))

import registry as reg  # noqa: E402
import tempfile  # noqa: E402

FALHAS = []


def check(label, cond, detail=""):
    marca = "OK   " if cond else "FALHA"
    print(f"[{marca}] {label}" + (f"  -- {detail}" if detail else ""))
    if not cond:
        FALHAS.append(label)


print("=" * 72)
print("1. PAPEL QUE NAO ESCREVE NUNCA ESCAPA (invariante basica)")
print("=" * 72)
for role in ("critic", "reader", "researcher"):
    check(
        f"{role} nao pode gravar em lugar nenhum",
        not reg.in_scope(role, "C:/qualquer/coisa.py"),
        f"in_scope={reg.in_scope(role, 'C:/qualquer/coisa.py')}",
    )

print()
print("=" * 72)
print("2. O EXPLOIT: fnmatch casa TEXTO, nao caminho")
print("=" * 72)
# Todos estes casam com o padrao "*.py" por comparacao de texto...
evases = [
    "C:/proj/../../etc/passwd.py",
    "C:/proj/../../../Windows/System32/evil.py",
    "C:/proj/sub/../../fora.py",
]
for p in evases:
    permitido = reg.in_scope("maker", p)
    print(f"  in_scope('maker', {p!r}) = {permitido}")
    # O que importa: o caminho RESOLVIDO sai do diretorio autorizado?
    resolvido = Path(p)
    saiu = ".." in p
    print(f"      contem '..': {saiu}")
    check(
        f"caminho com '..' barrado: {p[:40]}",
        not permitido,
        f"in_scope={permitido} <- ESCAPE DE ESCOPO se True",
    )

print()
print("=" * 72)
print("3. COM RAIZ: `..` INOFENSIVO PASSA, ESCAPE E BARRADO")
print("=" * 72)
# Esta e a versao 4 do escopo, e ela existe porque o `orquestrador` sabe qual
# arquivo esta sendo editado e passa o diretorio como raiz. Sem raiz, o
# escopo volta a barrar todo `..` (versao 2, o piso de seguranca).
#
# O comite de revisao (2026-10-01) tinha razao: barrar `..` recusa
# `sub/../ok.py`, que resolve para dentro e e trabalho legitimo. Aqui a raiz
# torna possivel aceitar esse caso SEM reabrir o buraco.
tmp_base = Path(tempfile.mkdtemp(prefix="escopo_"))
(tmp_base / "sub").mkdir()

casos_com_raiz = [
    (tmp_base / "sub" / ".." / "dentro.py", True, ".. cancela DENTRO: deve passar"),
    (
        tmp_base / "sub" / ".." / ".." / tmp_base.name / "ok2.py",
        True,
        ".. sobe e volta: deve passar",
    ),
    (tmp_base / "dentro.py", True, "caminho direto: deve passar"),
    (tmp_base.parent / "FORA_DA_RAIZ.py", False, "fora da raiz: deve ser barrado"),
    (tmp_base / "sub" / ".." / ".." / "FORA.py", False, ".. que SAI: deve ser barrado"),
]
for alvo, esperado, descricao in casos_com_raiz:
    obtido = reg.in_scope("maker", str(alvo), raiz=str(tmp_base))
    marca = "OK   " if obtido == esperado else "FALHA"
    print(f"[{marca}] {descricao}")
    if obtido != esperado:
        print(f"        esperado={esperado} obtido={obtido}  <- {alvo}")
    check(descricao, obtido == esperado, f"in_scope={obtido} esperado={esperado}")

print()
print("=" * 72)
print("3b. SEM RAIZ: `..` continua barrado (piso de seguranca)")
print("=" * 72)
for alvo, descricao in [
    (tmp_base / "sub" / ".." / "dentro.py", "sem raiz, .. barrado"),
]:
    permitido = reg.in_scope("maker", str(alvo))
    esperado_bool = not permitido
    check(descricao, esperado_bool, f"in_scope={permitido}")

# E o caminho sem `..` continua funcionando sem raiz (uso avulso).
check(
    "sem raiz, caminho direto continua ok",
    reg.in_scope("maker", str(tmp_base / "direto.py")),
)

print()
print("=" * 72)
print("4. O QUE DEVE PASSAR: caminho normal dentro do escopo")
print("=" * 72)
for p in [
    str(Path(__file__).resolve().parent / "registry.py").replace("\\", "/"),
    "C:/proj/app.py",
    "C:/proj/sub/mod.py",
    "C:/proj/README.md",
]:
    check(f"permitido: {p[-34:]}", reg.in_scope("maker", p))

print()
print("=" * 72)
print("5. O QUE DEVE SER BARRADO: extensao, diretorio e caminho vazio")
print("=" * 72)
for p in [
    "C:/proj/malware.exe",
    "C:/proj/config.sh",
    "/etc/passwd",
    str(tmp_base),  # diretorio: nao e arquivo
    "",  # vazio
]:
    check(f"barrado: {p[-24:] if p else '(vazio)'}", not reg.in_scope("maker", p))

print()
print("=" * 72)
print("6. EXPLOIT END-TO-END: o host realmente impede a gravacao?")
print("=" * 72)
import agent as agent_mod  # noqa: E402
import tempfile  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="escape_"))
alvo_fora = (tmp / ".." / "SAIU_DO_TEMP.py").resolve()
alvo_fora.parent.mkdir(parents=True, exist_ok=True)

# Caminho que casa com *.py mas ESCAPE do diretorio.
caminho_malicioso = str(tmp / ".." / "SAIU_DO_TEMP.py")
print(f"  diretorio autorizado: {tmp}")
print(f"  caminho malicioso   : {caminho_malicioso}")
print(
    f"  casa com '*.py'?    {__import__('fnmatch').fnmatch(caminho_malicioso.replace(chr(92), '/'), '*.py')}"
)

# COM raiz: e o caminho que o orquestrador usa, porque ele sabe o alvo.
tr = agent_mod.dispatch(
    "write_file",
    {"path": caminho_malicioso, "content": "pwned"},
    "maker",
    raiz=str(tmp),
)
print(f"  dispatch (com raiz) -> ok={tr.ok}  negado={'SIM' if tr.denied else 'NAO'}")
if tr.denied:
    print(f"    motivo: {tr.denied[:150]}")
check(
    "com raiz: host BARREU a escrita fora do escopo",
    tr.denied is not None,
    "VULNERAVEL" if tr.denied is None else "",
)
check(
    "com raiz: arquivo fora NAO foi criado",
    not alvo_fora.exists(),
    f"existe={alvo_fora.exists()}",
)

# SEM raiz: o piso de seguranca (barrar `..`) tem de continuar valendo.
tr_sem_raiz = agent_mod.dispatch(
    "write_file", {"path": caminho_malicioso, "content": "pwned2"}, "maker"
)
check(
    "sem raiz: host BARREU a escrita fora do escopo",
    tr_sem_raiz.denied is not None,
    "VULNERAVEL" if tr_sem_raiz.denied is None else "",
)
check(
    "sem raiz: arquivo fora NAO foi criado",
    not alvo_fora.exists(),
    f"existe={alvo_fora.exists()}",
)

# E o caminho legitimo tem que funcionar, senao "corrigi" quebrando tudo.
dentro = tmp / "dentro.py"
tr2 = agent_mod.dispatch(
    "write_file", {"path": str(dentro), "content": "ok"}, "maker", raiz=str(tmp)
)
check("host PERMITE escrita legitima", tr2.ok and dentro.exists(), f"ok={tr2.ok}")

# O CASO QUE O COMITE PEDIU: `..` que cancela dentro tem que GRAVAR de
# verdade, nao so passar no in_scope. E o que estava sendo recusado.
print()
print("  --- `..` inofensivo tem que GRAVAR de verdade (com raiz) ---")
(tmp / "sub").mkdir(exist_ok=True)
caminho_com_dotdot = tmp / "sub" / ".." / "criado_via_dotdot.py"
tr3 = agent_mod.dispatch(
    "write_file",
    {"path": str(caminho_com_dotdot), "content": "# criado via sub/../\n"},
    "maker",
    raiz=str(tmp),
)
print(f"    path : {caminho_com_dotdot}")
print(f"    real : {caminho_com_dotdot.resolve()}")
print(f"    ok={tr3.ok} negado={'SIM' if tr3.denied else 'NAO'}")
if tr3.denied:
    print(f"    motivo: {tr3.denied[:140]}")
check(
    "GRAVOU via `..` que nao escapa (o pedido do comite)",
    tr3.ok and caminho_com_dotdot.resolve().exists(),
    f"ok={tr3.ok} existe={caminho_com_dotdot.resolve().exists()}",
)
check(
    "`..` inofensivo nao e negado",
    tr3.denied is None,
    str(tr3.denied)[:100] if tr3.denied else "",
)

# Limpeza
for p in (alvo_fora,):
    try:
        p.unlink(missing_ok=True)
    except Exception:
        pass

print()
print("=" * 72)
if FALHAS:
    print(f"VULNERABILIDADES / FALHAS: {len(FALHAS)}")
    for f in FALHAS:
        print(f"  - {f}")
    sys.exit(1)
print("NENHUMA ESCADA: o escopo segura em todos os testes")
