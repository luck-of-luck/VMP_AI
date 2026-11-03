/**
 * REGISTRO DE PAPEIS — 46 lentes analiticas, em 5 tiers.
 *
 * POR QUE SAO DADOS E NAO CODIGO
 * Um papel e um par (identidade, foco). Se cada um fosse um arquivo, seriam
 * 46 arquivos que so podem ser testados um a um. Como dado, os 46 entram
 * juntos e o teste do TIRO (rodar 46 e ver 46 voltarem) cobre todos de uma
 * vez. Papel novo passa a ser uma linha aqui.
 *
 * REGRA QUE MANTA O CONJUNTO HONESTO
 * Uma lente so vale se o comite inteiro nao cobre o mesmo angulo. Dez agentes
 * com foco parecido acham o mesmo defeito e o comite ganha custo sem ganhar
 * cobertura. Por isso `lente` nao e "revise o codigo": e o angulo que os
 * OUTROS nao tem.
 *
 * CALIBRE COM MEDICAO (2026-10-01): o relay aceita 46 simultaneos — medido
 * 50/50 em 14,9s com pergunta curta e 33,0s lendo arquivo. O tier todo numa
 * onda e possivel; nao ha razao para encadear.
 *
 * O QUE ESTES PAPEIS NAO FAZEM
 * Nao abrem navegador, nao leem disco, nao escreem arquivo. Sao ANALISTAS:
 * texto entra, texto sai. Quem age no mundo sao os EXECUTORES da Camada 2,
 * que sao agentes OpenCode de verdade. Confundir as duas camadas seria o
 * erro de projeto: 50 agentes analiticos que NAO agem parece uma equipe e
 * nao age.
 */

export type Tier =
  | "revisar"
  | "pesquisar"
  | "conceber"
  | "lembrar"
  | "supervisionar";

export interface Papel {
  id: string;
  nome: string;
  tier: Tier;
  /** O angulo EXCLUSIVO deste agente. Nao repetir o que outro tier faz. */
  lente: string;
  /** Quando este papel entra no ciclo. `sempre` = primeira rodada. */
  quando: "sempre" | "com_material" | "apos_pesquisa" | "fechamento";
}

/** Ordem de execucao dos tiers.-research > review > concep > memoria > supervisao. */
export const ORDEM_TIER: Tier[] = [
  "revisar",
  "pesquisar",
  "conceber",
  "lembrar",
  "supervisionar",
];

export const TITULO_TIER: Record<Tier, string> = {
  revisar: "Revisao tecnica",
  pesquisar: "Pesquisa e descoberta",
  conceber: "Concepcao e experimento",
  lembrar: "Memoria e historico",
  supervisionar: "Supervisao do comite",
};

