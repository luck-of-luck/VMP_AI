/**
 * Navegador Visual — IA controlando o navegador em tempo real (estilo Codex)
 * Com gravação de vídeo e suporte a múltiplas abas.
 *
 * Uso:
 *   node scripts/navegador-visual.cjs <url> <acao1> <acao2> ...
 *
 * Ações:
 *   click:seletor       -> clica no elemento
 *   fill:seletor:texto  -> preenche input com texto
 *   press:tecla         -> pressiona tecla (Enter, Tab, Esc...)
 *   wait:ms             -> espera X milissegundos
 *   extract             -> extrai texto visível da página atual
 *   screenshot          -> tira screenshot manual da página atual
 *   tab:nova            -> abre uma nova aba
 *   tab:fechar          -> fecha a aba atual
 *   tab:trocar:N        -> troca para a aba de índice N (0-based)
 *   tab:listar          -> lista todas as abas abertas
 *   video:iniciar       -> inicia gravação de vídeo da sessão
 *   video:parar         -> para a gravação e salva o vídeo
 *
 * Exemplos:
 *   node scripts/navegador-visual.cjs https://google.com "fill:[name=q]:milho" press:Enter wait:3000 extract screenshot
 *   node scripts/navegador-visual.cjs https://exemplo.com video:iniciar click:.btn wait:2000 video:parar
 *   node scripts/navegador-visual.cjs https://google.com tab:nova https://bing.com tab:trocar:0 extract
 *
 * Screenshots e vídeos salvos em: %APPDATA%\opencode\screenshots-navegador\
 */

const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const SCREENSHOT_DIR = path.join(
  process.env.APPDATA || "",
  "opencode/screenshots-navegador"
);
const VIDEO_DIR = path.join(
  process.env.APPDATA || "",
  "opencode/videos-navegador"
);
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
fs.mkdirSync(VIDEO_DIR, { recursive: true });

let screenshotCount = 0;
let videoCount = 0;
let videoRecording = false;
let videoPath = null;

function nextShotName() {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return path.join(
    SCREENSHOT_DIR,
    `shot-${stamp}-${String(++screenshotCount).padStart(2, "0")}.png`
  );
}

function nextVideoName() {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  return path.join(VIDEO_DIR, `session-${stamp}-${String(++videoCount).padStart(2, "0")}.webm`);
}

