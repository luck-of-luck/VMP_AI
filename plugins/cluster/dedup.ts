/**
 * DEDUP — junta o que as 46 lentes disseram sobre o MESMO defeito.
 *
 * A MEDICAO QUE MOTIVOU ESTE ARQUIVO (2026-10-03)
 *
 *   49 linhas de achado -> 8 categorias distintas. Sinal util: 16%.
 *
 * Cuarenta e nove linhas dizendo oito coisas. O usuario lia ~6 linhas para
 * achar 1 novidade. Toda a maquina — 46 lentes, 5 tiers, checkpoint, board
 * — funcionava perfeitamente e entregava 16%. Entao o gargalo nao era
 * robustez, era valor.
 *
 * O QUE ESTE ARQUIVO FAZ, E O QUE NAO FAZ
 *
 * FAZ: junta achados equivalentes, conta quantas lentes cairam em cada
 * grupo, e ordena por essa contagem. A contagem vira CONFIANCA de graca:
 * 9 lentes independentes dizendo a mesma coisa e evidencia muito mais forte
 * que uma lente saying it com certeza. Esse dado ja existia e estava sendo
 * jogado fora.
 *
 * NAO FAZ: nao julga severidade. Seria inventar um numero que ninguem mediu.
 * A ordem e por concordancia, e a categoria aparece como ROTULO, nao como
 * nota. Se um dia a severidade vier de uma lente que a declara, ai sim vira
 * sinal — mas nao antes de existir a declaracao.
 *
 * COMO AGRUPA, E POR QUE NAO USO UM MAPA DE CATEGORIAS
 *
 * A primeira medicao (probe_sinal.ts) usou um mapa de 11 categorias que EU
 * escrevi. Funcionou como faixa, mas depende do meu julgamento: se o mapa
 * estiver errado, agrupa errado e eu nao tenho como perceber.
 *
 * Aqui a similitude e calculada sobre o PROPRIO TEXTO do achado: funcao
 * citada, linha citada, termos distintivos. Duas linhas sobre o mesmo defeito
 * compartilham o vocabulario especifico delas (o nome da funcao, o termo do
 * problema) mesmo quando escritas de formas diferentes. Isso nao depende de
 * eu saber a resposta.
 *
 * O LIMITE, DECLARADO: dois defeitos verdadeiramente diferentes no mesmo
 * lugar (mesma funcao, mesma linha) podem ser juntados. E preferivel: erro
 * de agrupamento custa ler uma linha a mais, erro de NAO agrupar custa ler
 * o mesmo defeito cinco vezes — que e o problema que estamos corrigindo.
 */

export interface Achado {
  lente: string
  texto: string
}

/** Grupo durante a montagem: guarda os indices para recalcular no fim. */
interface GrupoInterno extends Grupo {
  membros: number[]
  linhas: string[]
}

export interface Grupo {
  /** Texto representativo: o do achado mais completo do grupo. */
  texto: string
  /** Lentes distintas neste grupo, ordenadas por quantidade de achados. */
  lentes: string[]
  /** Quantos ACHADOS (nao lentes) cairam aqui. */
  qtd: number
  /** Todas as variantes, para quem quiser conferir o agrupamento. */
  variantes: string[]
  /** Linha citada, quando alguma lente citou. */
  linha?: string
}

/** Palavras que aparecem em quase todo achado e nao distinguem nada. */
const PARADAS = new Set([
  "de", "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da",
  "dos", "das", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem",
  "que", "se", "nao", "sim", "como", "quando", "onde", "isso", "isto", "este",
  "esta", "esse", "essa", "ao", "aos", "pela", "pelo", "e", "ou", "mas",
  "the", "and", "not", "use", "usar", "deve", "fazer", "esta", "esse", "sua",
  "seu", "ele", "ela", "voce", "aqui", "entao", "porque", "porem", "pode",
  "tem", "foi", "sao", "sera", "mais", "menos", "cada", "todo", "toda",
])