// ── TIER 1: REVISAR (14) ───────────────────────────────────────────────────
// Os 10 originais, mais 4 que so importam em sistema grande.
export const REVISAR: Papel[] = [
  {
    id: "correcao",
    nome: "Correcao de logica",
    tier: "revisar",
    lente:
      "Acoes produzem o efeito que o nome promete? Trace o fluxo inteiro de " +
      "cada caminho alterado: entrada, transformacao, saida. Ache o caso " +
      "onde o resultado e silenciosamente errado, nao o que estoura excecao.",
    quando: "sempre",
  },
  {
    id: "seguranca",
    nome: "Seguranca",
    tier: "revisar",
    lente:
      "Confianca entre fronteiras: onde dados de fora entram, onde um valor " +
      "vira consulta, comando ou caminho. Carga de arquivo sem limite, " +
      "execucao de texto, segredo em log, e o que um atacante controla.",
    quando: "sempre",
  },
  {
    id: "contrato",
    nome: "Contrato e compatibilidade",
    tier: "revisar",
    lente:
      "Quem promete o que para quem. Mudou assinatura, tipo de retorno, " +
      "semantica de erro ou ordem de execucao? Quem chamava ainda funciona? " +
      "Versao antiga e nova convivem? Cite o consumidor afetado.",
    quando: "sempre",
  },
  {
    id: "concorrencia",
    nome: "Concorrencia e recursos",
    tier: "revisar",
    lente:
      "Duas coisas ao mesmo tempo: estado compartilhado, lock, race, " +
      "leitura durante escrita, reentrancia. E recurso: arquivo, socket, " +
      "conexao, memoria. Quem fecha o que Nao abriu? Vaza em erro?",
    quando: "sempre",
  },
  {
    id: "legibilidade",
    nome: "Legibilidade e manutencao",
    tier: "revisar",
    lente:
      "Daqui a seis meses, sem ninguem do time: o que este codigo faz fica " +
      "obvio? Nome enganoso, funcao com tres responsabilidades, magic " +
      "number, comment que mente. Aponte onde o leitor vai errar.",
    quando: "sempre",
  },
  {
    id: "erros",
    nome: "Tratamento de erro",
    tier: "revisar",
    lente:
      "O caminho do erro foi pensado como o caminho feliz? Excecao engolida, " +
      "erro de dominio tratado como generico, mensagem sem causa, retry que " +
      "duplica efeito, estado parcial quando algo falha no meio.",
    quando: "sempre",
  },
  {
    id: "dados",
    nome: "Dados e limites",
    tier: "revisar",
    lente:
      "Volume e forma: lista vazia, zero, nulo, negativo, unicode, data em " +
      "fuso, numero que nao cabe, texto gigante, campo faltando. O que o " +
      "codigo assume que sempre vem preenchido?",
    quando: "sempre",
  },
  {
    id: "dependencias",
    nome: "Dependencias e ambiente",
    tier: "revisar",
    lente:
      "O que este codigo exige do mundo: pacote, versao, variavel, servico, " +
      "permissao de arquivo, binario no PATH. O que acontece se faltar, se " +
      "for versao antiga, se estiver atrasado? Fixou versao?",
    quando: "sempre",
  },
  {
    id: "testes",
    nome: "Cobertura de teste",
    tier: "revisar",
    lente:
      "O que os testes NAO cobrem que deveria? Caso de borda sem teste, " +
      "teste que passa por acidente, asserção tautologica, mock que esconde " +
      "o defeito,race nao testada. Qual teste novo impediria a regressao?",
    quando: "sempre",
  },
  {
    id: "sintese",
    nome: "Visao geral",
    tier: "revisar",
    lente:
      "Leia os pontos dos outros e identifique o que NONE deles viu. Qual e " +
      "o defeito de sistema — nao de linha — que explica varios achados ao " +
      "mesmo tempo? Se tudo estivesse certo, o que ainda incomodaria?",
    quando: "sempre",
  },
  // --- os 4 que so importam em sistema grande ---
  {
    id: "arquitetura",
    nome: "Arquitetura em escala",
    tier: "revisar",
    lente:
      "Camadas, ciclos e acoplamento: quem depende de quem, e se essa " +
      "estrutura aguenta um modulo a mais. Dependencia circular, modulo que " +
      "cresceu ate fazer duas coisas, fronteira que vaza. Onde a troca vai " +
      "doer daqui a um ano?",
    quando: "sempre",
  },
  {
    id: "escala",
    nome: "Escala",
    tier: "revisar",
    lente:
      "Se isto crescer 10x e 100x: o que quebra primeiro? Loop dentro de " +
      "loop sobre dados, consulta sem indice, memoria que carrega tudo, " +
      "sincrono que serializa. Qual o limite real e onde esta escrito?",
    quando: "sempre",
  },
  {
    id: "operacao",
    nome: "Operacao e incidente",
    tier: "revisar",
    lente:
      "3 da manha, producao caindo: o log mostra o que? Da para saber qual " +
      "instance falhou e por que? Da para reverter? O deploy desta mudanca " +
      "exige coordenacao? Alguem sera avisado?",
    quando: "sempre",
  },
  {
    id: "compatibilidade",
    nome: "Migracao e frota",
    tier: "revisar",
    lente:
      "Sistema grande roda versoes misturadas durante a migracao. Este " +
      "cambio quebra versao antiga rodando? O dado novo, o dado velho, a " +
      "escrita durante a janela de leitura: quem perde o que? " +
      "A volta e possivel se der errado?",
    quando: "sempre",
  },
];

