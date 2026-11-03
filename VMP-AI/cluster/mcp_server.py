#!/usr/bin/env python3
"""MCP do cluster: expoe o comite de 10 IAs como tools do OpenCode.

POR QUE ISTO EXISTE
Plugin custom tool nao funciona no OpenCode 1.18.34 (medido: nem um plugin
minimo registra tool, com e sem o array `plugin`). MCP funciona — ha 78
tools `amplia_*` disponiveis, todas via MCP. Entao o cluster vira MCP.

O motor nao foi reescrito: `engine.ts` continua sendo a fonte da verdade
dos 10 perfis e do transporte. Este servidor so traduz MCP -> motor,
chamando o motor por HTTP.

    stdio  -> opencode chama este processo
    HTTP   -> o motor (engine.ts) roda separado e serve as consultas
"""

import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENGINE = os.environ.get("CLUSTER_ENGINE_URL", "http://127.0.0.1:8791")

# MEDIDO: dez agentes com arquivo leem o disco, montam o prompt e consultam
# o relay — 83s. O `experimental.mcp_timeout` do OpenCode esta em 300000ms,
# e este valor tem de ser MENOR que ele, para que o MCP se auto-limite antes
# e devolva um erro honesto, em vez de o OpenCode reportar "Request timed
# out" e a lente perdida passar por "nenhum problema encontrado".
TIMEOUT_PADRAO = int(os.environ.get("CLUSTER_TIMEOUT", "270"))
socket.setdefaulttimeout(TIMEOUT_PADRAO)


def _log(msg: str) -> None:
    sys.stderr.write(f"[cluster-mcp] {msg}\n")
    sys.stderr.flush()


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _formatar_perfis(res: dict) -> str:
    """Lista a equipe de forma legivel para o modelo.

    O `/perfis` devolve JSON com perfis e uma lista de 46 lentes. Soltar o
    JSON cru no contexto do modelo gasta token sem fazer ninguem entender
    nada; a lista agrupada por tier e o que o coordenador precisa para
    escolher o perfil de ciclo.
    """
    linhas = [
        f"Equipe de {res.get('equipe')} lentes em {len(res.get('perfis') or {})} perfis de ciclo.",
        f"Orcamento padrao: {res.get('orcamentoPadrao')} tokens por lente.",
        "",
        "PERFIS DE CICLO (escolha conforme o prazo):",
    ]
    for _nome, _p in (res.get("perfis") or {}).items():
        linhas.append(f"  {_nome:<9} {_p.get('descricao', '')}")
    return "\n".join(linhas)


def _rota_board(acao: str) -> str:
    """Mapeia o nome da tool para a rota HTTP.

    MEDIDO: um tool por acao, mas o motor so tem cinco rotas. `board` e
    leitura; `criar`/`pegar`/`publicar`/`concluir`/`falhar` sao sub-rotas de
    POST. Concentrar o mapeamento aqui evita o `if/elif` crescendo no meio
    do `handle`, que foi onde a primeira versao perdeu o campo `autor`.
    """
    if acao == "cluster_board":
        return "/board"
    if acao == "cluster_board_criar":
        return "/board/criar"
    if acao == "cluster_board_pegar":
        return "/board/pegar"
    if acao == "cluster_board_publicar":
        return "/board/publicar"
    if acao == "cluster_board_concluir":
        return "/board/concluir"
    if acao == "cluster_board_falhar":
        return "/board/falhar"
    raise KeyError(acao)


def _dispatch_board(nome: str, args: dict) -> str:
    """Executa uma tool do board contra o motor.

    MEDIDO: `cluster_board` devolvia 404 porque eu enviava POST para `/board`,
    que so tem GET. Erro meu de mapeamento, nao do motor — e a resposta de
    erro era tecnicamente correta, o que tornou o bug confuso: "rota
    desconhecida" quando a rota existia, so no verbo errado.
    """
    rota = _rota_board(nome)
    metodo = "GET" if rota == "/board" else "POST"
    res = _call_engine(
        rota, args, TIMEOUT_PADRAO if metodo == "POST" else 30, method=metodo
    )
    return res.get("texto") or json.dumps(res, ensure_ascii=False)
    for nome, p in (res.get("perfis") or {}).items():
        linhas.append(f"  {nome:<9} {p.get('descricao', '')}")
    return "\n".join(linhas)


