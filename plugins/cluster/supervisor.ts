/**
 * SUPERVISOR — o ciclo de rodadas, e o que fecha o comite.
 *
 * POR QUE ISTO EXISTE
 * Rodar N agentes com uma pergunta e uma onda e o que o `/consultar` ja faz.
 * Isso nao e uma equipe: e uma enquete. Equipe precisa de (a) rodadas que se
 * retroalimentam, (b) alguem que leia as respostas dos OUTROS, e (c) estado
 * que sobreviva a sessao. As tres coisas vivem aqui.
 *
 * A ORDEM DAS RODADAS E UMA DECISAO, NAO UMA CONSTANTE
 *
 *   revisar -> pesquisar -> conceber -> lembrar -> supervisionar
 *
 * Cada tier existe por um motivo que impede inverter a ordem:
 *
 *  - revisar antes de pesquisar: nao se pesquisa solucao antes de saber
 *    qual e o defeito. Eh pesquisa com o problema ao avesso.
 *  - pesquisar antes de conceber: conceber sem opcoes e inventar. O tier
 *    conceber LITERALMENTE recebe as respostas da pesquisa.
 *  - conceber antes de lembrar: so ha o que registrar depois de decidir.
 *  - supervisionar por ultimo, SEMPRE: quem supervisiona precisa ver tudo.
 *    E o unico tier que pode dizer que o trabalho nao presta. Se rodar no
 *    meio, ele so viu metade — e meio parecer e pior que nenhum, porque
 *    passa seguranca.
 *
 * CALIBRE (2026-10-01): o relay mediu 46-50 simultaneos sem 429 (14,9s
 * pergunta curta; 33s lendo arquivo). Cada rodada e UMA onda. Nao ha razao
 * para encadear o que da para disparar junto.
 */

import { consultarTodos } from "./engine.ts"
import { PERFIS } from "./engine.ts"
import {
  ORDEM_TIER,
  TITULO_TIER,
  TODOS_PAPEIS,
  escolher,
  type Papel,
  type Tier,
} from "./roles.ts"
import { Trilha, novoId, type Checkpoint, type Rodada } from "./checkpoint.ts"
import { readFile } from "node:fs/promises"

/** Teto de caracteres por arquivo injetado no prompt. */
const MAX_CHARS_POR_ARQUIVO = 6000

/**
 * Sintetiza os papeis do comite no MESMO formato que `PERFIS` (o motor ja
 * sabe consultar esses). Sem isto o motor teria duas familias de perfil e
 * `consultarTodos` precisaria de dois caminhos.
 */
function paraPerfil(p: Papel) {
  return {
    id: p.id,
    nome: p.nome,
    lente: p.lente,
    tier: p.tier,
  }
}

/** Le o material e devolve o texto que entra no prompt. */
async function materialEm(arquivos: string[]): Promise<string> {
  if (!arquivos.length) return ""
  const partes: string[] = ["", "=== MATERIAL PARA VOCE VER (conteudo literal) ==="]
  for (const caminho of arquivos) {
    try {
      const txt = await readFile(caminho, "utf-8")
      const cortado =
        txt.length > MAX_CHARS_POR_ARQUIVO
          ? txt.slice(0, MAX_CHARS_POR_ARQUIVO) +
            `\n... [cortado em ${MAX_CHARS_POR_ARQUIVO} de ${txt.length} chars]`
          : txt
      partes.push(`\n--- ${caminho.split(/[\\/]/).pop()} ---\n${cortado}`)
    } catch (e: any) {
      partes.push(`\n--- ${caminho} ---\n(nao consegui ler: ${e?.message ?? e})`)
    }
  }
  return partes.join("\n")
}

/**
 * Resumo do que ja foi dito, para os tiers seguintes.
 *
 * O teto e o que mantem o ciclo inteiro dentro do orcamento: sem ele, cada
 * rodada carregaria tudo que veio antes e a 5a rodada nao caberia. Cortar
 * aqui e perder detalhe, e melhor que estourar — desde que o supervisor
 * (que ve tudo) seja quem tira a conclusao.
 */
function resumoAnterior(cp: Checkpoint, teto = 2400): string {
  const linhas: string[] = []
  for (const r of cp.rodadas) {
    linhas.push(`\n### Rodada ${r.tier}`)
    for (const [papel, texto] of Object.entries(r.respostas)) {
      linhas.push(`[${papel}] ${texto.slice(0, 260)}`)
    }
  }
  const tudo = linhas.join("\n")
  return tudo.length > teto ? tudo.slice(0, teto) + "\n... [resumo truncado]" : tudo
}