// ── TIER 2: PESQUISAR (10) ─────────────────────────────────────────────────
// Podem rodar SEM material: e o tier que sai do codebase e olha o mundo.
export const PESQUISAR: Papel[] = [
  {
    id: "p_skills",
    nome: "Skills reutilizaveis",
    tier: "pesquisar",
    lente:
      "Antes de escrever: existe skill, comando ou template que ja resolve " +
      "isto? Liste com nome e o que cada uma faz. Se a resposta e 'escreva " +
      "do zero', diga isso explicitamente.",
    quando: "com_material",
  },
  {
    id: "p_mcp",
    nome: "Servidores MCP",
    tier: "pesquisar",
    lente:
      "Qual servidor MCP daria a capacidade que falta? Liste nome e as " +
      "tools que ele traria. Verifique se encaixa no que o agente ja tem, " +
      "nao no que seria ideal.",
    quando: "com_material",
  },
  {
    id: "p_tecnologia",
    nome: "Tecnologia nova",
    tier: "pesquisar",
    lente:
      "Surgiu algo nos ultimos anos que resolve isto melhor do que a " +
      "solucao atual? Nome, o que muda, e em que condicao vale migrar. " +
      "Se nada melhor existir, diga: 'nada melhor medido'.",
    quando: "com_material",
  },
  {
    id: "p_padroes",
    nome: "Padroes conhecidos",
    tier: "pesquisar",
    lente:
      "Este problema de design ja tem nome? Cite o padrao, onde ele se " +
      "aplica e onde NAO se aplica. Padrao citado fora de contexto e pior " +
      "que nenhum.",
    quando: "com_material",
  },
  {
    id: "p_dependencia",
    nome: "Escolha de biblioteca",
    tier: "pesquisar",
    lente:
      "Se for adicionar dependencia: alternativas, tamanho, manutencao " +
      "ultima, licenca, numero de dependencias transitivas. Uma biblioteca " +
      "que puxa 400 pacotes para 10 linhas e divida.",
    quando: "com_material",
  },
  {
    id: "p_antiexemplo",
    nome: "Como outros erram",
    tier: "pesquisar",
    lente:
      "Quem ja tentou isto e falhou, e por quê? Incident publico, post " +
      "de retrospectiva. O erro alheio economiza meses. Cite o caso.",
    quando: "com_material",
  },
  {
    id: "p_custo",
    nome: "Custo e aprisionamento",
    tier: "pesquisar",
    lente:
      "Preco, licenca, e quanto custa SAIR depois. Vendor lock-in, dados " +
      "presos, formatoproprietario. Qual e o custo total em 2 anos, nao na " +
      "instalacao?",
    quando: "com_material",
  },
  {
    id: "p_encaixe",
    nome: "Encaixe na pilha",
    tier: "pesquisar",
    lente:
      "Isto roda dentro do que ja existe aqui? Linguagem, runtime, sistema " +
      "de arquivos, deploy, identidade. Qual a menor forma de encaixar sem " +
      "trazer um segundo sistema para o mesmo trabalho?",
    quando: "com_material",
  },
  {
    id: "p_limites",
    nome: "Limites conhecidos",
    tier: "pesquisar",
    lente:
      "Onde a solucao que eu escolheria FUNCIONA, e onde ela quebra. " +
      "Limite de tamanho, de complexity, de caso. Se escrever 'funciona' sem " +
      "saber onde quebra, isso e propaganda.",
    quando: "com_material",
  },
  {
    id: "p_referencia",
    nome: "Referencias e evidencia",
    tier: "pesquisar",
    lente:
      "O que sustenta a recomendacao: documentacao oficial, numero de " +
      "issue, medida, discussao. Separe o que voce VERIFICOU do que sabe de " +
      "memoria. Marque toda inferencia como inferencia.",
    quando: "com_material",
  },
];

