import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync, writeFileSync } from "fs"
import { join } from "path"

/**
 * 9Router Rotation Plugin
 * 
 * Provides automatic model rotation for 9Router free models.
 * The GRATIS-CODING combo uses round-robin across 7 models from 2 independent connections:
 * - 2 Kiro models (separate connection)
 * - 5 OpenRouter free models (shared connection)
 * 
 * When a model hits 429/402/quota, automatically rotates to the next working model.
 * State is persisted per session to avoid infinite loops.
 */

// GRATIS-CODING combo - verified working models (2026-10-30 / 2026-11-02)
// Inclui kc/openrouter/free e modelos free verificados via 9Router.
const GRATIS_CODING_MODELS = [
  // Prioridade solicitada pelo usuario:
  "9router/kc/openrouter/free",
  // Kiro models (independent connection via cl/ prefix)
  "9router/cl/anthropic/claude-sonnet-4.5",
  "9router/cl/anthropic/claude-sonnet-4",
  // OpenRouter free models (shared connection via 9Router)
  "9router/openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
  "9router/openrouter/cohere/north-mini-code:free",
  "9router/openrouter/nvidia/nemotron-3-super-120b-a12b:free",
  "9router/openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
  "9router/openrouter/poolside/laguna-s-2.1:free",
  "9router/openrouter/nvidia/nemotron-3.5-lightning:free",
] as const

// Full fallback chain including 9router + github-copilot
const FALLBACK_CHAIN = [
  // 9router GRATIS-CODING combo (round-robin)
  ...GRATIS_CODING_MODELS,
  // Modelos KC free
  "9router/kc/kilo-auto/free",
  "9router/kc/nvidia/nemotron-3-ultra-550b-a55b:free",
  "9router/kc/nvidia/nemotron-3.5-lightning:free",
  "9router/kc/poolside/laguna-s-2.1:free",
  "9router/kc/cohere/north-mini-code:free",
  "9router/kc/nvidia/nemotron-3-super-120b-a12b:free",
  "9router/kc/thinkingmachines/inkling-small:free",
  "9router/kc/dots-studio/dots-3-note-preview:free",
  "9router/kc/reflection/beam-free",
  "9router/kc/recursive/flint-v1.0:free",
  "9router/kc/xingchen-agi/xing4.0-29b-a4b:free",
  // Novos modelos free (medido 2026-10-30)
  "9router/ocg/space-bunny-free",
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
  // Modelos individuais do 9router (config em opencode.jsonc)
  "9router/openrouter/nvidia/nemotron-3-nano-30b-a3b:free",
  "9router/openrouter/google/gemma-4-26b-a4b-it:free",
  "9router/openrouter/google/gemma-4-31b-it:free",
  "9router/openrouter/poolside/laguna-m.1:free",
  "9router/openrouter/poolside/laguna-xs-2.1:free",
  "9router/openrouter/inclusionai/ling-3.0-flash:free",
  // GitHub Copilot (verified working)
  "github-copilot/gpt-4.1",
  "github-copilot/gpt-4o",
  "github-copilot/gpt-4o-mini",
] as const

type ModelId = typeof FALLBACK_CHAIN[number]

// Session state for rotation tracking
interface SessionState {
  currentIndex: number
  failures: Map<string, number>
  lastRotation: number
  workingModels: Set<string>
}

const sessionStates = new Map<string, SessionState>()

// Persistent cache of model health
const HEALTH_CACHE_FILE = join(
  process.env.APPDATA || "",
  "opencode/9router-health-cache.json"
)

interface HealthCache {
  models: Record<string, { status: "ok" | "fail" | "gone"; lastCheck: number; latency?: number }>
}

function loadHealthCache(): HealthCache {
  try {
    if (existsSync(HEALTH_CACHE_FILE)) {
      return JSON.parse(readFileSync(HEALTH_CACHE_FILE, "utf-8"))
    }
  } catch {}
  return { models: {} }
}

function saveHealthCache(cache: HealthCache): void {
  try {
    writeFileSync(HEALTH_CACHE_FILE, JSON.stringify(cache, null, 2))
  } catch {}
}

function getSessionState(sessionId: string): SessionState {
  let state = sessionStates.get(sessionId)
  if (!state) {
    state = {
      currentIndex: 0,
      failures: new Map(),
      lastRotation: Date.now(),
      workingModels: new Set(GRATIS_CODING_MODELS),
    }
    sessionStates.set(sessionId, state)
  }
  return state
}

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
    m.includes("token limit") ||
    m.includes("404") && (m.includes("unavailable for free") || m.includes("use this slug instead"))
  )
}

