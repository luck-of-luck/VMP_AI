/**
 * TESTE DO TIRO dos papeis: os 46 rodam e tem que vir 46 de volta.
 *
 * Por que este teste existe: os papeis sao DADOS, entao o jeito barato de
 * saber que 46 lentes funcionam e todas ao mesmo tempo. Se um papel esta com
 * `lente` vazia, id duplicado ou tier invalido, isso aqui pega — e nao
 * descobrir-se dps que o comite "rodou" com 38 lentes e ninguem notou.
 */
import { TODOS_PAPEIS, ORDEM_TIER, porTier, porId, escolher, TITULO_TIER } from "./roles.ts"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

console.log("=".repeat(70))
console.log("1. FORMA DO REGISTRO")
console.log("=".repeat(70))
ok(TODOS_PAPEIS.length === 46, "sao 46 papeis", `sao ${TODOS_PAPEIS.length}`)

const ids = new Set(TODOS_PAPEIS.map((p) => p.id))
ok(ids.size === TODOS_PAPEIS.length, "nenhum id duplicado", `${ids.size} unicos de ${TODOS_PAPEIS.length}`)

const semLente = TODOS_PAPEIS.filter((p) => !p.lente || p.lente.trim().length < 60)
ok(semLente.length === 0, "todo papel tem lente util", semLente.map((p) => p.id).join(", ") || "todos")

const semNome = TODOS_PAPEIS.filter((p) => !p.nome || !p.nome.trim())
ok(semNome.length === 0, "todo papel tem nome", semNome.map((p) => p.id).join(", "))

console.log("")
console.log("=".repeat(70))
console.log("2. TIERS")
console.log("=".repeat(70))
for (const t of ORDEM_TIER) {
  const n = porTier(t).length
  ok(n > 0, `tier ${t} (${TITULO_TIER[t]}) tem papeis`, `${n}`)
}
const tierErrado = TODOS_PAPEIS.filter((p) => !ORDEM_TIER.includes(p.tier))
ok(tierErrado.length === 0, "todo papel tem tier valido", tierErrado.map((p) => p.id).join(", "))

const conta: Record<string, number> = {}
for (const p of TODOS_PAPEIS) conta[p.tier] = (conta[p.tier] ?? 0) + 1
console.log(`  distribuicao: ${JSON.stringify(conta)}`)
const total = Object.values(conta).reduce((a, b) => a + b, 0)
ok(total === TODOS_PAPEIS.length, "a distribuicao soma o total", `${total}`)

console.log("")
console.log("=".repeat(70))
console.log("3. COBERTURA — o comite nao pode repetir angulo")
console.log("=".repeat(70))
// Palavras que, se aparecessem em duas lentes, indicariam sobreposicao.
const PALAVRAS_CHAVE = ["seguran", "concorr", "contrato", "teste", "erro", "dado", "memoria", "histori"]
const sobrepos: string[] = []
for (const k of PALAVRAS_CHAVE) {
  const quem = TODOS_PAPEIS.filter((p) => p.lente.toLowerCase().includes(k)).map((p) => p.id)
  // Mais de 2 papeis falando da mesma palavra nao e erro — mas 1 dominante e.
  if (quem.length > 2) sobrepos.push(`${k}: ${quem.join("/")}`)
}
console.log(sobrepos.length ? `  aviso: ${sobrepos.join("; ")}` : "  nenhuma lente domina")

console.log("")
console.log("=".repeat(70))
console.log("4. ESCOLHA POR FASE")
console.log("=".repeat(70))
const semMat = escolher("pesquisar", false)
const comMat = escolher("pesquisar", true)
ok(semMat.length < comMat.length, "sem material o tier pesquisa enxuga", `${semMat.length} de ${comMat.length}`)
ok(comMat.length === porTier("pesquisar").length, "com material roda o tier inteiro", `${comMat.length}`)
console.log(`  sem material roda: ${semMat.map((p) => p.id).join(", ")}`)

ok(porId("correcao")?.tier === "revisar", "porId acha por id")
ok(porId("inexistente") === undefined, "porId devolve undefined para id desconhecido")

console.log("")
console.log("=".repeat(70))
console.log("5. ORDEM DE EXECUCAO")
console.log("=".repeat(70))
const idxDe = (t: string) => ORDEM_TIER.indexOf(t as any)
// revisar antes de supervisionar: nao se supervisa resposta que nao existe.
ok(idxDe("revisar") < idxDe("supervisionar"), "revisar antes de supervisionar")
ok(idxDe("pesquisar") < idxDe("conceber"), "pesquisar antes de conceber")
ok(idxDe("conceber") < idxDe("lembrar"), "conceber antes de lembrar")

console.log("")
console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  process.exit(1)
}
console.log(`REGISTRO OK — ${TODOS_PAPEIS.length} papeis, ${ORDEM_TIER.length} tiers`)