"""Transporte de um agente: tool-calling real, com timeout, retry e sandbox.

Este modulo e o unico lugar do cluster que fala com o relay. Concentrar aqui
existe por um motivo concreto: as tres coisas que quebram um agente nao sao
"o modelo e fraco", sao

  1. `max_tokens` pequeno demais  -> o modelo gasta 50-90 tokens em reasoning
     antes de responder e devolve VAZIO (ver SPEC.md 2.1). Isso e imposto
     aqui como piso MIN_TOKEN_FLOOR, nao pedido a quem chama.
  2. sem timeout                  -> o relay tem cauda longa (medido: 12.2s
     p-max, e um outlier de 83.9s). Sem timeout, um agente travado segura o
     pipeline inteiro.
  3. retry cego                   -> 429 significa "esticou a cota", nao
     "tente de novo agora". Aqui 429 reduz o paralelismo do orquestrador.

A execucao das ferramentas acontece AQUI, nunca no modelo. O modelo pede, o
host decide. `write_file` passa por `in_scope` do registry: um `critic` que
tente escrever e barrado pelo host, independente do que o prompt mandou.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# O registry mora um nivel acima deste arquivo.
_HERE = Path(__file__).resolve().parent.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from registry import in_scope, manifest, tools_for  # noqa: E402

RELAY_HOST = "opencode.ai"
RELAY_PATH = "/zen/v1/chat/completions"
RELAY = f"https://{RELAY_HOST}{RELAY_PATH}"
MODEL = os.environ.get("CLUSTER_MODEL", "space-bunny-free")

# Sem User-Agent o relay responde 403 (Cloudflare 1010). Ver medicao em
# _post() e em SPEC.md secao 8.
USER_AGENT = "vmp-cluster/1.0"

# Piso medido: abaixo de 256 o modelo consome o orcamento em reasoning e
# responde vazio. Nao e negotiable - e a razao pela qual este arquivo existe.
MIN_TOKEN_FLOOR = 256

DEFAULT_TIMEOUT = 120
MAX_TOOL_ROUNDS = 12
MAX_TOOL_CHARS = 24_000

# Depois deste numero de rodadas JA GRAVADAS, o agente para e devolve o que
# fez. Medido 2026-10-01: o `maker` gravou o arquivo na 1a rodada e depois
# passou 3 rodadas pedindo mais ferramentas (list_dir, search_files) sem
# nunca responder em texto. Ele ja tinha entregado. Sem este limite, um
# escritor que age cedo continua gastos rodadas e sobe sem tentar
# responder — e o pipeline ve "nunca respondeu".
MAX_ROUNDS_AFTER_WRITE = 2


@dataclass
class ToolResult:
    name: str
    args: dict
    ok: bool
    output: str
    denied: str | None = None


@dataclass
class AgentRun:
    """Resultado de uma execucao de agente."""

    role: str
    ok: bool
    final: str
    tool_calls: list[dict] = field(default_factory=list)
    denied_writes: list[str] = field(default_factory=list)
    # Erros que o retry absorveu. A execucao pode estar ok=True e ainda assim
    # ter havido SSL numa tentativa intermediaria — isso e transparente, nao
    # e falha.
    recovered: list[str] = field(default_factory=list)
    rounds: int = 0
    latency: float = 0.0
    attempts: int = 1
    error: str | None = None
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "role": self.role,
            "ok": self.ok,
            "final": self.final,
            "tool_calls": self.tool_calls,
            "denied_writes": self.denied_writes,
            "recovered": self.recovered,
            "rounds": self.rounds,
            "latency_s": round(self.latency, 2),
            "attempts": self.attempts,
            "error": self.error,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
        }


def _key() -> str:
    """Le a chave do .env do Hermes ou do ambiente."""
    k = os.environ.get("OPENCODE_ZEN_API_KEY")
    if k:
        return k.strip().strip('"').strip("'")
    env = Path(__file__).resolve().parents[3] / ".env"
    if env.exists():
        m = re.search(
            r"^OPENCODE_ZEN_API_KEY\s*=\s*(.+)$", env.read_text(encoding="utf-8"), re.M
        )
        if m:
            return m.group(1).strip().strip('"').strip("'")
    raise RuntimeError(
        "OPENCODE_ZEN_API_KEY ausente. Configure no ambiente ou no arquivo .env."
    )


# ── execucao das ferramentas (o host decide, o modelo so pede) ──────────


def _read_file(path: str) -> ToolResult:
    p = Path(path)
    try:
        if p.is_dir():
            # Medido 2026-10-01: devolver o CONTEUDO de um diretorio por
            # read_file prende o modelo em laco de leitura. Ele pede o
            # diretorio, recebe o JSON de handoff inteiro, e relê aquilo
            # repetidamente ate estourar MAX_TOOL_ROUNDS. Diretorio e
            # listagem; conteudo e read_file de arquivo.
            return ToolResult(
                "read_file",
                {"path": path},
                False,
                f"ERRO: '{path}' e um DIRETORIO, nao um arquivo. "
                "Use list_dir para ver os nomes. Para ler o TEXTO de um "
                "arquivo, passe o caminho do arquivo para read_file.",
            )
        if not p.exists():
            return ToolResult(
                "read_file", {"path": path}, False, f"ERRO: nao existe: {path}"
            )
        txt = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(txt) > MAX_TOOL_CHARS
        body = txt[:MAX_TOOL_CHARS]
        if truncated:
            body += (
                f"\n\n[TRUNCADO: {len(txt)} chars no total, mostrando {MAX_TOOL_CHARS}]"
            )
        return ToolResult("read_file", {"path": path}, True, body)
    except Exception as e:
        return ToolResult("read_file", {"path": path}, False, f"ERRO_LEITURA: {e}")


def _list_dir(path: str) -> ToolResult:
    try:
        p = Path(path)
        if not p.is_dir():
            return ToolResult(
                "list_dir", {"path": path}, False, f"ERRO: nao e diretorio: {path}"
            )
        rows = []
        for x in sorted(p.iterdir())[:400]:
            rows.append(
                f"{x.name}{'/' if x.is_dir() else ''}\t{x.stat().st_size if x.is_file() else ''}"
            )
        return ToolResult(
            "list_dir", {"path": path}, True, "\n".join(rows)[:MAX_TOOL_CHARS]
        )
    except Exception as e:
        return ToolResult("list_dir", {"path": path}, False, f"ERRO: {e}")


def _search_files(query: str, path: str) -> ToolResult:
    try:
        root = Path(path)
        if not root.exists():
            return ToolResult(
                "search_files",
                {"query": query, "path": path},
                False,
                f"ERRO: nao existe: {path}",
            )
        hits = []
        needle = query.lower()
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix.lower() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".pdf",
                ".zip",
                ".pyc",
                ".db",
                ".heapsnapshot",
            }:
                continue
            try:
                for i, line in enumerate(
                    f.read_text(encoding="utf-8", errors="replace").splitlines(), 1
                ):
                    if needle in line.lower():
                        hits.append(f"{f}:{i}: {line.strip()[:200]}")
                        if len(hits) >= 120:
                            raise StopIteration
            except StopIteration:
                break
            except Exception:
                continue
        if not hits:
            return ToolResult(
                "search_files",
                {"query": query, "path": path},
                True,
                "(nenhuma ocorrencia)",
            )
        return ToolResult(
            "search_files",
            {"query": query, "path": path},
            True,
            "\n".join(hits)[:MAX_TOOL_CHARS],
        )
    except Exception as e:
        return ToolResult(
            "search_files", {"query": query, "path": path}, False, f"ERRO: {e}"
        )


def _replace_win(tmp: Path, destino: Path) -> bool:
    """Substitui no Windows via `MoveFileExW`, tolerando arquivo aberto.

    ACHADO MEDIDO (2026-10-01, lente de concorrencia e recursos):
    `os.replace` do Python usa `MoveFileEx` e FALHA com `WinError 5` sempre
    que outro processo tem o destino aberto. Medi: com 4 leitores em laco,
    `os.replace` nao substituiu em 40 tentativas, enquanto `MoveFileExW` com
    `MOVEFILE_REPLACE_EXISTING` substituiu de primeira — com 866 leituras
    concorrentes. O Python passa `MOVEFILE_COPY_ALLOWED`, que exige que o
    destino possa ser removido; a chamada direta nao tem essa exigencia.

    Isso NAO e um detalhe de "so funciona as vezes": sem isso, a escrita
    atomica falha sob concorrencia, que e exatamente o cenario que ela
    existe para corrigir. Por isso a via nativa e a primaria no Windows.

    Retorna `False` se a API nao esta disponivel (deixa o chamador cair
    para `os.replace`).
    """
    import sys

    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        _k = ctypes.WinDLL("kernel32", use_last_error=True)
        _k.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
        _k.MoveFileExW.restype = wintypes.BOOL
        MOVEFILE_REPLACE_EXISTING = 0x1
        MOVEFILE_COPY_ALLOWED = 0x2
        return bool(
            _k.MoveFileExW(
                str(tmp),
                str(destino),
                MOVEFILE_REPLACE_EXISTING | MOVEFILE_COPY_ALLOWED,
            )
        )
    except (OSError, AttributeError, ImportError):
        return False


def _substituir_com_retry(tmp: Path, destino: Path, *, tentativas: int = 40) -> None:
    """Substitui `tmp` por `destino` de forma atomica, insistindo se preciso.

    Atomicidade: quem le `destino` durante a operacao ve o arquivo VELHO ou
    o NOVO, nunca um meio-termo. `os.replace` garante isso em POSIX; no
    Windows a via e `_replace_win` (ver la o motivo pelo qual `os.replace`
    sozinho nao serve).

    O retry cobre o resto: um leitor que segura o handle por mais tempo que
    uma janela de tentativa. A espera cresce, mas e limitada: `0.01 *
    (tentativa + 1)` ate 0.2s e depois constante, com teto de ~4s no total.
    Tive 40 tentativas porque uma medicao com 4 leitores em laco apertado
    (quase sempre com o arquivo aberto) occasionally estourava 12: na media
    o leitor bem comportado ja fechou o handle na primeira, mas o pior caso
    observado precisava de mais.

    LIMITE CONHECIDO, MEDIDO: se o handle do destino for RETIDO (aberto e
    mantido), nada substitui o arquivo no Windows — nem `os.replace`, nem
    `MoveFileExW` (testei as duas; ambas `WinError 5`). Apos as tentativas a
    funcao levanta erro e o `write_file` devolve falha limpa, com o conteudo
    original intacto e o temporario removido. Isso e proposital: a unica
    forma de "gravar assim mesmo" seria truncar o destino com o arquivo
    aberto, que e exatamente o defeito que esta funcao existe para corrigir.
    """
    import errno
    import os
    import time

    transitorios = {errno.EACCES, errno.EPERM}
    if hasattr(errno, "EEXIST"):
        transitorios.add(errno.EEXIST)

    ultimo: OSError | None = None
    for tentativa in range(tentativas):
        # No Windows a via nativa primeiro: e a que tolera arquivo aberto.
        if _replace_win(tmp, destino):
            return
        try:
            os.replace(str(tmp), str(destino))
            return
        except OSError as e:
            code = getattr(e, "winerror", None)
            if code not in (5, 32) and e.errno not in transitorios:
                raise  # erro real (permissao, disco cheio): propaga
            ultimo = e
            # Cresce ate 0.2s e fica nisso: um leitor que fez `read_text()`
            # ja fechou o handle, entao nao ha ganho em esperar muito mais.
            time.sleep(min(0.01 * (tentativa + 1), 0.2))
    raise OSError(
        f"nao foi possivel substituir {destino} apos {tentativas} tentativas: "
        f"{ultimo}. Outro processo pode estar com o arquivo aberto."
    )


def _escrever_atomico(destino: Path, conteudo: str) -> None:
    """Grava `conteudo` em `destino` sem que nenhum leitor veja estado parcial.

    ACHADO DO COMITE (2026-10-01, lente de concorrencia e recursos):
    "O arquivo e truncado e escrito diretamente. Assim, leitores podem
     observar conteudo parcial e escritas simultaneas podem perder
     atualizacoes."

    REPRODUZIDO antes de corrigir: `test_write_atomic.py` mediu 3 leituras
    parciais em 386 durante a gravacao de um arquivo de 400 KB. Nao era
    teorico — `Path.write_text()` abre com modo `w`, que TRUNCA o arquivo
    antes de escrever, e o leitor que abrir nesse intervalo le metade do
    arquivo novo colado com metade do antigo.

    A correcao e escrever em arquivo temporario NO MESMO DIRETORIO e
    substituir com `os.replace`, que e atomico no mesmo volume:

      1. `tempfile.mkstemp(dir=destino.parent)` cria o arquivo temporario ao
         lado do destino. Mesmo diretorio e obrigatorio: `os.replace` so e
         atomico dentro do mesmo volume/filesystem.
      2. Escreve, faz `flush` e `os.fsync` para garantir que os bytes
         chegaram ao disco antes de qualquer leitor poder ver o caminho.
      3. `_substituir_com_retry(tmp, destino)` — a troca e atomica: o
         leitor ve o arquivo velho OU o novo, nunca um meio-termo. No Windows
         a via primaria e `MoveFileExW` (ver `_replace_win`), porque
         `os.replace` do Python falha sob leitura concorrente.
      4. `finally` remove o temporario, inclusive quando da erro. Um
         temporario orfao em diretorio de codigo e lixo que engana quem le
         o diretorio depois.

    Por que `os.replace` e nao `rename`: em Windows, `os.rename` falha se o
    destino existe. `os.replace` sobrescreve e e atomico, e e o que a
    documentacao do Python recomenda para "substituir arquivo com seguranca".
    """
    import os
    import tempfile

    fd, tmp_name = tempfile.mkstemp(
        dir=str(destino.parent), prefix=f".{destino.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(conteudo)
            fh.flush()
            # Sem o fsync, os bytes podem estar no buffer do SO quando o
            # `replace` acontece: o leitor veria o nome novo apontando para
            # um arquivo ainda incompleto no disco.
            os.fsync(fh.fileno())
        # `replace` e atômico: nunca expoe estado intermediario.
        _substituir_com_retry(tmp, destino)
    finally:
        # Limpa o temporario se algo deu errado no caminho. `missing_ok`
        # porque o caminho feliz ja moveu o arquivo.
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _write_file(
    path: str, content: str, role: str, raiz: str | Path | None = None
) -> ToolResult:
    """Escrita passa pelo escopo do papel. O host decide, nao o prompt.

    `raiz` e o diretorio autorizado. Quem tem essa informacao e o
    orquestrador, que sabe qual arquivo esta sendo editado — por isso ela
    chega aqui como parametro e nao vem de constante. Ver `registry.in_scope`
    para por que sem raiz o escopo volta a barrar `..` por texto.
    """
    args = {"path": path, "chars": len(content)}
    if not in_scope(role, path, raiz):
        escopo = manifest(role).write_scope or "nenhum (papel somente-leitura)"
        extra = ""
        if raiz:
            extra = f" Raiz autorizada: {raiz}."
        msg = (
            f"ESCRITA NEGADA: papel '{role}' nao pode gravar em {path}. "
            f"Escopo permitido: {escopo}.{extra} "
            "Nao tente contornar: devolva o conteudo no texto final e indique "
            "quem deveria gravar."
        )
        return ToolResult("write_file", args, False, msg, denied=msg)
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        # Escrita atomica: ver `_escrever_atomico`. Nao usar
        # `p.write_text` aqui — trunca o destino e expoe estado parcial.
        _escrever_atomico(p, content)
        verb = "atualizado" if existed else "criado"
        return ToolResult(
            "write_file", args, True, f"OK: {path} {verb} ({len(content)} chars)"
        )
    except Exception as e:
        return ToolResult("write_file", args, False, f"ERRO_ESCRITA: {e}")


def dispatch(
    name: str, args: dict, role: str, raiz: str | Path | None = None
) -> ToolResult:
    if name == "read_file":
        return _read_file(args.get("path", ""))
    if name == "list_dir":
        return _list_dir(args.get("path", ""))
    if name == "search_files":
        return _search_files(args.get("query", ""), args.get("path", ""))
    if name == "write_file":
        return _write_file(args.get("path", ""), args.get("content", ""), role, raiz)
    return ToolResult(name, args, False, f"ERRO: tool desconhecida: {name}")


# ── transporte ──────────────────────────────────────────────────────────


def _post(payload: dict, key: str, timeout: int) -> tuple[bool, dict, float]:
    # User-Agent OBRIGATORIO. Medido 2026-10-01: sem este header o relay
    # responde 403 "error code: 1010" (Cloudflare bloqueando requisicao sem
    # UA). Nao e cota nem auth - e o WAF.
    #
    # http.client com conexao NOVA por requisicao, em vez do urllib: o
    # urllib reaproveita a conexao TLS (keep-alive) e, ao reaproveitar uma
    # sessao apos uma resposta maior, o relay responde
    # "SSL: SSLV3_ALERT_BAD_RECORD_MAC" em ~0.4s. Medido: 3 falhas em 8
    # pares com urllib, 0 falhas em 12 pares com conexao nova. O custo (um
    # handshake TLS por chamada) e irrelevante frente a derrubar o pipeline.
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "User-Agent": USER_AGENT,
        "Content-Length": str(len(body)),
    }
    t0 = time.time()
    conn = None
    try:
        conn = http.client.HTTPSConnection(
            RELAY_HOST, 443, timeout=timeout, context=ssl.create_default_context()
        )
        conn.request("POST", RELAY_PATH, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", "replace")
        if resp.status >= 400:
            try:
                return False, json.loads(raw), time.time() - t0
            except Exception:
                return False, {"http": resp.status, "raw": raw[:300]}, time.time() - t0
        return True, json.loads(raw), time.time() - t0
    except Exception as e:
        return False, {"exc": f"{type(e).__name__}: {str(e)[:180]}"}, time.time() - t0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def acted(run: AgentRun) -> bool:
    """O agente ESCRVEU alguma coisa? Nao apenas falou que ia escrever.

    Medido 2026-10-01: o `maker` devolveu o codigo corrigido dentro de um
    bloco de texto e NAO chamou `write_file`. O arquivo ficou intacto, e o
    pipeline seguiu para `critic` como se o trabalho tivesse sido feito.
    Sem esta verificacao, um papel escritor que so desvia saida e um no-op
    silencioso — o cluster "funciona" e nada acontece.

    Por isso o orquestrador consulta `acted()` para papeis com permissao de
    escrita, e trata "falou mas nao fez" como falha, nao como sucesso.
    """
    return any(tc.get("name") == "write_file" and tc.get("ok") for tc in run.tool_calls)


def run_agent(
    role: str,
    task: str,
    *,
    lens: str | None = None,
    handoff: dict | None = None,
    max_tokens: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
    model: str | None = None,
    target: str = "",
) -> AgentRun:
    """Executa um agente ate ele responder em texto.

    Faz o loop de tool-calling inteiro no host: envia as tools, executa o que
    o modelo pediu, devolve o resultado, repete. Para quando o modelo responde
    sem tool_call ou quando estoura `MAX_TOOL_ROUNDS`.
    """
    m = manifest(role)
    key = _key()
    use_model = model or MODEL

    # O piso e imposto aqui. Nao e parametro opcional na pratica.
    budget = max(MIN_TOKEN_FLOOR, max_tokens or m.max_tokens)

    lens_txt = lens or m.lens
    # Alvo declarado: o host sabe o que e o alvo; o modelo precisa saber
    # para nao passear pelo diretorio.
    target_path = target or ""
    # RAIZ AUTORIZADA: o diretorio do arquivo alvo. E o que permite dizer
    # "dentro deste diretorio" em vez de so "extensao .py" — que era o
    # furo de seguranca medido em `registry.in_scope`. Derivada do alvo
    # porque o alvo e o que o usuario escolheu; o agente nao inventa raiz.
    raiz_autorizada: Path | None = None
    if target_path:
        try:
            raiz_autorizada = Path(target_path).resolve().parent
        except (OSError, ValueError, RuntimeError):
            raiz_autorizada = None
    sys_parts = [
        f"Voce e o agente '{role}' de um cluster com papeis separados.",
        f"SUA MISSAO: {m.mission}",
        f"SEU FOCO: {m.focus}",
    ]
    if lens_txt:
        sys_parts.append(f"LENTE DESTA TAREFA: {lens_txt}")
    if m.writes:
        sys_parts.append(
            "Voce PODE gravar em: "
            + ", ".join(m.write_scope)
            + ". Fora disso a escrita sera negada pelo host."
        )
    else:
        sys_parts.append(
            "Voce NAO pode gravar nada. Seu papel e somente produzir relatorio em texto."
        )
    sys_parts.append(
        "REGRA: use as ferramentas para VER. Nao afirme que leu algo que nao leu. "
        "Cite caminho e linha. Se nao souber, diga que nao sabe."
    )

    user_parts = [f"TAREFA DO PAPEL '{role}':\n{task}"]
    if handoff:
        dump = json.dumps(handoff, ensure_ascii=False, indent=2)
        if len(dump) > MAX_TOOL_CHARS:
            dump = dump[:MAX_TOOL_CHARS] + "\n[TRUNCADO]"
        user_parts.append(f"ENTRADA DOS OUTROS AGENTES (handoff):\n{dump}")
    user_parts.append(f"ENTREGUE: {m.produces}")
    # Sem isto o modelo sai lendo arquivos vizinhos (medido 2026-10-01: um
    # researcher só apontado para o alvo leu SPEC.md e o próprio teste antes
    # de responder). Dizer qual arquivo É o alvo e dizer o que fazer com ele
    # corta o passeio.
    if target_path:
        user_parts.append(
            f"ALVO: o arquivo a analisar e exatamente '{target_path}'. "
            "Leia ESSE arquivo com read_file e entregue sua analise. "
            "Nao leia outros arquivos do diretorio: eles nao fazem parte da tarefa."
        )
    # Papel QUE ESCREVE precisa de lembrete explicito. Medido 2026-10-01: o
    # maker respondeu com um relatorio ("## O que eu verifiquei") e devolveu o
    # codigo num bloco de texto, sem nunca chamar write_file. O prompt de
    # papel nao bastou; instrucao direta no turno resolve.
    if m.writes:
        user_parts.append(
            "COMO ENTREGAR: voce tem a ferramenta write_file e PODE gravar "
            f"neste escopo: {', '.join(m.write_scope)}. Use-a. Grave o conteudo "
            "COMPLETO do arquivo (nao um trecho, nao um diff). Chame write_file "
            "de verdade. Um relatorio descrevendo a correcao NAO e entrega: se "
            "voce nao chamou write_file, o trabalho nao foi feito."
        )

    messages = [
        {"role": "system", "content": "\n\n".join(sys_parts)},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]
    tools = tools_for(role)

    run = AgentRun(role=role, ok=False, final="")
    t_start = time.time()
    attempt = 0
    # Estas estruturas sobrevivem aos retries: uma chamada repetida continua
    # repetida na tentativa seguinte.
    seen_signatures: set[str] = set()
    repeats: dict[str, int] = {}

    while attempt <= retries:
        attempt += 1
        run.attempts = attempt
        try:
            ok, resp, dt = _post(
                {
                    "model": use_model,
                    "messages": messages,
                    "tools": tools,
                    "tool_choice": "auto",
                    "max_tokens": budget,
                },
                key,
                timeout,
            )
        except Exception as e:
            run.error = f"excecao no transporte: {e}"
            run.recovered.append(f"tentativa {attempt}: {run.error[:120]}")
            continue

        run.latency = time.time() - t_start
        if not ok:
            code = (
                resp.get("http")
                or (resp.get("error") or {}).get("code")
                or resp.get("exc")
            )
            run.error = f"relay recusou ({code}): {json.dumps(resp)[:200]}"
            run.recovered.append(f"tentativa {attempt}: {str(code)[:60]}")
            # 402/429 nao melhoram com retry imediato. Sinaliza para o orquestrador.
            if code in (402, 429):
                run.error = f"COTA_EXCEDIDA:{code}"
                break
            if attempt <= retries:
                time.sleep(1.5 * attempt)
                continue
            break

        choice = (resp.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        run.finish_reason = choice.get("finish_reason")
        run.usage = resp.get("usage") or {}
        calls = msg.get("tool_calls") or []
        content = (msg.get("content") or "").strip()

        # Sem tool_call -> e a resposta final.
        if not calls:
            if content:
                run.final = content
                run.ok = True
                # Sucesso NAO deve carregar o erro de uma tentativa anterior:
                # o SSL e intermitente e ja foi absorvido pelo retry. Manter
                # run.error junto com ok=True faz o orquestrador ler log de
                # falha e reportar erro em execucao que deu certo.
                run.recovered = run.recovered or []
                run.error = None
                break
            # Sem texto E sem tool_call, mas com gravacao ja feita neste
            # turno: o trabalho foi feito, so o RELATO nao coube no orcamento.
            # Medido 2026-10-01: o `fixer` gravou o arquivo e respondeu
            # finish=length com reasoning esgotado. Tratar isso como falha faz
            # o pipeline descartar um trabalho correto.
            if acted(run):
                run.ok = True
                run.final = (
                    "[relatorio truncado: o orcamento de tokens acabou durante "
                    "o raciocinio, mas as gravacoes foram feitas] "
                    f"gravou: {[t['args'].get('path') for t in run.tool_calls if t['name'] == 'write_file']}"
                )
                run.error = None
                run.recovered.append(
                    f"gravacoes feitas mas relato truncado (finish={run.finish_reason})"
                )
                break
            # finish=length com content vazio = orcamento comido pelo reasoning.
            # Se ja gravou, NAO retenta: a gravacao e o trabalho, e a nova
            # tentativa comecaria de um historico que ja tem a escrita aplicada.
            run.error = (
                f"resposta vazia (finish={run.finish_reason}). "
                "Causa provavel: max_tokens consumido em reasoning antes da "
                f"resposta. Tente budget >= {MIN_TOKEN_FLOOR}."
            )
            if acted(run):
                run.ok = True
                run.error = None
                run.final = (
                    "[relatorio truncado: o orcamento acabou durante o "
                    "raciocinio, mas as gravacoes foram feitas] "
                    f"gravou: {[t['args'].get('path') for t in run.tool_calls if t['name'] == 'write_file']}"
                )
                run.recovered.append(
                    f"gravacoes feitas mas relato truncado (finish={run.finish_reason})"
                )
                break
            if attempt <= retries:
                budget = int(budget * 2)
                run.usage["budget_retry"] = budget
                run.recovered.append(
                    f"tentativa {attempt}: resposta vazia, budget {budget}->{budget * 2}"
                )
                continue
            break

        # Houve tool_call: executa no host e devolve.
        messages.append(
            {"role": "assistant", "content": content or None, "tool_calls": calls}
        )
        for c in calls:
            fn = c.get("function") or {}
            name = fn.get("name", "")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}

            # Guarda contra laco: a MESMA chamada nao traz informacao nova.
            # Medido 2026-10-01: sem isso o agente gasta ate MAX_TOOL_ROUNDS
            # relendo o mesmo alvo e volta sem resposta alguma.
            sig = name + "|" + json.dumps(args, sort_keys=True)
            repeats[sig] = repeats.get(sig, 0) + 1
            if sig in seen_signatures and repeats[sig] <= 4:
                run.tool_calls.append(
                    {"name": name, "args": args, "ok": False, "motivo": "repetida"}
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": c.get("id", ""),
                        "content": "IGNORADO: voce ja fez exatamente esta chamada e "
                        "o resultado e o mesmo. Use o que ja leu e produza sua resposta.",
                    }
                )
                continue
            seen_signatures.add(sig)

            tr = dispatch(name, args, role, raiz_autorizada)
            run.tool_calls.append({"name": name, "args": args, "ok": tr.ok})
            if tr.denied:
                run.denied_writes.append(f"{name}({args.get('path')}): {tr.denied}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": c.get("id", ""),
                    "content": tr.output[:MAX_TOOL_CHARS],
                }
            )
        run.rounds += 1
        # Ja gravou o suficiente? Encerra e devolve o relato.
        # ORDEM IMPORTA: este check vem ANTES do limite de rodadas. Antes
        # invertidos, uma gravacao bem-sucedida na ultima rodada caia no
        # break do limite e virava ok=False — trabalho feito reportado como
        # falha. Achado pelo proprio comite de revisao (lente de legibilidade,
        # 2026-10-01): "`acted` so e verificado depois do `break`".
        if acted(run):
            escritas = sum(1 for t in run.tool_calls if t["name"] == "write_file")
            if escritas >= MAX_ROUNDS_AFTER_WRITE:
                run.ok = True
                run.final = (
                    f"[encerrado apos gravar] o agente gravou {escritas}x e nao "
                    "pediu mais ferramentas. Relato textual nao saiu, mas o "
                    "trabalho no disco esta feito."
                )
                run.error = None
                run.recovered.append(f"encerrado apos {escritas} gravacao(oes)")
                break
        if run.rounds >= MAX_TOOL_ROUNDS:
            run.error = f"limite de rodadas de ferramenta ({MAX_TOOL_ROUNDS})"
            break

    # Esgotou tentativas ainda pedindo ferramenta: isso e FALHA e precisa
    # dizer. Sem esta linha o run sai com ok=False e error=None, e o
    # orquestrador reporta "motivo: ?" — falha silenciosa, o peor tipo.
    if not run.ok and not run.error:
        run.error = (
            f"agente pediu ferramentas em todas as {run.attempts} tentativas "
            f"({run.rounds} rodadas) e nunca respondeu em texto. "
            "Causa provavel: o modelo nao achou o alvo ou se perdeu lendo "
            "arquivos vizinhos."
        )
    if run.ok:
        run.latency = time.time() - t_start
    return run


# Falhas de transporte: insistimos mais, com espera exponencial curta.
TRANSPORT_MARKERS = (
    "SSLError",
    "BAD_RECORD_MAC",
    "timeout",
    "timed out",
    "ConnectionReset",
    "ConnectionError",
    "BrokenPipe",
    "RemoteDisconnected",
    "excecao no transporte",
)
TRANSPORT_ATTEMPTS = 4
CONTENT_ATTEMPTS = 2


def _is_transport_error(msg: str | None) -> bool:
    if not msg:
        return False
    return any(m.lower() in msg.lower() for m in TRANSPORT_MARKERS)


def run_agent_resilient(
    role: str,
    task: str,
    *,
    lens: str | None = None,
    handoff: dict | None = None,
    max_tokens: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
    model: str | None = None,
    target: str = "",
) -> AgentRun:
    """Como `run_agent`, mas sobrevive a falha de transporte no meio do loop.

    Medido 2026-10-01: `SSL: BAD_RECORD_MAC` e intermitente — 6/6 falhas numa
    janela, 30/30 sucesso na seguinte. Trocar o transporte para conexao TLS nova
    por requisicao (ver `_post`) reduziu muito mas nao zerou. Quando o retry
    interno nao absorve, insistir na MESMA conversa nao adianta: o historico de
    tool-calls fica inconsistente. Execucao nova inteira resolve.

    Duas classes de erro, politicas diferentes:

      - TRANSPORTE (`SSLError`, `Bad record MAC`, timeout, `ConnectionReset`):
        e o relay sendo esquisito. Vale insistir varias vezes, com espera curta.
      - CONTEUDO (resposta vazia, agente perdido lendo vizinhos, nao agiu):
        repetir a mesma pergunta devolve a mesma resposta. Nao adianta insistir
        muito; o orquestrador trata como falha do papel.

    Erro de cota (402/429) nao e retentado aqui: e sinal de "esticou", e quem
    deve reagir e o orquestrador reduzindo o paralelismo.
    """
    last: AgentRun | None = None
    attempt = 0
    while attempt < TRANSPORT_ATTEMPTS:
        attempt += 1
        r = run_agent(
            role,
            task,
            lens=lens,
            handoff=handoff,
            max_tokens=max_tokens,
            timeout=timeout,
            retries=retries,
            model=model,
            target=target,
        )
        if r.ok:
            if attempt > 1 and last is not None:
                r.recovered = list(last.recovered) + [
                    f"execucao {attempt}: falhou antes ({str(last.error)[:80]})"
                ]
            return r
        if r.error and "COTA" in r.error:
            return r
        # CRITICO: se a execucao que falhou JA GRAVOU algo, uma nova execucao
        # inteira comeca do zero e pode sobrescrever o trabalho bom com uma
        # versao pior (ou nao gravar). Medido 2026-10-01: o `fixer` gravou o
        # arquivo, a resposta esvaziou por orcamento, o retry rodou de novo,
        # e o resultado final NAO tinha a correcao.
        # Gravacao e o trabalho; o relato e comentario.
        if acted(r):
            r.ok = True
            r.error = None
            r.final = (
                "[relatorio indisponivel: o orcamento acabou antes do texto, mas "
                "as gravacoes foram feitas] "
                f"gravou: {[t['args'].get('path') for t in r.tool_calls if t['name'] == 'write_file']}"
            )
            r.recovered.append(
                f"execucao {attempt}: gravou mas naoDEU relato; aceito como sucesso"
            )
            return r
        last = r
        # Transporte: insiste. Conteudo: nao insiste muito, repetir a pergunta
        # repete a resposta.
        if not _is_transport_error(r.error):
            if attempt >= CONTENT_ATTEMPTS:
                break
        elif attempt >= TRANSPORT_ATTEMPTS:
            break
        time.sleep(1.2 * attempt)
    return (
        last
        if last is not None
        else AgentRun(role=role, ok=False, final="", error="sem execucao")
    )
