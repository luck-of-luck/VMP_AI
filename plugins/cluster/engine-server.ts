/**
 * Servidor HTTP do cluster. Serve o motor (`engine.ts`) para o MCP.
 *
 * POR QUE EXISTE
 * Custom tools de plugin nao funcionam no OpenCode 1.18.34 (medido: nem um
 * plugin minimo registra tool). MCP funciona — ha 78 tools `amplia_*` ativas.
 * Entao o caminho comprovado e: OpenCode -> MCP (Python) -> HTTP -> motor.
 *
 * Este arquivo NAO reimplementa o motor: importa `consultarTodos` e
 * `rodarComRetry` de `engine.ts`. A logica das 10 lentes e do relay continua
 * em um lugar so.
 *
 * Uso:  node engine-server.ts          (porta 8791)
 */
import { createServer } from "node:http"
import { readFile } from "node:fs/promises"
import { PERFIS, consultarTodos } from "./engine.ts"
import { rodarCiclo, PERFIS_CICLO, ORCAMENTO_PADRAO, TAMANHO_EQUIPE } from "./supervisor.ts"
import { Trilha, type Checkpoint } from "./checkpoint.ts"
import { Board } from "./board.ts"
import { agrupar, emLinhas, relatar as relatarDedup } from "./dedup.ts"

const PORTA = Number(process.env.CLUSTER_ENGINE_PORT ?? 8791)
const TRILHA_PADRAO = process.env.CLUSTER_TRILHA ?? ".cluster/trilhas"
const BOARD_PADRAO = process.env.CLUSTER_BOARD ?? ".cluster/board"

function board(): Board {
  return new Board(BOARD_PADRAO)
}

function log(...a: unknown[]) {
  process.stderr.write("[cluster-engine] " + a.map(String).join(" ") + "\n")
}

/**
 * O que o coordenador entrega: o estado da equipe, na ordem de importance.
 *
 * Por que formatar aqui e nao deixar o modelo montar: as 46 respostas sao
 * longas, e a regra "calado vira bloqueio" e "cobertura baixa vira bloqueio"
 * tem de valer independente de o modelo lembrar dela. Confiar na instrucao
 * para nao mentir sobre lacuna e confiar na honestidade de quem foi hired
 * para mentir.
 */
function entregarCiclo(cp: Checkpoint, duracaoSegundos: number, perfil: string): string {
  const L: string[] = []
  const totalOk = cp.rodadas.reduce((a, r) => a + r.ok, 0)
  const totalChamados = cp.rodadas.reduce((a, r) => a + r.chamados, 0)

  L.push(`TRILHA ${cp.id} (v${cp.versao}) — perfil "${perfil}" em ${duracaoSegundos.toFixed(1)}s`)
  L.push(`PEDIDO: ${cp.pedido}`)
  L.push("")

  L.push("== RODADAS ==")
  for (const r of cp.rodadas) {
    L.push(`  ${r.tier.padEnd(13)} ${r.ok}/${r.chamados} em ${(r.duracaoMs / 1000).toFixed(1)}s`)
    if (r.calados.length) L.push(`      LENTES CALADAS: ${r.calados.join(", ")}`)
  }
  L.push("")

  if (cp.conclusao) {
    L.push("== CONCLUSAO DA EQUIPE ==")
    L.push(cp.conclusao)
    L.push("")
  } else {
    L.push("== CONCLUSAO ==")
    L.push(
      "(o tier de supervisao nao rodou neste perfil — nao ha triagem. " +
        "Use perfil=padrao ou completo se quiser ordem de prioridade.)",
    )
    L.push("")
  }

  // As conclusoes de cada lente, por tier. E o corpo do resultado.
  for (const r of cp.rodadas) {
    const entries = Object.entries(r.respostas)
    if (!entries.length) continue

    // A revisao entra CONSOLIDADA. MEDIDO (2026-10-03): as lentes escreveram
    // 49 linhas dizendo 8 coisas. Enviando as 49, o usuario lia ~6 linhas
    // por novidade — e a maquina inteira (46 lentes, 5 tiers, board,
    // checkpoint) funcionava perfeita para entregar 16% de sinal. O dedup
    // vira isso em problemas distintos ordenados por quantas lentes viram
    // cada um, que e medida real de confianca.
    if (r.tier === "revisar") {
      const achados = entries.map(([lente, texto]) => ({ lente, texto }))
      const linhas = emLinhas(achados)
      const grupos = agrupar(achados)
      if (grupos.length && grupos.length < linhas.length) {
        L.push(relatarDedup(grupos, linhas.length, entries.length))
        L.push("")
        L.push(
          "-- o bruto de cada lente esta no relatorio em disco, caso queira " +
            "conferir uma consolidacao que Pareca errada.",
        )
        L.push("")
        continue
      }
    }

    L.push(`== ${r.tier.toUpperCase()} — ${entries.length} lentes ==`)
    for (const [id, txt] of entries) {
      L.push("")
      L.push(`[${id}]`)
      L.push(txt)
    }
    L.push("")
  }

  if (cp.proximosPassos.length) {
    L.push("== PROXIMOS PASSOS PROPOSTOS ==")
    for (const p of cp.proximosPassos) L.push(`  - ${p}`)
    L.push("")
  }
  if (cp.bloqueios.length) {
    L.push("== BLOQUEIOS (leia antes de agir) ==")
    for (const b of cp.bloqueios) L.push(`  ! ${b}`)
    L.push("")
  }

  L.push(
    `COBERTURA: ${totalOk}/${totalChamados} lentes. ` +
      (totalOk === totalChamados
        ? "Todas responderam."
        : "Lentes caladas NAO significa 'nenhum problema': significa que ninguem olhou. " +
          "Os nomes estao acima."),
  )
  L.push("")
  L.push("RELATORIO COMPLETO: " + `${TRILHA_PADRAO}/${cp.id}/v${cp.versao}.md`)
  return L.join("\n")
}

