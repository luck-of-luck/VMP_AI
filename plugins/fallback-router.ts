import { readFileSync, existsSync } from "fs"

// Fallback inteligente — SSOT é Hermes config.yaml:fallback_model
// Este plugin lê ./config.yaml em tempo de execução
// para adesão fluida: edite só o Hermes, OpenCode segue automaticamente.
// Fallback hardcoded só se o arquivo não existir (primeiro boot).

const PROVIDER_MAP: Record<string, string> = {
  copilot: "github-copilot",
  "opencode-zen": "opencode",
  "opencode-free": "opencode",
  openrouter: "openrouter",
  "9router": "9router",
}

const KNOWN_PROVIDERS = new Set(["github-copilot", "opencode", "openrouter", "9router"])

function loadHermesFallback(): string[] {
  const candidates = [
    "./config.yaml",
    process.env.HERMES_HOME ? `${process.env.HERMES_HOME}/config.yaml` : "",
  ].filter(Boolean) as string[]
  for (const p of candidates) {
    try {
      if (!existsSync(p)) continue
      const txt = readFileSync(p, "utf-8")
      const lines = txt.split(/\r?\n/)
      const chain: string[] = []
      let inFallback = false
      let pendingProvider = ""

      for (const line of lines) {
        if (/^fallback_model:\s*$/.test(line)) {
          inFallback = true
          continue
        }
        if (!inFallback) continue

        if (/^\S/.test(line)) {
          if (chain.length) break
          if (!line.trimStart().startsWith("#")) break
          continue
        }

        const providerMatch = line.match(/^\s*-\s*provider:\s*"?([^"\s]+)"?\s*$/)
        if (providerMatch) {
          pendingProvider = providerMatch[1].trim()
          continue
        }
        const modelMatch = line.match(/^\s*model:\s*"?([^"#]+?)"?\s*(?:#.*)?$/)
        if (modelMatch && pendingProvider) {
          const hermesProvider = pendingProvider
          pendingProvider = ""
          const opencodeProvider = PROVIDER_MAP[hermesProvider]
          if (!opencodeProvider) continue
          if (!KNOWN_PROVIDERS.has(opencodeProvider)) continue
          chain.push(`${opencodeProvider}/${modelMatch[1].trim()}`)
        }
      }
      if (chain.length) return chain
    } catch {}
  }
  return []
}

const HARDCODED = [
  "9router/kc/openrouter/free",
  "9router/openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
  "9router/cl/anthropic/claude-sonnet-4.5",
  "9router/cl/anthropic/claude-sonnet-4",
  "9router/kc/kilo-auto/free",
  "9router/kc/nvidia/nemotron-3-ultra-550b-a55b:free",
  "9router/kc/nvidia/nemotron-3.5-lightning:free",
  "9router/openrouter/cohere/north-mini-code:free",
  "9router/openrouter/nvidia/nemotron-3-super-120b-a12b:free",
  "9router/openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "9router/openrouter/poolside/laguna-s-2.1:free",
  "9router/ocg/space-bunny-free",
  "9router/openrouter/nvidia/nemotron-3.5-lightning:free",
  "9router/openrouter/thinkingmachines/inkling-small:free",
  "9router/openrouter/thinkingmachines/inkling:free",
  "9router/openrouter/dots-studio/dots-3-note-preview:free",
  "9router/openrouter/apodex/apodex-1.1-mini:free",
  "9router/oc/nemotron-3-ultra-free",
  "9router/oc/north-mini-code-free",
  "9router/oc/laguna-s-2.1-free",
  "9router/oc/ling-3.0-flash-free",
  "9router/oc/mimo-v2.5-free",
  "9router/oc/mimo-v2.6-flash-free",
  "9router/oc/longcat-2.5-preview-free",
  "9router/oc/ling-3.0-flash-fin-free",
  "9router/oc/nemotron-3.5-lightning-free",
  "9router/oc/fledge-alpha-free",
  "9router/oc/ling-3.1-flash-free",
  "9router/oc/exo-free",
  "9router/oc/beam-free",
  "9router/oc/nemotron-3.5-super-vl-free",
  "9router/oc/deepseek-v4.1-flash-free",
  "9router/oc/glm-5.3-flash-free",
  "github-copilot/gpt-4.1",
  "github-copilot/gpt-4o",
  "github-copilot/gpt-4o-mini",
]

const FALLBACK_CHAIN = (() => {
  const dynamic = loadHermesFallback()
  return dynamic.length ? dynamic : HARDCODED
})()

function isExhaustionError(msg: string): boolean {
  const m = msg.toLowerCase()
  return (
    m.includes("429") ||
    m.includes("rate limit") ||
    m.includes("quota") ||
    m.includes("credit") ||
    m.includes("402") ||
    m.includes("exhausted") ||
    m.includes("billing") ||
    m.includes("context_length_exceeded") ||
    m.includes("context length") ||
    m.includes("max_tokens") ||
    m.includes("overloaded") ||
    m.includes("529") ||
    m.includes("503") ||
    m.includes("token limit")
  )
}

const sessionFailures = new Map<string, number>()

export default {
  id: "fallback-router",
  setup: async (api: any) => {
    if (api.tool?.transform) {
      try {
        api.tool.transform((tools: any) => {
          tools.add({
            id: "fallback-chain",
            name: "Fallback Chain",
            description: "Cadeia de fallback de modelos ativa",
            execute: async () => {
              const dynamic = loadHermesFallback()
              const source = dynamic.length ? "Hermes config.yaml:fallback_model" : "hardcoded (Hermes inacessível)"
              return [
                `Fonte: ${source}`,
                `Total: ${FALLBACK_CHAIN.length} modelos`,
                "",
                FALLBACK_CHAIN.map((m, i) => `  ${i + 1}. ${m}`).join("\n"),
              ].join("\n")
            }
          })
        })
      } catch {}
    }

    if (api.event?.subscribe) {
      try {
        api.event.subscribe(async (event: any) => {
          const e: any = event as any
          const type = e?.type ?? e?.event ?? ""
          const props = e?.properties ?? e?.data ?? {}
          const error = (props?.error ?? props?.message ?? e?.error ?? "") as string

          if (!error || !isExhaustionError(String(error))) return

          const sessionID = props?.sessionID ?? e?.sessionID ?? "global"
          const count = (sessionFailures.get(sessionID) ?? 0) + 1
          sessionFailures.set(sessionID, count)

          const idx = Math.min(count, FALLBACK_CHAIN.length - 1)
          const nextModel = FALLBACK_CHAIN[idx]
          console.error(
            `[fallback-router] Sessão ${sessionID} esgotou tokens/créditos (${error.slice(0, 120)}). ` +
              `Tentativa ${count} -> próximo modelo: ${nextModel}`
          )

          try {
            if (api.session?.update) {
              await api.session.update(sessionID, { model: nextModel })
            }
          } catch {}
        })
      } catch {}
    }
  }
}