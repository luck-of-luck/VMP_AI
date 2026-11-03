"""
Verifica os 2 casos que o aplicar_caminhos_absolutos.py NAO mexo:
  agriculture     -> uvx --from agriculture-mcp-server agriculture-server
  sqlite-ampliagro -> desligado de proposito (bug do pacote)

O motivo de um script so pra 2 casos: o agriculture precisa de --from e de um
executavel com nome diferente do pacote; o sqlite tem que permanecer
DESLIGADO e isso nao se prova com initialize() — prova-se com o traceback.
Este script confere os doisexplicitamente, e o agriculture so vale se
initialize() + tools/list passarem.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

CONFIG = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
UVX = r"uvx"


def carregar_config() -> dict:
    sys.path.insert(0, str(Path(__file__).parent))
    import verificar_mcps

    verificar_mcps.CONFIG = CONFIG
    return verificar_mcps.carregar_config()


async def testar_agriculture(argv):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["PATH"] = r"bin;" + env.get("PATH", "")
    params = StdioServerParameters(command=argv[0], args=argv[1:], env=env)
    async with stdio_client(params) as (rd, wr):
        async with ClientSession(rd, wr) as s:
            await s.initialize()
            r = await s.list_tools()
            return len(r.tools), sorted(t.name for t in r.tools)[:6]


def main():
    cfg = carregar_config()
    mcp = cfg["mcp"]

    print("=" * 68)
    print("CASOS MANUAIS")
    print("=" * 68)

    # ---- agriculture
    agro = mcp.get("agriculture")
    if not agro:
        print("  agriculture: AUSENTE do config")
        return 1
    print(f"  agriculture command: {agro['command']}")
    print(f"  agriculture enabled: {agro.get('enabled')}")
    print("  testando initialize() + tools/list ...")
    try:
        n, amostra = asyncio.run(testar_agriculture(agro["command"]))
        print(f"    OK — {n} tools")
        for t in amostra:
            print(f"      - {t}")
    except Exception as e:
        print(f"    ERRO: {type(e).__name__}: {str(e)[:160]}")
        return 1

    # ---- sqlite: tem que estar desligado E o bug tem que ser real
    print()
    sq = mcp.get("sqlite-ampliagro")
    if not sq:
        print("  sqlite-ampliagro: AUSENTE do config")
        return 1
    print(f"  sqlite-ampliagro enabled: {sq.get('enabled')}")
    if sq.get("enabled"):
        print("    PROBLEMA: deveria estar desligado (gasta contexto com tool morta)")
        return 1
    print("    OK — desligado de proposito")

    # confirma que o bug ainda existe (justificativa do desligamento)
    print("  confirmando que o bug do pacote ainda existe:")
    argv = [
        UVX,
        "mcp-server-sqlite",
        "--db-path",
        r"C:\Trabalho\Projetos\Ativos\Ampliagro\db.sqlite3",
    ]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=180)
    saida = (p.stdout or "") + (p.stderr or "")
    tem_bug = "list_resources" in saida
    print(
        f"    AttributeError list_resources presente: {'SIM' if tem_bug else 'NAO (bug corrigido?)'}"
    )
    if not tem_bug:
        print("    ATENCAO: se o bug sumiu, religar o servidor pode valer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