/**
 * Monta a fatia de cada agente.
 *
 * MEDIDO (2026-10-01): mandar so o CAMINHO nao funciona. Os agentes do relay
 * nao tem ferramenta de arquivo, entao respondem "nao li X" e o comite
 * inteiro vira opinion sobre codigo que ninguem viu. Entao o conteudo e
 * lido AQUI e vai no prompt.
 *
 * O `montarPrompt` do motor existe para dar a cada agente uma fatia
 * DIFERENTE: dez agentes lendo o mesmo trecho tendem a achar o mesmo defeito.
 * Aqui cada lente recebe o mesmo material, mas com sua lente focada — e o
 * corte por tamanho evita estourar o contexto.
 */
const MAX_CHARS_POR_ARQUIVO = 6000

async function fatiaDe(idx: number, perfil: any, prompt: string) {
  const arquivos = (globalThis as any).__arquivos ?? []
  if (!arquivos.length) return prompt
  const partes = [prompt, "", "ARQUIVOS PARA VOCE VER (conteudo literal, nao e caminho):"]
  for (const caminho of arquivos) {
    try {
      const txt = await readFile(caminho, "utf-8")
      const cortado =
        txt.length > MAX_CHARS_POR_ARQUIVO
          ? txt.slice(0, MAX_CHARS_POR_ARQUIVO) +
            `\n... [cortado em ${MAX_CHARS_POR_ARQUIVO} chars de ${txt.length}]`
          : txt
      const num = caminho.split(/[\\/]/).pop()
      partes.push(`\n--- ${num} ---\n${cortado}`)
    } catch (e: any) {
      partes.push(`\n--- ${caminho} ---\n(nao consegui ler: ${e?.message ?? e})`)
    }
  }
  return partes.join("\n")
}

async function lerCorpo(req: any): Promise<any> {
  const partes: Buffer[] = []
  for await (const p of req) partes.push(Buffer.from(p))
  if (!partes.length) return {}
  try {
    return JSON.parse(Buffer.concat(partes).toString("utf-8"))
  } catch {
    return {}
  }
}

function json(res: any, code: number, obj: unknown) {
  const buf = Buffer.from(JSON.stringify(obj), "utf-8")
  res.writeHead(code, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": buf.length,
    "Access-Control-Allow-Origin": "*",
  })
  res.end(buf)
}

