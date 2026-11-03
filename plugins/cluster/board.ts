/**
 * BOARD — a loja de artefatos onde os executores se encontram.
 *
 * POR QUE ISTO E O MEIO, E NAO UMA RESPOSTA DIRETA
 * Executores sao processos OpenCode separados. Nao existe chamada entre eles.
 * A unica coisa que eles compartilham e o disco. Entao o board e o meio: o
 * executor A publica um artefato, o B le. Isso e Limitacao real de
 * arquitetura, e fingir que eles "conversam" seria teatro.
 *
 * O QUE FAZ ISSO SER CONVERSA E NAO FILA
 * Um achado do ciclo vira tarefa com `origem` apontando a lente que o
 * achou. O executor B recebe a tarefa e os artefatos de quem a produziu, sem
 * nunca ter visto a conversa original. E assim que funciona revisao de
 * verdade: quem encontra nao e quem conserta, e o segundo ve o raciocinio do
 * primeiro, nao so o achado.
 *
 * LEASE: POR QUE EXISTE
 * Sem lease, um executor que morre (Ctrl+C, crash, sessao fechada) deixa a
 * tarefa presa em `em_andamento` para sempre e a fila morre com ela. Entao
 * toda captura tem prazo. Passou o prazo sem `concluir`, a tarefa volta
 * para `aberta` — e o log registra que voltou, para ninguem achar que
 * ninguem fez.
 *
 * A TRAVA DE CUSTO
 * Ciclo autonomo significa 20 minutos rodando sem ninguem perguntando. Isso
 * precisa de tres limites explicitos, todos em `Orcamento`:
 *   - `maxTarefas`: quantas tarefas o ciclo automático pode pegar.
 *   - `wallClockMs`: quanto tempo pode passar no total.
 *   - `maxTurnos`: quantas rodadas de execucao.
 * Um deles estourado e o ciclo PARA e registra o motivo. Limite que nao
 * existe nao e limite.
 */

import { mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

export type StatusTarefa = "aberta" | "em_andamento" | "bloqueada" | "concluida" | "falhou"

export type TipoArtefato =
  | "achado"
  | "patch"
  | "teste"
  | "print"
  | "log"
  | "nota"
  | "erro"

export interface Artefato {
  id: string
  tipo: TipoArtefato
  /** A qual tarefa pertence (opcional: achado solto). */
  tarefa?: string
  /** Quem produziu: id do executor. */
  autor: string
  titulo: string
  conteudo: string
  /** Para patch: caminho absoluto do arquivo tocado. */
  caminho?: string
  criadoEm: number
}

export interface Tarefa {
  id: string
  titulo: string
  /** O que fazer, com detalhe suficiente para outro agente executar sem contexto. */
  pedido: string
  /** De onde veio: `ciclo:<id>` ou `lente:<id>`. Permite rastrear quem achou. */
  origem: string
  /** Caminhos que o executor deve ler. */
  arquivos: string[]
  status: StatusTarefa
  /** Quem pegou. */
  claimedPor?: string
  /** Epoch ms ate quando a captura vale. */
  leaseAte?: number
  tentativas: number
  /** Ids dos artefatos ligados a esta tarefa. */
  artefatos: string[]
  resultado?: string
  erro?: string
  criadoEm: number
  atualizadoEm: number
}

export interface Evento {
  em: number
  tipo: string
  tarefa?: string
  quem?: string
  detalhe?: string
}

export interface Orcamento {
  /** Tarefas que o ciclo automatico pode pegar no total. */
  maxTarefas: number
  /** Tempo total de parede. */
  wallClockMs: number
  /** Rodadas de execucao. */
  maxTurnos: number
  /** Lease de captura, em ms. */
  leaseMs: number
}

export const ORCAMENTO_PADRAO_BOARD: Orcamento = {
  maxTarefas: 6,
  wallClockMs: 45 * 60 * 1000,
  maxTurnos: 12,
  leaseMs: 10 * 60 * 1000,
}

const SEG = (n: number) => `${Math.round(n / 1000)}s`

export class Board {
  readonly dir: string
  private estado: { tarefas: Tarefa[]; artefatos: Artefato[]; eventos: Evento[] }

  constructor(dir: string, orcamento?: Partial<Orcamento>) {
    this.dir = dir
    this.orcamento = { ...ORCAMENTO_PADRAO_BOARD, ...orcamento }
    mkdirSync(this.dir, { recursive: true })
    this.estado = { tarefas: [], artefatos: [], eventos: [] }
    this.carregar()
  }

  readonly orcamento: Orcamento

  private get arq(): string {
    return join(this.dir, "board.json")
  }

  private carregar() {
    if (!existsSync(this.arq)) return
    try {
      this.estado = JSON.parse(readFileSync(this.arq, "utf-8"))
      // Migracao: board gravado antes do orcamento existir.
      if (!this.estado.eventos) this.estado.eventos = []
    } catch {
      // Board corrompido: comeca vazio em vez de derrubar o ciclo. O log de
      // eventos preserva a rascunho anterior em board.json.corrompido.
      try {
        writeFileSync(this.arq + ".corrompido", readFileSync(this.arq))
      } catch {}
    }
  }

  private salvar() {
    writeFileSync(this.arq, JSON.stringify(this.estado, null, 2), "utf-8")
  }

  private log(tipo: string, tarefa?: string, quem?: string, detalhe?: string) {
    this.estado.eventos.push({ em: Date.now(), tipo, tarefa, quem, detalhe })
    // O log cresce sem parar num ciclo autonomo. Cortado para os 500 mais
    // recentes: um log que enche o disco derruba o proprio board.
    if (this.estado.eventos.length > 500) {
      this.estado.eventos = this.estado.eventos.slice(-500)
    }
  }

  private novoId(prefixo: string): string {
    return `${prefixo}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
  }

  // ── Tarefas ─────────────────────────────────────────────────────────────

  /** Cria tarefa. Devolve a tarefa pronta. */
  criarTarefa(t: {
    titulo: string
    pedido: string
    origem?: string
    arquivos?: string[]
  }): Tarefa {
    const agora = Date.now()
    const tarefa: Tarefa = {
      id: this.novoId("t"),
      titulo: t.titulo,
      pedido: t.pedido,
      origem: t.origem ?? "manual",
      arquivos: t.arquivos ?? [],
      status: "aberta",
      tentativas: 0,
      artefatos: [],
      criadoEm: agora,
      atualizadoEm: agora,
    }
    this.estado.tarefas.push(tarefa)
    this.log("tarefa_criada", tarefa.id, undefined, tarefa.titulo)
    this.salvar()
    return tarefa
  }

  /**
   * Pega a proxima tarefa disponivel para `quem`.
   *
   * REGRA DE CONCORRENCIA: um processo so. Dois executores sao processos
   * distintos, e o lease garante que so um tem a tarefa — mas nao ha
   * transacao de banco aqui. A janela entre ler e gravar existe. Por isso
   * o lease tem dono e prazo: se dois pegarem a mesma tarefa, o segundo
   * descobre na proxima checagem que o prazo foi roubado e larga. Isso e
   * aceitavel para "um arquivo, uma tarefa" e esta registrado como limite.
   */
  pegarTarefa(quem: string): Tarefa | null {
    this.expirarLeases()
    const agora = Date.now()
    // Prioridade: mais antiga primeiro. Tarefa antiga e tarefa que ninguem
    // pegou — sinal de que algo nela esta errado.
    const livre = this.estado.tarefas
      .filter((t) => t.status === "aberta")
      .sort((a, b) => a.criadoEm - b.criadoEm)[0]
    if (!livre) return null
    livre.status = "em_andamento"
    livre.claimedPor = quem
    livre.leaseAte = agora + this.orcamento.leaseMs
    livre.tentativas += 1
    livre.atualizadoEm = agora
    this.log("tarefa_pegou", livre.id, quem, `lease ate ${new Date(livre.leaseAte).toISOString()}`)
    this.salvar()
    return livre
  }

  /**
   * Devolve a fila as tarefas cujo lease venceu.
   *
   * Este e o ponto em que um executor morto para de travar a fila. E o
   * teste disso existe em `test_board.ts` com o tempo avancado artificialmente
   * — nao espero um executor morrer de verdade para descobrir que o lease
   * funciona.
   */
  expirarLeases(): number {
    const agora = Date.now()
    let n = 0
    for (const t of this.estado.tarefas) {
      if (t.status === "em_andamento" && t.leaseAte && t.leaseAte < agora) {
        const dono = t.claimedPor
        t.status = "aberta"
        t.claimedPor = undefined
        t.leaseAte = undefined
        t.atualizadoEm = agora
        n++
        this.log("lease_expirou", t.id, dono, `devolvida a fila apos ${SEG(this.orcamento.leaseMs)}`)
      }
    }
    if (n) this.salvar()
    return n
  }

  /** Estende o lease (o executor esta vivo e trabalhando). */
  renovar(tarefaId: string, quem: string): boolean {
    const t = this.estado.tarefas.find((x) => x.id === tarefaId)
    if (!t || t.status !== "em_andamento") return false
    // So o dono renova. Se nao for o dono, o lease foi roubado e o
    // executor antigo tem de saber disso.
    if (t.claimedPor !== quem) {
      this.log("renovacao_negada", tarefaId, quem, `dono atual e ${t.claimedPor}`)
      this.salvar()
      return false
    }
    t.leaseAte = Date.now() + this.orcamento.leaseMs
    t.atualizadoEm = Date.now()
    this.log("lease_renovado", tarefaId, quem)
    this.salvar()
    return true
  }

  concluir(tarefaId: string, quem: string, resultado: string): boolean {
    const t = this.estado.tarefas.find((x) => x.id === tarefaId)
    if (!t) return false
    if (t.claimedPor && t.claimedPor !== quem) {
      this.log("conclusao_negada", tarefaId, quem, `dono atual e ${t.claimedPor}`)
      this.salvar()
      return false
    }
    t.status = "concluida"
    t.resultado = resultado
    t.leaseAte = undefined
    t.atualizadoEm = Date.now()
    this.log("tarefa_concluida", tarefaId, quem, resultado.slice(0, 120))
    this.salvar()
    return true
  }

  falhar(tarefaId: string, quem: string, erro: string): boolean {
    const t = this.estado.tarefas.find((x) => x.id === tarefaId)
    if (!t) return false
    // So falha para `falhou` se ja tentou demais. Antes disso, volta para
    // aberta: talvez outro executor consiga.
    const esgotou = t.tentativas >= 3
    t.status = esgotou ? "falhou" : "aberta"
    t.erro = erro
    t.claimedPor = undefined
    t.leaseAte = undefined
    t.atualizadoEm = Date.now()
    this.log(esgotou ? "tarefa_falhou" : "tarefa_devolvida", tarefaId, quem, erro.slice(0, 160))
    this.salvar()
    return true
  }

  bloquear(tarefaId: string, quem: string, motivo: string): boolean {
    const t = this.estado.tarefas.find((x) => x.id === tarefaId)
    if (!t) return false
    t.status = "bloqueada"
    t.erro = motivo
    t.claimedPor = undefined
    t.leaseAte = undefined
    t.atualizadoEm = Date.now()
    this.log("tarefa_bloqueada", tarefaId, quem, motivo.slice(0, 160))
    this.salvar()
    return true
  }

  // ── Artefatos ───────────────────────────────────────────────────────────

  publicar(a: {
    tipo: TipoArtefato
    autor: string
    titulo: string
    conteudo: string
    tarefa?: string
    caminho?: string
  }): Artefato {
    const art: Artefato = {
      id: this.novoId("a"),
      tipo: a.tipo,
      autor: a.autor,
      titulo: a.titulo,
      conteudo: a.conteudo,
      ...(a.tarefa ? { tarefa: a.tarefa } : {}),
      ...(a.caminho ? { caminho: a.caminho } : {}),
      criadoEm: Date.now(),
    }
    this.estado.artefatos.push(art)
    if (a.tarefa) {
      const t = this.estado.tarefas.find((x) => x.id === a.tarefa)
      if (t) t.artefatos.push(art.id)
    }
    this.log("artefato", a.tarefa, a.autor, `${a.tipo}: ${a.titulo}`)
    this.salvar()
    return art
  }

  /** Lê uma tarefa com TODO o material de quem trabalhou nela antes. */
  contexto(tarefaId: string): {
    tarefa: Tarefa
    artefatos: Artefato[]
    eventos: Evento[]
  } | null {
    const tarefa = this.estado.tarefas.find((t) => t.id === tarefaId)
    if (!tarefa) return null
    const artefatos = this.estado.artefatos.filter(
      (a) => a.tarefa === tarefaId || tarefa.artefatos.includes(a.id),
    )
    const eventos = this.estado.eventos.filter((e) => e.tarefa === tarefaId)
    return { tarefa, artefatos, eventos }
  }

  listar(status?: StatusTarefa): Tarefa[] {
    this.expirarLeases()
    return status ? this.estado.tarefas.filter((t) => t.status === status) : [...this.estado.tarefas]
  }

  resumo(): string {
    this.expirarLeases()
    const por: Record<string, number> = {}
    for (const t of this.estado.tarefas) por[t.status] = (por[t.status] ?? 0) + 1
    const linhas = [
      `BOARD: ${this.estado.tarefas.length} tarefa(s), ${this.estado.artefatos.length} artefato(s), ${this.estado.eventos.length} evento(s)`,
    ]
    for (const [k, v] of Object.entries(por)) linhas.push(`  ${k.padEnd(13)} ${v}`)
    const ativas = this.estado.tarefas.filter((t) => t.status === "em_andamento")
    if (ativas.length) {
      linhas.push("")
      linhas.push("EM ANDAMENTO:")
      for (const t of ativas) {
        const resta = Math.max(0, (t.leaseAte ?? 0) - Date.now())
        linhas.push(`  ${t.id} <- ${t.claimedPor} (lease ${SEG(resta)} restantes) ${t.titulo}`)
      }
    }
    return linhas.join("\n")
  }

  /** Le um artefato pelo id. Usado para ligar achado a tarefa. */
  conteudoArtefato(id: string): string | null {
    const a = this.estado.artefatos.find((x) => x.id === id)
    return a ? `${a.tipo}: ${a.titulo} — por ${a.autor}\n${a.conteudo}` : null
  }

  /** Tipos de evento registrados, para diagnostico e teste. */
  logTipos(): string[] {
    return [...new Set(this.estado.eventos.map((e) => e.tipo))]
  }

  /** Ultimos eventos, para o relatorio. */
  ultimosEventos(n = 20): Evento[] {
    return this.estado.eventos.slice(-n)
  }

  // ── Trava de custo ──────────────────────────────────────────────────────

  /**
   * O ciclo automatico pode continuar?
   *
   * Isto e o que impede "rodar sozinho para sempre". Tres limites, e o
   * ciclo para quando QUALQUER um estourar — com o motivo registrado, para
   * que o relatorio diga qual.
   */
 guarda(): { pode: boolean; motivo?: string; usados: { tarefas: number; turnos: number; ms: number } } {
    this.expirarLeases()
    const inicio = this.estado.eventos[0]?.em ?? Date.now()
    const feitas = this.estado.tarefas.filter((t) => t.status === "concluida" || t.status === "falhou")
      .length
    const turnos = this.estado.eventos.filter((e) => e.tipo === "tarefa_pegou").length
    const ms = Date.now() - inicio
    const usados = { tarefas: feitas, turnos, ms }

    if (feitas >= this.orcamento.maxTarefas) {
      return { pode: false, motivo: `limite de tarefas (${this.orcamento.maxTarefas})`, usados }
    }
    if (turnos >= this.orcamento.maxTurnos) {
      return { pode: false, motivo: `limite de turnos (${this.orcamento.maxTurnos})`, usados }
    }
    if (ms >= this.orcamento.wallClockMs) {
      return { pode: false, motivo: `tempo de parede (${SEG(this.orcamento.wallClockMs)})`, usados }
    }
    return { pode: true, usados }
  }
}