#!/usr/bin/env node
/**
 * Audit free (`:free`) models exposed by 9Router.
 *
 * Run it BEFORE trusting that a free model is available. The catalog lies:
 * on 2026-10-03, 6 of 11 `:free` models were dead (404 = went paid, 429 = rate).
 *
 *   node audit-free-models.cjs
 *   node audit-free-models.cjs --second-path   # also probe kiro/nvidia
 *
 * NOTE ON RESPONSE BODIES — 9Router is not consistent here, and this bit me:
 *   1. OpenRouter-backed models return a plain `chat.completion` JSON object
 *      with `data: [DONE]\n\n` APPENDED. `JSON.parse` fails near the end.
 *   2. Kiro-backed models return real SSE: `data: {...}\n\n` chunks.
 *   Both are served with `content-type: text/event-stream` even when the
 *   request did NOT ask for `stream: true`.
 * So: never assume the body parses. See readBody() below.
 *
 * Read-only. Costs ~12 tiny completions.
 */
const path = require("path");

const BASE = process.env.NINEROUTER_URL || "http://localhost:20128/v1";
const DB =
  process.env.NINEROUTER_DB ||
  path.join(process.env.APPDATA || "", "9router/db/data.sqlite");

function loadKey() {
  let Database;
  try {
    Database = require(
      path.join(process.env.APPDATA, "9router/runtime/node_modules/better-sqlite3")
    );
  } catch {
    console.error("Could not load better-sqlite3 from the 9router runtime.");
    console.error("Set NINEROUTER_KEY=<your 9router api key> instead.");
    process.exit(2);
  }
  const db = new Database(DB, { readonly: true });
  const row = db.prepare("SELECT key FROM apiKeys WHERE isActive=1 LIMIT 1").get();
  db.close();
  if (!row) {
    console.error("No active API key in the 9router DB.");
    process.exit(2);
  }
  return row.key;
}

const KEY = process.env.NINEROUTER_KEY || loadKey();

/** Tolerant body reader. Returns { servedBy, text, error }. Never throws. */
function readBody(raw) {
  const out = { servedBy: null, text: "", error: null };

  // Case 1: real SSE — several `data: {json}` frames.
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
      } catch {
        /* skip malformed frame */
      }
    }
    out.text = text.trim();
    return out;
  }

  // Case 2: plain JSON possibly with a trailing `data: [DONE]`.
  const cleaned = raw.replace(/data:\s*\[DONE\]\s*$/g, "").trim();
  try {
    const j = JSON.parse(cleaned);
    out.servedBy = j.model || j.provider || null;
    const d = j.choices?.[0];
    out.text = String(d?.message?.content ?? d?.delta?.content ?? "").trim();
    out.error = j.error ? String(j.error.message ?? JSON.stringify(j.error)) : null;
    return out;
  } catch {
    /* fall through */
  }

  // Case 3: unknown shape — salvage an error message if one is present.
  const errMatch = raw.match(/"message"\s*:\s*"([^"]{10,300})"/);
  out.error = errMatch ? errMatch[1] : raw.replace(/\s+/g, " ").slice(0, 160);
  return out;
}

const WENT_PAID = /unavailable for free|use this slug instead|requires a subscription/i;

async function chat(model, prompt) {
  const t0 = Date.now();
  try {
    const res = await fetch(`${BASE}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${KEY}` },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 16,
      }),
    });
    const ms = Date.now() - t0;
    const body = readBody(await res.text());

    // Classify on the STATUS first — it is the only trustworthy signal here.
    if (res.ok) {
      return {
        model,
        ok: true,
        code: res.status,
        ms,
        verdict: "OK  ",
        note: `served_by=${body.servedBy || "?"}${body.text ? ` reply=${JSON.stringify(body.text.slice(0, 24))}` : ""}`,
      };
    }

    const msg = body.error || "";
    if (res.status === 404 && WENT_PAID.test(msg)) {
      return { model, ok: false, code: res.status, ms, verdict: "GONE", note: msg.slice(0, 120) };
    }
    return {
      model,
      ok: false,
      code: res.status,
      ms,
      verdict: "FAIL",
      note: msg.slice(0, 120) || "(no error message parsed)",
    };
  } catch (e) {
    return { model, ok: false, code: "ERR", ms: 0, verdict: "FAIL", note: e.message };
  }
}

(async () => {
  const all = (await (await fetch(`${BASE}/models`)).json()).data.map((m) => m.id);
  const free = all.filter((id) => /:free\b|-free\b/.test(id));
  const second = process.argv.includes("--second-path")
    ? all.filter((id) => /^(kr|nvidia)\//.test(id)).slice(0, 10)
    : [];

  console.log(`${BASE}\n${all.length} models total, ${free.length} tagged free\n`);

  const rows = [];
  for (const m of [...free, ...second]) rows.push(await chat(m, "Reply with exactly: OK"));

  for (const r of rows) {
    console.log(`${r.verdict} ${String(r.code).padEnd(4)} ${String(r.ms).padStart(5)}ms  ${r.model}\n         ${r.note}`);
  }

  const alive = rows.filter((r) => r.ok);
  const gone = rows.filter((r) => r.verdict === "GONE");
  const other = rows.filter((r) => !r.ok && r.verdict !== "GONE");

  console.log(`\n=== ALIVE: ${alive.length}/${rows.length} ===`);
  alive.forEach((r) => console.log("  " + r.model));
  if (gone.length) {
    console.log(`\n=== WENT PAID (remove from combos): ${gone.length} ===`);
    gone.forEach((r) => console.log("  " + r.model));
  }
  if (other.length) {
    console.log(`\n=== RATE-LIMITED / OTHER: ${other.length} ===`);
    other.forEach((r) => console.log("  " + r.model + "  [" + r.code + "]"));
  }
  console.log("\nA 429 alone is transient. Re-run before removing anything on a 429.");
})();