/** Monta o texto de resposta que o MCP devolve ao modelo. */
function formatar(perfis: any[], respostas: any[], pergunta: string): string {
  const ok = respostas.filter((r) => r?.ok).length
  const linhas = [
    `${ok}/${perfis.length} agentes responderam. Pergunta: ${pergunta.slice(0, 200)}`,
    "",
  ]
  for (let i = 0; i < perfis.length; i++) {
    const p = perfis[i]
    const r = respostas[i]
    const nome = p.nome ?? p.id
    if (!r?.ok) {
      linhas.push(`## ${nome} (${p.id})`)
      linhas.push(`(FALHOU: ${String(r?.erro ?? "sem resposta").slice(0, 160)})`)
      linhas.push("")
      continue
    }
    linhas.push(`## ${nome} (${p.id})`)
    linhas.push(String(r.texto ?? r.resposta ?? r.conteudo ?? "").trim())
    linhas.push("")
  }
  // DEFECT #8: perder um agente e perder uma LENTE. Dizer isso explicitamente
  // e o que impede o modelo de tratar 7 de 10 como se fosse 10 de 10.
  if (ok < perfis.length) {
    linhas.push(
      `ATENCAO: ${perfis.length - ok} lente(s) FALHARAM (acima marcadas como ` +
        `FALHOU). O que nao aparece aqui nao foi analisado — trate como lacuna, ` +
        `nao como "nenhum problema encontrado".`,
    )
    linhas.push("")
  }
  linhas.push(
    "LEIA COMO DIVERGENCIA, NAO COMO CONSENSO: onde os agentes discordam esta " +
      "o valor; onde todos concordam, provavelmente e verdade. Confirme com " +
      "read_file qualquer achado que vá causar mudanca de codigo.",
  )
  return linhas.join("\n")
}

/**
 * Formata o contexto de uma tarefa para o executor que acabou de pegar.
 *
 * Este e o momento da "conversa": quem pegou a tarefa NAO viu a discussao
 * original, mas ve o que quem produziu aquele achado escreveu. Sem isto, o
 * board seria so uma fila de ordens, e o executor repetiria trabalho ja
 * feito.
 */
function formatarContexto(ctx: any): string {
  const t = ctx.tarefa
  const L: string[] = []
  L.push(`TAREFA ${t.id}`)
  L.push(`Titulo: ${t.titulo}`)
  L.push(`Origem: ${t.origem}`)
  if (t.arquivos?.length) L.push(`Arquivos: ${t.arquivos.join(", ")}`)
  L.push(`Tentativas anteriores: ${t.tentativas - 1}`)
  if (t.tentativas > 1) L.push("  (alguem ja tentou. Leia os artefatos abaixo antes de repetir.)")
  if (t.erro) L.push(`Ultimo erro: ${t.erro}`)
  L.push("")
  L.push("PEDIDO:")
  L.push(t.pedido)
  L.push("")

  if (ctx.artefatos?.length) {
    L.push(`O QUE OUTROS JA FIZERAM (${ctx.artefatos.length} artefato(s)):`)
    for (const a of ctx.artefatos) {
      L.push("")
      L.push(`- [${a.tipo}] ${a.titulo} — por ${a.autor}`)
      if (a.caminho) L.push(`  arquivo: ${a.caminho}`)
      L.push(`  ${a.conteudo}`)
    }
    L.push("")
  }

  if (ctx.eventos?.length) {
    L.push("HISTORICO:")
    for (const e of ctx.eventos.slice(-8)) {
      L.push(`  ${new Date(e.em).toISOString().slice(11, 19)} ${e.tipo}${e.quem ? ` (${e.quem})` : ""}${e.detalhe ? `: ${e.detalhe.slice(0, 100)}` : ""}`)
    }
    L.push("")
  }

  L.push(
    "Para terminar: `write_file` para gravar, rode a verificacao do projeto, " +
      "depois `cluster_board_concluir` com o comando que rodou e a saida. " +
      "Se nao conseguir verificar, use `cluster_board_falhar` dizendo o motivo — " +
      "devolver a fila e melhor que concluir nao verificado.",
  )
  return L.join("\n")
}

