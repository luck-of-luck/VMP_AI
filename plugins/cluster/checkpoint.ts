/**
 * CHECKPOINT e HISTORICO — o que faz o trabalho sobreviver a sessao.
 *
 * DECISAO (2026-10-01): arquivo, nao banco.
 *
 * Por que: quem trabalha com sistema pesado precisa poder ABRIR o estado,
 * comparar versoes e ver o que a equipe mudou. Isso e texto em arquivo, e
 * `git diff` mostra a diferenca. Um SQLite guarda o mesmo dado e entrega
 * uma caixa-preta que nao da para ler no git nem para revisar em code
 * review. Alem disso, rollback ja existe e foi testado (`verify.py`), e
 * depende de arquivos.
 *
 * O que NAO e checkpoint: um resumo de "como foi a discussao". Checkpoint e
 * estado VERIFICAVEL: o que foi feito, o que falta, e o proximo passo
 * exato. Se alguem ler so o checkpoint e conseguir continuar, funcionou.
 */

import { mkdirSync, readFileSync, writeFileSync, existsSync, readdirSync } from "node:fs"
import { join } from "node:path"

export interface Rodada {
  tier: string;
  /** Epoch ms do inicio da rodada. */
  em: number;
  duracaoMs: number;
  /** Quantos papeis foram disparados. */
  chamados: number;
  /** Quantos responderam com texto nao vazio. */
  ok: number;
  /** Ids que NAO responderam — a lacuna, nomeada. */
  calados: string[];
  /** Resposta por papel. */
  respostas: Record<string, string>;
}

export interface Checkpoint {
  id: string;
  criadoEm: string;
  titulo: string;
  /** O que o usuario pediu, literal. */
  pedido: string;
  arquivos: string[];
  rodadas: Rodada[];
  /** Sintese da supervisao, se a rodada de supervisao rodou. */
  supervisao?: string;
  /** O que a equipe DECIDIU, em uma tela. */
  conclusao?: string;
  /** PassosFollowing, cada um verificavel. */
  proximosPassos: string[];
  /** Bloqueios conhecidos. */
  bloqueios: string[];
  /** Numero da versao; permite retomar. */
  versao: number;
}

export class Trilha {
  readonly raiz: string;

  constructor(raiz: string) {
    this.raiz = raiz
    mkdirSync(this.raiz, { recursive: true })
  }

  private dirDe(id: string): string {
    return join(this.raiz, id)
  }

  /**
   * Grava a versao nova sem perder a anterior.
   *
   * DECISAO: versao e arquivo novo, nao sobrescrita. Sobrescrever destroi a
   * pista de como o resultado chegou ate la — e essa pista e metade do
   * valor de um checkpoint. O diff entre v2 e v3 e o que responde "por que
   * isso mudou".
   */
  salvar(cp: Checkpoint): string {
    const d = this.dirDe(cp.id)
    mkdirSync(d, { recursive: true })
    const arq = join(d, `v${cp.versao}.json`)
    writeFileSync(arq, JSON.stringify(cp, null, 2), "utf-8")
    // O ultimo ponto de entrada: qual versao e a viva.
    writeFileSync(join(d, "atual.json"), JSON.stringify({ id: cp.id, versao: cp.versao }), "utf-8")
    return arq
  }

  /** Le a versao mais recente. Devolve null se nao houver trilha. */
  carregar(id: string): Checkpoint | null {
    const d = this.dirDe(id)
    const ptr = join(d, "atual.json")
    if (!existsSync(ptr)) return null
    const { versao } = JSON.parse(readFileSync(ptr, "utf-8"))
    const arq = join(d, `v${versao}.json`)
    if (!existsSync(arq)) return null
    return JSON.parse(readFileSync(arq, "utf-8")) as Checkpoint
  }

  versoes(id: string): number[] {
    const d = this.dirDe(id)
    if (!existsSync(d)) return []
    return readdirSync(d)
      .map((n) => /^v(\d+)\.json$/.exec(n))
      .filter((m): m is RegExpMatchArray => m !== null)
      .map((m) => Number(m[1]))
      .sort((a, b) => a - b)
  }

  /** Trilhas conhecidas. */
  listar(): string[] {
    if (!existsSync(this.raiz)) return []
    return readdirSync(this.raiz, { withFileTypes: true })
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
  }

  /**
   * Relatorio legivel do checkpoint. Isto e o que um humano (ou um agente
   * novo) le na manha seguinte.
   */
  relatorio(cp: Checkpoint): string {
    const L: string[] = []
    L.push(`# ${cp.titulo}`)
    L.push("")
    L.push(`- trilha: ${cp.id}  (v${cp.versao})`)
    L.push(`- criado: ${cp.criadoEm}`)
    L.push(`- pedido: ${cp.pedido}`)
    if (cp.arquivos.length) L.push(`- material: ${cp.arquivos.join(", ")}`)
    L.push("")
    L.push("## Rodadas")
    for (const r of cp.rodadas) {
      const s = (r.duracaoMs / 1000).toFixed(1)
      L.push(`- ${r.tier}: ${r.ok}/${r.chamados} em ${s}s`)
      if (r.calados.length) L.push(`  - CALADOS: ${r.calados.join(", ")}`)
    }
    if (cp.supervisao) {
      L.push("")
      L.push("## Supervisao")
      L.push(cp.supervisao)
    }
    if (cp.conclusao) {
      L.push("")
      L.push("## Conclusao")
      L.push(cp.conclusao)
    }
    if (cp.proximosPassos.length) {
      L.push("")
      L.push("## Proximos passos")
      for (const p of cp.proximosPassos) L.push(`1. ${p}`)
    }
    if (cp.bloqueios.length) {
      L.push("")
      L.push("## Bloqueios")
      for (const b of cp.bloqueios) L.push(`- ${b}`)
    }
    L.push("")
    L.push("---")
    L.push(
      "Se voce leu so isto e consegue continuar o trabalho, o checkpoint " +
        "funcionou. Se nao, falta informacao aqui.",
    )
    return L.join("\n")
  }

  /** Escreve o relatorio legivel ao lado do JSON. */
  salvarRelatorio(cp: Checkpoint): string {
    const arq = join(this.dirDe(cp.id), `v${cp.versao}.md`)
    writeFileSync(arq, this.relatorio(cp), "utf-8")
    return arq
  }
}

/** Id curto e ordenavel por tempo: 20261003-143022-a1b2. */
export function novoId(titulo: string): string {
  const d = new Date()
  const p = (n: number, w = 2) => String(n).padStart(w, "0")
  const carimbo = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`
  // 4 chars do titulo, para o nome da pasta dizer do que se trata.
  const tag = titulo
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 12)
  const aleatorio = Math.random().toString(36).slice(2, 6)
  return tag ? `${carimbo}-${tag}-${aleatorio}` : `${carimbo}-${aleatorio}`
}