/**
 * MEDICAO DEPOIS: o dedup entrega mais sinal do que as linhas brutas?
 *
 * Roda sobre uma trilha REAL ja gravada — nao sobre casos de teste. E a
 * pergunta que o arquivo `dedup.ts` existe para responder: as 46 lentes
 * produzem 49 linhas que dizem 8 coisas, ou produzem 49 coisas?
 *
 * Metodo: le a rodada de revisao, conta as linhas brutas, roda o dedup, e
 * compara. Nao usa o mapa de categorias do `probe_sinal.ts` — este usa o
 * proprio agrupamento, entao sao duas medicoes independentes chegando ao
 * mesmo lugar. Concordancia entre dois metodos diferentes vale mais do que
 * qualquer um deles sozinho.
 */
import { readdirSync, readFileSync, existsSync } from "node:fs"
import { join } from "node:path"
import { agrupar, emLinhas } from "./dedup.ts"

const BASE =
  process.env.CLUSTER_TRILHA ??
  (existsSync(".cluster/trilhas")
    ? ".cluster/trilhas"
    : "./.cluster/trilhas")

if (!existsSync(BASE)) {
  console.log(`Sem trilhas em ${BASE}. Rode um ciclo primeiro.`)
  process.exit(0)
}

const trilhas = readdirSync(BASE, { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => e.name)
  .sort()
  .reverse()
  .slice(0, 4)

console.log(`TRILHA".padEnd(36) + "LINHAS".padEnd(9) + "PROBLEMAS".padEnd(12) + "CORTES`)
console.log("-".repeat(72))

let totL = 0
let totG = 0
let totLentes = 0
const TABELA: { linha: string; g: number; l: number; corte: number; n: number }[] = []

for (const t of trilhas) {
  const dir = join(BASE, t)
  const v = readdirSync(dir).filter((f) => /^v\d+\.json$/.test(f)).sort().pop()
  if (!v) continue
  const cp = JSON.parse(readFileSync(join(dir, v), "utf-8"))
  const rev = cp.rodadas.find((r) => r.tier === "revisar")
  if (!rev) continue

  const achados = Object.entries(rev.respostas).map(([lente, texto]) => ({ lente, texto }))
  const linhas = emLinhas(achados).length
  const grupos = agrupar(achados)
  const corte = linhas ? Math.round((1 - grupos.length / linhas) * 100) : 0
  TABELA.push({ linha: t.slice(0, 34), g: grupos.length, l: linhas, corte, n: achados.length })
  totL += linhas
  totG += grupos.length
  totLentes += achados.length
  console.log(
    "  " + TABELA[TABELA.length - 1].linha.padEnd(34) +
    String(linhas).padEnd(9) +
    String(grupos.length).padEnd(12) +
    `${corte}%`,
  )
}

console.log("-".repeat(72))
if (!totL) {
  console.log("nenhuma linha para medir")
  process.exit(0)
}

console.log(
  `  ${totLentes} lentes -> ${totL} linhas -> ${totG} problemas ` +
    `(${Math.round((1 - totG / totL) * 100)}% de corte)`,
)
console.log("")
console.log("O QUE ISSO SIGNIFICA")
console.log(`  Antes: voce lia ${totL} linhas.`)
console.log(`  Agora: voce le ${totG} problemas, ordenados por quantas lentes viram cada um.`)
console.log("")

// A confianca: quantos problemas tem mais de uma lente?
const maiorTabela = TABELA[TABELA.length - 1]
const dir = join(BASE, maiorTabela.linha)
console.log("CONFIANCA por problema (ultima trilha):")
for (const t of trilhas.slice(0, 1)) {
  const d2 = join(BASE, t)
  const v = readdirSync(d2).filter((f) => /^v\d+\.json$/.test(f)).sort().pop()
  if (!v) continue
  const cp2 = JSON.parse(readFileSync(join(d2, v), "utf-8"))
  const rev2 = cp2.rodadas.find((r) => r.tier === "revisar")
  if (!rev2) continue
  const gs = agrupar(Object.entries(rev2.respostas).map(([lente, texto]) => ({ lente, texto })))
  for (const g of gs) {
    const f = g.lentes.length >= 5 ? "ALTA " : g.lentes.length >= 3 ? "MEDIA" : g.lentes.length === 2 ? "BAIXA" : "UNICA"
    console.log(`  [${f}] ${g.lentes.length} lentes :: ${g.texto.slice(0, 74)}`)
  }
  const semConcordancia = gs.filter((g) => g.lentes.length === 1).length
  console.log("")
  console.log(
    `  ${semConcordancia}/${gs.length} problema(s) vistos por UMA lente so.`,
  )
  if (semConcordancia > gs.length / 2) {
    console.log(
      "  Mais da metade e palpite de lente unica — trate esses como hipotese,",
    )
    console.log("  nao como achado confirmado. E o que a coluna de concordancia compra:")
    console.log("  nao e que o comite acerta, e que voce sabe ONDE DUVIDAR.")
  }
}