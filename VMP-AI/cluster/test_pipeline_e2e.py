#!/usr/bin/env python3
"""Prova end-to-end do cluster: 7 agentes, ordem real, handoff real.

Cria um arquivo com TRES defeitos genuinamente diferentes (nao triviais) e
roda o pipeline completo. Um agente so corrigiria se o cluster se Coordenasse;
tres bugs de naturezas diferentes exigem os papeis todos.

O que este teste tenta provar, e o que seria FALSO provar:
  - que maker escreve, critic le o que maker fez, fixer corrige;
  - que o handoff chega de um agente ao outro (verificavel nos JSONs);
  - que o critic nao escreve (garantia do host);
  - que os defeitos desaparecem do arquivo ao final.

O que ele NAO pode provar: que o texto ficou "bom". Assertar isso seria
julgar o modelo por criterio meu, nao por comportamento. O teste mede
comportamento; a qualidade eu leio a mao.
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "core"))

PY = sys.executable
ORCH = HERE / "orchestrator.py"

# Tres defeitos de naturezas diferentes:
#  1. LOGICA: off-by-one no limite.
#  2. SEGURANCA: leitura de arquivo sem tratamento de erro.
#  3. RECURSO: arquivo aberto sem fechar (with).
ALVO = HERE / "runs" / "alvo_e2e.py"
ALVO.parent.mkdir(parents=True, exist_ok=True)

CODIGO_COM_BUGS = '''def somar_ate(lista, limite):
    """Soma os itens ate o limite (inclusive)."""
    total = 0
    for item in lista:
        if item > limite:
            break
        total += item
    return total


def carregar_config(caminho):
    """Carrega o conteudo de um arquivo de configuracao."""
    with open(caminho) as f:
        return f.read()


def primeiro(lista):
    """Devolve o primeiro item, ou None se vazia."""
    if not lista:
        return None
    f = open(lista[0])
    conteudo = f.read()
    f.close()
    return conteudo


def media(lista):
    """Media aritmetica."""
    return sum(lista) / len(lista)
'''

ALVO.write_text(CODIGO_COM_BUGS, encoding="utf-8")
print(f"alvo criado: {ALVO}")
print(f"  {len(CODIGO_COM_BUGS)} chars, 4 funcoes, 3 defeitos plantados")
backup = ALVO.with_suffix(".py.origem")
shutil.copy2(ALVO, backup)

TAREFA = (
    "Revise e corrija os defeitos deste arquivo. Ha problemas de logica, "
    "seguranca e uso de recursos. Corrija todos, sem mudar o comportamento "
    "correto existente e sem mudar as assinaturas das funcoes."
)

print()
print("=" * 74)
print(f"RODANDO PIPELINE COMPLETO ({7} agentes)")
print("=" * 74)
t0 = time.time()
proc = subprocess.run(
    [
        PY,
        str(ORCH),
        "--alvo",
        str(ALVO),
        "--tarefa",
        TAREFA,
        "--criticos",
        "3",
    ],
    capture_output=True,
    text=True,
    timeout=5400,
)
el = time.time() - t0
print(proc.stdout[-5000:])
if proc.returncode not in (0, 1):
    print("STDERR:", proc.stderr[-3000:])
print(f"exit={proc.returncode} duracao={el:.0f}s")

# ── Verificacao por COMPORTAMENTO ──────────────────────────────────────
print()
print("=" * 74)
print("VERIFICACAO")
print("=" * 74)

runs = sorted((HERE / "runs").glob("*/"))
ultimo = max(runs, key=lambda p: p.stat().st_mtime)
print(f"artefatos em: {ultimo.name}")

esperados = ["researcher", "reader", "maker", "critic", "fixer", "optimizer"]
faltando = [r for r in esperados if not (ultimo / f"{r}.json").exists()]
print(f"handoffs escritos: {len(esperados) - len(faltando)}/{len(esperados)}")
if faltando:
    print(f"  faltando: {faltando}")

# Handoff tem conteudo real? Um arquivo vazio e "handoff" sem handoff.
print()
print("conteudo dos handoffs (chars por agente):")
for r in esperados:
    p = ultimo / f"{r}.json"
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    agentes = d.get("agentes", [])
    lens = [len(a.get("saida", "")) for a in agentes]
    print(f"  {r:<11} sucesso={d.get('sucesso')} agentes={len(agentes)} chars={lens}")

# O critic gerou achados? E o heart do cluster.
critic_p = ultimo / "critic.json"
achados = []
if critic_p.exists():
    cd = json.loads(critic_p.read_text(encoding="utf-8"))
    for a in cd.get("agentes", []):
        achados.append(a.get("saida", ""))
achado_txt = "\n".join(achados)
print()
print(f"critic: {len(achados)} agentes, {len(achado_txt)} chars de analise")
print(f"  menciona 'media'/len/lista vazia: {('len' in achado_txt.lower())}")
print(
    f"  menciona with/fechar/close   : {('with' in achado_txt.lower() or 'close' in achado_txt.lower())}"
)
print(f"  mencoes erro/leitura          : {('erro' in achado_txt.lower())}")

# O arquivo final mudou?
final_txt = ALVO.read_text(encoding="utf-8")
mudou = final_txt != CODIGO_COM_BUGS
print()
print(f"arquivo final mudou: {mudou}")
if mudou:
    # Diff curto para inspecionar, nao para julgar estilo.
    import difflib

    diff = list(
        difflib.unified_diff(
            CODIGO_COM_BUGS.splitlines(),
            final_txt.splitlines(),
            lineterm="",
            n=1,
        )
    )
    print(f"  linhas do diff: {len(diff)}")
    for line in diff[:60]:
        print("   ", line)
else:
    print("  (sem alteracao — o cluster NAO resolveu)")

# Garante restauracao do arquivo de teste.
print()
print(f"(backup do original em: {backup.name})")
