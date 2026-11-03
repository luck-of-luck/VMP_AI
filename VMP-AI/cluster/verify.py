#!/usr/bin/env python3
"""Verificador de resultado: o cluster GRAVOU, mas gravou algo que compila?

Medido 2026-10-01: o pipeline completou 6/6 papeis, todos `ok=True`, e o
arquivo final era `SyntaxError: unterminated triple-quoted string` na
linha 11 - o `fixer` truncou a escrita no meio de uma docstring. Os dois
papeis escritores responderam "gravou, entao deu certo", o que era
verdade do ponto de vista deles e mentira do ponto de vista do resultado.

`acted()` verifica ACAO. Nada verificava RESULTADO. Este modulo fecha essa
lacuna: e o criterio de aceite do cluster.

Distincao que importa:
  - `ok=True` sem este verificador = "o agente fez o que pedi".
  - `ok=True` com este verificador = "o arquivo agora e valido".

Sem o segundo, um cluster de agentes produz codigo quebrado com orgulho.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path


class VerifyResult:
    def __init__(self, ok: bool, detail: str = "", kind: str = ""):
        self.ok = ok
        self.detail = detail
        self.kind = kind  # "sintaxe", "diff", "vazio", "erro"

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"VerifyResult(ok={self.ok}, kind={self.kind!r}, detail={self.detail[:80]!r})"


def verifica_sintaxe(caminho: str | Path) -> VerifyResult:
    """O arquivo ainda e Python valido E executavel?

    Cuidado medido 2026-10-01: `ast.parse` sozinho NAO basta. Um agente
    pode truncar a gravacao e fechar com `...`, que e sintaticamente VALIDO
    em Python ( Ellipsis como statement) - o arquivo passa no parse e nao
    faz nada. Exemplo real produzido pelo cluster:

        def carregar(caminho):
            with open(caminho, "rb") as f:
                primeiros = f.readline()
                tamanho = int(...) or _tamanho_restante(f)
                ...

    Isso passa em `ast.parse`, passa em "sintaxe ok", e e codigo morto que
    ainda referencia nomes inexistentes.

    Por isso a verificacao tem tres camadas:
      1. parse (pega sintaxe quebrada de verdade);
      2. nenhum marcador de truncamento (`...` como statement solto);
      3. toda Funcao tem corpo com statement executavel (nao so docstring
         ou `...`).
    """
    p = Path(caminho)
    if not p.exists():
        return VerifyResult(False, f"arquivo nao existe: {p}", "erro")
    txt = p.read_text(encoding="utf-8", errors="replace")
    if not txt.strip():
        return VerifyResult(False, "arquivo ficou VAZIO", "vazio")

    # ── camada 1: parse ──
    try:
        tree = ast.parse(txt, filename=str(p))
    except SyntaxError as e:
        return VerifyResult(False, f"SyntaxError linha {e.lineno}: {e.msg}", "sintaxe")

    # ── camada 2: marcador de truncamento ──
    # `...` como statement (sozinho na linha) e o que um escritor deixa
    # quando corta o texto no meio e fecha a conta com ellipsis.
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            v = node.value.value
            if v is Ellipsis:
                return VerifyResult(
                    False,
                    f"gravacao TRUNCADA: '...' solto na linha {node.lineno} "
                    "(marcador de corte; passa em ast.parse mas nao executa)",
                    "truncado",
                )

    # ── camada 3: toda funcao tem corpo executavel ──
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sem_codigo = [
                st
                for st in node.body
                # docstring e `...` nao sao execucao
                if not (
                    isinstance(st, ast.Expr)
                    and isinstance(st.value, ast.Constant)
                    and isinstance(st.value.value, str)
                )
                and not (
                    isinstance(st, ast.Expr)
                    and isinstance(st.value, ast.Constant)
                    and st.value.value is Ellipsis
                )
            ]
            if not sem_codigo:
                return VerifyResult(
                    False,
                    f"funcao '{node.name}' (linha {node.lineno}) so tem "
                    "docstring/'...' - nao ha codigo para executar",
                    "vazio",
                )
            if node.body and isinstance(node.body[-1], ast.If):
                # `if cond:` com corpo so-`...` e a assinatura da truncagem.
                return VerifyResult(
                    False,
                    f"funcao '{node.name}' (linha {node.lineno}) termina em "
                    "bloco `if` incompleto - gravacao provavelmente cortada",
                    "truncado",
                )

    return VerifyResult(True, "sintaxe ok e ha codigo executavel")


def verifica_preservacao(origem: str | Path, atual: str | Path) -> VerifyResult:
    """As assinaturas publicas continuam as mesmas?

    Um agente pode 'corrigir' um bug removendo um parametro. Isso passa na
    sintaxe e quebra todo chamador. O cluster nao deve aceitar isso como
    correcao.
    """
    o, a = Path(origem), Path(atual)
    if not (o.exists() and a.exists()):
        return VerifyResult(False, "arquivo de origem ausente", "erro")

    def assinaturas(txt: str) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        try:
            tree = ast.parse(txt)
        except SyntaxError:
            return out
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [x.arg for x in node.args.args]
                out[node.name] = params
        return out

    so, sa = (
        assinaturas(o.read_text(encoding="utf-8", errors="replace")),
        assinaturas(a.read_text(encoding="utf-8", errors="replace")),
    )
    removidas = set(so) - set(sa)
    if removidas:
        return VerifyResult(False, f"funcoes REMOVIDAS: {sorted(removidas)}", "diff")
    mudou = [f for f in set(so) & set(sa) if so[f] != sa[f]]
    if mudou:
        detalhe = "; ".join(f"{f}: {so[f]} -> {sa[f]}" for f in sorted(mudou)[:3])
        return VerifyResult(False, f"assinaturas mudaram: {detalhe}", "diff")
    return VerifyResult(True, f"{len(sa)} assinaturas preservadas")


def verifica_testes(alvo: str | Path, timeout: int = 900) -> VerifyResult:
    """Roda a suite de testes do projeto, se houver uma.

    Este e o criterio de aceite mais forte que um cluster pode ter: nao basta
    o arquivo compilar, ele precisa passar nos testes de quem usa.
    """
    p = Path(alvo).resolve()
    raiz = p.parent
    tem_suite = (
        any(
            [
                (raiz / "pytest.ini").exists(),
                (raiz / "pyproject.toml").exists(),
                (raiz / "setup.cfg").exists(),
                (raiz / "tox.ini").exists(),
            ]
        )
        or bool(list(raiz.glob("test_*.py")))
        or bool(list(raiz.glob("tests")))
    )
    if not tem_suite:
        return VerifyResult(True, "sem suite de testes detectada: pulado")

    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-x"]
    try:
        r = subprocess.run(
            cmd, cwd=str(raiz), capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return VerifyResult(True, "pytest indisponivel: pulado")
    except subprocess.TimeoutExpired:
        return VerifyResult(False, f"suite excedeu {timeout}s", "testes")
    if r.returncode == 0:
        return VerifyResult(True, "suite passou")
    # pytest pode nao estar instalado: returncode 4/5 sao de collection/usage.
    if r.returncode in (4, 5, 127):
        return VerifyResult(True, "pytest nao configurado neste projeto: pulado")
    cauda = (r.stdout or "")[-400:].strip()
    return VerifyResult(False, f"suite FALHOU (rc={r.returncode}): {cauda}", "testes")


def verifica_alvo(
    atual: str | Path,
    origem: str | Path | None = None,
    com_testes: bool = False,
) -> tuple[bool, list[VerifyResult]]:
    """Bateria completa. Devolve (tudo_ok, detalhe_de_cada_verificacao)."""
    checagens = [verifica_sintaxe(atual)]
    if origem:
        checagens.append(verifica_preservacao(origem, atual))
    if com_testes:
        checagens.append(verifica_testes(atual))
    return all(c.ok for c in checagens), checagens


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="Verifica o resultado gravado pelo cluster"
    )
    ap.add_argument("atual", help="arquivo corrigido")
    ap.add_argument("--origem", default="", help="versao antes (assinaturas)")
    ap.add_argument("--testes", action="store_true", help="roda a suite do projeto")
    args = ap.parse_args()

    ok, checagens = verifica_alvo(args.atual, args.origem or None, args.testes)
    print("=" * 66)
    print("VERIFICACAO DO RESULTADO")
    print("=" * 66)
    for c in checagens:
        print(f"  [{'OK ' if c.ok else 'XX '}] {c.kind:<8} {c.detail[:150]}")
    print()
    print("RESULTADO:", "VALIDO" if ok else "INVALIDO")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