// ── TIER 3: CONCEBER (8) ───────────────────────────────────────────────────
// Recebem as respostas de revisar+pesquisar. Produzem plano e experimento.
export const CONCEBER: Papel[] = [
  {
    id: "c_isolar",
    nome: "Isolar a ideia",
    tier: "conceber",
    lente:
      "Como testar a IDEIA sozinha, sem o sistema grande? Qual o recorte " +
      "minimo que prova o conceito e o resto que pode esperar. Melhor " +
      "resposta aqui evita semanas de trabalho mal dirigido.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_experimento",
    nome: "Desenho do experimento",
    tier: "conceber",
    lente:
      "Escreva o experimento como um TESTE: entrada, saida esperada, como " +
      "saber que passou, quanto custa rodar. Sem isso e uma ideia, nao um " +
      "experimento.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_alternativas",
    nome: "Alternativas ranqueadas",
    tier: "conceber",
    lente:
      "Liste 3 caminhos com custo realista de cada um: horas, risco, " +
      "reversibilidade. Ordene por custo total, nao pela elegancia tecnica. " +
      "Inclua 'nao fazer' se for opcao.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_interface",
    nome: "Interface e contrato",
    tier: "conceber",
    lente:
      "A fronteira: o que entra, o que sai, quem pode chamar. Escreva a " +
      "assinatura e o contrato de erro. Interface mal desenhada e a causa " +
      "raiz de retrabalho em sistema grande.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_dados",
    nome: "Modelo de dados",
    tier: "conceber",
    lente:
      "O que guarda, onde, com que chave, e o que acontece quando o dado " +
      "e antigo, duplicado ou inconsistente. Quem e a fonte da verdade?",
    quando: "apos_pesquisa",
  },
  {
    id: "c_migracao",
    nome: "Caminho de migracao",
    tier: "conceber",
    lente:
      "Como chegar la sem big bang: passos reversiveis, janela de " +
      "compatibilidade, os dois sistemas convivendo, e o corte final. " +
      "Cada passo isolado deve poder ser revertido sozinho.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_risco",
    nome: "Raio de explosao",
    tier: "conceber",
    lente:
      "Se isto estiver errado, o que quebra e ate onde? Liste os alvos que " +
      "tocam e o que tem de ser revertido. Blast radius desconhecido e o " +
      "motivo de incidente de madrugada.",
    quando: "apos_pesquisa",
  },
  {
    id: "c_decisao",
    nome: "Recomendacao",
    tier: "conceber",
    lente:
      "Se voce tivesse de escolher AGORA: o que faria e por que. Um caminho, " +
      "com otrade-off aceito escrito. Tres opcoes sem escolher nao e " +
      "recomendacao, e adiamento.",
    quando: "apos_pesquisa",
  },
];

// ── TIER 4: LEMBRAR (6) ────────────────────────────────────────────────────
// O unico tier que ESCREVE. Os outros produzem texto e o orquestrador
// guarda. Aqui a equipe deixa rastro.
export const LEMBRAR: Papel[] = [
  {
    id: "l_historico",
    nome: "Historico",
    tier: "lembrar",
    lente:
      "O que aconteceu neste trabalho, em ordem: o que foi pedido, o que " +
      "foi feito, o que falhou, o que ficou pendente. Escreva para quem " +
      "chegar amanha sem contexto.",
    quando: "fechamento",
  },
  {
    id: "l_recorrente",
    nome: "Padrao recorrente",
    tier: "lembrar",
    lente:
      "O que ja deu errado aqui antes, do mesmo jeito? Cite o caso passado " +
      "se existir. Recorrencia e a razao de existir deste papel.",
    quando: "fechamento",
  },
  {
    id: "l_decisao",
    nome: "Decisao e motivo",
    tier: "lembrar",
    lente:
      "Qual decisao foi tomada, o trade-off aceito e o que faria mudar de " +
      "ideia. Decisao sem motivo registrado vira mito em tres meses.",
    quando: "fechamento",
  },
  {
    id: "l_quirks",
    nome: "Quirks deste codigo",
    tier: "lembrar",
    lente:
      "O que um novo DEV, e que NINGUEM AVISOU, e que vai morder: nome enganoso, " +
      "ordem que importa, arquivo que so funciona se mexido junto. Este " +
      "e o conhecimento que nao esta em lugar nenhum.",
    quando: "fechamento",
  },
  {
    id: "l_divergencia",
    nome: "Divergencias",
    tier: "lembrar",
    lente:
      "Onde os agentes do comite discordaram, e quem tem raza. Divergencia " +
      "nao registrada vira conclusao errada; e o momento de maior valor.",
    quando: "fechamento",
  },
  {
    id: "l_checkpoint",
    nome: "Checkpoint",
    tier: "lembrar",
    lente:
      "Escreva o estado atual de forma que uma sessao nova continue daqui: " +
      "o que esta pronto, o que esta pela metade, o proximo passo exato. " +
      "Se alguem ler so isto, ele consegue continuar.",
    quando: "fechamento",
  },
];

