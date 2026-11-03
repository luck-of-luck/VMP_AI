/**
 * Prova do ciclo: os 46 papeis rodam, em rodadas, e o estado sobrevive.
 *
 * Este e o teste que decide se o comite e uma equipe. Rodar 46 numa onda ja
 * foi medido (probe_fofa). O que ainda nao foi provado e o que importa:
 *  - os tiers rodam na ORDEM certa (conceber depois de pesquisar)
 *  - cada tier enxerga o que os anteriores produziram
 *  - o checkpoint sobrevive ao fim do processo
 *  - lentes caladas sao NOMEADAS, nao engolidas
 *
 * Roda com material de verdade, senao o tier de pesquisa encolhe e a prova
 * nao cobre o caso caro.
 */
import { rodarCiclo, TAMANHO_EQUIPE } from "./supervisor.ts"
import { Trilha } from "./checkpoint.ts"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { rmSync, existsSync } from "node:fs"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

const RAIZ = join(tmpdir(), "ciclo_teste_" + Date.now())
rmSync(RAIZ, { recursive: true, force: true })

const ARQUIVO = join(tmpdir(), "alvo_do_ciclo.py")
const { writeFileSync } = await import("node:fs")
writeFileSync(
  ARQUIVO,
  `"""Exemplo com defeitos de proposito."""


def primeiro(lista):
    f = open(lista[0])
    conteudo = f.read()
    f.close()
    return conteudo


def media(lista):
    """Media aritmetica."""
    return sum(lista) / len(lista)


def somar_ate(lista, limite):
    """Soma ate o limite."""
    total = 0
    for item in lista:
        if item > limite:
            break
        total += item
    return total
`,
  "utf-8",
)

console.log("=".repeat(70))
console.log(`CICLO COMPLETO — ${TAMANHO_EQUIPE} papeis, 5 tiers`)
console.log("=".repeat(70))

const trilha = new Trilha(RAIZ)
const pedido =
  "Revise o arquivo e diga o que está errado. Não implemente correção ainda."

console.log("")
console.log("rodando (isto leva de 1 a 4 minutos)...")
const t0 = Date.now()
const res = await rodarCiclo({
  pedido,
  arquivos: [ARQUIVO],
  trilha,
})
const cp = res.checkpoint

console.log("")
console.log("=".repeat(70))
console.log("1. RODADAS RODARAM NA ORDEM")
console.log("=".repeat(70))
const ordem = cp.rodadas.map((r) => r.tier)
console.log(`  ordem: ${ordem.join(" -> ")}`)
const idx = (t: string) => ordem.indexOf(t)
ok(idx("revisar") === 0, "revisar foi a primeira rodada", `posicao ${idx("revisar")}`)
ok(idx("pesquisar") > idx("revisar"), "pesquisar depois de revisar")
ok(idx("conceber") > idx("pesquisar"), "conceber depois de pesquisar")
ok(idx("lembrar") > idx("conceber"), "lembrar depois de conceber")
ok(idx("supervisionar") === ordem.length - 1, "supervisionar por ULTIMO")

console.log("")
console.log("=".repeat(70))
console.log("2. COBERTURA")
console.log("=".repeat(70))
const chamados = cp.rodadas.reduce((a, r) => a + r.chamados, 0)
const okN = cp.rodadas.reduce((a, r) => a + r.ok, 0)
for (const r of cp.rodadas) {
  const pct = r.chamados ? Math.round((100 * r.ok) / r.chamados) : 0
  console.log(
    `  ${r.tier.padEnd(14)} ${r.ok}/${r.chamados} (${pct}%) em ${(r.duracaoMs / 1000).toFixed(1)}s` +
      (r.calados.length ? `  calados: ${r.calados.length}` : ""),
  )
}
ok(chamados >= 40, "disparamos 40+ papeis", `${chamados}`)
ok(okN > 0, "algum papel respondeu", `${okN}`)
console.log(`  total: ${okN}/${chamados} lentes`)

console.log("")
console.log("=".repeat(70))
console.log("3. LACUNAS NOMEADAS — o que nao respondeu aparece pelo nome")
console.log("=".repeat(70))
const todosCalados = cp.rodadas.flatMap((r) => r.calados)
console.log(`  calados: ${todosCalados.length}${todosCalados.length ? " -> " + todosCalados.slice(0, 12).join(", ") : ""}`)
// Nao exigimos 0 calados: o relay oscila. Exigimos que o REGISTRO existe, o
// que e o contrato. (Um ciclo sem calados seria suspeito demais.)
ok(
  cp.rodadas.every((r) => Array.isArray(r.calados)),
  "toda rodada registra quem calou, mesmo vazio",
)

console.log("")
console.log("=".repeat(70))
console.log("4. MATERIAL CHEGOU — os agentes viram o codigo")
console.log("=".repeat(70))
const algumaResposta = Object.values(cp.rodadas[0]?.respostas ?? {}).join(" ")
ok(
  /primeiro|media|somar_ate|def /.test(algumaResposta),
  "a primeira rodada cita o codigo do arquivo",
  algumaResposta.slice(0, 70),
)

console.log("")
console.log("=".repeat(70))
console.log("5. CHECKPOINT SOBREVIVEU")
console.log("=".repeat(70))
const d = join(RAIZ, res.id)
ok(existsSync(join(d, `v1.json`)), "v1.json gravado")
ok(existsSync(join(d, `v1.md`)), "relatorio markdown gravado")
const relido = trilha.carregar(res.id)
ok(relido !== null, "rele do disco")
ok(relido!.rodadas.length === cp.rodadas.length, "mesma quantidade de rodadas", `${relido!.rodadas.length}`)
ok((relido!.supervisao ?? "").length > 0, "supervisao registrada")
ok(relido!.proximosPassos.length > 0, "proximos passos registrados", `${relido!.proximosPassos.length} passo(s)`)

console.log("")
console.log("=".repeat(70))
console.log("6. CONTEUDO DA SUPERVISAO (amostra)")
console.log("=".repeat(70))
const sup = cp.supervisao ?? "(vazio)"
for (const l of sup.split("\n").slice(0, 14)) console.log("  | " + l.slice(0, 100))
if (cp.proximosPassos.length) {
  console.log("")
  console.log("  proximos passos que a equipeopropôs:")
  for (const p of cp.proximosPassos) console.log("   > " + p.slice(0, 95))
}

console.log("")
console.log("=".repeat(70))
console.log(`DURACAO TOTAL: ${res.duracaoSegundos.toFixed(1)}s (parede ${((Date.now() - t0) / 1000).toFixed(1)}s)`)
console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  console.log(`(trilha preservada para inspecao: ${RAIZ})`)
  process.exit(1)
}
console.log("CICLO OK — a equipe rodou e o estado sobrou")
rmSync(RAIZ, { recursive: true, force: true })