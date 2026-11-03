/**
 * Teste do board: fila, lease, custo, e o caso que nao se ve — o executor
 * que MORRE no meio da tarefa.
 *
 * Por que testar o lease com tempo artificial: um executor morrer de verdade
 * para provar que o lease funciona e um teste carissimo e raro. Aqui o tempo
 * e avancado no arquivo, que e o mesmo mecanismo (o lease e epoch ms).
 */
import { Board, ORCAMENTO_PADRAO_BOARD } from "./board.ts"
import { join } from "node:path"
import { tmpdir } from "node:os"
import { rmSync, readFileSync, writeFileSync } from "node:fs"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

const RAIZ = join(tmpdir(), "board_teste_" + Date.now())
rmSync(RAIZ, { recursive: true, force: true })

/**
 * Faz o lease vencer e devolve um Board NOVO, recarregando do disco.
 *
 * DOIS ERROS MEUOS NESTE HELPER, ambos medidos:
 *
 * 1. A primeira versao editava o arquivo e devolvia nada. O `Board` tem
 *    estado em memoria e sobrescreve o arquivo no proximo `salvar()` —
 *    entao mexer no JSON nao mudava nada para a instancia viva, e o teste
 *    acusava o lease quando o quebrado era o helper.
 *
 * 2. Somar `leaseMs` ao `leaseAte` deixa o lease MAIS no futuro
 *    (`agora + lease` vira `agora + 2*lease`), nunca vencido. Para vencer,
 *    o `leaseAte` tem de ir para o PASSADO. Isto e "o executor morreu ha
 *    10 minutos", que e o cenario real.
 *
 * Recriar o Board e o cenario real: o processo acabou, um novo le do disco.
 */
function vencerLease(board: Board): Board {
  const arq = join(board.dir, "board.json")
  const e = JSON.parse(readFileSync(arq, "utf-8"))
  const passado = Date.now() - 60_000 // morreu a um minuto
  for (const t of e.tarefas) if (t.leaseAte) t.leaseAte = passado
  writeFileSync(arq, JSON.stringify(e, null, 2))
  return new Board(board.dir, board.orcamento)
}

/** Empurra o inicio do board para o passado, para testar tempo de parede. */
function recuarInicio(board: Board, ms: number): Board {
  const arq = join(board.dir, "board.json")
  const e = JSON.parse(readFileSync(arq, "utf-8"))
  e.eventos = e.eventos.map((x: any) => ({ ...x, em: x.em - ms }))
  writeFileSync(arq, JSON.stringify(e, null, 2))
  return new Board(board.dir, board.orcamento)
}

console.log("=".repeat(70))
console.log("1. FILA BASICA")
console.log("=".repeat(70))
const b = new Board(join(RAIZ, "b1"))
b.criarTarefa({ titulo: "Corrigir media() vazia", pedido: "Retornar None em vez de ZeroDivisionError." })
b.criarTarefa({ titulo: "Corrigir primeiro()", pedido: "Devolver lista[0]." })
ok(b.listar("aberta").length === 2, "duas tarefas abertas", `${b.listar("aberta").length}`)

const t1 = b.pegarTarefa("exec-1")
ok(t1 !== null, "primeira tarefa pega")
ok(t1!.status === "em_andamento", "status em_andamento")
ok(t1!.claimedPor === "exec-1", "dono registrado")
ok((t1!.leaseAte ?? 0) > Date.now(), "lease no futuro")
ok(b.listar("aberta").length === 1, "so resta uma aberta", `${b.listar("aberta").length}`)

const t2 = b.pegarTarefa("exec-2")
ok(t2 !== null && t2!.id !== t1!.id, "segundo pega a OUTRA tarefa", `t1=${t1!.id} t2=${t2!.id}`)

console.log("")
console.log("=".repeat(70))
console.log("2. FILA ESGOTADA — nao inventa tarefa")
console.log("=".repeat(70))
ok(b.pegarTarefa("exec-3") === null, "sem tarefa livre devolve null")

console.log("")
console.log("=".repeat(70))
console.log("3. O EXECUTOR QUE MORRE — o lease devolve a fila")
console.log("=".repeat(70))
// exec-2 pega uma tarefa e "morre": nao conclui, nao falha, nao renova.
let b2 = new Board(join(RAIZ, "b2"))
b2.criarTarefa({ titulo: "Tarefa que ninguem vai terminar", pedido: "..." })
const presa = b2.pegarTarefa("exec-morto")
ok(presa !== null, "tarefa capturada pelo executor que morre")
ok(b2.listar("aberta").length === 0, "fila vazia: presa em andamento")
ok(
  b2.listar("em_andamento").some((t) => t.claimedPor === "exec-morto"),
  "tarefa esta presa em exec-morto",
)

// Faz o lease vencer e RECRIA o board — um processo novo, como seria.
const b2b = vencerLease(b2)
ok(b2b.listar("aberta").length === 1, "lease expirou e devolveu a fila", `${b2b.listar("aberta").length}`)

const recuperada = b2b.pegarTarefa("exec-vivo")
ok(recuperada !== null, "outro executor consegue pegar")
ok(recuperada!.id === presa!.id, "e a MESMA tarefa", `${recuperada!.id}`)
ok(recuperada!.tentativas === 2, "tentativas comptadas", `${recuperada!.tentativas}`)
ok(
  b2b.logTipos().includes("lease_expirou"),
  "o log registra que a tarefa voltou (ninguem pode achar que ninguem fez)",
)
b2 = b2b

