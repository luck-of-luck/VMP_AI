#!/usr/bin/env python3
"""Orquestrador do cluster: ordem, handoff e gate de qualidade.

O orquestrador e soberano. O modelo sugere; ele decide. Concretamente:

  - a ORDEM e fixa (`registry.PIPELINE`) e nao muda porque um agente pediu;
  - o HANDOFF e arquivo em disco, nao memoria de processo: um agente que
    "nasce" le o que o anterior deixou, e o resultado sobrevive a uma falha;
  - o PARALELISMO so existe onde faz sentido (varios `critic` com lentes
    distintas). As demais etapas sao sequenciais porque dependem da anterior;
  - existe um GATE: se a etapa de revisao nao rodar, o pipeline PARA em vez
    de seguir para `fixer` as cegas.

Ultimo ponto e o mais importante. Um pipeline que pula a revisao quando a
revisao falha parece rapido e produz o defeito silenciosamente - exatamente o
modo de falha que um cluster de agentes promete eliminar.

Uso:
    python orchestrator.py --alvo <arquivo_ou_dir> --tarefa "<o que fazer>" [--criticos N]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE / "core") not in sys.path:
    sys.path.insert(0, str(HERE / "core"))

from agent import AgentRun, acted, run_agent_resilient as run_agent  # noqa: E402
import verify as verifier  # noqa: E402
import registry as reg  # noqa: E402

RUNS = HERE / "runs"

# Quantos agentes por etapa. So o 'critic' ganha mais de um, porque e o unico
# papel que rende com paralelismo (lentes diferentes, mesmo alvo).
DEFAULT_PARALLEL = {
    "researcher": 1,
    "reader": 1,
    "maker": 1,
    "critic": 3,
    "fixer": 1,
    "optimizer": 1,
}


@dataclass
class StageResult:
    role: str
    runs: list[AgentRun] = field(default_factory=list)
    ok: bool = True
    reason: str = ""
    # Parte dos agentes rodou em paralelo e falhou, mas o suficiente respondeu.
    partial: bool = False


@dataclass
class Pipeline:
    run_id: str
    target: str
    task: str
    out: Path
    snapshot: Path | None = None
    stages: dict[str, StageResult] = field(default_factory=dict)

    def path(self, name: str) -> Path:
        return self.out / name

    def write_handoff(self, role: str, payload: dict) -> None:
        p = self.path(f"{role}.json")
        p.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def read_upstream(self, roles: tuple[str, ...]) -> dict:
        """Le o handoff das etapas anteriores. O que nao existe, se diz."""
        out = {}
        for r in roles:
            p = self.path(f"{r}.json")
            if p.exists():
                try:
                    out[r] = json.loads(p.read_text(encoding="utf-8"))
                except Exception as e:
                    out[r] = {"_erro": f"handoff ilegivel: {e}"}
            else:
                out[r] = {"_ausente": f"{r} nao produziu handoff"}
        return out


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _summarize(r: AgentRun, idx: int, total: int) -> dict:
    return {
        "agente": f"{r.role}#{idx + 1}" if total > 1 else r.role,
        "ok": r.ok,
        "saida": r.final[:4000],
        "lentes": r.finish_reason,
        "ferramentas": [{"nome": t["name"], "ok": t["ok"]} for t in r.tool_calls],
        "escritas_negadas": r.denied_writes,
        "erros_recuperados": r.recovered,
        "latencia_s": round(r.latency, 1),
    }


def run_stage(
    p: Pipeline,
    role: str,
    n: int,
    *,
    lens: str | None = None,
    upstream: tuple[str, ...] = (),
) -> StageResult:
    """Executa um papel. `n` agentes em paralelo so quando o papel permite."""
    log(f"-> {role}" + (f" x{n} paralelo" if n > 1 else ""))

    runs: list[AgentRun] = []
    # 429/402 sao sinal de cota, nao de erro pontual: reduz carga e espera.
    for attempt in range(4):
        if n == 1:
            r = run_agent(
                role,
                p.task,
                lens=lens,
                handoff=p.read_upstream(upstream) if upstream else None,
                target=p.target,
            )
            runs = [r]
        else:
            # Paralelismo so rende com lentes DISTINTAS: n copias do mesmo
            # prompt tendem a devolver o mesmo achado (e a gastar n vezes o
            # mesmo tokens para isso).
            if lens:
                pool = [lens] * n
            else:
                pool = (list(reg.CRITIC_LENSES) * n)[:n]
            with ThreadPoolExecutor(max_workers=n) as ex:
                futs = [
                    ex.submit(
                        run_agent,
                        role,
                        p.task,
                        lens=lg,
                        handoff=p.read_upstream(upstream) if upstream else None,
                        target=p.target,
                    )
                    for lg in pool
                ]
                runs = [f.result() for f in futs]

        quota = [r for r in runs if r.error and r.error.startswith("COTA_EXCEDIDA")]
        if quota and attempt < 3:
            wait = 20 * (attempt + 1)
            log(f"   cota excedida. reduzindo carga: {n} -> 1, aguardando {wait}s")
            n, time.sleep(wait)
            n = 1
            continue
        break

    ok = all(r.ok for r in runs)
    res = StageResult(
        role=role,
        runs=runs,
        ok=ok,
        reason="" if ok else "; ".join((r.error or "?")[:90] for r in runs if not r.ok),
    )

    # Um papel QUE ESCREVE e nao escreve nao teve sucesso. Medido
    # 2026-10-01: o `maker` devolveu o codigo corrigido em bloco de texto, nao
    # chamou write_file, e o pipeline seguiu como se estivesse feito. Fala nao
    # e acao; so conta `write_file` bem-sucedido.
    sem_acao: list[int] = []
    if reg.manifest(role).writes and res.ok:
        sem_acao = [i for i, r in enumerate(runs) if not acted(r)]
        if sem_acao:
            # Uma segunda tentativa com a tarefa reforcada. Medido: o maker
            # respondeu com relatorio e nao gravou; com o lembrete explicito
            # de "use write_file" ele grava. Desistir na primeira custa o
            # pipeline inteiro.
            log(f"   {role}: falou mas nao agiu. tentando de novo com reforco...")
            for i in sem_acao:
                runs.pop(i)
            n = 1
            reforco = (
                f"{p.task}\n\nIMPORTANTE DA ULTIMA VEZ: voce NAO chamou "
                "write_file na tentativa anterior e por isso o trabalho foi "
                "descartado. Agora: leia o alvo, faca a correcao e CHAME "
                "write_file com o conteudo completo do arquivo. Se nao for "
                "gravar, pare e diga por que."
            )
            runs = [
                run_agent(
                    role,
                    reforco,
                    target=p.target,
                    handoff=p.read_upstream(upstream) if upstream else None,
                )
            ]
            sem_acao = [i for i, r in enumerate(runs) if not acted(r)]
    # Tolerancia a falha parcial SO para papeis que rodam em paralelo com
    # lente distinta (hoje: os 3 criticos). Medido 2026-10-01: 2 de 3
    # criticos tiveram sucesso e acharam defeitos reais; o terceiro esbarrou
    # em orcamento. Reprovar a revisao inteira por causa de um agente joga
    # fora trabalho bom - e o gate de qualidade existe para pegar AUSENCIA
    # de revisao, nao para descartar revisao parcial.
    #
    # Regra: se pelo menos METADE dos agentes do papel respondeu, a etapa vale
    # (declarada com ressalva no handoff). Se NENHUM respondeu, e falha real.
    if len(runs) > 1 and res.ok:
        falhados = [r for r in runs if not r.ok]
        if falhados and len(falhados) <= len(runs) // 2:
            res.ok = True
            res.reason = ""
            res.partial = True
            log(
                f"   {role}: {len(falhados)} de {len(runs)} agentes falharam, mas "
                f"{len(runs) - len(falhados)} produziram revisao. Seguindo com ressalva."
            )

    # ── VERIFICACAO DE RESULTADO (o criterio de aceite do cluster) ──
    # `acted()` diz que o agente GRAVOU. Nao diz que o arquivo esta VALIDO.
    # Medido 2026-10-01: 6/6 papeis ok=True e o resultado foi
    # `SyntaxError: unterminated triple-quoted string` - um escritor truncou a
    # gravacao no meio de uma docstring, e o proximo agente construiu em cima.
    #
    # Apos um papel QUE GRAVA, o arquivo precisa continuar compilando. Se nao
    # continua, a etapa e FALHA e o pipeline para: nao existe "corrigir depois"
    # quando o ponto de partida ja esta quebrado.
    if reg.manifest(role).writes and p.snapshot is not None:
        destino = Path(p.target)
        if destino.suffix == ".py":
            chk = verifier.verifica_sintaxe(destino)
            if not chk.ok:
                res.ok = False
                res.reason = f"RESULTADO INVALIDO apos '{role}': {chk.detail}"
                log(f"   [FALHA] {role} QUEBROU o arquivo: {chk.detail}")
                log("   o pipeline para aqui: nao ha como o proximo agente")
                log("   corrigir um arquivo que nao compila.")
                # Restaura a versao boa. Um arquivo quebrado no disco e pior
                # que um arquivo intocado: o proximo agente (ou a proxima
                # pessoa) vai construir em cima de lixo, e o snapshot e
                # justamente a rede de seguranca contra isso. O conteudo
                # quebrado fica salvo em `_alvo_quebrado.py` para inspecao.
                if p.snapshot is not None and p.snapshot.exists():
                    try:
                        quebrado = p.out / "_alvo_quebrado.py"
                        try:
                            shutil.copy2(p.target, quebrado)
                        except Exception:
                            pass
                        shutil.copy2(p.snapshot, p.target)
                        log(f"   versao boa restaurada em {p.target}")
                        log(f"   o que o agente gravou (para inspecao): {quebrado}")
                    except Exception as e:
                        log(f"   nao consegui restaurar: {e}")
                        log(f"   versao boa esta em: {p.snapshot}")

    if sem_acao:
        res.ok = False
        res.reason = (
            f"{len(sem_acao)} de {len(runs)} agente(s) responderam mas NAO gravaram "
            "nada (nenhum write_file bem-sucedido). Descrever a correcao no texto "
            "nao e fazer a correcao."
        )
        for i in sem_acao:
            runs[i].ok = False
            runs[i].error = "respondeu sem gravar: nenhum write_file bem-sucedido"
        log(f"   [FALHA] {role}: falou mas nao agiu ({len(sem_acao)}/{len(runs)})")

    p.stages[role] = res

    payload = {
        "papel": role,
        "alvo": p.target,
        "tarefa": p.task,
        "sucesso": res.ok,
        "agentes": [_summarize(r, i, len(runs)) for i, r in enumerate(runs)],
    }
    if res.partial:
        payload["ressalva"] = (
            "parte dos agentes desta etapa falhou; a etapa segue com a "
            "revisao dos que responderam"
        )
    if not res.ok and res.reason:
        payload["motivo"] = res.reason
    p.write_handoff(role, payload)

    for i, r in enumerate(runs):
        tag = f"{role}#{i + 1}" if len(runs) > 1 else role
        if r.ok:
            log(f"   [OK] {tag} {r.latency:.0f}s {len(r.tool_calls)} tools")
        else:
            log(f"   [FALHA] {tag}: {(r.error or '')[:90]}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="Orquestrador do cluster de agentes")
    ap.add_argument("--alvo", required=True, help="arquivo ou diretorio alvo")
    ap.add_argument("--tarefa", required=True, help="o que o pipeline deve fazer")
    ap.add_argument(
        "--criticos", type=int, default=3, help="quantos critic em paralelo (1-5)"
    )
    ap.add_argument("--ate", default="", help="para apos este papel (ex.: critic)")
    ap.add_argument(
        "--model", default="", help="override do modelo (ex.: space-bunny-free)"
    )
    args = ap.parse_args()

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    out = RUNS / run_id
    out.mkdir(parents=True, exist_ok=True)

    alvo = Path(args.alvo)
    if not alvo.exists():
        log(f"ERRO: alvo inexistente: {alvo}")
        return 2

    if args.model:
        import agent as agent_mod

        agent_mod.MODEL = args.model

    # Snapshot do alvo ANTES de qualquer escrita: e o que permite dizer se o
    # cluster removeu ou mudou assinatura de alguma funcao (quebraria quem chama).
    snapshot = out / "_alvo_antes.py"
    try:
        if alvo.is_file():
            snapshot.write_text(
                alvo.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
            )
    except Exception:
        snapshot = None

    p = Pipeline(
        run_id=run_id, target=str(alvo), task=args.tarefa, out=out, snapshot=snapshot
    )
    log(f"run {run_id}")
    log(f"alvo: {alvo}")
    log(f"tarefa: {args.tarefa[:110]}")
    log(f"artefatos: {out}")

    if args.criticos < 1:
        args.criticos = 1
    if args.criticos > len(reg.CRITIC_LENSES):
        args.criticos = len(reg.CRITIC_LENSES)
    DEFAULT_PARALLEL["critic"] = args.criticos

    t0 = time.time()
    etapas = list(reg.PIPELINE)
    if args.ate:
        if args.ate not in etapas:
            log(f"ERRO: papel desconhecido em --ate: {args.ate}")
            return 2
        etapas = etapas[: etapas.index(args.ate) + 1]

    # Ordem do pipeline. Cada etapa le o handoff das anteriores.
    upstream_por_papel = {
        "researcher": (),
        "reader": ("researcher",),
        "maker": ("researcher", "reader"),
        "critic": ("researcher", "reader", "maker"),
        "fixer": ("researcher", "reader", "maker", "critic"),
        "optimizer": ("researcher", "reader", "maker", "critic", "fixer"),
    }

    halted = ""
    for role in etapas:
        n = DEFAULT_PARALLEL.get(role, 1)
        res = run_stage(p, role, n, upstream=upstream_por_papel.get(role, ()))
        if not res.ok:
            halted = role
            break

    log("-" * 60)
    if halted:
        log(f"PIPELINE PAROU em '{halted}'")
        log(f"motivo: {p.stages[halted].reason}")
        if halted == "critic":
            log("gate de qualidade: NAO avancou para 'fixer' sem revisao concluida.")
            log("isso e deliberado - pular a revisao introduz o defeito em silencio.")
    else:
        log("PIPELINE COMPLETO")
    log(f"duracao: {time.time() - t0:.0f}s")

    # Sumario por papel, para nao obrigar ninguem a abrir os JSONs.
    print()
    print("=" * 68)
    print("SUMARIO")
    print("=" * 68)
    for role, res in p.stages.items():
        # A marca vem do VEREDITO DA ETAPA, nao do run individual. Um agente
        # pode ter respondido (ok=True) e ainda assim a etapa ter falhado
        # porque o resultado que ele gravou nao compila. Mostrar "OK" aqui
        # seria dizer ao usuario que deu certo o que deu errado.
        marca = "OK " if res.ok else "XX "
        linhas = [f"{marca}{role:<11} {len(res.runs)} agente(s)"]
        if res.partial:
            linhas.append("     PARCIAL: parte dos agentes falhou; a etapa segue")
        if res.reason and not res.ok:
            linhas.append(f"     motivo: {res.reason[:120]}")
        for i, r in enumerate(res.runs):
            tag = f"#{i + 1}" if len(res.runs) > 1 else ""
            linhas.append(
                f"     {tag} ok={r.ok} {r.latency:.0f}s tools={len(r.tool_calls)} "
                f"chars={len(r.final)}"
            )
            if r.denied_writes:
                linhas.append(f"        escritas negadas: {len(r.denied_writes)}")
        print("\n".join(linhas))
    # Veredito final: o cluster terminou, mas o ARQUIVO e quem responde.
    print()
    print("=" * 68)
    print("VEREDITO DO RESULTADO")
    print("=" * 68)
    if p.snapshot is not None and Path(p.target).suffix == ".py":
        ok_res, checagens = verifier.verifica_alvo(
            p.target, p.snapshot, com_testes=False
        )
        for c in checagens:
            print(f"  [{'OK ' if c.ok else 'XX '}] {c.kind:<10} {c.detail[:140]}")
        print()
        print("RESULTADO FINAL:", "VALIDO" if ok_res else "INVALIDO")
        if not ok_res:
            print(f"  versao boa (antes do cluster): {p.snapshot}")
            print("  NENHUM agente pode ser considerado bem-sucedido sobre um")
            print("  arquivo invalido, por mais que os handoffs digam ok=True.")
    else:
        print("  (alvo nao e .py ou sem snapshot: verificacao de sintaxe pulada)")
    print()
    print(f"artefatos: {out}")
    (out / "resumo.txt").write_text(
        json.dumps(
            {r: s.__dict__ for r, s in p.stages.items()},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    # O codigo de retorno reflete o RESULTADO, nao apenas "o pipeline rodou".
    # Um pipeline que completa e produz codigo quebrado tem de sair != 0:
    # e o que o comando do opencode le para decidir se reporta sucesso.
    if halted:
        return 1
    if p.snapshot is not None and Path(p.target).suffix == ".py":
        ok_res, _ = verifier.verifica_alvo(p.target, p.snapshot, com_testes=False)
        if not ok_res:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