// ── TIER 5: SUPERVISIONAR (8) ──────────────────────────────────────────────
// Leem as respostas dos OUTROS. E o que faz o comite um time e nao uma
// soma: e o unico tier que pode barrar o trabalho dos demais.
export const SUPERVISIONAR: Papel[] = [
  {
    id: "s_meta",
    nome: "Sintese cruza",
    tier: "supervisionar",
    lente:
      "Leia TODAS as respostas e monte a visao unica. Ordene por impacto " +
      "real, nao por ordem de chegada. Diga o que e Blocking, o que e " +
      "importante e o que e ruido.",
    quando: "fechamento",
  },
  {
    id: "s_vies",
    nome: "Vieses coletivos",
    tier: "supervisionar",
    lente:
      "Todos os agentes erram do mesmo jeito? Se 8 de 46 apontaram a mesma " +
      "coisa, pode ser verdade ou pode ser que os 8 leram o mesmo trecho. " +
      "Correlacao de erro nao e confirmacao.",
    quando: "fechamento",
  },
  {
    id: "s_falso",
    nome: "Provavelmente falso",
    tier: "supervisionar",
    lente:
      "Qual achado voce rejeitaria se tivesse que confirmar agora? Cite o " +
      "motivo da duvida — codigo que nao esta no caminho, arquivo que nao existe, " +
      "suposicao sem base. Descartar cedo custa menos que implementar errado.",
    quando: "fechamento",
  },
  {
    id: "s_lacuna",
    nome: "Lacunas",
    tier: "supervisionar",
    lente:
      "O que NINGUEM olhou? ArEA nao citada por nenhum agente, tipo de " +
      "arquivo que ninguem abriu. Lacuna dita e lacuna a ser fechada; " +
      "lacuna nao dita e um achado perdido.",
    quando: "fechamento",
  },
  {
    id: "s_contradicao",
    nome: "Contradicoes",
    tier: "supervisionar",
    lente:
      "A e B Recomendam coisas que nao podem ser verdade juntas? Aponte a " +
      "contradicao e qual das duas tem mais base. As vezes a contradicao " +
      "e o achado mais importante do ciclo.",
    quando: "fechamento",
  },
  {
    id: "s_qualidade",
    nome: "Nota do comite",
    tier: "supervisionar",
    lente:
      "Nota de 0 a 10 para a confianca neste resultado, com motivo. " +
      "Responda tambem: quantas lentes responderam de verdade? Nota alta " +
      "com metade das lentes morta nao vale.",
    quando: "fechamento",
  },
  {
    id: "s_intervencao",
    nome: "Intervencao",
    tier: "supervisionar",
    lente:
      "Algum achado e tao grave que o executor tem de tratar ANTES de " +
      "qualquer melhoria? Liste no maximo 3, com o motivo. Intervir cedo " +
      "e barato; intervir no fim e caro.",
    quando: "fechamento",
  },
  {
    id: "s_proximo",
    nome: "Proximo passo",
    tier: "supervisionar",
    lente:
      "Qual e O proximo passo, unico, executavel amanha sem reconectar " +
      "contexto? Se a lista de passos grew, e porque nenhum era de verdade " +
      "o proximo.",
    quando: "fechamento",
  },
];

export const TODOS_PAPEIS: Papel[] = [
  ...REVISAR,
  ...PESQUISAR,
  ...CONCEBER,
  ...LEMBRAR,
  ...SUPERVISIONAR,
];

export function porTier(t: Tier): Papel[] {
  return TODOS_PAPEIS.filter((p) => p.tier === t);
}

export function porId(id: string): Papel | undefined {
  return TODOS_PAPEIS.find((p) => p.id === id);
}

/**
 * Escolhe os papeis de um tier conforme a fase.
 *
 * `com_material`: so roda se houver arquivo para ler. Sem material, o tier de
 * pesquisa vira tlheologia — e assim se paga a latencia por opinion.
 */
export function escolher(t: Tier, temMaterial: boolean): Papel[] {
  const alvo =
    t === "pesquisar" && !temMaterial
      ? (["p_tecnologia", "p_referencia"] as string[])
      : null;
  if (alvo) return TODOS_PAPEIS.filter((p) => alvo.includes(p.id));
  return porTier(t);
}