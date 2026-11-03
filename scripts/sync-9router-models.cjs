#!/usr/bin/env node
// Sincroniza TODOS os modelos expostos pelo 9Router (GET /v1/models) para o
// bloco providers["9router"].models do opencode.jsonc.
//
// Por que: o OpenCode v2 só lista modelos de provider customizado que estejam
// declarados no config (não há auto-descoberta para openai-compatible).
//
// Uso:
//   node scripts/sync-9router-models.cjs            # grava (com backup .bak-9router-sync)
//   node scripts/sync-9router-models.cjs --dry-run  # só mostra contagens
//   depois: opencode reload
//
// Env opcionais: NINEROUTER_URL (padrão http://127.0.0.1:20128/v1),
//                NINEROUTER_API_KEY (padrão: settings.apiKey do bloco 9router).
//
// Regras:
// - Modelos declarados à mão no bloco 9router (fora dos marcadores) NÃO são
//   tocados nem duplicados (ex.: cx/* com nome/limites próprios).
// - Tudo entre os marcadores AUTO_START/AUTO_END é regenerado a cada execução.
"use strict"

const fs = require("fs")
const os = require("os")
const path = require("path")

const CONFIG = path.join(os.homedir(), ".config", "opencode", "opencode.jsonc")
const AUTO_START = "// >>> 9router-auto-models (gerado por scripts/sync-9router-models.cjs; nao editar a mao)"
const AUTO_END = "// <<< 9router-auto-models"
const DRY = process.argv.includes("--dry-run")
// IDs seguros para chave JSON e para o seletor "provider/model#variant".
// Inclui [] por causa de variantes como "cx/gpt-5.6-luna[1m]" (contexto 1M).
const SAFE_ID = /^[A-Za-z0-9._~:@\/+\-\[\]]+$/

function fail(msg, cause) {
  const err = new Error(msg, cause ? { cause } : undefined)
  console.error(`[sync-9router] ERRO: ${msg}${cause ? ` (causa: ${cause.message || cause})` : ""}`)
  throw err
}

function findProviderBlock(text) {
  const start = text.indexOf('"9router": {')
  if (start < 0) fail('bloco "9router" nao encontrado em providers')
  const modelsIdx = text.indexOf('"models": {', start)
  if (modelsIdx < 0) fail('bloco "9router".models nao encontrado')
  // Fecha o objeto "models" contando chaves (ignora strings e comentarios //).
  let i = text.indexOf("{", modelsIdx)
  let depth = 0
  let inStr = false
  for (; i < text.length; i++) {
    const ch = text[i]
    if (inStr) {
      if (ch === "\\") i++
      else if (ch === '"') inStr = false
      continue
    }
    if (ch === '"') inStr = true
    else if (ch === "/" && text[i + 1] === "/") i = text.indexOf("\n", i) - 1
    else if (ch === "{") depth++
    else if (ch === "}" && --depth === 0) break
  }
  if (depth !== 0) fail('nao foi possivel fechar o bloco "9router".models')
  return { start, modelsOpen: text.indexOf("{", modelsIdx), modelsClose: i }
}

function readSetting(block, key) {
  const m = block.match(new RegExp(`"${key}"\\s*:\\s*"([^"]+)"`))
  return m ? m[1] : undefined
}

function toEntry(m) {
  const cap = m.capabilities || {}
  const input = ["text"]
  if (cap.vision) input.push("image")
  if (cap.pdf) input.push("pdf")
  if (cap.audioInput) input.push("audio")
  if (cap.videoInput) input.push("video")
  const context = Number(m.context_length || cap.contextWindow) || 128000
  let output = Number(m.max_completion_tokens || cap.maxOutput) || 32000
  if (output > context) output = context
  const capabilities = { tools: cap.tools !== false, input, output: ["text"] }
  if (cap.reasoning) capabilities.reasoning = { supported: true }
  return { name: m.id, capabilities, limit: { context, output } }
}

