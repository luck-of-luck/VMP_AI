/**
 * AUTO-DESPACHO: o veredicto do comite vira tarefa na fila.
 *
 * POR QUE ISTO PRECISA DE PERMISSAO EXPLICITA
 * Despachar sozinho significa rodar trabalho de verdade (o executor escreve
 * arquivo) sem ninguem pedir. Dois motifs Known: um comite de 46 lentes
 * produz findings de qualidade variavel, e transformar achado em tarefa sem
 * filtro joga trabalho ruim na fila. Entao o padrao e `modo: "sugerir"` —
 * a Camada 1 NOMEIA as tarefas e o humano decide. So vira automatico com
 * `modo: "automatico"`, e mesmo assim com trava de custo.
 *
 * O FILTRO: nem todo achado vira tarefa
 * Um achado sem caminho verificavel nao e tarefa, e texto. Tarefa que o
 * executor nao consegue verificar devolve para a fila e trava o ciclo. Entao
 * o criterio e concreto: tem arquivo, tem verbo de mudanca, e cabe em um
 * numero limitado de tarefas.
 */

import { Board } from "./board.ts"
import type { Checkpoint } from "./checkpoint.ts"

/** Verbo de acao: sem isso e observacao, nao trabalho. */
const VERBOS = /\b(corrig|criar|remover|renomear|extrair|substituir|adicionar|implementar|fixar|trocar|unificar|extrair)\w*\b/i

export interface AchadoBruto {
  lente: string
  texto: string
}

export interface OpcoesDespacho {
  /** `sugerir` (padrao) devolve a lista sem criar. `automatico` cria de verdade. */
  modo?: "sugerir" | "automatico"
  maxTarefas?: number
  /** So considerar achados destas lentes. Vazio = todas. */
  lentes?: string[]
}

export interface ResultadoDespacho {
  criadas: { id: string; titulo: string; origem: string }[]
  descartadas: { lente: string; texto: string; motivo: string }[]
  dentroDoOrcamento: boolean
  motivoLimite?: string
}

/**
 * Extrai tarefas dos achados de uma rodada de revisao.
 *
 * Heuristicas, e sao heuristicas — por isso cada descarte devolve o motivo.
 * Um filtro opaco que joga coisa fora sem explicar obriga quem opera a
 * confiar cegamente no filtro, que e o oposto de ter filtro.
 */
function extrair(achados: AchadoBruto[], arquivos: string[]): {
  candidatos: { lente: string; titulo: string; pedido: string }[]
  descartados: { lente: string; texto: string; motivo: string }[]
} {
  const candidatos: { lente: string; titulo: string; pedido: string }[] = []
  const descartados: { lente: string; texto: string; motivo: string }[] = []

  for (const a of achados) {
    const t = a.texto.trim()
    if (t.length < 40) {
      descartados.push({ lente: a.lente, texto: t, motivo: "curto demais para virar tarefa" })
      continue
    }
    const temCaminho = arquivos.length > 0 || /:\d+|L\d+|\.py|\.ts|\.js/.test(t)
    const temVerbo = VERBOS.test(t)
    if (!temVerbo) {
      descartados.push({ lente: a.lente, texto: t, motivo: "observacao, sem verbo de mudanca" })
      continue
    }
    if (!temCaminho) {
      descartados.push({ lente: a.lente, texto: t, motivo: "sem caminho verificavel" })
      continue
    }
    // First line vira titulo; o resto vira pedido.
    const linhas = t.split("\n").map((l) => l.replace(/^[\s\-*•\d.)\]]+/, "").trim()).filter(Boolean)
    if (!linhas.length) {
      descartados.push({ lente: a.lente, texto: t, motivo: "sem conteudo util" })
      continue
    }
    candidatos.push({
      lente: a.lente,
      titulo: linhas[0].slice(0, 110),
      pedido: t.slice(0, 1200),
    })
  }
  return { candidatos, descartados }
}

export function despachar(
  cp: Checkpoint,
  board: Board,
  op: OpcoesDespacho = {},
): ResultadoDespacho {
  const modo = op.modo ?? "sugerir"
  const max = op.maxTarefas ?? 3
  const permitidas = op.lentes?.length ? new Set(op.lentes) : null

  // So a rodada de REVISAO vira tarefa. Conceber produz plano, nao codigo;
  // transformá-lo em tarefa gera trabalho sem criterio.
  const revisao = cp.rodadas.find((r) => r.tier === "revisar")
  if (!revisao) {
    return {
      criadas: [],
      descartadas: [],
      dentroDoOrcamento: false,
      motivoLimite: "o ciclo nao rodou o tier de revisao",
    }
  }

  const achados = Object.entries(revisao.respostas)
    .filter(([lente]) => !permitidas || permitidas.has(lente))
    .map(([lente, texto]) => ({ lente, texto }))

  const { candidatos, descartados } = extrair(achados, cp.arquivos)

  // A trava de custo vale aqui tambem, antes de criar qualquer coisa.
  const g = board.guarda()
  if (!g.pode) {
    return {
      criadas: [],
      descartadas: descartados,
      dentroDoOrcamento: false,
      motivoLimite: g.motivo,
    }
  }

  const criadas: ResultadoDespacho["criadas"] = []
  for (const c of candidatos.slice(0, max)) {
    if (modo === "sugerir") {
      criadas.push({ id: "(nao criada)", titulo: c.titulo, origem: `lente:${c.lente}` })
      continue
    }
    const t = board.criarTarefa({
      titulo: c.titulo,
      pedido: c.pedido,
      origem: `lente:${c.lente}`,
      arquivos: cp.arquivos,
    })
    // O achado original vira artefato ligado: quem for corrigir le o
    // raciocinio de quem achou, nao so a ordem.
    board.publicar({
      tipo: "achado",
      autor: c.lente,
      titulo: c.titulo,
      conteudo: c.pedido,
      tarefa: t.id,
    })
    criadas.push({ id: t.id, titulo: c.titulo, origem: `lente:${c.lente}` })
  }

  const excedeu = candidatos.length > max
  return {
    criadas,
    descartadas: descartados,
    dentroDoOrcamento: true,
    motivoLimite: excedeu
      ? `${candidatos.length} candidato(s), criei no maximo ${max}`
      : undefined,
  }
}

/** Texto para o modelo entender o que o despacho fez (ou faria). */
export function relatar(r: ResultadoDespacho, modo: string): string {
  const L: string[] = []
  L.push(
    modo === "automatico"
      ? `DESPACHO AUTOMATICO: ${r.criadas.length} tarefa(s) criada(s).`
      : `SUGESTAO DE DESPACHO (nada foi criado; modo=${modo}):`,
  )
  L.push("")
  if (r.criadas.length) {
    for (const c of r.criadas) L.push(`  ${c.id === "(nao criada)" ? "-" : c.id}  [${c.origem}] ${c.titulo}`)
  } else {
    L.push("  (nenhuma tarefa sugerida)")
  }
  if (r.motivoLimite) {
    L.push("")
    L.push(`LIMITE: ${r.motivoLimite}`)
  }
  if (r.descartadas.length) {
    L.push("")
    L.push(`DESCARTADOS (${r.descartadas.length}) — cada um com motivo, para nao sumir sem explicacao:`)
    const porMotivo: Record<string, number> = {}
    for (const d of r.descartadas) porMotivo[d.motivo] = (porMotivo[d.motivo] ?? 0) + 1
    for (const [m, n] of Object.entries(porMotivo)) L.push(`  ${n}x ${m}`)
  }
  return L.join("\n")
}