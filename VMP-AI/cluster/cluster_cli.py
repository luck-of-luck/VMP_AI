#!/usr/bin/env python3
"""CLI do cluster, para o opencode chamar via comando `!`.

Dois subcomandos:

  standby   verifica e aquece o pool, imprime o estado. Nao executa trabalho.
  run       roda o pipeline completo e imprime o resumo.

Um detalhe que importa: o stdout aqui vai DIRETO para o prompt do opencode.
Entao (a) ASCII puro, sem acento e sem box-drawing - o console do Windows
(cp1252) quebra em multi-byte e o prompt receberia lixo; e (b) sem volume
desnecessario, porque tudo isso vira token do modelo que le o resultado.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (str(HERE), str(HERE / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

# stdout em utf-8 com replace: o console do Windows e cp1252, e um unico
# acento quebraria o processo inteiro (UnicodeEncodeError), Losing a
# execucao por causa de um "cao" e o tipo de falha boba que mais custou
# tempo nesta construcao. ASCII puro no conteudo, utf-8 no canal.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def cmd_standby(args: argparse.Namespace) -> int:
    from pool import AgentPool

    pool = AgentPool(args.slots)
    t0 = time.time()
    st = pool.standby()
    el = time.time() - t0

    print("=" * 68)
    print(f"POOL DE AGENTES PRONTO - {st.slots_ok}/{st.slots_total} slots")
    print("=" * 68)
    print(f"modelo        : {st.model}")
    print(f"verificacao   : {el:.1f}s")
    print(f"cache prompt  : {'quente' if st.cache_warm else 'frio'}")
    print(
        f"handshake med : {st.handshake_median:.2f}s"
        if st.handshake_median
        else "handshake med : -"
    )
    print()
    print(f"{'slot':<6}{'papel':<12}{'estado':<10}{'latencia'}")
    for s in pool.slots:
        estado = "pronto" if s.ok else "FALHOU"
        print(f"{s.idx:<6}{s.role:<12}{estado:<10}{s.latency:.2f}s")
        if not s.ok and s.error:
            print(f"       erro: {s.error[:100]}")
    print()

    if st.ready:
        print("STATUS: PRONTO. Todos os slots respondem.")
        print("Use /cluster <arquivo> <tarefa> para rodar o pipeline de 10 agentes.")
        print()
        print("Observacao honesta sobre o que 'pronto' significa:")
        print("  - a credencial responde e a cota esta viva AGORA")
        print("  - o prompt cache de cada slot esta aquecido (system prompt estavel)")
        print("  - NAO e conexao TCP quente: o relay usa keep-alive e e justamente ele")
        print("    que causa 'SSL: BAD_RECORD_MAC'. Cada chamada paga um handshake.")
        return 0

    print("STATUS: NAO PRONTO. Nao execute o pipeline ainda.")
    for e in st.errors:
        print(f"  - {e}")
    print()
    print("Causas provaveis:")
    print(
        "  - OPENCODE_ZEN_API_KEY ausente ou invalida em %s"
        % (Path(__file__).resolve().parents[2] / ".env")
    )
    print("  - cota do relay esgotada (o cluster usa UM token; sem fallback interno)")
    print("  - rede / relay fora do ar (medido: sem credencial todas as 15 falham)")
    return 1


def cmd_run(args: argparse.Namespace) -> int:
    import orchestrator as orch

    alvo = Path(args.alvo)
    if not alvo.exists():
        print(f"ERRO: alvo inexistente: {alvo}")
        return 2

    from pool import AgentPool

    pool = AgentPool(args.slots)
    st = pool.standby()
    print(
        f"[pre-flight] pool {st.slots_ok}/{st.slots_total} pronto "
        f"({st.handshake_median:.1f}s por slot)"
        if st.handshake_median
        else f"[pre-flight] pool {st.slots_ok}/{st.slots_total}"
    )
    if not st.ready:
        print("ABORTADO: o pool nao ficou pronto. Nao vou comecar trabalho serio")
        print("com agentes que nao respondem - isso produz resultado falso.")
        for e in st.errors:
            print(f"  - {e}")
        return 1

    sys.argv = [
        "orchestrator",
        "--alvo",
        str(alvo),
        "--tarefa",
        args.tarefa,
        "--criticos",
        str(args.criticos),
    ]
    if args.ate:
        sys.argv += ["--ate", args.ate]
    return orch.main()


def cmd_status(args: argparse.Namespace) -> int:
    """Estado do ultimo run, sem chamar a rede."""
    runs = sorted(
        (
            p
            for p in (HERE / "runs").glob("*/")
            if (p / "resumo.txt").exists() or any(p.glob("*.json"))
        ),
        key=lambda p: p.stat().st_mtime,
    )
    if not runs:
        print("Nenhum run encontrado em", HERE / "runs")
        return 1
    ultimo = runs[-1]
    print(f"ultimo run: {ultimo.name}")
    print(
        f"em        : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ultimo.stat().st_mtime))}"
    )
    print()
    papeis = ["researcher", "reader", "maker", "critic", "fixer", "optimizer"]
    for papel in papeis:
        p = ultimo / f"{papel}.json"
        if not p.exists():
            print(f"  {papel:<11} (nao rodou)")
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  {papel:<11} (handoff ilegivel: {e})")
            continue
        ok = d.get("sucesso")
        agentes = d.get("agentes", [])
        marca = "OK " if ok else "XX "
        chars = [len(a.get("saida", "")) for a in agentes]
        print(f"  {marca}{papel:<11} {len(agentes)} agente(s)  chars={chars}")
        if not ok and d.get("motivo"):
            print(f"      motivo: {d['motivo'][:110]}")
    print()
    print(f"artefatos: {ultimo}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="CLI do cluster de agentes")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("standby", help="verifica e aquece o pool")
    s1.add_argument("--slots", type=int, default=10)
    s1.set_defaults(fn=cmd_standby)

    s2 = sub.add_parser("run", help="roda o pipeline completo")
    s2.add_argument("--alvo", required=True)
    s2.add_argument("--tarefa", required=True)
    s2.add_argument("--criticos", type=int, default=3)
    s2.add_argument("--slots", type=int, default=10)
    s2.add_argument("--ate", default="", help="para apos este papel")
    s2.set_defaults(fn=cmd_run)

    s3 = sub.add_parser("status", help="estado do ultimo run (offline)")
    s3.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    try:
        return args.fn(args)
    except KeyboardInterrupt:
        print("interrompido")
        return 130


if __name__ == "__main__":
    sys.exit(main())
