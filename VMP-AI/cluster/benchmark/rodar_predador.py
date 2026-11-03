"""
Pipeline do predador contra o benchmark: comite (probabilistico) + scanners
(deterministicos), cruzados por LINHA.

Este script e a verificacao deterministica do predador. Ele:
  1. roda bandit / semgrep / ast-grep no planted.py
  2. le o ground_truth.json
  3. classifica cada achado: CONFIRMADO / CORROBORADO
  4. calcula recall separando "o scanner falhou" de "o scanner nao podia ver"

A distincao do item 4 e o ponto inteiro do exercicio. Contar um bug de
robustez (except generico) como false negative de um scanner de seguranca
seria fabricar um numero. Ground truth tem `detectavel_por` justamente para
impedir isso.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ALVO = HERE / "planted.py"
GT = HERE / "ground_truth.json"
SAST = Path(r"VMP-AI/mcps/sast-mcp/.venv/Scripts")
AST_GREP = Path(r"ast-grep")


def rodar(cmd, timeout=240):
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                **__import__("os").environ,
                "PATH": str(SAST) + ";" + __import__("os").environ.get("PATH", ""),
            },
        )
        return p.stdout, p.stderr, p.returncode
    except Exception as e:
        return "", f"{type(e).__name__}: {e}", -1


def bandit():
    out, err, rc = rodar(
        [str(SAST / "python.exe"), "-m", "bandit", "-r", str(ALVO), "-f", "json", "-q"]
    )
    achados = []
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            for r in d.get("results", []):
                achados.append(
                    {
                        "linha": r["line_number"],
                        "regra": r["test_id"],
                        "msg": r["issue_text"],
                        "sev": r["issue_severity"],
                    }
                )
        except Exception:
            pass
    return achados, rc == 0 or bool(achados)


def semgrep():
    out, err, rc = rodar(
        [
            r"uvx",
            "--quiet",
            "semgrep",
            "scan",
            "--config",
            "auto",
            "--json",
            "--quiet",
            str(ALVO),
        ]
    )
    achados = []
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            for r in d.get("results", []):
                achados.append(
                    {
                        "linha": r["start"]["line"],
                        "regra": r["check_id"].split(".")[-1],
                        "msg": (r.get("extra", {}).get("message", "") or "")[:80],
                        "sev": (r.get("extra", {}).get("severity", "") or "").upper(),
                    }
                )
        except Exception:
            pass
    return achados, rc == 0 or bool(achados)


def astgrep_smells():
    """ast-grep estrutural: procura finally sem try, open sem with."""
    achados = []
    if not AST_GREP.exists():
        return achados, False
    for pat, regra, msg in [
        ("f = open($P)", "open-sem-context", "open() sem with/context manager"),
        ("except Exception:", "except-generico", "except Exception genérico"),
    ]:
        out, err, rc = rodar(
            [str(AST_GREP), "run", "--pattern", pat, "--lang", "python", str(ALVO)]
        )
        ok = rc == 0
        for ln in re.findall(r"planted\.py:(\d+)", out):
            achados.append(
                {"linha": int(ln), "regra": regra, "msg": msg, "sev": "MEDIUM"}
            )
    return achados, True


def main():
    gt = json.loads(GT.read_text(encoding="utf-8"))
    bugs = {b["linha"]: b for b in gt["bugs"]}
    detectavel = {}
    for b in gt["bugs"]:
        detectavel[b["linha"]] = b["detectavel_por"]

    print("=" * 70)
    print("PIPELINE DO PREDADOR — verificacao deterministica")
    print("=" * 70)
    print(f"alvo: {ALVO.name}  ({sum(1 for _ in ALVO.open(encoding='utf-8'))} linhas)")
    print()

    resultados = {}
    for nome, fn in [
        ("bandit", bandit),
        ("semgrep", semgrep),
        ("astgrep", astgrep_smells),
    ]:
        achados, rodou = fn()
        resultados[nome] = achados
        status = "rodou" if rodou else "FALHOU"
        print(f"[{nome}] {status} — {len(achados)} achado(s)")
        for a in sorted(achados, key=lambda x: x["linha"]):
            marca = ""
            if a["linha"] in bugs:
                marca = f"  <== bug #{bugs[a['linha']]['id']} PLANTADO"
            print(f"    L{a['linha']:<4} [{a['regra']:<28}] {a['msg'][:42]}{marca}")
        print()

    # cruzamento por linha
    linhas = {}
    for nome, achados in resultados.items():
        for a in achados:
            linhas.setdefault(a["linha"], set()).add(nome)

    print("-" * 70)
    print("CRUZAMENTO (por linha)")
    print("-" * 70)
    confirmados, corroborados = [], []
    for ln in sorted(linhas):
        quem = linhas[ln]
        tag = "CORROBORADO" if len(quem) > 1 else "CONFIRMADO"
        (corroborados if tag == "CORROBORADO" else confirmados).append(ln)
        b = bugs.get(ln)
        desc = f"bug #{b['id']} {b['titulo']}" if b else "FORA DO GROUND TRUTH"
        print(f"  {tag:<13} L{ln:<4} {sorted(quem)}  {desc[:40]}")

    # recall honesto
    print()
    print("-" * 70)
    print("RECALL (so onde o scanner TEM como ver)")
    print("-" * 70)
    acertos, falhas, nao_visiveis = [], [], []
    for b in gt["bugs"]:
        ln = b["linha"]
        if ln in linhas:
            acertos.append(b["id"])
        elif ln in detectavel and detectavel[ln]:
            falhas.append((b["id"], ln, b["titulo"]))
        else:
            nao_visiveis.append(b["id"])

    print(f"  ACERTOS           : {len(acertos)}  {acertos}")
    print(f"  FALHAS REAIS      : {len(falhas)}  {[(i, l) for i, l, _ in falhas]}")
    print(f"  nao p/ scanner    : {len(nao_visiveis)}  {nao_visiveis}")
    if falhas:
        for i, ln, t in falhas:
            print(f"      ! bug #{i} (L{ln}) {t}")
    total_vis = len(acertos) + len(falhas)
    if total_vis:
        print(
            f"  RECALL: {len(acertos)}/{total_vis} = {len(acertos) / total_vis * 100:.0f}%"
        )
    print()
    print("  NOTA: 'nao p/ scanner' NAO e falha. Ground truth marca esses como")
    print("  inalcancavel para SAST — except generico e divisao por zero sao")
    print("  robustez, nao seguranca. Contar como false negative seria teatro.")
    print()
    print(f"  CONFIRMADOS : {len(confirmados)}")
    print(f"  CORROBORADOS : {len(corroborados)}")
    return 0 if not falhas else 2


if __name__ == "__main__":
    sys.exit(main())
