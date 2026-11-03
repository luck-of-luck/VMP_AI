/**
 * MEDE A SINTAXE DO COMITE: quantos achados distintos existem de verdade?
 *
 * Por que esta e a medicao que mais importa, e eu nao tinha feito.
 *
 * Hasta agora eu medi SÓ ENCANAMENTO: quantas lentes responderam, quanto
 * demorou, o relay aguentou. Nada sobre QUALIDADE. Entao eu tenho 46 agentes
 * funcionando e zero evidencia de que o que eles dizem presta. Uma equipe
 * grande que produz confianca errada e pior que uma equipe pequena: o
 * usuario para de conferir.
 *
 * A hipotese a testar: 46 lentes sobre o mesmo arquivo produzem MUITOS
 * achados repetidos. Cada lente olha seu angulo, mas Defeito de arquivo
 * vazio, encoding faltando e recurso nao fechado aparecem para varias lentes
 * ao mesmo tempo — e o usuario le 15 linhas para descobrir 3 problemas.
 *
 * Metodo: classificar cada achado por sua特性 (caracteristica) e contar
 * classes distintas. Isso e uma aproximacao, e dita como tal: depende de
 * um mapa de categorias que eu escrevi, e um mapa errado da zero
 * categoria. O numero e uma FAIXA, nao uma verdade.
 */

import { readdirSync, readFileSync, existsSync } from "node:fs"
import { join } from "node:path"

// As trilhas ficam no cwd do MOTOR. Rodar o probe de outro diretorio
// acharia zero e pareceria "o comite nunca produziu nada" — um falso
// negativo silencioso, que e o pior tipo de falso.
const BASE =
  process.env.CLUSTER_TRILHA ??
  (existsSync(".cluster/trilhas")
    ? ".cluster/trilhas"
    : "./.cluster/trilhas")

// ── Categorias: assinatura de cada defeito POSSIVEL. ─────────────────────
// O criterio e "o que o codigo precisa fazer de diferente", nao a palavra
// usada. "Falta encoding" e "open() sem encoding explicito" sao a MESMA categoria
// mesmo com palavras diferentes — que e exatamente o ponto.
const CATEGORIAS: { nome: string; rx: RegExp }[] = [
  { nome: "divisao-por-zero / vazio", rx: /\b(zerodivision|divis[aã]o|lista vazia|empty|dividir por zero|len\(\))\b/i },
  { nome: "recurso nao fechado", rx: /\b(fechad|clos[eo]|with open|open\(\)|file handle|vazament|leak|fd)\b/i },
  { nome: "encoding ausente", rx: /\b(encod|utf-?8|decode|locale|charset)\b/i },
  { nome: "break/continue em laco", rx: /\b(break|continue|interromp|parar no primeiro)\b/i },
  { nome: "falta de validacao de entrada", rx: /\b(valid|indexerror|keyerror|fora de faixa|out of range|entrada)\b/i },
  { nome: "concorrencia / recurso compartilhado", rx: /\b(thread|lock|concorr|race|compartilhad)\b/i },
  { nome: "sem teste / cobertura", rx: /\b(teste|test|cobertura|cobrir)\b/i },
  { nome: "contrato / tipo de retorno", rx: /\b(retorno|return|contrato|assinatura|api|p[uú]blico)\b/i },
  { nome: "desempenho / escala", rx: /\b(performance|desempenh|escala|complexidade|o\(n|n\+1|loop)\b/i },
  { nome: "erro nao tratado", rx: /\b(exce[cç][aã]o|error|try|except|tratamento|engol)\b/i },
  { nome: "seguranca / injecao", rx: /\b(seguran|inje[cç]|sql|escape|sanitiz|path traversal|credencial|segredo)\b/i },
]

function classificar(texto: string): string[] {
  const achados: string[] = []
  for (const c of CATEGORIAS) {
    if (c.rx.test(texto)) achados.push(c.nome)
  }
  return achados
}

// ── Le as trilhas ─────────────────────────────────────────────────────────
if (!existsSync(BASE)) {
  console.log(`Nenhuma trilha em ${BASE}. Rode um ciclo primeiro.`)
  process.exit(0)
}

const trilhas = readdirSync(BASE, { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => e.name)
  .sort()
  .reverse()

const ultimas = trilhas.slice(0, 4)
console.log(`Trilhas: ${trilhas.length} | analisando as ${ultimas.length} mais recentes`)
console.log("")

let totalAchados = 0
let totalClasses = 0
let ClassSetPorTrilha: { trilha: string; linhas: number; classes: number; cobertura: number }[] = []

for (const t of ultimas) {
  const dir = join(BASE, t)
  const v = readdirSync(dir).filter((f) => /^v\d+\.json$/.test(f)).sort().pop()
  if (!v) continue
  const cp = JSON.parse(readFileSync(join(dir, v), "utf-8"))
  const revisao = cp.rodadas.find((r) => r.tier === "revisar")
  if (!revisao) continue

  const respostas = Object.entries(revisao.respostas)
  // Uma linha por bullet: cada "- " e um achado separado.
  const linhas: { lente: string; texto: string }[] = []
  for (const [lente, txt] of respostas) {
    for (const l of txt.split("\n")) {
      const s = l.replace(/^\s*[-*\d.)\]]+\s*/, "").trim()
      if (s.length > 25) linhas.push({ lente, texto: s })
    }
  }
  if (!linhas.length) continue

  const classes = new Set<string>()
  let semClasse = 0
  for (const l of linhas) {
    const c = classificar(l.texto)
    if (!c.length) semClasse++
    for (const x of c) classes.add(x)
  }
  totalAchados += linhas.length
  totalClasses += classes.size
  ClassSetPorTrilha.push({
    trilha: t,
    linhas: linhas.length,
    classes: classes.size,
    cobertura: Number(((classes.size / linhas.length) * 100).toFixed(0)),
  })
}

console.log("TRILHA".padEnd(34) + "ACHADOS".padEnd(12) + "DISTINTOS".padEnd(14) + "SINAL")
for (const r of ClassSetPorTrilha) {
  console.log(
    "  " + r.trilha.slice(0, 32).padEnd(33) +
    String(r.linhas).padEnd(11) +
    String(r.classes).padEnd(13) +
    r.cobertura + "%",
  )
}

if (totalAchados) {
  console.log("")
  console.log(`TOTAL: ${totalAchados} linhas de achado -> ${totalClasses} categorias distintas`)
  console.log(`Sinal util: ${((totalClasses / totalAchados) * 100).toFixed(0)}%` +
    `  (1:1 = cada linha e um problema novo)`)
  console.log("")
  if (totalClasses / totalAchados < 0.35) {
    console.log(
      "LEITURA: sinal baixo. As lentes concordam entre si mais do que discordam —\n" +
        "que e o oposto do que uma equipe grande deveria fazer. O custo e o\n" +
        "mesmo: o usuario le N linhas para achar P problemas.",
    )
  } else {
    console.log("LEITURA: sinal razoavel. As lentes estao achando coisas diferentes.")
  }
  console.log("")
  console.log(
    "LIMITE DESTA MEDICAO: depende do mapa de categorias que EU escrevi.\n" +
      "Um mapa errado produz zero categoria e um sinal artificialmente baixo.\n" +
      "E 'linha' nao e 'problema': uma linha pode citar dois defeitos, e um\n" +
      "defeito pode estar em tres linhas. E uma faixa, nao uma verdade.",
  )
}