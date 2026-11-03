"""Pool de agentes em prontidao.

O que "prontidao" significa AQUI, medido em 2026-10-01:

  ENTREGA:
    - falha cedo se a credencial ou a cota morreu (na selecao, nao no meio
      da tarefa - o pior lugar para descobrir);
    - prompt cache ja aquecido: o system prompt estavel de cada papel vira
      token de graca (medido: 138 de 173 tokens em cache, 80%);
    - prova de que os N slots respondem AGORA, antes de prometer 10 agentes.

  NAO ENTREGA:
    - conexao quente. O relay (Cloudflare) anuncia keep-alive e e exatamente
      ele que produz "SSL: BAD_RECORD_MAC". Cada chamada paga um handshake
      (medido: mediana 1.87s). Nao ha como evitar sem reintroduzir o bug.

Ou seja: prontidao aqui e um POOL VERIFICADO, nao um keep-alive. Se este
arquivo prometer conexao persistente, ele esta mentindo.

O ciclo de vida e: `standby()` verifica e aquece; o cluster chama `dispatch()`
para trabalho real. O pool nao segura sockets - segura a certeza de que,
quando o trabalho comecar, a infra responde.
"""

from __future__ import annotations

import http.client
import json
import ssl
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for p in (str(_HERE), str(_HERE / "core")):
    if p not in sys.path:
        sys.path.insert(0, p)

import agent as agent_core  # noqa: E402
import registry as reg  # noqa: E402

HOST = agent_core.RELAY_HOST
PATH_ = agent_core.RELAY_PATH
MODEL = agent_core.MODEL

# Numero de slots. O pipeline usa 6 papeis; 3 criticos rodam em paralelo.
# 10 da folga para nunca serializar por falta de slot.
DEFAULT_SLOTS = 10


@dataclass
class Slot:
    """Um agente pronto, com o papel que ele vai interpretar."""

    idx: int
    role: str
    system_prompt: str
    tools: list[dict]
    max_tokens: int
    ok: bool = False
    latency: float = 0.0
    error: str | None = None

    @property
    def alive(self) -> bool:
        return self.ok


@dataclass
class PoolStatus:
    ready: bool
    slots_ok: int
    slots_total: int
    model: str
    cache_warm: bool
    checked_at: float
    errors: list[str] = field(default_factory=list)
    handshake_median: float | None = None