const server = createServer(async (req, res) => {
  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "content-type",
    })
    res.end()
    return
  }

  if (req.method === "GET" && req.url === "/health") {
    json(res, 200, { ok: true, perfis: PERFIS.length })
    return
  }

  if (req.method === "POST" && req.url === "/consultar") {
    const body = await lerCorpo(req)
    const pergunta = String(body.pergunta ?? "").trim()
    if (!pergunta) {
      json(res, 400, { erro: "pergunta obrigatoria" })
      return
    }
    const n = Math.min(Math.max(Number(body.n ?? 10) || 10, 1), PERFIS.length)
    const orcamento = Number(body.orcamento ?? 3000)
    const arquivos: string[] = Array.isArray(body.arquivos) ? body.arquivos : []

    // `fatiaDe` le o arquivo e devolve o prompt com o CONTEUDO. Sem isso os
    // agentes nao veem o codigo (ver o comentario la em cima).
    ;(globalThis as any).__arquivos = arquivos

    const perfis = PERFIS.slice(0, n)
    log(
      `consultar: ${n} agentes, orcamento=${orcamento}, ` +
        `${arquivos.length} arquivo(s), ${pergunta.length} chars`,
    )
    const t0 = Date.now()
    try {
      const r = await consultarTodos(perfis, pergunta, {
        orcamento,
        montarPrompt: (idx: number, p: any) => fatiaDe(idx, p, pergunta),
      })
      const dt = ((Date.now() - t0) / 1000).toFixed(1)
      log(`concluido em ${dt}s — ${r.ok}/${r.total} ok`)
      json(res, 200, {
        texto: formatar(perfis, r.respostas, pergunta),
        segundos: Number(dt),
        ok: r.ok,
        total: r.total,
      })
    } catch (e: any) {
      log("falhou: " + (e?.message ?? e))
      json(res, 200, {
        texto:
          `ERRO do motor: ${e?.message ?? e}. ` +
          `Os ${perfis.length} agentes foram disparados mas a consulta nao terminou.`,
      })
    }
    return
  }

  if (req.method === "POST" && req.url === "/prontidao") {
    json(res, 200, {
      texto:
        `motor de pe. ${TAMANHO_EQUIPE} papeis disponiveis em ${TAMANHO_EQUIPE} lentes. ` +
        `Perfis de ciclo: ${Object.keys(PERFIS_CICLO).join(", ")}. ` +
        `Orcamento padrao: ${ORCAMENTO_PADRAO} tokens.`,
    })
    return
  }

  if (req.method === "GET" && req.url === "/perfis") {
    json(res, 200, {
      equipe: TAMANHO_EQUIPE,
      orcamentoPadrao: ORCAMENTO_PADRAO,
      perfis: PERFIS_CICLO,
      lentes: PERFIS.map((p) => ({ id: p.id, nome: p.nome })),
    })
    return
  }

  if (req.method === "POST" && req.url === "/ciclo") {
    const body = await lerCorpo(req)
    const pedido = String(body.pedido ?? body.pergunta ?? "").trim()
    if (!pedido) {
      json(res, 400, { erro: "pedido obrigatorio" })
      return
    }
    const perfil = (body.perfil ?? "padrao") as any
    const trilha = new Trilha(TRILHA_PADRAO)
    const t0 = Date.now()
    log(`ciclo: perfil=${perfil} pedido="${pedido.slice(0, 70)}"`)
    try {
      const r = await rodarCiclo({
        pedido,
        arquivos: Array.isArray(body.arquivos) ? body.arquivos : [],
        perfil,
        trilha,
        ...(body.id ? { id: String(body.id) } : {}),
        ...(body.orcamento ? { orcamento: Number(body.orcamento) } : {}),
      })
      log(
        `ciclo concluido em ${r.duracaoSegundos.toFixed(1)}s — ` +
          `trilha ${r.id} v${r.versao}`,
      )
      json(res, 200, {
        texto: entregarCiclo(r.checkpoint, r.duracaoSegundos, r.perfilUsado),
        id: r.id,
        versao: r.versao,
        segundos: Number(r.duracaoSegundos.toFixed(1)),
        relatorio: `${TRILHA_PADRAO}/${r.id}/v${r.versao}.md`,
      })
    } catch (e: any) {
      log("ciclo falhou: " + (e?.message ?? e))
      json(res, 200, {
        texto:
          `ERRO do ciclo: ${e?.message ?? e}. ` +
          `Nada foi entregue; a trilha anterior (se houver) segue valendo.`,
      })
    }
    return
  }

  if (req.method === "GET" && req.url?.startsWith("/trilha")) {
    const id = decodeURIComponent(req.url.split("/").pop() ?? "")
    const trilha = new Trilha(TRILHA_PADRAO)
    const cp = trilha.carregar(id)
    if (!cp) {
      json(res, 200, { texto: `Nao achei a trilha "${id}". ${trilha.listar().length} trilha(s) existem.` })
      return
    }
    json(res, 200, {
      texto: trilha.relatorio(cp),
      id: cp.id,
      versao: cp.versao,
      versoes: trilha.versoes(id),
    })
    return
  }

  if (req.method === "GET" && req.url?.startsWith("/board")) {
    // MEDIDO: `const [, acao] = url.split("/")` pegava "board", nao "tarefas"
    // — `acao` era o NOME do recurso, e o prefixo `board` ja estava em
    // `acao`. Resultado: /board/tarefas caia no resumo e devolvia o JSON
    // errado sem erro nenhum. E o POST usava `[2]` e funcionava, entao os
    // dois verbos discordavam. Agora os dois usam o mesmo indice.
    const partes = req.url.split("?")[0].split("/")
    const acao = partes[2]
    const b = board()
    // GET /board            -> resumo
    // GET /board/tarefas    -> lista (com ?status=)
    // GET /board/contexto?id -> tarefa + artefatos de quem trabalhou nela
    if (acao === "tarefas") {
      const q = new URL(req.url, "http://x").searchParams
      const status = q.get("status") as any
      const lista = b.listar(status)
      return json(res, 200, {
        texto:
          lista.length === 0
            ? `Nenhuma tarefa${status ? ` com status ${status}` : ""}.`
            : lista
                .map((t) => {
                  const dono = t.claimedPor ? ` <- ${t.claimedPor}` : ""
                  return `[${t.status}] ${t.id} ${t.titulo}${dono}\n    ${t.pedido.slice(0, 200)}`
                })
                .join("\n"),
        tarefas: lista,
      })
    }
    if (acao === "contexto") {
      const id = new URL(req.url, "http://x").searchParams.get("id") ?? ""
      const ctx = b.contexto(id)
      if (!ctx) return json(res, 200, { texto: `Tarefa ${id} nao existe.` })
      return json(res, 200, { texto: formatarContexto(ctx), contexto: ctx })
    }
    const g = b.guarda()
    return json(res, 200, {
      texto:
        b.resumo() +
        `\nORCAMENTO: ${b.orcamento.maxTarefas} tarefas, ${b.orcamento.maxTurnos} turnos, ` +
        `${Math.round(b.orcamento.wallClockMs / 60000)} min de parede` +
        (g.pode ? "" : `\nTRAVA ATIVA: ${g.motivo}`),
      pode: g.pode,
      usados: g.usados,
    })
  }

  if (req.method === "POST" && req.url?.startsWith("/board/")) {
    const acao = req.url.split("/")[2]
    const body = await lerCorpo(req)
    const b = board()
    const quem = String(body.quem ?? "desconhecido")
    const g = b.guarda()

    // A trava de custo vale para DISPARAR TAREFA, nao so para completar.
    // Se o ciclo automatico estourou o orcamento, ele nao cria mais fila —
    // senao "parou" so significa "parou de consumir", e a fila continua
    // crescendo para quando alguem voltar.
    if (acao === "criar" && !g.pode && body.automatico) {
      return json(res, 200, {
        texto:
          `TRAVA DE CUSTO ATIVA: ${g.motivo}. ` +
          `A tarefa NAO foi criada. Consuma o que ja existe ou suba o orcamento.`,
        criada: false,
        motivo: g.motivo,
      })
    }

    switch (acao) {
      case "criar": {
        const t = b.criarTarefa({
          titulo: String(body.titulo ?? "(sem titulo)"),
          pedido: String(body.pedido ?? ""),
          origem: String(body.origem ?? "manual"),
          arquivos: Array.isArray(body.arquivos) ? body.arquivos : [],
        })
        // Ligar o achado que gerou a tarefa. Sem isto, quem for executar ve
        // a ORDEM mas nao o raciocinio de quem achou — e o board vira fila
        // de ordens em vez de conversa.
        const ligados: string[] = []
        for (const aid of Array.isArray(body.artefatos) ? body.artefatos : []) {
          const conteudo = String(
            (b as any).conteudoArtefato?.(String(aid)) ?? "(artefato nao encontrado)",
          )
          const copiado = b.publicar({
            tipo: "achado",
            autor: String(body.autor ?? body.quem ?? "desconhecido"),
            titulo: `[da tarefa] ${String(body.titulo ?? "")}`.slice(0, 110),
            conteudo,
            tarefa: t.id,
          })
          ligados.push(copiado.id)
        }
        return json(res, 200, {
          texto:
            `Tarefa criada: ${t.id}\n${t.titulo}\n\n${t.pedido}` +
            (ligados.length ? `\n\n${ligados.length} artefato(s) ligado(s) — quem executar vai ler o raciocinio.` : ""),
          tarefa: t,
        })
      }
      case "pegar": {
        const t = b.pegarTarefa(quem)
        if (!t) {
          const r = b.resumo()
          return json(res, 200, {
            texto: `Nenhuma tarefa aberta para voce agora.\n\n${r}\n\nSe a fila esta vazia e havia trabalho esperado, o ciclo nao despachou — diga isso em vez de inventar tarefa.`,
            tarefa: null,
          })
        }
        // O contexto vem JUNTO com a captura: o executor precisa do que os
        // outros produziram para nao refazer o que ja foi feito.
        const ctx = b.contexto(t.id)!
        return json(res, 200, { texto: formatarContexto(ctx), tarefa: t })
      }
      case "publicar": {
        // `autor` e `quem` sao o mesmo campo. Medido: aceitar so `quem`
        // fazia quem chamasse com `autor` (que e o nome natural, e o que o
        // artefato CHAMA) receber "autor=desconhecido" — e a autoria
        // perdida e justamente o que torna a cadeia rastreavel.
        const autor = String(body.autor ?? body.quem ?? "desconhecido")
        const a = b.publicar({
          tipo: (body.tipo ?? "nota") as any,
          autor,
          titulo: String(body.titulo ?? ""),
          conteudo: String(body.conteudo ?? ""),
          ...(body.tarefa ? { tarefa: String(body.tarefa) } : {}),
          ...(body.caminho ? { caminho: String(body.caminho) } : {}),
        })
        return json(res, 200, {
          texto: `Artefato ${a.id} publicado (${a.tipo}) por ${autor}: ${a.titulo}`,
          artefato: a,
        })
      }
      case "concluir": {
        const ok = b.concluir(String(body.tarefa ?? ""), quem, String(body.resultado ?? ""))
        return json(res, 200, {
          texto: ok
            ? `Tarefa ${body.tarefa} concluida.`
            : `Nao consegui concluir ${body.tarefa}: ou nao existe, ou o dono do lease e outro agente.`,
          ok,
        })
      }
      case "falhar": {
        const id = String(body.tarefa ?? "")
        if (!id) {
          // MEDIDO: sem `tarefa`, o log ficava "Falha registrada em undefined"
          // e a tarefa seguia presa em em_andamento ate o lease vencer —
          // ou seja, o chamador achava que devolveu a fila e nao devolveu.
          return json(res, 200, {
            texto:
              "FALTA o campo `tarefa`. Nao registrei nada: sem o id nao da " +
              "para devolver a tarefa a fila. Repita com tarefa=<id>.",
            ok: false,
          })
        }
        b.falhar(id, quem, String(body.erro ?? "sem motivo"))
        return json(res, 200, {
          texto:
            `Falha registrada em ${id}; a tarefa voltou a fila para outro ` +
            `executor tentar (ou foi marcada como falhou apos 3 tentativas).`,
          ok: true,
        })
      }
      case "bloquear": {
        b.bloquear(String(body.tarefa ?? ""), quem, String(body.motivo ?? "sem motivo"))
        return json(res, 200, { texto: `Tarefa ${body.tarefa} bloqueada.`, ok: true })
      }
      case "renovar": {
        const ok = b.renovar(String(body.tarefa ?? ""), quem)
        return json(res, 200, {
          texto: ok
            ? `Lease renovado.`
            : `Nao renovei: a tarefa nao esta em andamento ou o dono e outro agente.`,
          ok,
        })
      }
      default:
        return json(res, 400, { erro: `acao de board desconhecida: ${acao}` })
    }
  }

  json(res, 404, { erro: "rota desconhecida" })
})

server.listen(PORTA, "127.0.0.1", () => {
  log(`ouvindo em http://127.0.0.1:${PORTA} com ${PERFIS.length} perfis`)
})