console.log("")
console.log("=".repeat(70))
console.log("4. RENOVAR E CONCLUIR SO DONO")
console.log("=".repeat(70))
ok(b2.renovar(recuperada!.id, "exec-vivo"), "dono renova")
ok(!b2.renovar(recuperada!.id, "exec-intruso"), "intruso nao renova")
ok(!b2.concluir(recuperada!.id, "exec-intruso", "fui eu"), "intruso nao conclui")
ok(b2.concluir(recuperada!.id, "exec-vivo", "feito e verificado"), "dono conclui")
ok(b2.listar("concluida").length === 1, "tarefa concluida")

console.log("")
console.log("=".repeat(70))
console.log("5. CONVERSA — o artefato viaja de um agente para o outro")
console.log("=".repeat(70))
const b3 = new Board(join(RAIZ, "b3"))
const achado = b3.publicar({
  tipo: "achado",
  autor: "lente_sintese",
  titulo: "media() estoura em lista vazia",
  conteudo: "media([]) -> ZeroDivisionError. Sem guarda.",
})
const tarefa = b3.criarTarefa({
  titulo: "Corrigir media()",
  pedido: "Faça media([]) devolver None.",
  origem: "ciclo:abc123",
})
b3.publicar({
  tipo: "achado",
  autor: "lente_sintese",
  titulo: "contexto para quem for corrigir",
  conteudo: "A guarda precisa ser ANTES da divisao, nao depois.",
  tarefa: tarefa.id,
})

const ctx = b3.contexto(tarefa.id)
ok(ctx !== null, "contexto da tarefa existe")
ok(ctx!.artefatos.length === 1, "artefato ligado a tarefa", `${ctx!.artefatos.length}`)
ok(ctx!.artefatos[0].conteudo.includes("ANTES"), "o executor novo ve o raciocinio de quem achou")
ok(ctx!.tarefa.origem === "ciclo:abc123", "origem rastreavel ate o ciclo")
ok(achado.tarefa === undefined, "achado solto nao fica preso em tarefa")

console.log("")
console.log("=".repeat(70))
console.log("6. FALHA — devolve ate 3 tentativas, depois marca como falhou")
console.log("=".repeat(70))
const b4 = new Board(join(RAIZ, "b4"))
const tf = b4.criarTarefa({ titulo: "Impossivel", pedido: "..." })
// O ciclo real e pegar -> trabalhar -> falhar. Sem o `pegar`, `tentativas`
// nao avanca e a tarefa nunca esgota as tentativas — que foi exatamente o
// que a primeira versao deste teste fez.
const ciclo = (quem: string) => {
  const p = b4.pegarTarefa(quem)
  if (!p) return false
  b4.falhar(p.id, quem, `erro de ${quem}`)
  return true
}
ok(ciclo("e1"), "1o ciclo: falha devolve para aberta")
ok(b4.listar("aberta").length === 1, "1a falha deixa a tarefa aberta", `${b4.listar("aberta").length}`)
ok(ciclo("e2"), "2o ciclo")
ok(b4.listar("aberta").length === 1, "2a falha ainda deixa aberta")
ok(ciclo("e3"), "3o ciclo: tentativas esgotadas")
ok(b4.listar("falhou").length === 1, "3a falha marca como falhou", `falhou=${b4.listar("falhou").length}`)
ok(b4.listar("aberta").length === 0, "saiu da fila de vez")
ok(b4.pegarTarefa("e4") === null, "tarefa falhada nao volta a ser pega")
ok(!b4.falhar("id_inexistente", "x", "y"), "falhar id inexistente devolve false")

console.log("")
console.log("=".repeat(70))
console.log("7. TRAVA DE CUSTO — o ciclo para sozinho")
console.log("=".repeat(70))
const b5 = new Board(RAIZ, { maxTarefas: 2, maxTurnos: 3, wallClockMs: 60_000, leaseMs: 5000 })
for (let i = 0; i < 4; i++) b5.criarTarefa({ titulo: `T${i}`, pedido: "..." })

let parouPor = ""
for (let i = 0; i < 6; i++) {
  const g = b5.guarda()
  if (!g.pode) {
    parouPor = g.motivo ?? "?"
    break
  }
  const t = b5.pegarTarefa(`e${i}`)
  if (t) b5.concluir(t.id, `e${i}`, "ok")
}
ok(parouPor.includes("tarefas") || parouPor.includes("turnos"), "ciclo parou por limite", parouPor)

const g1 = new Board(join(RAIZ, "g1"), { maxTarefas: 99, maxTurnos: 99, wallClockMs: 1000, leaseMs: 5000 })
g1.criarTarefa({ titulo: "x", pedido: "y" })
const g1b = recuarInicio(g1, 5000)
const g1r = g1b.guarda()
ok(!g1r.pode && g1r.motivo!.includes("parede"), "limite de tempo de parede para", g1r.motivo)

const g2 = new Board(join(RAIZ, "g2"), { maxTarefas: 99, maxTurnos: 1, wallClockMs: 999999, leaseMs: 5000 })
g2.criarTarefa({ titulo: "x", pedido: "y" })
g2.pegarTarefa("a")
const g2r = g2.guarda()
ok(!g2r.pode && g2r.motivo!.includes("turnos"), "limite de turnos para", g2r.motivo)

console.log("")
console.log("=".repeat(70))
console.log("8. PERSISTENCIA — sobrevive a novo processo")
console.log("=".repeat(70))
const b6 = new Board(join(RAIZ, "b6"))
b6.criarTarefa({ titulo: "Persiste", pedido: "..." })
const b7 = new Board(join(RAIZ, "b6")) // "outro processo", mesmo disco
ok(b7.listar().length >= 1, "board novo enxerga a tarefa")
ok(b7.listar().length === b6.listar().length, "mesma contagem")

console.log("")
console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  process.exit(1)
}
console.log("BOARD OK")
rmSync(RAIZ, { recursive: true, force: true })