// 2026-10-17 BLINDAGEM: paradas no meio do nada + loops de repeticao.
// Medido neste host: modelos :free param sem erro (stream corta) ou
// entram em eco (repetem a mesma palavra). Esses sinais NAO sao
// esgotamento de cota — sao instabilidade do modelo/relay — e o plugin
// antigo ignorava todos eles (so olhava 429/402).
// Sinais cobertos:
//  - stream cortado: "stream closed", "connection reset", "aborted",
//    "truncated", "incomplete", "empty response", "no response"
//  - eco/loop: "repetition", "repetitive", "loop detected", saida com
//    a mesma palavra/frase repetida N vezes (detectado no event text)
function isTruncationError(msg: string): boolean {
  const m = msg.toLowerCase()
  return (
    m.includes("stream closed") ||
    m.includes("stream ended") ||
    m.includes("connection reset") ||
    m.includes("connection aborted") ||
    m.includes("aborted") ||
    m.includes("truncated") ||
    m.includes("incomplete") ||
    m.includes("empty response") ||
    m.includes("no response") ||
    m.includes("no content") ||
    m.includes("stop_reason") && m.includes("error") ||
    m.includes("finish_reason") && m.includes("error") ||
    m.includes("socket hang up") ||
    m.includes("econnreset") ||
    m.includes("etimedout") ||
    m.includes("timeout") && m.includes("stream")
  )
}

// Detecta eco: mesma palavra (4+ letras) repetida 8+ vezes seguidas,
// ou mesma frase (10+ chars) repetida 4+ vezes. Custo O(n), roda so
// no texto do erro/evento (curto), nunca no historico inteiro.
function looksLikeLoop(text: string): boolean {
  if (!text || text.length < 50) return false
  const sample = text.slice(0, 4000)
  if (/\b([a-zA-ZÀ-ÿ]{4,})(\s+\1){7,}/i.test(sample)) return true
  const m = sample.match(/(.{15,80}?)\1{3,}/)
  if (m) return true
  return false
}

function isGoneError(msg: string): boolean {
  return /unavailable for free|use this slug instead|requires a subscription/i.test(msg)
}

function getNextModel(sessionId: string, exclude: Set<string> = new Set()): ModelId | null {
  const state = getSessionState(sessionId)
  const cache = loadHealthCache()
  
  // First try working models from GRATIS-CODING combo
  for (let i = 0; i < GRATIS_CODING_MODELS.length; i++) {
    const idx = (state.currentIndex + i) % GRATIS_CODING_MODELS.length
    const model = GRATIS_CODING_MODELS[idx]
    if (exclude.has(model)) continue
    
    const health = cache.models[model]
    if (health?.status === "gone") continue
    if (health?.status === "fail" && Date.now() - health.lastCheck < 300000) continue // 5 min cooldown
    
    state.currentIndex = (idx + 1) % GRATIS_CODING_MODELS.length
    return model
  }
  
  // Then try full fallback chain
  for (let i = 0; i < FALLBACK_CHAIN.length; i++) {
    const idx = (state.currentIndex + i) % FALLBACK_CHAIN.length
    const model = FALLBACK_CHAIN[idx]
    if (exclude.has(model)) continue
    
    const health = cache.models[model]
    if (health?.status === "gone") continue
    if (health?.status === "fail" && Date.now() - health.lastCheck < 300000) continue
    
    state.currentIndex = (idx + 1) % FALLBACK_CHAIN.length
    return model
  }
  
  return null
}

function recordFailure(sessionId: string, model: string, error: string): void {
  const state = getSessionState(sessionId)
  const count = (state.failures.get(model) || 0) + 1
  state.failures.set(model, count)
  
  const cache = loadHealthCache()
  if (!cache.models[model]) {
    cache.models[model] = { status: "ok", lastCheck: 0 }
  }
  
  if (isGoneError(error)) {
    cache.models[model].status = "gone"
    state.workingModels.delete(model)
  } else if (isTruncationError(error) || looksLikeLoop(error)) {
    // 2026-10-17: corte/loop = instabilidade TRANSIENTE, nao cota.
    // Cooldown curto (60s, nao 5min): o modelo pode voltar no proximo
    // retry, so nao pode ser o retry IMEDIATO (se nao, eco em cima de eco).
    // lastCheck retroativo = 4min atras, restam 60s de cooldown.
    cache.models[model].status = "fail"
    cache.models[model].lastCheck = Date.now() - 240000
  } else {
    cache.models[model].status = "fail"
    cache.models[model].lastCheck = Date.now()
  }
  saveHealthCache(cache)
}