class AgentPool:
    """Pool verificado de slots prontos para trabalhar.

    Uso normal:

        pool = AgentPool(10)
        st = pool.standby()          # verifica credencial, cota e slots
        if not st.ready:
            print(st.errors); return
        run = pool.dispatch("critic", "tarefa...", target="app.py")

    `standby()` pode ser chamado a cada prompt: e barato (~3s para 10 slots) e
    e o que mantem o pool honesto. O relay pode estourar a cota a qualquer
    momento; um pool que so verifica na primeira vez mente sobre o estado.
    """

    def __init__(self, size: int = DEFAULT_SLOTS, model: str | None = None):
        self.size = max(1, int(size))
        self.model = model or MODEL
        self.slots: list[Slot] = []
        self._key: str | None = None
        self._lock = threading.Lock()
        self._cache_warm = False
        self._handshake: list[float] = []
        self._build_slots()

    # ── composicao dos slots ────────────────────────────────────────────
    def _system_prompt(self, role: str) -> str:
        """Exatamente o mesmo texto que `run_agent` manda, para que o
        prompt cache do relay acerte. Divergir aqui desperdicaria o cache."""
        m = reg.manifest(role)
        parts = [
            f"Voce e o agente '{role}' de um cluster com papeis separados.",
            f"SUA MISSAO: {m.mission}",
            f"SEU FOCO: {m.focus}",
        ]
        if m.lens:
            parts.append(f"LENTE DESTA TAREFA: {m.lens}")
        if m.writes:
            parts.append(
                "Voce PODE gravar em: "
                + ", ".join(m.write_scope)
                + ". Fora disso a escrita sera negada pelo host."
            )
        else:
            parts.append(
                "Voce NAO pode gravar nada. Seu papel e somente produzir relatorio em texto."
            )
        parts.append(
            "REGRA: use as ferramentas para VER. Nao afirme que leu algo que nao leu. "
            "Cite caminho e linha. Se nao souber, diga que nao sabe."
        )
        return "\n\n".join(parts)

    def _build_slots(self) -> None:
        """Distribui os papeis entre os slots.

        O pipeline chama papeis em ordem, e o 'critic' e o unico que paraleliza.
        Por isso a distribuicao garante os 6 papeis base e completa com o que
        sobra de onde mais rende paralelismo (criticos extras).
        """
        base = list(reg.PIPELINE)
        seq = list(base)
        i = 0
        while len(seq) < self.size:
            # Prioriza 'critic' como preenchimento: e o papel que mais ganha
            # rodando em paralelo.
            seq.append("critic" if i % 3 != 2 else base[i % len(base)])
            i += 1
        self.slots = [
            Slot(
                idx=n,
                role=role,
                system_prompt=self._system_prompt(role),
                tools=reg.tools_for(role),
                max_tokens=reg.manifest(role).max_tokens,
            )
            for n, role in enumerate(seq[: self.size])
        ]

    # ── transporte ──────────────────────────────────────────────────────
    def _ping(self, slot: Slot) -> None:
        """Verifica que o slot responde, e aquece o prompt cache dele."""
        if self._key is None:
            self._key = agent_core._key()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": slot.system_prompt},
                {"role": "user", "content": "Responda apenas: PRONTO"},
            ],
            "tools": slot.tools,
            "tool_choice": "auto",
            # A resposta de readiness e minúscula ("PRONTO"), mas o modelo
            # pode gastar o orcamento inteiro em reasoning antes. Medido: com
            # o piso de 256 um slot devolveu vazio. 1024 dá folga e ainda é
            # barato: sao ~4 tokens de saida.
            "max_tokens": 1024,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._key}",
            "User-Agent": agent_core.USER_AGENT,
            "Content-Length": str(len(body)),
        }
        t0 = time.time()
        conn = None
        try:
            conn = http.client.HTTPSConnection(
                HOST, 443, timeout=90, context=ssl.create_default_context()
            )
            conn.request("POST", PATH_, body=body, headers=headers)
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8", "replace"))
            if resp.status >= 400:
                slot.ok = False
                slot.error = f"HTTP {resp.status}: {json.dumps(data)[:120]}"
                return
            content = ((data.get("choices") or [{}])[0].get("message") or {}).get(
                "content"
            ) or ""
            slot.ok = bool(content.strip())
            slot.error = None if slot.ok else "resposta vazia no readiness"
            usage = data.get("usage") or {}
            cached = (usage.get("prompt_tokens_details") or {}).get(
                "cached_tokens"
            ) or 0
            if cached > 0:
                self._cache_warm = True
        except Exception as e:
            slot.ok = False
            slot.error = f"{type(e).__name__}: {str(e)[:100]}"
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        slot.latency = time.time() - t0
        self._handshake.append(slot.latency)

    # ── API publica ─────────────────────────────────────────────────────
    def standby(self) -> PoolStatus:
        """Verifica e aquece todos os slots. Barato (~3s para 10)."""
        with self._lock:
            self._handshake.clear()
            errors: list[str] = []
            try:
                self._key = agent_core._key()
            except Exception as e:
                return PoolStatus(
                    ready=False,
                    slots_ok=0,
                    slots_total=self.size,
                    model=self.model,
                    cache_warm=False,
                    checked_at=time.time(),
                    errors=[str(e)[:200]],
                )

            # Os slots sao verificados em paralelo: e o que torna isto
            # barato. Medido: 10 slots em 3.2s.
            with ThreadPoolExecutor(max_workers=self.size) as ex:
                list(ex.map(self._ping, self.slots))

            # Segunda passada so para quem falhou por resposta vazia. O
            # defeito e INTERMITENTE (medido em SPEC.md 3.2): o mesmo prompt
            # passa ou falha conforme o tamanho. Reprovar um slot por causa
            # disso e reprovar o pool inteiro.
            retry = [s for s in self.slots if not s.ok and "vazia" in (s.error or "")]
            if retry:
                with ThreadPoolExecutor(max_workers=len(retry)) as ex:
                    list(ex.map(self._ping, retry))

            for s in self.slots:
                if not s.ok:
                    errors.append(f"slot {s.idx} ({s.role}): {s.error}")

            lat = sorted(self._handshake)
            median = lat[len(lat) // 2] if lat else None
            ok_n = sum(1 for s in self.slots if s.ok)
            # Prontidao exige TODOS os slots. Cluster com metade dos agentes
            # prontos e um cluster que falha no meio - pior que recusar.
            return PoolStatus(
                ready=ok_n == self.size,
                slots_ok=ok_n,
                slots_total=self.size,
                model=self.model,
                cache_warm=self._cache_warm,
                checked_at=time.time(),
                errors=errors,
                handshake_median=median,
            )

    def dispatch(
        self,
        role: str,
        task: str,
        *,
        lens: str | None = None,
        handoff: dict | None = None,
        target: str = "",
    ) -> agent_core.AgentRun:
        """Entrega trabalho real a um slot com este papel.

        O pool NAO reimplementa a inferencia: chama `run_agent_resilient`, que
        ja tem o loop de ferramentas, o sandbox e o retry. O pool existe para
        saber que a infra responde, nao para duplicar o transporte.
        """
        if role not in self.slots_roles():
            raise ValueError(
                f"o pool nao tem slot para o papel '{role}'. "
                f"Papeis disponiveis: {sorted(self.slots_roles())}"
            )
        return agent_core.run_agent_resilient(
            role, task, lens=lens, handoff=handoff, target=target, model=self.model
        )

    def slots_roles(self) -> set[str]:
        return {s.role for s in self.slots}

    def report(self) -> str:
        """Relatorio curto para o usuario ver o que esta pronto."""
        ok_n = sum(1 for s in self.slots if s.ok)
        lat = sorted(s.latency for s in self.slots if s.latency)
        med = f"{lat[len(lat) // 2]:.2f}s" if lat else "-"
        linhas = [
            f"POOL {self.model}  {ok_n}/{self.size} slots prontos  "
            f"handshake mediano={med}  cache={'quente' if self._cache_warm else 'frio'}",
            "",
            f"{'slot':<6}{'papel':<12}{'estado':<9}{'latencia':<10}cache",
        ]
        for s in self.slots:
            estado = "pronto" if s.ok else "FALHOU"
            linhas.append(f"{s.idx:<6}{s.role:<12}{estado:<9}{s.latency:<10.2f}-")
            if not s.ok and s.error:
                linhas.append(f"       erro: {s.error[:80]}")
        return "\n".join(linhas)