/** Funcao, classe ou metodo citado: o token mais distintivo do achado. */
const RX_SIMBOLO =
  /\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\(|\bclass\s+([A-Za-z_][A-Za-z0-9_]{2,})|\bdef\s+([A-Za-z_][A-Za-z0-9_]{2,})/g

function simbolos(texto: string): Set<string> {
  const out = new Set<string>()
  for (const m of texto.matchAll(RX_SIMBOLO)) {
    const s = (m[1] ?? m[2] ?? m[3] ?? "").toLowerCase()
    if (s.length > 2) out.add(s)
  }
  return out
}

/**
 * Linha citada: SO depois de dois-pontos, ou da palavra "linha"/"line".
 *
 * MEDIDO (2026-10-03): a versao anterior tinha os grupos todos opcionais e
 * casava o "2" de "alvo_e2e" como linha 2. Duas consequencias, as duas ruins:
 *
 *   1. O relatorio dizia "linha citada: 2" para um defeito na linha 29.
 *   2. PIOR: o passo de fusao por simbolo+linha usava essa linha falsa, e por
 *      isso juntou `primeiro()` com `media()` -- dois defeitos de funcoes
 *      diferentes viraram um problema so. Os numeros de corte que eu tinha
 *      reportado foram medidos com este sinal quebrado.
 *
 * Entao: exige dois-pontos, ou a palavra linha/line. Nome de arquivo com
 * numero dentro (`e2e`, `v2`) nao tem dois-pontos antes do digito.
 */
const RX_LINHA =
  /:(\d{1,5})\s*(?:[-–,]\s*(\d{1,5}))?|\b(?:linha|line)\s+(\d{1,5})/i

function linhaCitada(texto: string): string | undefined {
  const m = texto.match(RX_LINHA)
  if (!m) return undefined
  const a = m[1] ?? m[3]
  const b = m[2]
  if (!a) return undefined
  return b ? a + "-" + b : a
}
/** Termos distintivos: fora da lista de paradas. */
function termos(texto: string): Set<string> {
  const limpo = texto
    .toLowerCase()
    .replace(/`[^`]*`/g, " ")
    .replace(/[^a-z0-9_]+/g, " ")
  const out = new Set<string>()
  for (const t of limpo.split(/\s+/)) {
    if (t.length > 3 && !PARADAS.has(t)) out.add(t)
  }
  return out
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (!a.size || !b.size) return 0
  let inter = 0
  for (const x of a) if (b.has(x)) inter++
  return inter / (a.size + b.size - inter)
}

/** Um achado e util? Curto demais nao diz nada; sem texto e nao diz nada. */
function util(texto: string): boolean {
  const t = texto.trim()
  return t.length >= 25
}

/**
 * A lente NAO achou nada — ela disse que nao pode olhar.
 *
 * MEDIDO (2026-10-03): numa rodada real, lentes responderam coisas como
 * "Sem ferramenta de arquivos; conferi apenas a literal fornecida" e
 * "Nao li o arquivo em disco". Isso nao e achado: e a lente relatando que nao
 * tem o que dizer. No consolidado elas viravam problemas de primeira linha,
 * com o mesmo peso de um bug confirmado.
 *
 * E o caso mais perigoso do comite: "Nenhum teste foi fornecido" lido como
 * problema e uma acusacao falsa sobre o codigo.
 *
 * DETALHE QUE CUSTOU UMA RODADA (2026-10-03): o padrao era `nao li` sem
 * acento, e o modelo escreve `nao` COM acento. O filtro nao casava nada e as
 * tres linhas de ruido continuaram no consolidado. Por isso `n` casa com
 * `n` acentuado tambem.
 */
const NAO_ACHADO =
  /(sem ferramenta|nenhum[^.;]{0,32}fornecid|n[ãa]o (?:foi )?fornecid[oa]|n[ãa]o (?:havia|tem|possui|h[áa])[^.;]{0,24}ferramenta|conferi apenas|revis[ãa]o limitada|n[ãa]o pude|n[ãa]o consigo|n[ãa]o li o arquivo|n[ãa]o h[áa] ferramenta|sem acesso ao)/i

function eNaoAchado(texto: string): boolean {
  return NAO_ACHADO.test(texto)
}

/** Quantas linhas uma lente=_NAO_ACHADO_ empurrou para o noise. */
export function descartadosComoNaoAchado(achados: Achado[]): number {
  let n = 0
  for (const a of achados) {
    for (const bruta of String(a.texto ?? "").split("\n")) {
      const t = bruta.replace(/^\s*[-*\u2022\d.)\]]+\s*/, "").trim()
      if (util(t) && eNaoAchado(t)) n++
    }
  }
  return n
}

/**
 * Um achado vira linha. As lentes escrevem em formatos diferentes:
 * bullet, numeracao, ou prosa corrida. Split por linha e o unico metodo
 * que nao depende do formato.
 */
export function emLinhas(achados: Achado[]): Achado[] {
  const saida: Achado[] = []
  for (const a of achados) {
    for (const bruta of String(a.texto ?? "").split("\n")) {
      const t = bruta.replace(/^\s*[-*\u2022\d.)\]]+\s*/, "").trim()
      if (util(t) && !eNaoAchado(t)) saida.push({ lente: a.lente, texto: t })
    }
  }
  return saida
}

/**
 * Agrupa. Criterio, em ordem: simbolo citado em comum (forte) OU linha
 * citada em comum (forte) OU similaridade de termos (fraca). Dois de tres
 * bastam — porque os dois primeiros falham em achados que nao citam linha,
 * e o terceiro sozinho e fraco demais.
 */
/** Uma linha de achado ja digerida: simbolos, termos e linha citados. */
interface Item {
  idx: number
  lente: string
  texto: string
  sim: Set<string>
  termos: Set<string>
  linha?: string
}

/** "22" -> [22]; "27-29" -> [27,28,29]; "21,24" -> [21,24]. */
function faixa(linha?: string): number[] {
  if (!linha) return []
  const nums = linha
    .split(",")
    .flatMap((p) => {
      const m = p.trim().match(/^(\d+)\s*[-–]+\s*(\d+)$/)
      if (m) {
        const a = Number(m[1])
        const b = Number(m[2])
        const out: number[] = []
        // Faixa gigante (ex.: 1-29) e o arquivo inteiro: nao ajuda a
        // localizar nada e faz todo mundo se sobrepor.
        if (b - a > 40) return []
        for (let i = Math.min(a, b); i <= Math.max(a, b); i++) out.push(i)
        return out
      }
      const n = p.trim().match(/^(\d+)$/)
      return n ? [Number(n[1])] : []
    })
    .filter((n) => Number.isFinite(n))
  return [...new Set(nums)]
}

/**
 * POS-PROCESSAMENTO: junta grupos que apontam o MESMO simbolo em linhas
 * SOBREPOSTAS.
 *
 * MEDIDO (2026-10-03): numa rodada real, `media()` com ZeroDivisionError
 * aparecia em 4 grupos separados porque as lentes citaram linhas diferentes
 * — 26, 27-29, 29. O agrupamento por termos nao une, porque o resto da frase
 * varia. Mas sao o MESMO defeito: mesma funcao, linhas que se sobrepoem.
 *
 * Este passo usa sinal OBJETIVO (simbolo citado + interseccao de linhas), nao
 * ajuste de indice de similaridade. E uma regra que se sustenta sem calibrar
 * nada: se duas frases falam da mesma funcao e apontam linhas que se cruzam,
 * sao sobre o mesmo codigo.
 *
 * Entao por que o passo principal nao ja faz isso? Porque ele agrupava
 * por termos ANTES de ver a linha, e o grupo ja formado nao se reavalia.
 * Aqui e uma segunda passada, so sobre grupos ja decididos.
 */
function fundirPorSimboloELinha(grupos: Grupo[], itens: Item[]): Grupo[] {
  const info = grupos.map((g, gi) => {
    const simbolos = new Set<string>()
    const linhas = new Set<number>()
    for (const i of g.membros!) {
      for (const s of itens[i].sim) simbolos.add(s)
      for (const l of faixa(itens[i].linha)) linhas.add(l)
    }
    return { gi, g, simbolos, linhas }
  })

  const pai = info.map((_, i) => i)
  const achar = (i: number): number => (pai[i] === i ? i : (pai[i] = achar(pai[i])))

  for (let a = 0; a < info.length; a++) {
    for (let b = a + 1; b < info.length; b++) {
      // Simbolo em comum E linhas em comum: sem os dois, nao junta.
      const simbolo = [...info[a].simbolos].some((s) => info[b].simbolos.has(s))
      if (!simbolo) continue
      const linha = [...info[a].linhas].some((l) => info[b].linhas.has(l))
      if (!linha) continue
      const ra = achar(a)
      const rb = achar(b)
      if (ra !== rb) pai[ra] = rb
    }
  }

  const porRaiz = new Map<number, Grupo>()
  for (const info2 of info) {
    const r = achar(info2.gi)
    const alvo = porRaiz.get(r)
    if (!alvo) {
      porRaiz.set(r, { ...info2.g, membros: [...info2.g.membros!] })
    } else {
      alvo.membros!.push(...info2.g.membros!)
      alvo.qtd += info2.g.qtd
      alvo.variantes.push(...info2.g.variantes)
      for (const s of info2.simbolos) {
        if (!alvo.simbolos) alvo.simbolos = new Set()
        ;(alvo as any).simbolos.add(s)
      }
    }
  }

  const saida = [...porRaiz.values()]
  for (const g of saida) {
    const c = new Map<string, number>()
    for (const i of g.membros!) c.set(itens[i].lente, (c.get(itens[i].lente) ?? 0) + 1)
    g.lentes = [...c.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => l)
    const peso = (i: number) => itens[i].sim.size * 10 + Math.min(itens[i].texto.length, 400) / 100
    const melhor = g.membros!.reduce((x, y) => (peso(y) > peso(x) ? y : x))
    g.texto = itens[melhor].texto
    if (!g.linha) g.linha = itens[melhor].linha
  }
  return saida
}

export function agrupar(achados: Achado[]): Grupo[] {
  const linhas = emLinhas(achados)

  const itens: Item[] = []
  for (let i = 0; i < linhas.length; i++) {
    const l = linhas[i]
    itens.push({
      idx: i,
      lente: l.lente,
      texto: l.texto,
      sim: simbolos(l.texto),
      termos: termos(l.texto),
      linha: linhaCitada(l.texto),
    })
  }

  const grupos: Grupo[] = []

  /**
   * COMPARA COM O CENTROIDE, E NAO COM CADA MEMBRO.
   *
   * MEDIDO (2026-10-03): a primeira versao comparava o candidato com TODOS os
   * membros ja agrupados. Isso encadeia — A casa com B, B casa com C, e C
   * entra mesmo sem ser parecido com A. Num arquivo real, 49 linhas viraram
   * 4 grupos e o maior dizia "12 de 12 lentes de acordo", sendo que as 12
   * lenses NUNCA concordaram entre si. Isso e pior do que nao agrupar: e
   * fabricating confianca, que era exatamente o que esta coluna promete nao
   * fazer.
   *
   * Comparar so com o representante tira o encadeamento: se C se parece com B
   * mas nao com o centroide do grupo, C nao entra. O grupo pode perder um
   * achado legitimo que se parecia so com um membro lateral — e isso e
   * aceitavel, porque C vira um grupo proprio e continua visivel.
   */
  for (const item of itens) {
    let alvo: GrupoInterno | null = null
    let melhorScore = -1

    for (const g of grupos) {
      const idxs = g.membros

      const centro = new Set<string>()
      for (const i of idxs) for (const t of itens[i].termos) centro.add(t)

      const sem = jaccard(item.termos, centro)
      // Similaridade de termo e NECESSARIA, mesmo quando simbolo ou linha
      // batem: so o vocabulario do defeito separa "arquivo nao fecha" de
      // "falta encoding".
      if (sem < 0.18) continue

      const simEmComum = idxs.some((i) => [...item.sim].some((s) => itens[i].sim.has(s)))
      const linhaEmComum = idxs.some((i) => !!item.linha && itens[i].linha === item.linha)
      if (!(simEmComum || linhaEmComum || sem >= 0.42)) continue

      const score = sem + (simEmComum ? 0.3 : 0) + (linhaEmComum ? 0.2 : 0)
      if (score > melhorScore) {
        melhorScore = score
        alvo = g
      }
    }

    if (alvo) {
      alvo.membros.push(item.idx)
      alvo.qtd += 1
      alvo.variantes.push(item.texto)
      if (item.linha && !alvo.linhas.includes(item.linha)) {
        alvo.linhas.push(item.linha)
        alvo.linhas.sort()
        alvo.linha = alvo.linhas[0]
      }
    } else {
      grupos.push({
        texto: item.texto,
        lentes: [item.lente],
        qtd: 1,
        variantes: [item.texto],
        membros: [item.idx],
        linhas: item.linha ? [item.linha] : [],
        linha: item.linha,
      })
    }
  }

  // Contagem de lentes por grupo: DISTINTAS. Uma lente que repete o mesmo
  // defeito em tres linhas continua valendo UMA lente de concordancia — que
  // e a leitura correta de "concordancia". Antes eu vetava a segunda linha da
  // mesma lente e ela virava um grupo duplicado (achado repetido, separado),
  // o que e o oposto do que o dedup existe para fazer. A confianca ja e
  // immune a isso porque conta lentes, nao linhas.
  for (const g of grupos) {
    const c = new Map<string, number>()
    for (const i of g.membros!) c.set(itens[i].lente, (c.get(itens[i].lente) ?? 0) + 1)
    g.lentes = [...c.entries()].sort((a, b) => b[1] - a[1]).map(([l]) => l)
    const peso = (i: number) => itens[i].sim.size * 10 + Math.min(itens[i].texto.length, 400) / 100
    const melhor = g.membros!.reduce((a, b) => (peso(b) > peso(a) ? b : a))
    g.texto = itens[melhor].texto
  }

  return fundirPorSimboloELinha(grupos, itens)
    .sort((a, b) => b.lentes.length - a.lentes.length || b.texto.length - a.texto.length)
    .map(({ membros: _m, linhas: _l, ...pub }) => pub)
}
/** O texto que entra no relatorio. */
export function relatar(grupos: Grupo[], totalLinhas: number, totalLentes: number): string {
  const L: string[] = []
  const compactacao = totalLinhas ? ((grupos.length / totalLinhas) * 100).toFixed(0) : "0"

  L.push(`== ACHADOS CONSOLIDADOS ==`)
  L.push(
    `${totalLentes} lentes escreveram ${totalLinhas} linhas, que sao ` +
      `${grupos.length} problema(s) distinto(s). ` +
      `Voce le ${grupos.length} em vez de ${totalLinhas}.`,
  )
  L.push("")
  L.push("A ORDEM E POR CONCORRENCIA: quantas lentes independentes citaram o mesmo codigo.")
  L.push("Isso e a unica medida de confianca que temos, e ela e real — nao e eu")
  L.push("estimando. Concordancia entre lentes DIFERENTES (que nao se veem) e")
  L.push("evidencia. Concordancia de uma unica lente nao prova nada.")
  L.push("")
  L.push(
    "LEIA O NUMERO COM CUIDADO: ele conta lentes que citaram ALGO DESTE grupo,",
  )
  L.push(
    "nao lentes que concordaram palavra por palavra. Se um grupo juntou dois",
  )
  L.push(
    "defeitos do mesmo trecho, 12 lentes podem ter encontrado um dos dois. As",
  )
  L.push("versoes ficam listadas, entao da para conferir o que cada uma viu.")
  L.push("")
  L.push(
    "Severidade NAO aparece aqui de proposito: eu teria que inventar uma nota " +
      "que ninguem mediu. As categorias estao como rotulo, nao como pontuacao.",
  )
  L.push("")

  grupos.forEach((g, i) => {
    const n = g.lentes.length
    const forca =
      n >= 5 ? "ALTA" : n >= 3 ? "MEDIA" : n === 2 ? "BAIXA" : "UNICA"
    L.push(`${i + 1}. [${forca} — ${n} de ${totalLentes} lentes citaram] ${g.texto}`)
    L.push(`   lentes: ${g.lentes.join(", ")}`)
    if (g.linha) L.push(`   linha citada: ${g.linha}`)
    if (g.variantes.length > 1) {
      L.push(`   (${g.variantes.length} versoes do mesmo achado — agrupadas porque ` +
        `${n} lentes apontaram o mesmo lugar)`)
    }
    L.push("")
  })

  L.push("---")
  L.push(`Leitura antes: ${totalLinhas} linhas. Agora: ${grupos.length} problemas (${compactacao}% do volume).`)
  return L.join("\n")
}