/**
 * Orcamento padrao por papel.
 *
 * MEDIDO (2026-10-01, probe_orcamento.ts): 3000 era herdo do `/consultar` e
 * e superdimensionado. Com 800, 1200, 2000 e 3000 NENHUM devolveu resposta
 * vazia, e o tempo escala ~linear com o orcamento acima de 1200
 * (15,7s / 24,2s / 32,7s para o tier revisar com 14 papeis).
 *
 * 1500 fica como padrao: folga acima do piso observado e cerca de 2x mais
 * rapido que 3000. Uma amostra por ponto — isto e indicacao, nao curva.
 * O SPEC 3.4 registra resposta vazia em 600, entao nao se desce disso.
 */
export const ORCAMENTO_PADRAO = 1500

/**
 * Perfis de ciclo, do mais barato ao mais fundo.
 *
 * POR QUE EXISTEM: o ciclo completo mediu 1143s (19 min). Isso e aceitavel
 * para revisao profunda de sistema pesado, mas e impraticavel para o uso
 * diario. A alavanca mais forte NAO e baixar o orcamento — e rodar menos
 * tiers, porque cada tier e uma onda sequencial de minutos.
 *
 * Escolha do coordenador:
 *   rapido    -> so `revisar`. Achou o grave, para.
 *   padrao    -> revisar + supervisionar. Achado com triagem e proximo passo.
 *   completo  -> os 5 tiers. Decisao com pesquisa, experimento e memoria.
 *   profundo  -> os 5 + orcamento alto, para quando a resposta importa mais
 *                 que os minutos.
 */
export const PERFIS_CICLO: Record<string, { tiers: Tier[]; orcamento: number; descricao: string }> = {
  rapido: {
    tiers: ["revisar"],
    orcamento: 1200,
    descricao: "so revisao. ~1-2 min. Achou o grave, ja basta.",
  },
  padrao: {
    tiers: ["revisar", "supervisionar"],
    orcamento: 1500,
    descricao: "revisao + supervisao. Achado com triagem e proximo passo. ~5-10 min.",
  },
  completo: {
    tiers: ["revisar", "pesquisar", "conceber", "lembrar", "supervisionar"],
    orcamento: 1500,
    descricao: "os 5 tiers, com pesquisa, experimento e memoria. ~15-20 min.",
  },
  profundo: {
    tiers: ["revisar", "pesquisar", "conceber", "lembrar", "supervisionar"],
    orcamento: 3000,
    descricao: "os 5 tiers com orcamento alto. ~25-35 min, respostas mais longas.",
  },
}

/**
 * A resposta conta como resposta?
 *
 * "Nao vazio" nao basta. MEDIDO (2026-10-01, primeiro ciclo completo): a
 * lente `s_vies` devolveu `<tool_call>` — o modelo tentou
 * CHAMAR FERRAMENTA numa completion que so aceita texto. Isso e texto nao
 * vazio, entao passou como resposta, e entrou no relatorio como se fosse
 * um parecer. E pior do que calar: calar e honesto, isso e lixo com
 * aparencia de achado.
 *
 * Entao: marca-dade-devagar. Resposta que e So marca de tool-call conta
 * como calada, e o nome da lente aparece na lista de lacunas.
 */
function respostaUtil(txt: string): boolean {
  const t = txt.trim()
  if (t.length < 20) return false // fragmento inutil
  // Marca de tool-call com o texto inteiro sendo isso (>=80%) = lixo.
  const marcas = /(<\|tool_call\|>|<tool_call>|tool_calls|\[tool_call\]|<\|im_start\|>|<\|minimax\|>)/g
  const n = (t.match(marcas) ?? []).length
  if (n > 0 && n * 40 >= t.length) return false
  return true
}

export interface OpcoesCiclo {
  pedido: string;
  arquivos?: string[];
  /** Tiers a rodar. Padrao: todos, na ordem de ORDEM_TIER. */
  tiers?: Tier[];
  /** Perfil pronto (`rapido`, `padrao`, `completo`, `profundo`). Tem precedencia sobre `tiers`/`orcamento`. */
  perfil?: keyof typeof PERFIS_CICLO;
  orcamento?: number;
  /** Onde gravar. Padrao: ao lado do motor. */
  trilha?: Trilha;
  /** Id para retomar uma trilha existente. */
  id?: string;
  /**_callback por rodada, para log. */
  aoTerminarRodada?: (r: Rodada) => void;
}

