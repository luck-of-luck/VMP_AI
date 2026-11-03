"""Registry de agentes do cluster.

Cada papel e um manifest. O manifest — nao o prompt — e a fonte da verdade
sobre o que um agente pode fazer. Duas consequencias deliberadas:

1. `write` decide se o agente recebe a ferramenta de escrita. `critic` e
   `reader` tem `write=False` e portanto NAO recebem essa tool: um revisor
   que edita o proprio texto deixa de revisar. Isso e sandbox, nao pedido.

2. `write_scope` limita os caminhos gravaveis. Sem isso, um `fixer` com um
   path malformado escreve onde nao deve e nenhum prompt impede.

Um manifest tambem pode trocar o `model`. O cluster roda hoje com um so
modelo gratuito, mas a separacao existe para que "use um frontier pago no
papel de critico" seja uma linha e nao uma refatoracao.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Role = Literal["researcher", "reader", "maker", "critic", "fixer", "optimizer"]


@dataclass(frozen=True)
class RoleManifest:
    """Contrato de um papel."""

    role: Role
    # Identidade: define para onde o olhar do agente aponta.
    mission: str
    # Ferramentas concedidas. `write` e a unica que concede mutacao.
    can_read: bool = True
    can_write: bool = False
    # Padroes de caminho gravaveis quando can_write=True. Vazio = proibido.
    write_scope: tuple[str, ...] = ()
    # Foco obrigatorio no prompt (imposto pelo orquestrador, nao sugerido).
    focus: str = ""
    # Como o agente recebe o trabalho dos outros.
    consumes: tuple[str, ...] = ()
    # O que o agente DEVE entregar, em formato legivel por maquina.
    produces: str = ""
    # Foco especifico quando varios 'critic' rodam em paralelo.
    lens: str = ""
    # Teto de tokens de saida (piso real e 256 — ver SPEC.md secao 2.1).
    max_tokens: int = 1024

    @property
    def writes(self) -> bool:
        return self.can_write and bool(self.write_scope)


# Ordem canonica do pipeline. O orquestrador itera ESTA lista; um papel novo
# entra aqui e passa a rodar, sem tocar em mais nada.
PIPELINE: tuple[Role, ...] = (
    "researcher",
    "reader",
    "maker",
    "critic",
    "fixer",
    "optimizer",
)

# Lentes para o 'critic' rodar em paralelo. Um so critic tender a achar o
# mesmo defeito de cinco formas; cada lente aponta para uma classe diferente.
CRITIC_LENSES: tuple[str, ...] = (
    "CORRECAO: procure erros de logica, off-by-one, condicoes invertidas, "
    "casos de borda nao tratados, estado nao inicializado.",
    "SEGURANCA: procure injecao, segredo em codigo, caminho de arquivo nao "
    "validado, comando concatenado, permissao ampla demais.",
    "CONTRATO: procure quebra de API, mudanca de assinatura sem migracao, "
    "campo obrigatorio que some, valor de retorno mudado em silencio.",
    "CONCORRENCIA: procure estado compartilhado sem trava, corrida de leitura/"
    "escrita, uso apos liberacao, operacao nao atomica onde precisa ser.",
    "MANUTENIBILIDADE: procure nome que nao diz o que faz, duplicacao que vai "
    "divergir, funcao com responsabilidades misturadas, comentario que mente.",
)

READ_TOOLS: tuple[dict, ...] = (
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Le um arquivo do disco e devolve o conteudo. Use para VER, nunca para supor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "caminho absoluto do arquivo",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "Lista o conteudo de um diretorio.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "caminho absoluto do diretorio",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Busca um texto e devolve as linhas que casam, com arquivo e numero.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "texto a buscar"},
                    "path": {"type": "string", "description": "raiz da busca"},
                },
                "required": ["query"],
            },
        },
    },
)

WRITE_TOOL: dict = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": (
            "Grava um arquivo. SO e permitido dentro do escopo concedido ao "
            "seu papel. Nao edite arquivo fora do escopo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "caminho absoluto do arquivo",
                },
                "content": {
                    "type": "string",
                    "description": "conteudo completo a gravar",
                },
            },
            "required": ["path", "content"],
        },
    },
}


# ── Manifests ───────────────────────────────────────────────────────────

REGISTRY: dict[Role, RoleManifest] = {
    "researcher": RoleManifest(
        role="researcher",
        mission=(
            "Levantar o que ja existe e o que pode dar errado, antes de "
            "qualquer codigo ser escrito. Nao propoe solucao —-establish fatos."
        ),
        focus=(
            "Identifique o estado atual, as restricoes reais, os arquivos "
            "envolvidos e os riscos. Cite arquivo e linha. Se nao verificou, "
            "diga que nao verificou."
        ),
        produces="relatorio de fatos: o que existe, restricoes, riscos, lacunas",
        # Medido 2026-10-01: com 1400 o modelo gastou reasoning=1399 e devolveu
        # ZERO chars (finish=length). O teto por papel precisa de folga sobre o
        # pior caso de raciocinio, nao apenas o suficiente para a resposta.
        max_tokens=3000,
    ),
    "reader": RoleManifest(
        role="reader",
        mission=(
            "Mapear a estrutura e os contratos do codigo, para que quem "
            "implementar saiba exatamente onde mexer e o que nao pode quebrar."
        ),
        focus=(
            "Mapeie: fluxo principal, funcoes envolvidas, contratos de entrada "
            "e saida, e o ponto MINIMO de mudanca. Cite arquivo e linha sempre."
        ),
        produces="mapa: fluxo, contratos, ponto minimo de mudanca, o que nao pode quebrar",
        max_tokens=3000,
    ),
    "maker": RoleManifest(
        role="maker",
        mission="Implementar a mudanca pedida, no escopo concedido, sem refatorar de quebra.",
        can_write=True,
        write_scope=(
            "*.py",
            "*.md",
            "*.json",
            "*.yaml",
            "*.yml",
            "*.ts",
            "*.tsx",
            "*.js",
        ),
        focus=(
            "Faca a MENOR mudanca que resolve. NaoMexa em arquivo fora do "
            "escopo. Preserve estilo e nomes existentes. Se o escopo nao "
            "resolver o problema, pare e diga — nao amplie por conta propria."
        ),
        produces="o arquivo JA GRAVADO via write_file, mais 1 frase do que mudou. Sua entrega e a gravacao, nao um relatorio: descrever a correcao no texto sem antes chamar write_file NAO conta como trabalho feito.",
        max_tokens=4000,
    ),
    "critic": RoleManifest(
        role="critic",
        mission=(
            "Achar o defeito no trabalho do outro. Nao escrever codigo. Um "
            "critico que edita o proprio texto deixa de revisar."
        ),
        focus=(
            "Procure defeito REAL, com arquivo/linha. Nao valide por elogio: se "
            "nao achou nada, devolva lista vazia em vez de elogio. Distinga "
            "defeito de preferencia de estilo."
        ),
        produces="lista priorizada de defeitos: [{severidade, arquivo, linha, defeito, correcao}]",
        lens=CRITIC_LENSES[0],
        max_tokens=3500,
    ),
    "fixer": RoleManifest(
        role="fixer",
        mission="Corrigir os defeitos apontados. Nada alem disso.",
        can_write=True,
        write_scope=(
            "*.py",
            "*.md",
            "*.json",
            "*.yaml",
            "*.yml",
            "*.ts",
            "*.tsx",
            "*.js",
        ),
        focus=(
            "Corrija UM defeito por vez. Nao refatore junto. Nao 'aproveite' "
            "para mexer em outra coisa. Se um defeito apontado exigir "
            "decisao que voce nao tem, deixe ele aberto e explique."
        ),
        produces="diff corretivo + quais defeitos foram fechados e quais ficaram abertos",
        max_tokens=4000,
    ),
    "optimizer": RoleManifest(
        role="optimizer",
        mission=(
            "Melhorar legibilidade e manutencao SEM mudar comportamento. "
            "Nao e o papel de mudar requisito."
        ),
        can_write=True,
        write_scope=(
            "*.py",
            "*.md",
            "*.json",
            "*.yaml",
            "*.yml",
            "*.ts",
            "*.tsx",
            "*.js",
        ),
        focus=(
            "So mexa se o ganho for claro. Antes de reescrever, pergunte se o "
            "codigo esta errado ou so feio. Preserve TODOS os testes "
            "existentes. Justifique cada mudanca em uma frase."
        ),
        produces="diff + justificativa de cada mudanca",
        max_tokens=3000,
    ),
}

# Papeles que NUNCA recebem a tool de escrita, independente de qualquer coisa.
# Esta e a invariante de separacao do cluster.
READ_ONLY: frozenset[Role] = frozenset({"researcher", "reader", "critic"})


def manifest(role: str) -> RoleManifest:
    """Manifest por papel. Erro explicito para papel desconhecido."""
    if role not in REGISTRY:
        raise KeyError(
            f"papel desconhecido: {role!r}. papeis validos: {sorted(REGISTRY)}"
        )
    return REGISTRY[role]


def tools_for(role: str, *, lens: str | None = None) -> list[dict]:
    """Tools concedidas a um papel.

    A concessao de escrita passa por `READ_ONLY` de proposito: e a unica
    garantia de que revisor nao edita. Nao depende do prompt obedecer.
    """
    m = manifest(role)
    if role in READ_ONLY:
        return list(READ_TOOLS)
    tools = list(READ_TOOLS)
    if m.can_write and m.write_scope:
        tools.append(WRITE_TOOL)
    return tools


def _resolver_raiz(raiz: str | Path | None) -> Path | None:
    """Canonicaliza a raiz informada. `None` quando nao ha raiz valida."""
    if raiz is None:
        return None
    try:
        return Path(str(raiz).replace("\\", "/").strip()).resolve()
    except (OSError, ValueError, RuntimeError):
        return None


def _raiz_autorizada(role: str) -> Path | None:
    """Raio base do escopo quando nao vem por parametro. Hoje, nenhuma.

    O escopo por diretorio precisa de uma raiz. Ela pode chegar de duas
    maneiras, e ambas estao implementadas:

      1. Por parametro `raiz=` em `in_scope` — o caminho usado pelo
         orquestrador, que sabe qual arquivo esta sendo editado e passa o
         diretorio dele. E o caminho certo e o primario.
      2. Por variavel de ambiente `VMP_CLUSTER_ROOT`, como plano B para uso
         fora do orquestrador.

    Sem nenhuma das duas, o escopo volta a barrar `..` por texto — seguro,
    porem conservador. Registrado em `in_scope`.
    """
    return _resolver_raiz(os.environ.get("VMP_CLUSTER_ROOT") or None)


def in_scope(role: str, path: str, raiz: str | Path | None = None) -> bool:
    """Um caminho pode ser gravado por este papel?

    QUATRO VERSOES, todas testadas com exploit real (`test_escape.py`):

    1. `any(fnmatch(path, pat))` sobre o TEXTO do caminho.
       FURADO: `C:/tmp/x/../SAIU.py` casa com `*.py` e gravava fora.

    2. Rejeitar TODO caminho com `..`.
       SEGURO, mas conservador: recusa `sub/../ok.py`, que resolve para
       dentro e e trabalho legitimo. Achado do comite de revisao.

    3. Resolver o caminho e checar so a extensao.
       FURADO DE NOVO — as versoes 1 e 3 falham pelo mesmo motivo: sem um
       diretorio autorizado, "saiu do escopo" nao e pergunta com resposta.

    4. (esta) Resolver, exigir que fique DENTRO da raiz, e so entao checar a
       extensao. Com raiz, `..` que cancela dentro passa — que e o que o
       comite pediu — e `..` que sai e barrado, que e o buraco.

    O parametro `raiz` e o que faz a versao 4 existir. Quem tem essa
    informacao e o orquestrador, que sabe qual arquivo esta sendo editado;
    por isso `raiz` entra como parametro e nao como constante.
    """
    from fnmatch import fnmatch

    m = manifest(role)
    if role in READ_ONLY or not m.can_write:
        return False

    alvo = path.replace("\\", "/").strip()
    if not alvo:
        return False

    base = _resolver_raiz(raiz)
    if base is None:
        base = _raiz_autorizada(role)

    try:
        canonical = Path(alvo).resolve()
    except (OSError, ValueError, RuntimeError):
        return False

    # Gravar em diretorio nao faz sentido e nao casa com extensao nenhuma,
    # mas explicitar deixa a intencao clara.
    if canonical.is_dir():
        return False

    if base is None:
        # Sem raiz: piso de seguranca (versao 2). Barrar `..` no texto.
        if ".." in alvo.split("/"):
            return False
        if ".." in canonical.as_posix().split("/"):
            return False
        return any(fnmatch(canonical.name, pat) for pat in m.write_scope)

    # Com raiz: o filesystem decide. `resolve()` ja colapsou `..`, entao o
    # caminho e o que seria realmente aberto.
    if ".." in canonical.as_posix().split("/"):
        return False

    # `is_relative_to` e a comparacao correta. `str(base) in str(canonical)`
    # daria falso positivo com `/proj` contra `/projeto`.
    try:
        dentro = canonical.is_relative_to(base)
    except AttributeError:
        # Python < 3.9: emula o comportamento.
        dentro = str(canonical).startswith(str(base) + os.sep) or canonical == base
    if not dentro:
        return False

    return any(fnmatch(canonical.name, pat) for pat in m.write_scope)


def describe() -> str:
    """Tabela legivel dos papeis — usada pelo CLI e pela documentacao."""
    rows = [f"{'papel':<11}{'escreve':<9}{'tokens':<8}missao"]
    rows.append("-" * 88)
    for role in PIPELINE:
        m = manifest(role)
        w = ", ".join(m.write_scope[:3]) if m.writes else "—"
        rows.append(f"{role:<11}{w:<9}{m.max_tokens:<8}{m.mission[:46]}")
    return "\n".join(rows)