function recordSuccess(model: string, latency: number): void {
  const cache = loadHealthCache()
  if (!cache.models[model]) {
    cache.models[model] = { status: "ok", lastCheck: 0 }
  }
  cache.models[model].status = "ok"
  cache.models[model].lastCheck = Date.now()
  cache.models[model].latency = latency
  saveHealthCache(cache)
}

export default {
  id: "9router-rotation",
  setup: async (api: any) => {
    if (api.tool?.transform) {
      try {
        api.tool.transform((tools: any) => {
          tools.add({
            id: "9router-health-check",
            name: "9Router Health Check",
            description: "Verifica a saúde dos modelos 9Router",
            execute: async () => {
              const cache = loadHealthCache()
              const results = GRATIS_CODING_MODELS.map(model => {
                const health = cache.models[model] || { status: "unknown", lastCheck: 0 }
                return `${health.status === "ok" ? "✅" : health.status === "fail" ? "⚠️" : health.status === "gone" ? "❌" : "❓"} ${model} - ${health.status} (last: ${health.lastCheck ? new Date(health.lastCheck).toLocaleTimeString() : "never"}${health.latency ? `, ${health.latency}ms` : ""})`
              })
              return results.join("\n")
            }
          })

          tools.add({
            id: "9router-rotate",
            name: "9Router Rotate",
            description: "Rotaciona manualmente para o próximo modelo disponível",
            execute: async (input: { sessionId?: string; reason?: string }) => {
              const sessionId = input?.sessionId || "global"
              const state = getSessionState(sessionId)
              const exclude = new Set<string>()
              for (const [model, failures] of state.failures) {
                if (failures > 0) exclude.add(model)
              }
              const nextModel = getNextModel(sessionId, exclude)
              if (nextModel) {
                try {
                  if (api.session?.update) {
                    await api.session.update(sessionId, { model: nextModel })
                  }
                  return `Rotated to ${nextModel}${input?.reason ? ` (reason: ${input.reason})` : ""}`
                } catch {
                  return `Next model would be ${nextModel}, but auto-update failed.`
                }
              }
              return "No available models to rotate to!"
            }
          })

          tools.add({
            id: "9router-reset",
            name: "9Router Reset",
            description: "Reseta o estado de rotação",
            execute: async (input: { sessionId?: string }) => {
              const sessionId = input?.sessionId || "global"
              sessionStates.delete(sessionId)
              return `Rotation state reset for session ${sessionId}`
            }
          })
        })
      } catch {}
    }

    if (api.event?.subscribe) {
      try {
        api.event.subscribe(async (event: any) => {
          const e: any = event as any
          const props = e?.properties ?? e?.data ?? {}
          const error = (props?.error ?? props?.message ?? e?.error ?? "") as string
          const sessionId = props?.sessionID ?? e?.sessionID ?? "global"

          const eventText = String(
            props?.text ?? props?.output ?? props?.content ?? props?.delta ?? ""
          )
          const errStr = String(error ?? "")
          const loopByText = looksLikeLoop(eventText) || looksLikeLoop(errStr)
          const isTrunc = isTruncationError(errStr)
          const isExh = isExhaustionError(errStr)

          if (!errStr && !loopByText) return
          if (!isExh && !isTrunc && !loopByText) return

          const cause = !isExh && (isTrunc || loopByText)
            ? (loopByText ? "loop/eco" : "stream cortado")
            : "cota/erro"

          const currentModel = (props?.model ?? e?.model ?? "") as string
          if (currentModel) {
            recordFailure(sessionId, currentModel, error)
          }

          const state = getSessionState(sessionId)
          const count = (state.failures.get(currentModel) || 0)
          const exclude = new Set<string>()
          for (const [model, failures] of state.failures) {
            if (failures > 0) exclude.add(model)
          }

          const nextModel = getNextModel(sessionId, exclude)
          if (nextModel) {
            console.error(
              `[9router-rotation] Session ${sessionId}: ${currentModel} falhou por ${cause} (${errStr.slice(0, 100)}). ` +
              `Rotating to ${nextModel} (attempt ${count})`
            )
            try {
              if (api.session?.update) {
                await api.session.update(sessionId, { model: nextModel })
              }
            } catch {}
          }
        })
      } catch {}
    }
  }
}
