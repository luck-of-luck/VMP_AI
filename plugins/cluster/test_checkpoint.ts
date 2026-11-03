/**
 * Teste do checkpoint e da trilha, SEM rede.
 *
 * Feito separado do teste do ciclo porque checkpoint e a parte que ninguem
 * nota quando falha: sem estado, o trabalho se perde entre sessoes e nada
 * quebra de forma visivel. O que quebra e a confianca.
 */
import { Trilha, novoId, type Checkpoint } from "./checkpoint.ts"
import { rmSync, readFileSync, existsSync, readdirSync } from "node:fs"
import { join } from "node:path"
import { tmpdir } from "node:os"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

const RAIZ = join(tmpdir(), "trilha_teste_" + Date.now())
rmSync(RAIZ, { recursive: true, force: true })
const t = new Trilha(RAIZ)

function cpBase(id: string, versao: number): Checkpoint {
  return {
    id,
    versao,
    criadoEm: new Date().toISOString(),
    titulo: "Teste de trilha",
    pedido: "verificar se o estado sobrevive",
    arquivos: ["C:/exemplo.py"],
    rodadas: [
      {
        tier: "revisar",
        em: Date.now(),
        duracaoMs: 1234,
        chamados: 3,
        ok: 2,
        calados: ["seguranca"],
        respostas: { correcao: "achou A", contrato: "achou B" },
      },
    ],
    proximosPassos: ["arrumar A", "checar B"],
    bloqueios: ["nenhum teste para o lens e"],
  }
}

console.log("=".repeat(70))
console.log("1. GRAVAR E RECARREGAR")
console.log("=".repeat(70))
const id = novoId("Revisar o sistema de arquivos")
t.salvar(cpBase(id, 1))
const lido = t.carregar(id)
ok(lido !== null, "checkpoint gravado e relido")
ok(lido!.versao === 1, "versao correta", `v${lido!.versao}`)
ok(lido!.pedido === "verificar se o estado sobrevive", "pedido preservado")
ok(lido!.rodadas[0].calados.includes("seguranca"), "lente calada registrada")
ok(lido!.rodadas[0].respostas.correcao === "achou A", "respostas preservadas")

console.log("")
console.log("=".repeat(70))
console.log("2. VERSAO — nao sobrescreve, porque o diff e metade do valor")
console.log("=".repeat(70))
t.salvar(cpBase(id, 2))
const vs = t.versoes(id)
ok(vs.length === 2 && vs[0] === 1 && vs[1] === 2, "as duas versoes coexistem", vs.join(","))
ok(existsSync(join(RAIZ, id, "v1.json")), "v1.json ainda existe")
ok(t.carregar(id)!.versao === 2, "carregar traz a mais recente", `v${t.carregar(id)!.versao}`)

console.log("")
console.log("=".repeat(70))
console.log("3. RELATORIO — o que alguem le amanha")
console.log("=".repeat(70))
t.salvarRelatorio(t.carregar(id)!)
const rel = readFileSync(join(RAIZ, id, "v2.md"), "utf-8")
ok(rel.includes("Teste de trilha"), "relatorio tem o titulo")
ok(rel.includes("CALADOS: seguranca"), "relatorio NOMEIA a lente calada")
ok(rel.includes("arrumar A"), "relatorio traz proximos passos")
ok(rel.includes("Bloqueios"), "relatorio tem secao de bloqueios")
// "conseguir continuar" vs "pode continuar": o relatorio diz "Se voce leu so
// isto e CONSEGUIR continuar". A falha anterior era o teste procurando a
// palavra errada — um teste que falha por grafia e um teste que treina a
// pessoa a nao confiar no teste.
ok(/conseguir continuar|continuar o trabalho/.test(rel), "relatorio diz para quem e")
console.log("")
console.log("--- o relatorio, para inspecao visual ---")
for (const l of rel.split("\n").slice(0, 22)) console.log("  | " + l)

console.log("")
console.log("=".repeat(70))
console.log("4. TRILHA INEXISTENTE — o caso que devolve null, nao lanca")
console.log("=".repeat(70))
ok(t.carregar("nao_existe_xyz") === null, "carregar de id desconhecido devolve null")
ok(t.versoes("nao_existe_xyz").length === 0, "versoes de id desconhecido e vazio")
ok(t.listar().includes(id), "listar encontra a trilha")

console.log("")
console.log("=".repeat(70))
console.log("5. ID ORDENAVEL")
console.log("=".repeat(70))
const a = novoId("Primeira tarefa")
const b = novoId("Primeira tarefa")
ok(a !== b, "ids distintos (tem componente aleatorio)")
ok(/^\d{8}-\d{6}-/.test(a), "id comeca com carimbo de tempo", a)
// A tag e TRUNCADA em 12 chars (para o nome da pasta caber em Windows). De
// "Primeira tarefa" sobra "primeira-tar" — 12 chars, exatamente. O teste
// antigo exigia a frase inteira, que nunca coube. Agora exige o que o codigo
// promete: ate 12 chars, e sem espaco.
const tag = a.split("-").slice(2, -1).join("-")
ok(tag.length > 0 && tag.length <= 12, "tag do titulo tem ate 12 chars", `"${tag}" (${tag.length})`)
ok(!tag.includes(" "), "tag sem espaco (nome de pasta seguro)")

console.log("")
console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  process.exit(1)
}
console.log("TRILHA OK")
rmSync(RAIZ, { recursive: true, force: true })