export interface ResultadoCiclo {
  id: string;
  versao: number;
  checkpoint: Checkpoint;
  duracaoSegundos: number;
  perfilUsado: string;
}

export async function rodarCiclo(op: OpcoesCiclo): Promise<ResultadoCiclo> {
  const t0 = Date.now()
  const arquivos = op.arquivos ?? []
  const trilha = op.trilha ?? new Trilha(process.env.CLUSTER_TRILHA ?? ".cluster/trilhas")
  const id = op.id ?? novoId(op.pedido)

  // Perfil pronto resolve tiers e orcamento de uma vez. Passar `tiers` ou
  // `orcamento` na mao continua funcionando para quem quiser mountar um
  // ciclo sob medida.
  const perfil = op.perfil ? PERFIS_CICLO[op.perfil] : null
  const orcamento = op.orcamento ?? perfil?.orcamento ?? ORCAMENTO_PADRAO

  // Retomar ≠ recomecar. Se a trilha tem versao, a nova herda as rodadas
  // anteriores e o numero de versao sobe. Perder o historico ao "rodar de
  // novo" seria exatamente o defeito que o checkpoint existe para evitar.
  const anterior = trilha.carregar(id)
  const cp: Checkpoint = anterior
    ? { ...anterior, versao: anterior.versao + 1, criadoEm: new Date().toISOString() }
    : {
        id,
        versao: 1,
        criadoEm: new Date().toISOString(),
        titulo: op.pedido.slice(0, 80),
        pedido: op.pedido,
        arquivos,
        rodadas: [],
        proximosPassos: [],
        bloqueios: [],
      }

  const material = await materialEm(arquivos)
  const temMaterial = material.length > 0
  const tiers = op.tiers ?? perfil?.tiers ?? ORDEM_TIER
  if (op.perfil && !perfil) {
    cp.bloqueios.push(
      `perfil '${op.perfil}' nao existe. Use: ${Object.keys(PERFIS_CICLO).join(", ")}`,
    )
  }

  for (const tier of tiers) {
    const papeis = escolher(tier, temMaterial)
    if (!papeis.length) continue

    const tR = Date.now()
    // O prompt de cada tier carrega o que os anteriores produziram. E isto
    // que permite "conceber depois de pesquisar" e nao so 46 respostas
    // independentes.
    const herdado =
      cp.rodadas.length > 0 ? `\n\n=== O QUE A EQUIPE JA DISSE ===\n${resumoAnterior(cp)}` : ""
    const base = `${op.pedido}${material}${herdado}`
    const papelNoPrompt =
      tier === "supervisionar"
        ? "\n\nVoce le as respostas de TODOS os outros agentes acima. Nao repita o que eles acharam: diga o que eles NAO viram, o que contradizem e o que fazer."
        : ""

    process.stderr.write(
      `[ciclo] ${tier}: disparando ${papeis.length} papeis (${TITULO_TIER[tier]})\n`,
    )

    let respostas: any[] = []
    try {
      const r = await consultarTodos(
        papeis.map(paraPerfil),
        // O motor aplica a `lente` de cada perfil; aqui entra o resto.
        base,
        {
          orcamento,
          montarPrompt: async (_i: number, _p: any) => base + papelNoPrompt,
        } as any,
      )
      respostas = r.respostas
    } catch (e: any) {
      process.stderr.write(`[ciclo] ${tier} FALHOU: ${e?.message ?? e}\n`)
      cp.bloqueios.push(`tier ${tier} falhou: ${String(e?.message ?? e).slice(0, 160)}`)
      continue
    }

    const mapa: Record<string, string> = {}
    const calados: string[] = []
    papeis.forEach((p, i) => {
      const r = respostas[i]
      const txt = String(r?.texto ?? r?.content ?? "").trim()
      if (r?.ok && respostaUtil(txt)) mapa[p.id] = txt
      else calados.push(p.id)
    })

    const rodada: Rodada = {
      tier,
      em: Date.now(),
      duracaoMs: Date.now() - tR,
      chamados: papeis.length,
      ok: Object.keys(mapa).length,
      calados,
      respostas: mapa,
    }
    cp.rodadas.push(rodada)

    // Lente calada e LACUNA NOMEADA. Sem este registro, 38 de 46 lentes
    // respondendoLooks igual a 46 de 46 — e a consolidatecao passa a tratar
    // "ninguem olhou performance" como "ninguem achou problema de performance".
    if (calados.length) {
      process.stderr.write(
        `[ciclo] ${tier}: ${calados.length} calado(s) — ${calados.join(", ")}\n`,
      )
    }
    process.stderr.write(
      `[ciclo] ${tier}: ${rodada.ok}/${rodada.chamados} em ${(rodada.duracaoMs / 1000).toFixed(1)}s\n`,
    )
    op.aoTerminarRodada?.(rodada)

    // A supervisao e a conclusao do ciclo: guarda separado porque e a
    // resposta que o coordenador entrega ao usuario.
    //
    // ACHADO NO PRIMEIRO CICLO REAL (2026-10-01): dependei de `s_meta` para
    // a sintese, e `s_meta` foi uma das duas lentes que calaram (44/46). O
    // resultado: `supervisao` ficou VAZIO mesmo com 6 das 8 lentes de
    // supervisao responders — e o ciclo terminou sem entrega. Depender de
    // UMA lente para a entrega e o mesmo erro de "tratar lente faltante
    // como nao ha problema", so invertido: vira "tratar lente faltante como
    // nao ha resposta".
    //
    // Entao a entrega e feita com o que RESPONDEU. A sintese principal vem
    // do s_meta quando ha; senao, das demais lentes de supervisao, que ja
    // leram tudo e discutem o mesmo.
    if (tier === "supervisionar") {
      const ordem = ["s_meta", "s_proximo", "s_intervencao", "s_lacuna", "s_vies"]
      const partes: string[] = []
      for (const id of ordem) {
        if (mapa[id]) partes.push(`[${id}] ${mapa[id]}`)
      }
      const sobrando = Object.entries(mapa).filter(([k]) => !ordem.includes(k))
      for (const [k, v] of sobrando) partes.push(`[${k}] ${v}`)

      cp.supervisao = partes.join("\n\n")
      const principal = mapa["s_meta"] ?? partes[0] ?? ""
      const interv = mapa["s_intervencao"] ?? ""
      cp.conclusao = [principal, interv].filter(Boolean).join("\n\n")

      if (!principal && partes.length) {
        cp.bloqueios.push(
          "s_meta nao respondeu; a entrega veio das outras lentes de " +
            "supervisao. Vale ler com mais cuidado.",
        )
      }

      // Proximos passos: pega do s_proximo quando ele existe. Sem ele, usa
      // a lente de lacunas, que e a mais proxima do que fazer.
      const fonte = mapa["s_proximo"] ?? mapa["s_lacuna"] ?? ""
      if (fonte) {
        cp.proximosPassos = fonte
          .split("\n")
          .map((l) =>
            l
              .replace(/^\s*[-*\d]+[.)-]?\s*/, "")
              // Corta a linha no primeiro ponto-final: um achado de revisao
              // costuma ser uma frase, nao um passo. Sem isso, "proximos
              // passos" virava lista de defeitos.
              .split(/\.\s/)[0]
              .trim(),
          )
          .filter((l) => l.length > 18)
          .slice(0, 5)
      }
    }
  }

  const totalOk = cp.rodadas.reduce((a, r) => a + r.ok, 0)
  const totalChamados = cp.rodadas.reduce((a, r) => a + r.chamados, 0)
  if (totalOk < totalChamados * 0.6) {
    cp.bloqueios.push(
      `cobertura baixa: ${totalOk}/${totalChamados} lentes responderam. ` +
        `Trate o resultado como parcial, nao como "nada foi encontrado".`,
    )
  }

  trilha.salvar(cp)
  trilha.salvarRelatorio(cp)

  return {
    id,
    versao: cp.versao,
    checkpoint: cp,
    duracaoSegundos: (Date.now() - t0) / 1000,
    perfilUsado: op.perfil ?? "customizado",
  }
}

/** Exporta o total, para o coordenador saber o tamanho da equipe. */
export const TAMANHO_EQUIPE = TODOS_PAPEIS.length
export { PERFIS }