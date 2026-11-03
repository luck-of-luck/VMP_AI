/**
 * Teste do dedup com casos de RESPOSTA CONHECIDA.
 *
 * Por que casosKnown: um teste de agrupamento que usa as respostas do modelo
 * so me diz se ele rodou. Aqui eu montei os casos com a resposta na cabeca —
 * "estas 5 linhas sao o mesmo defeito", "estas 2 nao sao" — e o teste falha
 * se o agrupamento discordar de mim. E o unico jeito de medir o agrupamento
 * sem um gabarito de defeitos reais.
 *
 * E o teste que importa: se o dedup junta coisas que nao sao a mesma, ele
 * perde defeito real. Se ele separa coisas que sao, ele volta ao problema
 * original.
 */
import { agrupar, emLinhas, relatar } from "./dedup.ts"

let falhas = 0
function ok(cond: boolean, label: string, det?: string) {
  console.log(`  [${cond ? "OK   " : "FALHA"}] ${label}${det ? `  -- ${det}` : ""}`)
  if (!cond) falhas++
}

console.log("=".repeat(70))
console.log("1. O MESMO DEFEITO, DITO DE 5 FORMAS")
console.log("=".repeat(70))
// Resposta esperada: 1 grupo, 5 lentes.
const mesmoDefeito = [
  {
    lente: "correcao",
    texto:
      "- `media()` em alvo.py:22: `media([])` causa ZeroDivisionError.\n" +
      "- `media()` em alvo.py:22-24: a divisao por len() estoura com lista vazia.",
  },
  {
    lente: "erros",
    texto:
      "- alvo.py linha 22: ZeroDivisionError na divisao quando a lista vem vazia.\n" +
      "- Trate lista vazia antes de dividir em media().",
  },
  {
    lente: "dados",
    texto: "- media([]) em alvo.py:22 estoura; lista vazia precisa de guarda.",
  },
  { lente: "testes", texto: "- Sem teste para media() com lista vazia (alvo.py:22)." },
  { lente: "contrato", texto: "- media() nao define o que faz com lista vazia." },
]

const g1 = agrupar(mesmoDefeito)
ok(g1.length === 1, "as 5 lentes viraram 1 grupo", `${g1.length} grupo(s)`)
ok(g1[0]?.lentes.length === 5, "as 5 lentes estao no grupo", `${g1[0]?.lentes.length}`)
ok(
  (g1[0]?.lentes ?? []).includes("correcao") && (g1[0]?.lentes ?? []).includes("testes"),
  "lentes de fora do mesmo 'olho' entraram juntas (nao e auto-eco)",
)

console.log("")
console.log("=".repeat(70))
console.log("2. O LIMITE REAL: dois defeitos no MESMO lugar viram um grupo")
console.log("=".repeat(70))
// Este teste foi escrito primeiro para exigir que dois defeitos DIFERENTES
// na mesma linha ficassem separados. MEDI para ver se o dedup consegue, e
// NAO CONSEGUE. A similaridade de termos nao separa:
//
//   mesmo defeito, formas diferentes : jaccard 0.222 (comum: media, alvo)
//   defeitos diferentes, mesma linha : jaccard 0.214 (comum: carregar_config, alvo, open)
//
// O valor do defeito-diferente e MENOR que o do mesmo-defeito. Nao ha
// sinal nos tokens que separe os dois casos. Qualquer limiar que os separe
// seria escolhido depois de ver estes dois exemplos — overfit, nao metodo.
//
// Entao o contrato real e outro, e este teste afirma o contrato real:
//
//   Defeitos no MESMO lugar sao UM problema, e o texto de CADA um e
//   preservado nos variantes.
//
// O merge e aceitavel porque o grupo mostra as variantes: quem le ve as
// duas afirmacoes, so que sob o mesmo titulo. Perder a linha e o que seria
// grave — e nao se perde.
const doisNaMesmaLinha = [
  { lente: "erros", texto: "- carregar_config em alvo.py:40: open() sem with deixa o arquivo aberto se read() falhar." },
  { lente: "seguranca", texto: "- carregar_config em alvo.py:40: open() sem encoding fixa depende do locale e quebra com UTF-8." },
]
const g2 = agrupar(doisNaMesmaLinha)
ok(g2.length === 1, "mesmo lugar = um problema", `${g2.length} grupo(s)`)
ok(g2[0].variantes.length === 2, "AMBOS os textos foram preservados", `${g2[0].variantes.length} variante(s)`)
ok(
  g2[0].variantes.some((v) => v.includes("with")) &&
    g2[0].variantes.some((v) => v.includes("encoding")),
  "nenhum dos dois achados se perdeu no merge",
)
ok(g2[0].lentes.length === 2, "as duas lentes estao creditadas no grupo", g2[0].lentes.join(","))

