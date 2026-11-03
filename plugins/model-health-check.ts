async function probe(modelId: string, apiKey: string) {
  const t0 = Date.now()
  try {
    const res = await fetch(`${BASE}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: modelId,
        messages: [{ role: "user", content: "Reply with exactly: OK" }],
        max_tokens: 4,
      }),
    })
    const ms = Date.now() - t0
    const body = readBody(await res.text())

    if (res.ok) {
      return {
        model: modelId,
        ok: true,
        verdict: "OK",
        code: res.status,
        ms,
        note: `served_by=${body.servedBy || "?"}`,
      }
    }

    const msg = body.error || ""
    if (res.status === 404 && WENT_PAID.test(msg)) {
      return {
        model: modelId,
        ok: false,
        verdict: "GONE",
        code: res.status,
        ms,
        note: msg.slice(0, 120),
      }
    }
    if (EXHAUSTED.test(msg) || [429, 402, 410, 503, 529].includes(res.status)) {
      return {
        model: modelId,
        ok: false,
        verdict: "FAIL",
        code: res.status,
        ms,
        note: msg.slice(0, 120) || `HTTP ${res.status}`,
      }
    }
    return {
      model: modelId,
      ok: false,
      verdict: "FAIL",
      code: res.status,
      ms,
      note: msg.slice(0, 120) || `HTTP ${res.status}`,
    }
  } catch (e: any) {
    return {
      model: modelId,
      ok: false,
      verdict: "ERROR",
      code: "ERR",
      ms: 0,
      note: e.message,
    }
  }
}

import type { Plugin } from "@opencode-ai/plugin"
import { execSync } from "child_process"
import { readFileSync, existsSync, writeFileSync } from "fs"
import { join } from "path"

const PLUGIN_NAME = "model-health-check"
const REPORT_PATH = join(
  process.env.APPDATA || "",
  "opencode/model-health-report.json"
)

function listConfiguredModels(): string[] {
  try {
    const out = execSync("opencode models 9router", {
      encoding: "utf8",
      maxBuffer: 1024 * 1024,
    })
    return out
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.startsWith("9router/"))
  } catch {
    return []
  }
}

function readBody(raw: string) {
  const out = { servedBy: null as string | null, text: "", error: null as string | null }
  if (/^\s*data:\s*\{/.test(raw)) {
    let text = ""
    for (const line of raw.split(/\r?\n/)) {
      const m = line.match(/^data:\s*(\{.*\})\s*$/)
      if (!m) continue
      try {
        const j = JSON.parse(m[1])
        out.servedBy = out.servedBy || j.model || j.provider || null
        const d = j.choices?.[0]
        const piece = d?.delta?.content ?? d?.message?.content ?? null
        if (typeof piece === "string") text += piece
      } catch { /* skip */ }
    }
    out.text = text.trim()
    return out
  }
  const cleaned = raw.replace(/data:\s*\[DONE\]\s*$/g, "").trim()
  try {
    const j = JSON.parse(cleaned)
    out.servedBy = j.model || j.provider || null
    const d = j.choices?.[0]
    out.text = String(d?.message?.content ?? d?.delta?.content ?? "").trim()
    out.error = j.error ? String(j.error.message ?? JSON.stringify(j.error)) : null
    return out
  } catch { /* fall through */ }
  const errMatch = raw.match(/"message"\s*:\s*"([^"]{10,300})"/)
  out.error = errMatch ? errMatch[1] : raw.replace(/\s+/g, " ").slice(0, 160)
  return out
}

const WENT_PAID = /unavailable for free|use this slug instead|requires a subscription/i
const EXHAUSTED = /429|rate limit|quota|exhausted|credit|402|billing|529|503|overloaded/i
const BASE = "http://localhost:20128/v1"

function loadApiKey(): string | null {
  if (process.env.NINEROUTER_KEY) return process.env.NINEROUTER_KEY
  try {
    const raw = readFileSync(
      "./opencode.jsonc",
      "utf8"
    )
    const m = raw.match(/"apiKey"\s*:\s*"([^"]+)"/)
    if (m) return m[1]
  } catch { /* ignore */ }
  try {
    const Database = require(
      join(process.env.APPDATA || "", "9router/runtime/node_modules/better-sqlite3")
    )
    const DB =
      process.env.NINEROUTER_DB ||
      join(process.env.APPDATA || "", "9router/db/data.sqlite")
    const db = new Database(DB, { readonly: true })
    const row = db
      .prepare("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1")
      .get()
    db.close()
    if (row) return row.key
  } catch { /* ignore */ }
  return null
}

export default {
  id: "model-health-check",
  setup: async (api) => {
    if (api.tool?.transform) {
      try {
        api.tool.transform((tools) => {
          tools.add({
            id: "model-health-check",
            name: "Model Health Check",
            description: "Verifica a saúde dos modelos configurados",
            execute: async () => {
              const apiKey = loadApiKey()
              if (!apiKey) {
                return "Nenhuma API key encontrada. Defina NINEROUTER_KEY ou preencha provider.9router.options.apiKey no opencode.jsonc."
              }

              const models = listConfiguredModels()
              if (!models.length) {
                return "Nenhum modelo 9router encontrado via opencode models 9router."
              }

              const rows = []
              for (const modelId of models) {
                rows.push(await probe(modelId, apiKey))
              }

              const ok = rows.filter((r) => r.ok)
              const gone = rows.filter((r) => r.verdict === "GONE")
              const fail = rows.filter((r) => !r.ok && r.verdict !== "GONE")

              const lines = []
              lines.push("Model Health Check — " + BASE)
              lines.push("Modelos testados: " + rows.length + "\n")
              lines.push(
                "Veredito".padEnd(8) + " " + "HTTP".padEnd(6) + " " + "ms".padEnd(6) + " Modelo"
              )
              lines.push(
                "-".repeat(8) + " " + "-".repeat(6) + " " + "-".repeat(6) + " " + "-".repeat(40)
              )
              for (const r of rows) {
                lines.push(
                  r.verdict.padEnd(8) + " " + String(r.code).padEnd(6) + " " + String(r.ms).padStart(4) + "ms  " + r.model + (r.note ? "  | " + r.note : "")
                )
              }

              lines.push("\n=== DISPONÍVEIS: " + ok.length + "/" + rows.length + " ===")
              ok.forEach((r) => lines.push("  ✅ " + r.model + " (" + r.ms + "ms)"))
              if (gone.length) {
                lines.push("\n=== VIROU PAGO (remover do combo): " + gone.length + " ===")
                gone.forEach((r) => lines.push("  ❌ " + r.model + " — " + r.note))
              }
              if (fail.length) {
                lines.push("\n=== LIMITE ESGOTADO / FALHA: " + fail.length + " ===")
                fail.forEach((r) => lines.push("  ⚠️  " + r.model + " [" + r.code + "] — " + r.note))
              }
              lines.push(
                "\nUm 429 sozinho é transiente. Re-execute antes de remover qualquer modelo por 429."
              )

              const report = {
                generatedAt: new Date().toISOString(),
                base: BASE,
                total: rows.length,
                available: ok.length,
                gonePaid: gone.length,
                failed: fail.length,
                models: rows,
              }
              try {
                writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2))
              } catch { /* ignore write errors */ }

              return lines.join("\n")
            }
          })
        })
      } catch {}
    }
  }
}