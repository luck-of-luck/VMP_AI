/**
 * Prova do PERFIL RÁPIDO — o caminho do uso diario.
 *
 * O ciclo completo mediu 1143s (19 min). Isso nao serve para o dia a dia, e
 * nao adianta culpar o relay: cada tier e uma onda sequencial de minutos, e
 * rodar 3 tiers e 3 ondas. A alavanca e CORTE DE TIERS, nao orcamento.
 *
 * Este teste prova que o perfil `rapido` entrega revisao com triagem em
 * tempo de cafe — e que ele NAO finge ter feito o ciclo completo.
 */
import { rodarCiclo, PERFIS_CICLO, ORCAMENTO_PADRAO, TAMANHO_EQUIPE } from "./supervisor.ts"
import { Trilha } from "./checkpoint.ts"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { rmSync, writeFileSync } from "node:fs"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

const RAIZ = join(tmpdir(), "perfil_teste_" + Date.now())
rmSync(RAIZ, { recursive: true, force: true })
const ARQUIVO = join(tmpdir(), "alvo_perfil.py")
writeFileSync(
  ARQUIVO,
  `def primeiro(lista):
    f = open(lista[0])
    conteudo = f.read()
    f.close()
    return conteudo


def media(lista):
    return sum(lista) / len(lista)
`,
  "utf-8",
)

console.log("=".repeat(70))
console.log("1. OS PERFIS DECLARADOS")
console.log("=".repeat(70))
for (const [nome, p] of Object.entries(PERFIS_CICLO)) {
  const eq = p.tiers.reduce((a, t) => a + (t === "revisar" ? 14 : t === "pesquisar" ? 10 : t === "conceber" ? 8 : t === "lembrar" ? 6 : 8), 0)
  console.log(`  ${nome.padEnd(9)} ${String(p.tiers.length)} tier(s), ~${eq} lentes, orc ${p.orcamento}`)
  ok(p.tiers.length > 0 && p.orcamento > 0, `perfil ${nome} esta coerente`)
  ok(p.tiers[0] === "revisar", `perfil ${nome} comeca por revisar`, p.tiers[0])
  if (p.tiers.includes("supervisionar")) {
    ok(
      p.tiers[p.tiers.length - 1] === "supervisionar",
      `perfil ${nome} termina em supervisionar`,
    )
  }
}
ok(PERFIS_CICLO.rapido.tiers.length === 1, "rapido e um tier so")
ok(PERFIS_CICLO.completo.tiers.length === 5, "completo e os 5 tiers")
ok(ORCAMENTO_PADRAO < 3000, "orcamento padrao abaixo do historico", `${ORCAMENTO_PADRAO} < 3000`)
ok(ORCAMENTO_PADRAO > 800, "orcamento padrao acima do piso medido", `${ORCAMENTO_PADRAO} > 800`)

console.log("")
console.log("=".repeat(70))
console.log("2. PERFIL RAPIDO DE VERDADE (com rede)")
console.log("=".repeat(70))
const trilha = new Trilha(RAIZ)
console.log("  rodando perfil=rapido ...")
const res = await rodarCiclo({
  pedido: "Revise e diga o que está errado. Não implemente.",
  arquivos: [ARQUIVO],
  perfil: "rapido",
  trilha,
})
const cp = res.checkpoint
const tiersRodados = cp.rodadas.map((r) => r.tier)

ok(res.perfilUsado === "rapido", "perfil registrado no resultado", res.perfilUsado)
ok(tiersRodados.length === 1, "rodou UM tier", tiersRodados.join(","))
ok(tiersRodados[0] === "revisar", "e o tier revisar")
ok(res.duracaoSegundos < 180, "cabem em um cafe", `${res.duracaoSegundos.toFixed(1)}s (limite 180s)`)
console.log(`  duracao real: ${res.duracaoSegundos.toFixed(1)}s`)

const r = cp.rodadas[0]
ok(r.chamados === 14, "14 lentes de revisao disparadas", `${r.chamados}`)
ok(r.ok >= 10, "pelo menos 10 responderam", `${r.ok}/14`)

console.log("")
console.log("  --- o que o perfil rapido achou ---")
const achados = Object.entries(r.respostas).slice(0, 3)
for (const [id, txt] of achados) {
  console.log(`  [${id}] ${txt.replace(/\s+/g, " ").slice(0, 110)}`)
}

console.log("")
console.log("  --- o que ele NAO fez, e precisa dizer ---")
// O ponto perigoso do perfil curto: ele NAO rodou supervisao. Se a entrega
// nao disser isso, o usuario le 14 respostas e acha que tem triagem.
const relatorio = (await import("./checkpoint.ts")).Trilha.prototype.relatorio.call(trilha, cp)
ok(
  !relatorio.includes("## Supervisao"),
  "relatorio do perfil rapido NAO finge que houve supervisao",
)
ok(cp.proximosPassos.length === 0, "perfil rapido nao inventa proximos passos sem supervisao", `${cp.proximosPassos.length}`)
console.log("  (0 proximos passos e o comportamento CORRETO: sem tier de supervisao,")
console.log("   nao ha quem proponha o proximo passo. Inventar seria mentira.)")

console.log("")
console.log("=".repeat(70))
console.log("3. PERFIL INVALIDO FALHA VISIVEL")
console.log("=".repeat(70))
const ruim = await rodarCiclo({
  pedido: "teste de perfil invalido",
  perfil: "nao_existe" as any,
  trilha,
})
ok(
  ruim.checkpoint.bloqueios.some((b) => b.includes("nao_existe")),
  "perfil inexistente vira bloqueio registrado, nao erro silencioso",
)

console.log("")
console.log("=".repeat(70))
console.log(`EQUIPE: ${TAMANHO_EQUIPE} papeis | padrao: ${ORCAMENTO_PADRAO} tokens`)
console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  process.exit(1)
}
console.log("PERFIS OK")
rmSync(RAIZ, { recursive: true, force: true })