async function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function parseAction(arg) {
  const mClick = arg.match(/^click:(.+)$/);
  if (mClick) return { type: "click", selector: mClick[1] };

  const mFill = arg.match(/^fill:(.+):(.+)$/);
  if (mFill) return { type: "fill", selector: mFill[1], text: mFill[2] };

  const mPress = arg.match(/^press:(.+)$/);
  if (mPress) return { type: "press", key: mPress[1] };

  const mWait = arg.match(/^wait:(\d+)$/);
  if (mWait) return { type: "wait", ms: parseInt(mWait[1], 10) };

  const mTabSwitch = arg.match(/^tab:trocar:(\d+)$/);
  if (mTabSwitch) return { type: "tab:trocar", index: parseInt(mTabSwitch[1], 10) };

  if (arg === "extract") return { type: "extract" };
  if (arg === "screenshot") return { type: "screenshot" };
  if (arg === "tab:nova") return { type: "tab:nova" };
  if (arg === "tab:fechar") return { type: "tab:fechar" };
  if (arg === "tab:listar") return { type: "tab:listar" };
  if (arg === "video:iniciar") return { type: "video:iniciar" };
  if (arg === "video:parar") return { type: "video:parar" };
  if (arg.match(/^https?:\/\//)) return { type: "navigate", url: arg };

  return { type: "unknown", raw: arg };
}

// __MAIN__
(async () => {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.log("Uso: node scripts/navegador-visual.cjs <url> <acao1> <acao2> ...");
    console.log("");
    console.log("Ações: click:sel | fill:sel:texto | press:tecla | wait:ms | extract | screenshot");
    console.log("       tab:nova | tab:fechar | tab:trocar:N | tab:listar | video:iniciar | video:parar");
    console.log("Exemplo: node scripts/navegador-visual.cjs https://google.com video:iniciar \"fill:[name=q]:milho\" press:Enter extract");
    process.exit(1);
  }

  const wantsVideo = args.includes("video:iniciar") || args.includes("--video");

  console.log("╔══════════════════════════════════════════════════════════════════════════════╗");
  console.log("║  NAVEGADOR VISUAL — IA em ação (modo headful, visível)                      ║");
  console.log("╚══════════════════════════════════════════════════════════════════════════════╝");
  console.log(wantsVideo
    ? "🎬 Gravação de vídeo: ATIVA (salva ao final da sessão)"
    : "🎬 Gravação de vídeo: desligada (use video:iniciar para ativar)");
  console.log("");

  const browser = await chromium.launch({
    headless: false,
    args: ["--start-maximized", "--disable-web-security", "--disable-features=IsolateOrigins,site-per-process"],
  });

  const context = await browser.newContext({
    viewport: { width: 1366, height: 768 },
    ...(wantsVideo ? { recordVideo: { dir: VIDEO_DIR, size: { width: 1366, height: 768 } } } : {}),
  });

  const pages = [];
  const videoPromises = [];

  function attach(page) {
    page.on("console", (msg) => {
      if (msg.type() === "error") console.log(`  [console error] ${msg.text()}`);
    });
    page.on("pageerror", (err) => console.log(`  [page error] ${err.message}`));
    pages.push(page);
    if (wantsVideo) {
      const v = page.video();
      if (v) videoPromises.push(v);
    }
    return page;
  }

  let currentPage = attach(await context.newPage());

  async function takeScreenshot(label) {
    const file = nextShotName();
    await currentPage.screenshot({ path: file, fullPage: true });
    console.log(`  📷 Screenshot: ${file}${label ? ` — ${label}` : ""}`);
    return file;
  }

  function tabInfo() {
    return `aba ${pages.indexOf(currentPage) + 1}/${pages.length}`;
  }

  for (const arg of args) {
    const action = parseAction(arg);
    console.log(`\n▶ Ação: ${action.type}` +
      (action.selector ? ` seletor="${action.selector}"` : "") +
      (action.text ? ` texto="${action.text}"` : "") +
      (action.key ? ` tecla="${action.key}"` : "") +
      (action.ms ? ` ms="${action.ms}"` : "") +
      (action.index !== undefined ? ` índice=${action.index}` : "") +
      (action.url ? ` url="${action.url}"` : ""));

    try {
      switch (action.type) {
        case "navigate":
          console.log(`  Navegando para ${action.url}... (${tabInfo()})`);
          await currentPage.goto(action.url, { waitUntil: "networkidle", timeout: 30000 });
          await takeScreenshot(`carregou ${action.url}`);
          break;

        case "click": {
          await currentPage.waitForSelector(action.selector, { timeout: 10000 });
          const box = await currentPage.locator(action.selector).boundingBox();
          if (box) console.log(`  Clicando em ${action.selector} (x:${Math.round(box.x)}, y:${Math.round(box.y)})`);
          await currentPage.click(action.selector);
          await takeScreenshot(`clicou ${action.selector}`);
          break;
        }
        case "fill": {
          await currentPage.waitForSelector(action.selector, { timeout: 10000 });
          await currentPage.fill(action.selector, action.text);
          console.log(`  Preencheu ${action.selector} com "${action.text}"`);
          await takeScreenshot(`preencheu ${action.selector}`);
          break;
        }

        case "press":
          await currentPage.press("body", action.key);
          console.log(`  Pressionou tecla "${action.key}"`);
          await takeScreenshot(`pressionou ${action.key}`);
          break;

        case "wait":
          console.log(`  Esperando ${action.ms}ms...`);
          await sleep(action.ms);
          await takeScreenshot(`esperou ${action.ms}ms`);
          break;

        case "extract": {
          const texto = await currentPage.evaluate(
            () => document.body.innerText || document.body.textContent || ""
          );
          console.log(`  Texto extraído (${texto.length} chars):`);
          console.log(`  ${texto.slice(0, 500)}${texto.length > 500 ? "..." : ""}`);
          break;
        }

        case "screenshot":
          await takeScreenshot("manual");
          break;

        case "tab:nova": {
          const np = attach(await context.newPage());
          currentPage = np;
          console.log(`  Nova aba aberta (${tabInfo()})`);
          await takeScreenshot("nova aba");
          break;
        }

        case "tab:fechar": {
          if (pages.length <= 1) {
            console.log("  Última aba — não é possível fechar.");
            break;
          }
          const idx = pages.indexOf(currentPage);
          await currentPage.close();
          pages.splice(idx, 1);
          currentPage = pages[Math.min(idx, pages.length - 1)];
          await currentPage.bringToFront();
          console.log(`  Aba fechada. Agora em ${tabInfo()}: ${currentPage.url()}`);
          await takeScreenshot("aba fechada");
          break;
        }

        case "tab:trocar": {
          if (action.index < 0 || action.index >= pages.length) {
            console.log(`  ❌ Aba ${action.index} não existe (${pages.length} aba(s) aberta(s)).`);
            break;
          }
          currentPage = pages[action.index];
          await currentPage.bringToFront();
          console.log(`  Trocado para ${tabInfo()}: ${currentPage.url()}`);
          await takeScreenshot(`aba ${action.index}`);
          break;
        }

        case "tab:listar": {
          console.log(`  ${pages.length} aba(s) aberta(s):`);
          for (let i = 0; i < pages.length; i++) {
            const mark = pages[i] === currentPage ? "▶" : " ";
            console.log(`  ${mark} [${i}] ${pages[i].url()}`);
          }
          break;
        }

        case "video:iniciar":
          if (wantsVideo) {
            console.log("  🎬 Gravação ativa desde o início da sessão (Playwright grava do 1º ao último frame).");
          } else {
            console.log("  ⚠️ Gravação não ativa — adicione 'video:iniciar' entre os argumentos para gravar a sessão inteira.");
          }
          break;

        case "video:parar":
          if (wantsVideo) {
            console.log("  🎬 Fim da gravação marcado — o vídeo será salvo ao fechar o navegador.");
          } else {
            console.log("  ⚠️ Nenhuma gravação ativa.");
          }
          break;

        default:
          console.log(`  Ação desconhecida: ${arg}`);
      }
    } catch (e) {
      console.log(`  ❌ Erro: ${e.message}`);
      await takeScreenshot(`erro-${action.type}`);
    }
  }
  console.log(`\n✓ Sessão concluída. ${screenshotCount} screenshot(s) salvos em:`);
  console.log(`  ${SCREENSHOT_DIR}`);

  console.log("  Navegador fecha em 10 segundos...");
  await sleep(10000);

  await context.close();

  if (wantsVideo && videoPromises.length > 0) {
    console.log("  🎥 Salvando vídeo(es) da sessão...");
    for (let i = 0; i < videoPromises.length; i++) {
      try {
        const src = await videoPromises[i].path();
        const base = nextVideoName();
        const dest = videoPromises.length > 1
          ? base.replace(/\.webm$/, `-tab${i + 1}.webm`)
          : base;
        fs.renameSync(src, dest);
        console.log(`  🎥 Vídeo: ${dest}`);
      } catch (e) {
        console.log(`  ❌ Erro ao salvar vídeo ${i + 1}: ${e.message}`);
      }
    }
  }

  await browser.close();
  console.log("  Navegador fechado.");
})();