def _call_engine(
    path: str, payload: dict, timeout: int = 900, method: str = "POST"
) -> dict:
    """Chama o motor por HTTP. Erro vira texto honesto, nao traceback.

    MEDIDO: `_dispatch_board` calculava `metodo = "GET"` para `/board` e mesmo
    assim o motor respondia 404 — porque aqui o verbo nunca era usado:
    `urllib` infere POST de `data=`. Entao todo GET era POST, e `/board` so
    aceita GET. A resposta de erro ("rota desconhecida") era CORRETA sobre o
    verbo errado, o que a torna confusa de diagnosticar.

    `method="GET"` remove `data`, e sem `data` o urllib usa GET.
    """
    url = f"{ENGINE}{path}"
    dados = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=dados if method.upper() == "POST" else None,
        headers={"Content-Type": "application/json"},
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"motor respondeu {e.code}: {corpo}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"nao consegui falar com o motor em {ENGINE} ({e.reason}). "
            "Ele precisa estar rodando: `node plugins/cluster/engine-server.ts`"
        ) from None
    except TimeoutError:
        raise RuntimeError(
            f"motor em {ENGINE} nao respondeu em {timeout}s. "
            "Ou o relay esta lento, ou o motor travou."
        ) from None


# ── Protocolo MCP (stdio, JSON-RPC) ────────────────────────────────────────

TOOLS = [
    {
        "name": "cluster_consultar",
        "description": (
            "Consulta N agentes de IA em paralelo, cada um com uma lente "
            "diferente (correcao, seguranca, contrato, concorrencia, "
            "legibilidade, erros, dados, dependencias, testes, visao geral), e "
            "consolida tudo em uma resposta so. Use para revisar codigo, achar "
            "defeitos, auditar, ou pegar uma segunda opiniao. E mais lento que "
            "uma chamada normal, porque sao dez modelos pensando."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "O que os agentes devem analisar. Inclua o codigo ou texto.",
                },
                "n": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": "Quantos agentes usar (1 a 10). Padrao 10.",
                },
                "arquivos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Caminhos absolutos de arquivos para cada agente ler antes.",
                },
                "orcamento": {
                    "type": "integer",
                    "minimum": 512,
                    "maximum": 12000,
                    "description": "Tokens de saida por agente. Padrao 3000.",
                },
            },
            "required": ["pergunta"],
        },
    },
    {
        "name": "cluster_prontidao",
        "description": "Verifica se o motor do cluster esta de pe e quantos eventos chegou do relay.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cluster_ciclo",
        "description": (
            "SUPER-EQUIPE: roda o comite em RODADAS (revisao -> pesquisa -> "
            "concepcao -> memoria -> supervisao), onde cada tier le o que os "
            "anteriores produziram, e grava um checkpoint que sobrevive a "
            "sessao. Use para trabalho grande: revisar, auditar, pesquisar "
            "solucao e deixar registro. Perfis: rapido (~1-2min, so revisao), "
            "padrao (~5-10min, revisao+supervisao), completo (~3-20min, os 5 "
            "tiers), profundo (idem, respostas mais longas)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pedido": {
                    "type": "string",
                    "description": "O que a equipe deve fazer. Seja especifico: eles nao veem sua tela.",
                },
                "perfil": {
                    "type": "string",
                    "enum": ["rapido", "padrao", "completo", "profundo"],
                    "description": "Padrao 'padrao'. 'rapido' so revisao; 'completo' os 5 tiers.",
                },
                "arquivos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Caminhos absolutos. Os agentes leram o CONTEUDO.",
                },
                "orcamento": {
                    "type": "integer",
                    "description": "Tokens por lente. Padrao do perfil. Minimo pratico 800.",
                },
                "id": {
                    "type": "string",
                    "description": "Retomar uma trilha existente (nova versao). Sem isto, trilha nova.",
                },
            },
            "required": ["pedido"],
        },
    },
    {
        "name": "cluster_perfis",
        "description": "Lista a equipe: 46 papeis em 5 tiers e os perfis de ciclo com o tempo de cada um.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "cluster_trilha",
        "description": "Le o checkpoint de uma trilha: o que foi feito, o que falta, o proximo passo.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "Id da trilha (ex.: 20261003-142200-revisar-a1b2).",
                }
            },
            "required": ["id"],
        },
    },
    # --- board: como os executores conversam entre si ---
    {
        "name": "cluster_board_pegar",
        "description": (
            "OPERARIO: pega a proxima tarefa da fila e devolve o QUE OUTROS "
            "JA FIZERAM junto (artefatos, erros de quem ja tentou). E assim "
            "que os executores conversam: quem pegou nunca viu a discussao "
            "original, mas ve o raciocinio de quem produziu o achado."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "quem": {"type": "string", "description": "Seu id. Ex.: exec-1."}
            },
            "required": ["quem"],
        },
    },
    {
        "name": "cluster_board_publicar",
        "description": "Publica um artefato: achado, patch, teste, print, log ou nota.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": [
                        "achado",
                        "patch",
                        "teste",
                        "print",
                        "log",
                        "nota",
                        "erro",
                    ],
                },
                "autor": {"type": "string", "description": "Seu id."},
                "titulo": {"type": "string"},
                "conteudo": {
                    "type": "string",
                    "description": "O que voce fez ou encontrou.",
                },
                "tarefa": {
                    "type": "string",
                    "description": "Id da tarefa (para o executor ve-la).",
                },
                "caminho": {
                    "type": "string",
                    "description": "Arquivo tocado, para patch.",
                },
            },
            "required": ["tipo", "autor", "titulo", "conteudo"],
        },
    },
    {
        "name": "cluster_board_concluir",
        "description": "Conclui a tarefa com o comando de verificacao que rodou e a saida.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tarefa": {"type": "string"},
                "quem": {"type": "string"},
                "resultado": {
                    "type": "string",
                    "description": "O que fez + como verificou.",
                },
            },
            "required": ["tarefa", "quem", "resultado"],
        },
    },
    {
        "name": "cluster_board_falhar",
        "description": "Devolve a tarefa a fila dizendo o que impediu. Melhor que concluir sem verificar.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tarefa": {"type": "string"},
                "quem": {"type": "string"},
                "erro": {"type": "string"},
            },
            "required": ["tarefa", "quem", "erro"],
        },
    },
    {
        "name": "cluster_board_criar",
        "description": "Cria tarefa na fila.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "pedido": {"type": "string"},
                "origem": {
                    "type": "string",
                    "description": "lente:<id> ou ciclo:<id>.",
                },
                "arquivos": {"type": "array", "items": {"type": "string"}},
                "artefatos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ids de achados a ligar.",
                },
            },
            "required": ["titulo", "pedido"],
        },
    },
    {
        "name": "cluster_board",
        "description": "Estado do board: tarefas, artefatos e a trava de custo (limite de tarefas, turnos e tempo).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    # --- fim do board ---
]


