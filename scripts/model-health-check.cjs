#!/usr/bin/env node
const { execSync } = require("child_process");

function listModelsFromOpencode() {
  try {
    const out = execSync("opencode models 9router", { encoding: "utf8", maxBuffer: 1024 * 1024 });
    return out
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l.startsWith("9router/"))
      .map((id) => id.replace(/^9router\//, ""));
  } catch (e) {
    console.error("Nao foi possivel executar 'opencode models 9router':", e.message);
    return [];
  }
}

function collectModels(cfg) {
  const ids = listModelsFromOpencode();
  return ids.map((id) => ({ id, from: "opencode models 9router" }));
}

async function probe(modelId) {
  const t0 = Date.now();
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
    });
    const ms = Date.now() - t0;
    const body = readBody(await res.text());

    if (res.ok) {
      return {
        model: modelId,
        ok: true,
        verdict: "OK",
        code: res.status,
        ms,
        note: `served_by=${body.servedBy || "?"}`,
      };
    }

    const msg = body.error || "";
    if (res.status === 404 && WENT_PAID.test(msg)) {
      return { model: modelId, ok: false, verdict: "GONE", code: res.status, ms, note: msg.slice(0, 120) };
    }
    if (EXHAUSTED.test(msg) || [429, 402, 410, 503, 529].includes(res.status)) {
      return { model: modelId, ok: false, verdict: "FAIL", code: res.status, ms, note: msg.slice(0, 120) || `HTTP ${res.status}` };
    }
    return { model: modelId, ok: false, verdict: "FAIL", code: res.status, ms, note: msg.slice(0, 120) || `HTTP ${res.status}` };
  } catch (e) {
    return { model: modelId, ok: false, verdict: "ERROR", code: "ERR", ms: 0, note: e.message };
  }
}

/**
 * Super script de health check de modelos 9Router / opencode.jsonc
 *
 * Testa CADA modelo configurado no provider 9router do opencode.jsonc,
 * verifica se responde (200 OK) e se o limite nao esta esgotado (429/402/quota).
 *
 *   node scripts/model-health-check.cjs
 *   node scripts/model-health-check.cjs --json   # so relatorio JSON no stdout
 *   node scripts/model-health-check.cjs --quiet  # so codigo de saida
 *
 * Leitura de chave:
 *   1. env NINEROUTER_KEY
 *   2. provider 9router.options.apiKey no opencode.jsonc
 *   3. banco SQLite da 9router (mesmo metodo do audit-free-models.cjs)
 *
 * Classificacao:
 *   OK     - HTTP 200: modelo disponivel e com limite livre
 *   GONE   - HTTP 404 + "unavailable for free/use this slug": virou pago (remover do combo)
 *   FAIL   - 429/402/410/503/529 (limite esgotado ou transiente) ou erro de rede
 *   ERROR  - nao conseguiu nem conectar ao 9Router
 *
 * Saida: tabela no console + relatorio JSON em scripts/model-health-report.json
 */

const fs = require("fs");
const path = require("path");

const CONFIG = "./opencode.jsonc";
const BASE = process.env.NINEROUTER_URL || "http://localhost:20128/v1";
const REPORT_PATH = path.join(
  path.dirname(CONFIG),
  "scripts",
  "model-health-report.json"
);

const WENT_PAID = /unavailable for free|use this slug instead|requires a subscription/i;
const EXHAUSTED = /429|rate limit|quota|exhausted|credit|402|billing|529|503|overloaded/i;

function stripComments(s) {
  let out = "";
  let inStr = false;
  let strChar = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    const n = s[i + 1];
    if (inStr) {
      out += c;
      if (c === strChar && s[i - 1] !== "\\") inStr = false;
    } else {
      if (c === '"' || c === "'") {
        inStr = true;
        strChar = c;
        out += c;
      } else if (c === "/" && n === "/") {
        while (i < s.length && s[i] !== "\n") i++;
      } else if (c === "/" && n === "*") {
        i += 2;
        while (i < s.length - 1 && !(s[i] === "*" && s[i + 1] === "/")) i++;
        i += 1;
      } else {
        out += c;
      }
    }
  }
  return out;
}

