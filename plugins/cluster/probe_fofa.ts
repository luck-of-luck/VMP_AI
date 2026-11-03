/**
 * Mede o teto REAL de concorrencia do relay.
 *
 * Por que medir antes de desenhar: "50 agentes simultaneos" so e uma frase
 * se o relay aceita 50 de uma vez. Se aceitar 10, entao 50 e 5 ondas — e o
 * desenho depende MUITO disso: ondas mudam a latencia total, mudam o formato
 * do checkpoint e mudam o que "simultaneo" significa para o agente.
 *
 * Este nao e benchmark estetico. E o numero que decide se o comite de 50
 * roda em uma camada ou em cadeia.
 */
import { RELAY, MODELO, chamarRelay } from "./engine.ts"

/**
 * ACHADO NA PRIMEIRA TENTATIVA DESTA SONDA (importante):
 * Com `max_tokens: 600` o relay devolveu 0 respostas com conteudo em 10, 25 e
 * 50 chamadas — sem erro, sem excecao, so `content` vazio. Esta e a
 * DEFESA do SPEC 3.4 aparecendo de novo: o modelo gasta o orcamento em
 * reasoning e nao escreve nada. Nao era o relay recusando; era orcamento
 * insuficiente.
 *
 * Entao a sonda mede o teto com o ORCAMENTO QUE FUNCIONA (3000, o mesmo do
 * caminho medido em /consultar). Registrar isso aqui porque a leitura errada
 * seria "o relay aguenta 0 simultaneos".
 */

async function uma(id: number) {
  const t0 = Date.now()
  try {
    // `chamarRelay` JA NORMALIZA: devolve { ok, content, finish, ... }.
    // Assumption errada na primeira versao desta sonda: eu tratava como
    // resposta OpenAI crua, entao `choices[0]` vinha indefinido e TODA a
    // rajada/media como 0 ok — "relay quebrado" quando o relay estava bem.
    const r: any = await chamarRelay(
      {
        model: MODELO,
        messages: [
          {
            role: "user",
            content: `Agente ${id}. Responda APENAS o numero ${id}. Nada mais.`,
          },
        ],
        max_tokens: 3000,
      },
      { tentativas: 1, timeoutMs: 120000 },
    )
    const txt = String(r?.content ?? "").trim()
    return {
      id,
      ok: !!r?.ok && txt.length > 0,
      ms: Date.now() - t0,
      txt: txt.slice(0, 30),
      fin: String(r?.finish ?? "-"),
      err: String(r?.erro ?? ""),
    }
  } catch (e: any) {
    return {
      id,
      ok: false,
      ms: Date.now() - t0,
      txt: "",
      fin: "-",
      err: String(e?.message ?? e).slice(0, 100),
    }
  }
}

async function rajada(n: number) {
  const t0 = Date.now()
  const rs = await Promise.all(Array.from({ length: n }, (_, i) => uma(i + 1)))
  const ok = rs.filter((r) => r.ok).length
  const ms = Date.now() - t0
  const erros = [...new Set(rs.filter((r) => !r.ok).map((r) => r.err))]
  const fins = [...new Set(rs.map((r) => r.fin))]
  // "ordem certa": cada agente devolveu o numero pedido. Detecta resposta
  // trocada entre agentes, que e o modo de falha SILENCIOSO de um relay.
  // Sem isto, uma falha total daria "ordem certa = SIM" por vacuidade.
  const todosResponderam = ok === n
  const ord = todosResponderam
    ? rs.every((r, i) => r.txt.includes(String(i + 1)))
    : false
  return { n, ok, ms, ord, fins, todosResponderam, erros }
}

process.stderr.write(`relay ${RELAY}\nmodelo ${MODELO}\norcamento 3000\n\n`)
for (const n of [10, 25, 50]) {
  process.stderr.write(`rajada curta de ${n}...`)
  const r = await rajada(n)
  console.log(`\n=== ${n} simultaneos, pergunta curta ===`)
  console.log(`  ok          : ${r.ok}/${r.n}`)
  console.log(`  tempo total : ${(r.ms / 1000).toFixed(1)}s`)
  console.log(`  finish      : ${r.fins.join(", ")}`)
  console.log(
    `  ordem certa : ${r.todosResponderam ? (r.ord ? "SIM" : "NAO") : "n/a (houve falha)"}`,
  )
  if (r.erros.length) console.log(`  erros       : ${r.erros.join(" | ")}`)
}

// ── O CASO QUE IMPORTA ───────────────────────────────────────────────────
// "50 agentes" com pergunta de 3 palavras nao e o caso de uso. O caso real
// e 50 agentes lendo um arquivo. A diferenca e o que decide se a super
// equipe cabe num cafe.
const ARQ = "./VMP-AI/cluster/runs/alvo_e2e.py.origem"
let codigo = ""
try {
  const { readFileSync } = await import("node:fs")
  codigo = readFileSync(ARQ, "utf-8").slice(0, 6000)
} catch {
  process.stderr.write("codigo nao encontrado, pulando o caso com arquivo\n")
}

if (codigo) {
  for (const n of [50]) {
    process.stderr.write(`rajada de ${n} COM arquivo...`)
    const t0 = Date.now()
    const prompt =
      `Revise este arquivo e aponte UM defeito concreto, com linha.\n\n` +
      `--- arquivo ---\n${codigo}`
    const rs = await Promise.all(
      Array.from({ length: n }, (_, i) =>
        chamarRelay(
          {
            model: MODELO,
            messages: [{ role: "user", content: prompt + `\n\n(agente ${i + 1})` }],
            max_tokens: 3000,
          },
          { tentativas: 1, timeoutMs: 180000 },
        ).then((r: any) => ({
          ok: !!r?.ok && String(r?.content ?? "").trim().length > 0,
        })),
      ),
    )
    const ms = Date.now() - t0
    const ok = rs.filter((r) => r.ok).length
    console.log(`\n=== ${n} simultaneos, LENDO ARQUIVO (6 KB no prompt) ===`)
    console.log(`  ok          : ${ok}/${n}`)
    console.log(`  tempo total : ${(ms / 1000).toFixed(1)}s`)
    console.log(
      `  custo de payload: ${n} x ${(codigo.length / 1000).toFixed(1)} KB = ` +
        `${((n * codigo.length) / 1e6).toFixed(2)} MB de entrada`,
    )
  }
}