async function main() {
  let text
  try {
    text = fs.readFileSync(CONFIG, "utf8")
  } catch (e) {
    fail(`nao consegui ler ${CONFIG}`, e)
  }
  const nl = text.includes("\r\n") ? "\r\n" : "\n"

  const { start, modelsOpen, modelsClose } = findProviderBlock(text)
  const block = text.slice(start, modelsClose)
  const baseURL = (process.env.NINEROUTER_URL || readSetting(block, "baseURL") || "http://127.0.0.1:20128/v1").replace(/\/+$/, "")
  const apiKey = process.env.NINEROUTER_API_KEY || readSetting(block, "apiKey")

  let payload
  try {
    const res = await fetch(`${baseURL}/models`, {
      headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : {},
      signal: AbortSignal.timeout(15000),
    })
    if (!res.ok) fail(`GET ${baseURL}/models respondeu HTTP ${res.status}`)
    payload = await res.json()
  } catch (e) {
    if (e.message && e.message.startsWith("GET ")) throw e
    fail(`falha ao consultar ${baseURL}/models (o 9Router esta rodando?)`, e)
  }
  if (!payload || !Array.isArray(payload.data)) fail("resposta de /models sem array 'data'")

  // Remove o bloco auto anterior (se houver) para calcular os modelos manuais.
  let models = text.slice(modelsOpen + 1, modelsClose)
  const a = models.indexOf(AUTO_START)
  const b = models.indexOf(AUTO_END)
  if ((a < 0) !== (b < 0) || b < a) fail("marcadores 9router-auto-models inconsistentes; corrija a mao")
  if (a >= 0) {
    const lineStart = models.lastIndexOf("\n", a) + 1
    const lineEnd = models.indexOf("\n", b)
    models = models.slice(0, lineStart) + models.slice(lineEnd < 0 ? models.length : lineEnd + 1)
  }
  const manual = new Set([...models.matchAll(/"([^"]+)"\s*:\s*\{/g)].map((m) => m[1]))

  const seen = new Set()
  const skipped = []
  const entries = []
  for (const m of payload.data) {
    const id = m && typeof m.id === "string" ? m.id.trim() : ""
    if (!id || !SAFE_ID.test(id)) {
      skipped.push(String(m && m.id))
      continue
    }
    if (manual.has(id) || seen.has(id)) continue
    seen.add(id)
    entries.push([id, toEntry(m)])
  }
  entries.sort(([x], [y]) => x.localeCompare(y))

  const freeCount = entries.filter(([id]) => /free/i.test(id)).length
  console.log(`[sync-9router] 9Router expoe ${payload.data.length} modelos; manuais preservados: ${manual.size}; gerados: ${entries.length} (free: ${freeCount})`)
  if (skipped.length) console.log(`[sync-9router] ignorados por ID invalido: ${skipped.join(", ")}`)
  if (DRY) return

  const indent = "        "
  const lines = entries.map(([id, e]) => `${indent}${JSON.stringify(id)}: ${JSON.stringify(e)},`)
  const autoBlock = [`${indent}${AUTO_START}`, ...lines, `${indent}${AUTO_END}`].join(nl)

  // Insere no fim do bloco models (antes da linha que fecha "}").
  const trimmed = models.replace(/\s*$/, "")
  const needsComma = trimmed.length && !/[,{]$/.test(trimmed.replace(/\/\/[^\n]*$/gm, "").trimEnd())
  const closeIndent = text.slice(text.lastIndexOf("\n", modelsClose) + 1, modelsClose)
  const newModels = `${trimmed}${needsComma ? "," : ""}${nl}${autoBlock}${nl}${closeIndent}`
  const out = text.slice(0, modelsOpen + 1) + newModels + text.slice(modelsClose)

  const backup = `${CONFIG}.bak-9router-sync`
  try {
    fs.copyFileSync(CONFIG, backup)
    fs.writeFileSync(CONFIG, out, "utf8")
  } catch (e) {
    fail(`falha ao gravar ${CONFIG}`, e)
  }
  console.log(`[sync-9router] gravado ${CONFIG} (backup: ${backup}). Rode: opencode reload`)
}

main().catch((e) => {
  if (!String(e.message).startsWith("[sync-9router]")) console.error(e)
  process.exitCode = 1
})