let config;
let apiKey = process.env.NINEROUTER_KEY || null;
try {
  const raw = fs.readFileSync(CONFIG, "utf8");
  // extrai apenas a apiKey com regex (evita parse completo do JSONC com comentarios)
  const m = raw.match(/"apiKey"\s*:\s*"([^"]+)"/);
  if (m && !apiKey) apiKey = m[1];
  // tenta parsear o JSONC apenas para referencia (nao usado para modelos)
  try {
    config = JSON.parse(raw.replace(/\/\/[^\n]*\n/g, "\n").replace(/\/\*[\s\S]*?\*\//g, ""));
  } catch { /* config nao eh estritamente necessario */ }
} catch (e) {
  console.error(`ERRO ao ler ${CONFIG}: ${e.message}`);
  process.exit(2);
}

if (!apiKey) {
  try {
    const Database = require(
      path.join(process.env.APPDATA || "", "9router/runtime/node_modules/better-sqlite3")
    );
    const DB =
      process.env.NINEROUTER_DB ||
      path.join(process.env.APPDATA || "", "9router/db/data.sqlite");
    const db = new Database(DB, { readonly: true });
    const row = db.prepare("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1").get();
    db.close();
    if (row) apiKey = row.key;
  } catch {
    /* ignore */
  }
}

if (!apiKey) {
  console.error("NENHUMA API KEY ENCONTRADA.");
  console.error("Defina NINEROUTER_KEY ou preencha provider.9router.options.apiKey no opencode.jsonc.");
  process.exit(2);
}

function readBody(raw) {
  const out = { servedBy: null, text: "", error: null };
  if (/^\s*data:\s*\{/.test(raw)) {
    let text = "";
    for (const line of raw.split(/\r?\n/)) {
      const m = line.match(/^data:\s*(\{.*\})\s*$/);
      if (!m) continue;
      try {
        const j = JSON.parse(m[1]);
        out.servedBy = out.servedBy || j.model || j.provider || null;
        const d = j.choices?.[0];
        const piece = d?.delta?.content ?? d?.message?.content ?? null;
        if (typeof piece === "string") text += piece;
      } catch { /* skip */ }
    }
    out.text = text.trim();
    return out;
  }
  const cleaned = raw.replace(/data:\s*\[DONE\]\s*$/g, "").trim();
  try {
    const j = JSON.parse(cleaned);
    out.servedBy = j.model || j.provider || null;
    const d = j.choices?.[0];
    out.text = String(d?.message?.content ?? d?.delta?.content ?? "").trim();
    out.error = j.error ? String(j.error.message ?? JSON.stringify(j.error)) : null;
    return out;
  } catch { /* fall through */ }
  const errMatch = raw.match(/"message"\s*:\s*"([^"]{10,300})"/);
  out.error = errMatch ? errMatch[1] : raw.replace(/\s+/g, " ").slice(0, 160);
  return out;
}

(async () => {
  const models = collectModels(config);
  console.log(`9Router health check — ${BASE}`);
  console.log(`Modelos encontrados no opencode.jsonc: ${models.length}\n`);

  const rows = [];
  for (const { id } of models) {
    rows.push(await probe(id));
  }

  console.log(
    `${"Veredito".padEnd(8)} ${"HTTP".padEnd(6)} ${"ms".padEnd(6)} Modelo`
  );
  console.log(`${"-".repeat(8)} ${"-".repeat(6)} ${"-".repeat(6)} ${"-".repeat(40)}`);
  for (const r of rows) {
    console.log(
      `${r.verdict.padEnd(8)} ${String(r.code).padEnd(6)} ${String(r.ms).padStart(4)}ms  ${r.model}${
        r.note ? `  | ${r.note}` : ""
      }`
    );
  }

  const ok = rows.filter((r) => r.ok);
  const gone = rows.filter((r) => r.verdict === "GONE");
  const fail = rows.filter((r) => !r.ok && r.verdict !== "GONE");

  console.log(`\n=== DISPONIVEIS: ${ok.length}/${rows.length} ===`);
  ok.forEach((r) => console.log(`  ✓ ${r.model} (${r.ms}ms)`));
  if (gone.length) {
    console.log(`\n=== VIROU PAGO (remover do combo): ${gone.length} ===`);
    gone.forEach((r) => console.log(`  ✗ ${r.model} — ${r.note}`));
  }
  if (fail.length) {
    console.log(`\n=== LIMITE ESGOTADO / FALHA: ${fail.length} ===`);
    fail.forEach((r) => console.log(`  ! ${r.model} [${r.code}] — ${r.note}`));
  }

  const report = {
    generatedAt: new Date().toISOString(),
    base: BASE,
    total: rows.length,
    available: ok.length,
    gonePaid: gone.length,
    failed: fail.length,
    models: rows,
  };
  try {
    fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
    console.log(`\nRelatorio salvo em: ${REPORT_PATH}`);
  } catch (e) {
    console.error(`Nao foi possivel salvar relatorio: ${e.message}`);
  }

  console.log(
    `\nUm 429 sozinho e transiente. Re-Execute antes de remover qualquer modelo por 429.`
  );

  process.exit(fail.length + gone.length > 0 ? 1 : 0);
})();