def handle(msg: dict):
    metodo = msg.get("method")
    mid = msg.get("id")

    if metodo == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vmp-cluster", "version": "1.0.0"},
            },
        }

    if metodo == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}

    if metodo == "resources/list":
        # Declarado para o cliente que sonda este metodo. O board e lido por
        # tool, nao por recurso — mas responder vazio e melhor que deixar o
        # cliente esperando um timeout que vira "MCP nao responde".
        return {"jsonrpc": "2.0", "id": mid, "result": {"resources": []}}

    if metodo == "tools/call":
        nome = str((msg.get("params") or {}).get("name") or "")
        args = (msg.get("params") or {}).get("arguments") or {}
        try:
            if nome == "cluster_consultar":
                res = _call_engine("/consultar", args, TIMEOUT_PADRAO)
                texto = res.get("texto") or json.dumps(res, ensure_ascii=False)
            elif nome == "cluster_ciclo":
                res = _call_engine("/ciclo", args, TIMEOUT_PADRAO)
                texto = res.get("texto") or json.dumps(res, ensure_ascii=False)
            elif nome == "cluster_perfis":
                res = _call_engine("/perfis", {}, 20, method="GET")
                texto = (
                    res.get("perfis") and _formatar_perfis(res) or res.get("texto", "")
                )
            elif nome == "cluster_trilha":
                res = _call_engine(
                    f"/trilha/{args.get('id', '')}", {}, 30, method="GET"
                )
                texto = res.get("texto") or json.dumps(res, ensure_ascii=False)
            elif nome == "cluster_prontidao":
                # MEDIDO 2026-10-06: engine-server.ts:340 so aceita POST em /prontidao.
                # Com GET devolvia 404 {"erro":"rota desconhecida"}.
                res = _call_engine("/prontidao", {}, 20, method="POST")
                texto = res.get("texto") or json.dumps(res, ensure_ascii=False)
            elif nome.startswith("cluster_board"):
                texto = _dispatch_board(str(nome), args)
            else:
                texto = f"tool desconhecida: {nome}"
        except KeyError:
            texto = f"tool desconhecida: {nome}"
        except RuntimeError as e:
            texto = f"ERRO: {e}"
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {"content": [{"type": "text", "text": texto}]},
        }

    # notifications/initialize etc: sem resposta
    return None


def main() -> int:
    _log(f"iniciado. motor em {ENGINE}")
    for linha in sys.stdin:
        linha = linha.strip()
        if not linha:
            continue
        try:
            msg = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if "id" not in msg:
            continue  # notification
        resp = handle(msg)
        if resp is not None:
            _send(resp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
