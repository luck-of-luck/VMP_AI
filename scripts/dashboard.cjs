#!/usr/bin/env node
/**
 * Dashboard de interface — visão geral do sistema OpenCode + 9Router + Multiagente
 *
 *   node scripts/dashboard.cjs
 *
 * Mostra:
 *   - MCP servers conectados / falhados / desabilitados
 *   - Modelos 9Router disponíveis (último health check)
 *   - Agentes configurados (arquivos .md + seção agent do opencode.jsonc)
 *   - Skills disponíveis
 *   - Plugins
 *   - Relatório resumido em cores
 */

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const CONFIG = "./opencode.jsonc";
const REPORT = "./scripts/model-health-report.json";
const AGENTS_DIR = "./agents";
const SKILLS_DIR = "./skills";

function cmd(c) {
  try {
    return execSync(c, { encoding: "utf8", maxBuffer: 1024 * 1024 }).trim();
  } catch {
    return "";
  }
}

function header(t) {
  console.log("\n════════════════════════════════════════════════════════════════════════════════════");
  console.log("  " + t);
  console.log("════════════════════════════════════════════════════════════════════════════════════");
}

function extractAgentNamesFromConfig() {
  const raw = fs.readFileSync(CONFIG, "utf8");
  const names = [];
  const agentSectionMatch = raw.match(/"agent"\s*:\s*\{([\s\S]*?)\n  \}/);
  if (agentSectionMatch) {
    const section = agentSectionMatch[1];
    const nameMatches = section.match(/"([^"]+)"\s*:\s*\{/g);
    if (nameMatches) {
      nameMatches.forEach(function (m) {
        var n = m.replace(/"([^"]+)"\s*:\s*\{/, "$1");
        names.push(n);
      });
    }
  }
  return names;
}

(function () {
  // ---------- 1. MCP ----------
  header("MCP SERVERS");
  var mcpOut = cmd("opencode mcp list");
  var connected = (mcpOut.match(/✓ connected/g) || []).length;
  var failed = (mcpOut.match(/failed/g) || []).length;
  var disabled = (mcpOut.match(/disabled/g) || []).length;
  var totalMatch = mcpOut.match(/(\d+) server\(s\)/);
  var total = totalMatch ? totalMatch[1] : "?";
  console.log("  Total: " + total + "   Conectados: " + connected + "   Falhados: " + failed + "   Desabilitados: " + disabled);

  var failedLines = mcpOut.split("\n").filter(function (l) { return /failed/.test(l); });
  if (failedLines.length) {
    console.log("\n  Falhados:");
    failedLines.forEach(function (l) { console.log("    " + l.trim()); });
  }

  var disabledLines = mcpOut.split("\n").filter(function (l) { return /disabled/.test(l); });
  if (disabledLines.length) {
    console.log("\n  Desabilitados:");
    disabledLines.forEach(function (l) { console.log("    " + l.trim()); });
  }

  // ---------- 2. Modelos 9Router ----------
  header("MODELOS 9ROUTER (último health check)");
  var health = null;
  try {
    health = JSON.parse(fs.readFileSync(REPORT, "utf8"));
  } catch { }
  if (health) {
    console.log("  Total: " + health.total + "   Disponíveis: " + health.available + "   Pagos/GONE: " + health.gonePaid + "   Falha/Limite: " + health.failed);
    health.models.forEach(function (m) {
      var icon = m.ok ? "✅" : m.verdict === "GONE" ? "❌" : "⚠️";
      console.log("  " + icon + " " + m.model.padEnd(45) + " [" + m.code + "] " + m.ms + "ms");
    });
  } else {
    console.log("  (sem relatório — rode `node scripts/model-health-check.cjs`)");
  }

  // ---------- 3. Agentes ----------
  header("AGENTES CONFIGURADOS");
  var configAgents = extractAgentNamesFromConfig();
  var agentFiles = [];
  try {
    var files = fs.readdirSync(AGENTS_DIR);
    files.forEach(function (f) {
      if (f.endsWith(".md") && !f.startsWith("_")) {
        agentFiles.push(f.replace(/\.md$/, ""));
      }
    });
  } catch { }
  var allAgents = [].concat(configAgents, agentFiles).filter(function (v, i, a) { return a.indexOf(v) === i; }).sort();
  allAgents.forEach(function (name) {
    var inConfig = configAgents.indexOf(name) >= 0 ? "✓" : " ";
    console.log("  [" + inConfig + "] " + name.padEnd(20));
  });

  // ---------- 4. Skills ----------
  header("SKILLS DISPONÍVEIS");
  try {
    var skills = fs.readdirSync(SKILLS_DIR, { withFileTypes: true })
      .filter(function (d) { return d.isDirectory(); })
      .map(function (d) { return d.name; });
    skills.forEach(function (s) { console.log("  • " + s); });
  } catch {
    console.log("  (não foi possível listar skills)");
  }

  // ---------- 5. Plugins ----------
  header("PLUGINS");
  var raw = fs.readFileSync(CONFIG, "utf8");
  var pluginMatch = raw.match(/"plugin"\s*:\s*\[([^\]]*)\]/);
  if (pluginMatch) {
    var plugins = pluginMatch[1]
      .split(",")
      .map(function (p) { return p.trim().replace(/["']/g, ""); })
      .filter(Boolean);
    plugins.forEach(function (p) { console.log("  • " + p); });
  }

  // ---------- 6. Resumo ----------
  header("RESUMO");
  var okModels = health ? health.available : 0;
  var failModels = health ? health.failed + health.gonePaid : 0;
  console.log("  MCP conectados: " + connected + "/" + total);
  console.log("  Modelos OK: " + okModels + "/" + (health ? health.total : "?"));
  console.log("  Agentes: " + allAgents.length);
  var pluginCount = pluginMatch ? pluginMatch[1].split(",").filter(Boolean).length : 0;
  console.log("  Plugins: " + pluginCount);

  console.log("\n  Última atualização: " + new Date().toLocaleString("pt-BR"));
  console.log("════════════════════════════════════════════════════════════════════════════════════\n");
})();