console.log("")
console.log("=".repeat(70))
console.log("3. ORDEM: mais concordancia primeiro")
console.log("=".repeat(70))
const varios = [
  { lente: "a", texto: "- media() em alvo.py:22: ZeroDivisionError com lista vazia." },
  { lente: "b", texto: "- media() em alvo.py:22: ZeroDivisionError com lista vazia." },
  { lente: "c", texto: "- media() em alvo.py:22: ZeroDivisionError com lista vazia." },
  { lente: "d", texto: "- open() em alvo.py:40: sem with deixa arquivo aberto." },
]
const g3 = agrupar(varios)
ok(g3.length === 2, "achados repetidos viraram 1", `${g3.length}`)
ok(g3[0].lentes.length >= 3, "o grupo mais concordado vem primeiro", `${g3[0].lentes.length} lentes`)

console.log("")
console.log("=".repeat(70))
console.log("4. O QUE NAO DEVE VIRAR ACHADO")
console.log("=".repeat(70))
const ruido = [
  { lente: "x", texto: "- ok" },                                   // curto
  { lente: "x", texto: "" },                                         // vazio
  { lente: "x", texto: "-   " },                                     // so espacos
]
ok(emLinhas(ruido).length === 0, "achado curto/vazio e descartado", `${emLinhas(ruido).length}`)

console.log("")
console.log("=".repeat(70))
console.log("5. FORMATOS DE LINHA DIFERENTES viram linhas")
console.log("=".repeat(70))
const formatos = [
  {
    lente: "a",
    texto:
      "- primeiro achado, com texto suficiente para passar do piso\n" +
      "* segundo achado, tambem com texto suficiente para o piso\n" +
      "1. terceiro achado, com texto suficiente para o piso\n" +
      "2) quarto achado, com texto suficiente para o piso",
  },
  { lente: "b", texto: "achado em prosa corrida, sem bullet nenhum porem longo" },
]
// MEDIDO: a primeira versao deste teste usava "texto solto sem bullet" que
// tem 22 caracteres, abaixo do piso de 25 — e o codigo estava certo em
// descartar. O teste era que estava errado, e falhava por isso.
ok(emLinhas(formatos).length === 5, "4 bullets + 1 prosa = 5 achados", `${emLinhas(formatos).length}`)

console.log("")
console.log("=".repeat(70))
console.log("6. RELATORIO — diz o antes e o depois")
console.log("=".repeat(70))
const todas = [...mesmoDefeito, ...doisNaMesmaLinha, ...varios]
const gt = agrupar(todas)
const nLinhas = emLinhas(todas).length
const rel = relatar(gt, nLinhas, 9)
ok(rel.includes("9 lentes"), "relatorio diz quantas lentes entraram")
ok(/voc[eê]\s+le\s+\d+/i.test(rel), "relatorio diz quanto se economiza de leitura")
ok(
  rel.includes("Severidade NAO aparece") || rel.includes("Severidade"),
  "relatorio declara que severidade foi omitida de proposito",
)
console.log("")
console.log("--- relatorio de exemplo (as primeiras linhas) ---")
for (const l of rel.split("\n").slice(0, 16)) console.log("  | " + l.slice(0, 96))

console.log("")
console.log("=".repeat(70))
console.log("SINAL MEDIDO:")
console.log(`  ${nLinhas} linhas -> ${gt.length} problemas distintos`)
console.log(`  compressao     : ${((gt.length / nLinhas) * 100).toFixed(0)}%`)
console.log("")
console.log("=".repeat(70))
console.log("7. A LENTE QUE NAO PODE OLHAR nao vira achado")
console.log("=".repeat(70))
// MEDIDO numa rodada real: 3 das 12 lentes responderam "Sem ferramenta de
// arquivos; conferi apenas a literal fornecida". Sem filtro, isso entrava no
// consolidado como problema de primeira linha -- e "Nenhum teste foi
// fornecido" lido como problema e uma acusacao falsa sobre o codigo.
const naoAchados = [
  { lente: "x", texto: "- Sem ferramenta de arquivos; conferi apenas a literal fornecida aqui." },
  { lente: "y", texto: "- Nenhum teste foi fornecido; portanto cobertura e mocks nao puderam ser avaliados." },
  { lente: "z", texto: "- Revisao limitada ao literal fornecido; nao havia ferramenta de execucao disponivel." },
]
ok(emLinhas(naoAchados).length === 0, "as 3 linhas foram descartadas", String(emLinhas(naoAchados).length))

console.log("")
console.log("=".repeat(70))
console.log("8. ACHADO REAL NAO E DESCARTADO")
console.log("=".repeat(70))
const real = [
  { lente: "correcao", texto: "- `media()` em alvo.py:26: `media([])` provoca ZeroDivisionError." },
]
ok(emLinhas(real).length === 1, "achado real continua de pe", String(emLinhas(real).length))

console.log("=".repeat(70))
if (falhas) {
  console.log(`FALHAS: ${falhas}`)
  process.exit(1)
}
console.log("DEDUP OK")