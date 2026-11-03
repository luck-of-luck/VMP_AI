import { readFileSync, existsSync } from "fs"
import { join } from "path"

/**
 * Codex Swarm Plugin (2026-10-18)
 *
 * 5 contas OAuth ChatGPT no provider "codex" do 9Router, round-robin por
 * requisição. Este plugin expõe o status do swarm direto no TUI:
 *
 *   /tool codex-swarm-status  — contas ativas + últimas requisições por conta
 *
 * Le o SQLite do 9Router em modo somente-leitura. Nada e escrito, nada de
 * tokens no output.
 */

const DB_PATH = join(
  process.env.APPDATA || "",
  "9router/db/data.sqlite"
)

// better-sqlite3 vem no runtime do 9Router — resolvemos por require absoluto
const BETTER_SQLITE = join(
  process.env.APPDATA || "",
  "9router/runtime/node_modules/better-sqlite3"
)

interface CodexRow {
  timestamp: string
  model: string
  connectionId: string
  status: string
}

interface ConnRow {
  id: string
  email: string
  isActive: number
  priority: number
}

function loadUsage(limit = 20): string {
  if (!existsSync(DB_PATH)) {
    return `Banco do 9Router não encontrado em ${DB_PATH}. 9Router rodando?`;
  }
  try {
    const Database = require(BETTER_SQLITE)
    const db = new Database(DB_PATH, { readonly: true })
    try {
      const conns = db
        .prepare(
          "SELECT id, email, isActive, priority FROM providerConnections WHERE provider='codex' ORDER BY priority"
        )
        .all() as ConnRow[]
      const usage = db
        .prepare(
          "SELECT timestamp, model, connectionId, status FROM usageHistory WHERE provider='codex' ORDER BY id DESC LIMIT ?"
        )
        .all(limit) as CodexRow[]

      const emailOf = new Map(conns.map((c) => [c.id, c.email]))
      const perAccount = new Map<string, number>()
      for (const u of usage) {
        const email = emailOf.get(u.connectionId) || u.connectionId
        perAccount.set(email, (perAccount.get(email) || 0) + 1)
      }

      const lines: string[] = []
      lines.push(`CONTAS CODEX ATIVAS (${conns.filter((c) => c.isActive).length}/${conns.length}):`)
      for (const c of conns) {
        const count = perAccount.get(c.email) || 0
        const bar = "█".repeat(Math.min(count, 30))
        lines.push(
          `  ${c.isActive ? "✅" : "⛔"} #${c.priority} ${c.email} — ${count} reqs recentes ${bar}`
        )
      }
      lines.push("")
      lines.push(`ÚLTIMAS ${usage.length} REQUISIÇÕES (mais recente primeiro):`)
      for (const u of usage) {
        const email = emailOf.get(u.connectionId) || u.connectionId
        lines.push(
          `  ${u.timestamp}  ${u.model}  ->  ${email}  [${u.status}]`
        )
      }
      lines.push("")
      lines.push(
        "Round-robin: cada requisição cai na próxima conta. Subagentes paralelos = contas simultâneas."
      )
      return lines.join("\n")
    } finally {
      db.close()
    }
  } catch (err: any) {
    return `Erro ao ler banco do 9Router: ${err?.message || err}`;
  }
}

export default {
  id: "codex-swarm",
  setup: async (api: any) => {
    if (api.tool?.transform) {
      try {
        api.tool.transform((tools: any) => {
          tools.add({
            id: "codex-swarm-status",
            name: "Codex Swarm Status",
            description: "Codex Swarm — status das 5 contas",
            execute: async () => {
              return loadUsage(20);
            }
          });
        });
      } catch {}
    }
  }
};
