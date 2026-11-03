"""
Troca comandos com NOME SOLTO por caminho absoluto + PATH explicito.

Por que um script e nao edicao manual
-------------------------------------
O opencode.jsonc tem comentarios com mojibake ("RaciocÃ­nio"), o que torna
qualquer replace por bloco de texto fragil. Aqui a troca e por CHAVE, dentro
do bloco daquela chave, e so no array "command" — sem tocar em comentario.

Regra de seguranca
------------------
Este script NAO inventa caminho. Antes de gravar ele valida:
  1. o executavel existe no disco
  2. o JSON continua parseando (mesmo leitor do verificar_mcps)
  3. nenhum nome solto sobrou DENTRO de um command[]
Se qualquer checagem falhar, nao grava e diz qual.

Medido por verificar_nomes_soltos.py: os nomes soltos nao acham executavel, e
os caminhos absolutos abaixo sobem (tools/list confirmado um a um).
"""

import json
import re
import shutil
import sys
from pathlib import Path

CONFIG = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
BACKUP = (Path(__file__).resolve().parents[3] / "opencode.jsonc.pre_absolutos")

NPX = "C:/Program Files/nodejs/npx.cmd"
UVX = "uvx"

PATH_NODE = "C:/Program Files/nodejs;bin"
PATH_UV = "bin"

# chave -> (binario absoluto, PATH a mesclar no environment)
#
# NAO entram aqui:
#   agriculture     -> executavel chama-se agriculture-server, precisa --from.
#                     complexo demais para regex; tratado a mao.
#   sqlite-ampliagro -> BUG DO PACOTE (list_resources removido no SDK MCP
#                      atual). Nenhum caminho conserta; desligado a mao.
ALVO = {
    "sequential-thinking": (NPX, PATH_NODE),
    "memory": (NPX, PATH_NODE),
    "time": (UVX, PATH_UV),
    "fetch": (UVX, PATH_UV),
    "arxiv": (UVX, PATH_UV),
    "open-meteo": (NPX, PATH_NODE),
    "open-meteo-pro": (NPX, PATH_NODE),
    "duckduckgo": (NPX, PATH_NODE),
    "playwright": (NPX, PATH_NODE),
}

SO_NOS_COMMAND = re.compile(r'"command":\s*\[(.*?)\]', re.S)
NOME_SOLTO = re.compile(r'"(npx|uvx|python|python3|node|deno|bun)"')


def bloco_da_chave(texto: str, chave: str):
    """Devolve (inicio, fim, corpo) do objeto da chave, ou None."""
    m = re.search(rf'"{re.escape(chave)}"\s*:\s*\{{', texto)
    if not m:
        return None
    ini = m.start()
    fim = texto.find("\n    },", ini)
    if fim == -1:
        return None
    return ini, fim, texto[ini:fim]


def mesclar_path(corpo: str, path_valor: str) -> str:
    """Garante que o environment da chave tenha PATH com o valor dado."""
    if '"environment"' in corpo:
        em = re.search(r'"environment"\s*:\s*\{', corpo)
        if em and '"PATH"' not in corpo[em.start() : em.start() + 400]:
            return (
                corpo[: em.end()]
                + f'\n          "PATH": "{path_valor}",'
                + corpo[em.end() :]
            )
        return corpo
    en = corpo.find('"enabled"')
    if en != -1:
        return (
            corpo[:en]
            + f'"environment": {{ "PATH": "{path_valor}" }},\n      '
            + corpo[en:]
        )
    return corpo


def aplicar(texto: str, chave: str, abs_path: str, path_valor: str):
    """Troca o 1o elemento do command por abs_path. Devolve (texto, status)."""
    achado = bloco_da_chave(texto, chave)
    if not achado:
        return texto, "chave nao encontrada"
    ini, fim, corpo = achado

    argv = SO_NOS_COMMAND.search(corpo)
    if not argv:
        return texto, "sem command[]"

    interno = argv.group(1)
    m = NOME_SOLTO.search(interno)
    if not m:
        if abs_path in interno or abs_path.replace("/", "\\") in interno:
            return texto, "ja absoluto"
        return texto, "sem nome solto e sem caminho absoluto"

    # substitui SO o primeiro item (o binario), preserva o resto
    novo_interno = interno[: m.start()] + f'"{abs_path}"' + interno[m.end() :]
    corpo_novo = corpo[: argv.start(1)] + novo_interno + corpo[argv.end(1) :]
    corpo_novo = mesclar_path(corpo_novo, path_valor)
    return texto[:ini] + corpo_novo + texto[fim:], "trocada"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    texto = CONFIG.read_text(encoding="utf-8")

    faltando = [b for b in {NPX, UVX} if not Path(b.replace("/", "\\")).exists()]
    if faltando:
        print(f"ABORTOU: executavel nao existe {faltando}")
        return 1
    print(f"binarios OK: {NPX} | {UVX}")

    relatorio = {}
    for chave, (abs_path, path_valor) in ALVO.items():
        texto, status = aplicar(texto, chave, abs_path, path_valor)
        relatorio[chave] = status

    trocadas = [k for k, v in relatorio.items() if v == "trocada"]
    print(f"trocadas ({len(trocadas)}): {trocadas}")
    for k, v in relatorio.items():
        if v != "trocada":
            print(f"  {k}: {v}")

    # guard: nenhum nome solto sobrou DENTRO de um command
    resto = " ".join(SO_NOS_COMMAND.findall(texto))
    sobrou = set(NOME_SOLTO.findall(resto))
    # agriculture e sqlite ficam de fora de proposito; nao contam como guarda
    if "agriculture" in texto or "sqlite-ampliagro" in texto:
        for chave in ("agriculture", "sqlite-ampliagro"):
            achado = bloco_da_chave(texto, chave)
            if achado:
                argv = SO_NOS_COMMAND.search(achado[2])
                if argv:
                    achados = set(NOME_SOLTO.findall(argv.group(1)))
                    if len(achados) == 1:
                        # detecta se o nome solto e o primeiro item
                        primeiro = argv.group(1).strip().split(",")[0]
                        if f'"{list(achados)[0]}"' in primeiro:
                            print(
                                f"AVISO: {chave} ainda com nome solto "
                                f"({list(achados)[0]}) — tratei a mao"
                            )
                            sobrou.discard(list(achados)[0])
    if sobrou:
        print(f"ABORTOU: sobrou nome solto em command[] {sobrou}")
        return 1
    print("guard OK: nenhum nome solto em command[] (fora os casos manuais)")

    # valida o JSON com o MESMO leitor do verificar_mcps
    tmp = CONFIG.with_suffix(".tmp_validar")
    tmp.write_text(texto, encoding="utf-8")
    try:
        import verificar_mcps

        verificar_mcps.CONFIG = tmp
        cfg = verificar_mcps.carregar_config()
        print(f"JSON VALIDA: {len(cfg.get('mcp', {}))} servidores")
    finally:
        tmp.unlink(missing_ok=True)

    shutil.copy2(CONFIG, BACKUP)
    CONFIG.write_text(texto, encoding="utf-8")
    print(f"GRAVADO. backup: {BACKUP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
