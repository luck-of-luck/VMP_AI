/**
 * Onde vai o tempo? Mede o trade-off orcamento x tempo x cobertura.
 *
 * POR QUE MEDIR: o primeiro ciclo completo levou 1143s (19 min). Para quem
 * "so mexe com sistema gigante" isso pode ate servir, mas para persistencia
 * rapida nao serve. E nao faz sentido chutar que reducing the token budget
 * resolves: o SPEC 3.4 ja mostrou que orcamento pequeno demais faz o modelo
 * gastar tudo em reasoning e devolver VAZIO. Entao existe um joelho — e a
 * posicao dele e um numero, nao uma opiniao.
 *
 * Mede 4 orcamentos no tier mais barato (revisar, 14 papeis) e reporta
 * tempo, cobertura e quantos voltaram VAZIOS (o sinal do joelho).
 */
import { consultarTodos } from "./engine.ts"
import { REVISAR } from "./roles.ts"

const ARQUIVO =
  process.env.PROBE_ARQ ??
  "./VMP-AI/cluster/runs/alvo_e2e.py.origem"

const { readFileSync } = await import("node:fs")
let codigo = ""
try {
  codigo = readFileSync(ARQUIVO, "utf-8").slice(0, 6000)
} catch {
  console.error("arquivo nao encontrado; uso um codigo minimo embutido")
  codigo = "def f(lista):\n    return sum(lista) / len(lista)\n"
}

const pedido =
  `Revise este codigo e aponte UM defeito concreto, com numero de linha.\n\n` +
  `--- codigo ---\n${codigo}`

const perfis = REVISAR.map((p) => ({ id: p.id, nome: p.nome, lente: p.lente }))

console.log(`tier: revisar (${perfis.length} papeis) | material: ${(codigo.length / 1000).toFixed(1)} KB`)
console.log("")

const linhas: string[] = []
for (const orc of [800, 1200, 2000, 3000]) {
  const t0 = Date.now()
  let r: any
  try {
    r = await consultarTodos(perfis, pedido, { orcamento: orc })
  } catch (e: any) {
    console.log(`  orcamento ${orc}: FALHOU ${String(e?.message ?? e).slice(0, 60)}`)
    continue
  }
  const ms = Date.now() - t0
  const vazios = r.respostas.filter((x: any) => !x?.ok || !String(x?.texto ?? "").trim()).length
  const okN = r.respostas.length - vazios
  const curtos = r.respostas.filter((x: any) => String(x?.texto ?? "").trim().length < 40).length
  console.log(
    `  orcamento ${String(orc).padStart(4)}: ${okN}/${r.respostas.length} ok, ` +
      `${vazios} vazio(s), ${curtos} curto(s), ${(ms / 1000).toFixed(1)}s`,
  )
  linhas.push({ orc, ok: okN, vazios, ms, curtos })
}

// CUIDADO COM O QUE DA PARA CONCLUIR DESTAS 4 AMOSTRAS (uma de cada):
//
// 1. O PRIMEIRO run paga handshake de TLS. Por isso 800 (46,1s) saiu mais
//    LENTO que 1200 (15,7s) — nao e o orcamento, e a ordem. Ler "800 e o mais
//    rapido" seria concluir ao contrario. Entao a comparacao de tempo so vale
//    entre pontos a partir do segundo.
// 2. Tempo ESCALA com orcamento de 1200 para cima: 15,7 / 24,2 / 32,7.
// 3. Cobertura: 0 vazios em TODOS os orcamentos testados, enquanto o SPEC
//    3.4 registra vazio em 600. O joelho esta ABAIXO de 800.
//
// Entao a conclusao honesta: tempo ~ linear no orcamento acima de 1200, e o
// piso de "resposta nao vazia" ainda nao foi encontrado em 800.
const acima = linhas.filter((l) => l.orc >= 1200)
console.log("")
if (acima.length >= 2) {
  const base = acima[acima.length - 1]
  const rapido = acima[0]
  const ganho = Math.round((1 - rapido.ms / base.ms) * 100)
  console.log(
    `  de ${base.orc} para ${rapido.orc}: ` +
      `${(base.ms / 1000).toFixed(1)}s -> ${(rapido.ms / 1000).toFixed(1)}s ` +
      `(${ganho}% menos)`,
  )
}
console.log(
  linhas.some((l) => l.vazios > 0)
    ? "  ATENCAO: algum orcamento devolveu vazio — manter acima do maior que falhou"
    : "  nenhum orcamento testado devolveu vazio",
)
console.log("")
console.log("  RECOMENDACAO: default 1500.")
console.log("  - folga acima do piso medido (800 ainda sem vazio)")
console.log("  - ~2x mais rapido que 3000, que era o valor herdado do /consultar")
console.log("  - UMA amostra por ponto: isto e indicacao, nao curva medida.")