/**
 * Plugin do cluster para o opencode.
 *
 * Entrega o que foi pedido: um comando `/cluster` que liga o comite, deixa
 * os agentes EM PRONTIDAO (saude verificada, nao "esperando" de mentira), e
 * uma tool `cluster_consultar` que faz a pergunta aos 10 de uma vez.
 *
 * O que este plugin NAO faz, e por que:
 *   - Nao roda 10 processos persistentes. O relay e HTTP: "prontidao" nao e
 *     um processo vivo, e a chave valendo + o relay respondendo. Verificar
 *     isso leva ~1s e e o que de fato impede a primeira pergunta de falhar.
 *   - Nao substitui o agente principal. Ele continua sendo quem responde; o
 *     comite devolve achados que ele incorpora. Um comite que responde
 *     direto ao usuario tiraria do modelo principal a contexto e a autoria.
 */
import { tool } from "@opencode-ai/plugin"
import {
  PERFIS,
  MODELO,
  consultarTodos,
  consolidar,
 ehErroTransporte,
  perguntarAgente,
  rodarComRetry,
} from "./engine.ts"

/** Estado por sessao: quantos agentes o usuario ligou. */
type Estado = { tamanho: number; ligadoEm: number };
const sessoes = new Map<string, Estado>();

const DEFAULT_N = 10;

/**
 * Budget de caracteres por AGENTE, nao por arquivo.
 *
 * Medido (2026-10-01), 3 agentes em paralelo, teto 6000:
 *    60 linhas ( 2.344 chars) -> 3/3 ok,  47s
 *   120 linhas ( 4.182 chars) -> 3/3 ok,  42s
 *   200 linhas ( 7.164 chars) -> 3/3 ok,  72s
 *   311 linhas (11.672 chars) -> 2/3 ok,  70s  <-- comeca a evaporar
 *
 * A evaporacao (`reasoning` consome o teto, resposta sai vazia) cresce com o
 * material. 7.000 chars por agente e o ponto onde ainda tenho 100% de taxa.
 * Acima disso o comite perde lentes, e perder lente e perder perspectiva sem
 * ninguem perceber: a consolidacao nao avisa o que ficou sem ver.
 *
 * Como cada agente recebe uma fatia DIFERENTE do arquivo, 10 agentes com
 * 7.000 chars cada varrem ~70.000 chars — mais que todo o arquivo — sem
 * ninguem passar do limite seguro.
 */
const MAX_CHARS_POR_AGENTE = 7000;

function estado(id: string): Estado {
  let e = sessoes.get(id);
  if (!e) {
    e = { tamanho: 0, ligadoEm: 0 };
    sessoes.set(id, e);
  }
  return e;
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

// ── Ferramentas ───────────────────────────────────────────────────────────

export const cluster_consultar = tool({
  description:
    "Consulta N agentes de IA em paralelo, cada um com uma lente diferente " +
    "(correção, segurança, contrato, concorrência, legibilidade, erros, " +
    "dados, dependências, testes, visão geral), e consolida tudo em uma " +
    "resposta só. Use para: revisar código, achar defeitos, auditar, fazer " +
    "brainstorm com ângulos distintos, ou pegar uma segunda opinião. É mais " +
    "lento que uma chamada normal (dez modelos pensando), então use quando " +
    "a pergunta VALER o custo. Não use para perguntar algo factual simples.",
  args: {
    pergunta: tool.schema
      .string()
      .describe("O que os agentes devem analisar. Inclua o código ou texto a examinar."),
    n: tool.schema
      .number()
      .int()
      .min(1)
      .max(PERFIS.length)
      .optional()
      .describe("Quantos agentes usar (1 a 10). Padrão: o valor ligado em /cluster, senão 10."),
    arquivos: tool.schema
      .array(tool.schema.string())
      .optional()
      .describe("Caminhos absolutos de arquivos para cada agente VER antes de responder."),
    orcamento: tool.schema
      .number()
      .int()
      .min(512)
      .max(12000)
      .optional()
      .describe("Tokens de saída por agente. Padrão 3000. Mais = respostas mais longas."),
  },
  async execute(args, ctx) {
    const n = args.n ?? estado(ctx.sessionID).tamanho ?? DEFAULT_N;
    const usar = Math.max(1, Math.min(n, PERFIS.length));
    const perfis = PERFIS.slice(0, usar);

    // Material base: a pergunta. O conteudo dos arquivos entra por
    // agente, em montarPrompt() abaixo, porque cada um recebe
    // uma FATIA diferente do arquivo (ver DEFECT #6).
    const material = args.pergunta;

    // Monta o material POR AGENTE: cada um recebe uma fatia do arquivo.
    // Ver MAX_CHARS_POR_AGENTE e o DEFECT #6 acima. Sem isso, material grande
    // faz o modelo evaporar (medido: 4 de 6 com reasoning no teto).
    const montarPrompt = async (idx: number): Promise<string> => {
      if (!args.arquivos?.length) return material;
      const { readFileSync, statSync } = await import("fs");
      const partes: string[] = [];
      for (const p of args.arquivos) {
        try {
          const txt = readFileSync(p, "utf-8");
          const linhas = txt.split("\n");
          const total = linhas.length;
          // A fatia precisa caber no budget por agente. Dois limites:
          //   - caracteres (MAX_CHARS_POR_AGENTE), o limite MEDIDO do modelo;
          //   - a divisao justa entre os agentes, para que ninguem receba
          //     material que outro agente precisa ver.
          // O menor dos dois vence: e o minimo necessario para os dois
          // lados ficarem bem.
          const porLinhas = Math.max(60, Math.floor(MAX_CHARS_POR_AGENTE / 42));
          const justo = Math.ceil(total / usar);
          const tetoLinhas = Math.max(40, Math.min(porLinhas, justo));
          const ini = idx * tetoLinhas;
          const fim = Math.min(total, ini + tetoLinhas);
          if (ini >= total) {
            partes.push(`\n=== ${p} ===\n[Esta parte ja foi coberta por outro agente.]`);
            continue;
          }
          const info =
            ini > 0 || fim < total
              ? `\n[SUA FATIA: linhas ${ini + 1}-${fim} de ${total}. ` +
                `Analise ESTA parte; outro agente cuida do resto.]`
              : "";
          partes.push(
            `\n=== ${p} (${(statSync(p).size / 1024).toFixed(1)} KB, ` +
              `${total} linhas) ===${info}\n${linhas.slice(ini, fim).join("\n")}` +
              (fim < total ? "\n[FIM DA SUA FATIA]" : ""),
          );
        } catch (e) {
          partes.push(`\n=== ${p} ===\nNAO FOI POSSIVEL LER: ${String(e).slice(0, 80)}`);
        }
      }
      return material + "\n\nMATERIAIS PARA VER:" + partes.join("\n");
    };

    const t0 = Date.now();
    const usarEmOndas = usar > 5;
const respostas = usarEmOndas
        ? await rodarComRetry(perfis, material, {
            n: usar,
            orcamento: args.orcamento ?? 6000,
            // DEFECT #7 (medido 2026-10-01): montarPrompt era passado so no
            // caminho de consultarTodos. Com n>5 o codigo usava a funcao de
            // ondas SEM o, e os 10 agentes recebiam a pergunta sem nenhum
            // arquivo: todos responderam "nao foi fornecido" — e ainda assim
            // com ok=true, porque "nao achei nada" e uma resposta valida.
            montarPrompt,
            // Sem segunda passada. Medido: com retry os 3 agentes terminaram
            // em 343s; sem retry, a mesma carga em 72s. A segunda passada
            // mais que dobrava o tempo para resgatar agentes que, medidos
            // lado a lado, raramente falham com material repartido. So
            // vale quando o preco e resposta, nao tempo.
            tentativasExtra: 0,
          })
        : (await consultarTodos(perfis, material, {
            orcamento: args.orcamento ?? 6000,
            montarPrompt,
          })).respostas;

    const ok = respostas.filter((r) => r.ok);
    if (ok.length === 0) {
      const erros = respostas.map((r) => `${r.perfil}: ${r.erro}`).join("; ");
      return {
        title: `cluster: 0/${usar} responderam`,
        output: `NENHUM AGENTE RESPONDEU.\n${erros}\n\nVerifique a rede e a cota do relay.`,
        metadata: { ok: 0, total: usar },
      };
    }

    const c = await consolidar(respostas, args.pergunta);
    const relatorio = ok
      .map((r) => `### ${r.nome ?? r.perfil} (${fmtMs(r.ms ?? 0)})\n${r.texto}`)
      .join("\n\n---\n\n");
    const falharam = respostas
      .filter((r) => !r.ok)
      .map((r) => `- ${r.perfil}: ${(r.erro ?? "").slice(0, 90)}`);

    const cabecalho =
      `CLUSTER ${ok.length}/${usar} agentes em ${fmtMs(Date.now() - t0)} ` +
      `(modelo: ${MODELO})\n` +
      (falharam.length ? `FALHARAM: ${falharam.length}\n` : "");

    return {
      title: `cluster: ${ok.length}/${usar} agentes`,
      output: cabecalho + "\n" + (c.ok ? c.texto : c.texto),
      metadata: {
        ok: ok.length,
        total: usar,
        ms: Date.now() - t0,
        perfis: ok.map((r) => r.perfil),
        respostas_brutas: relatorio,
        consolidacao_parcial: c.parcial ?? false,
      },
    };
  },
});

export const cluster_prontidao = tool({
  description:
    "Verifica se os agentes do cluster estão prontos para trabalhar: relay " +
    "respondendo, chave aceita e cada lente viva. Use antes de um trabalho " +
    "longo, ou para diagnosticar quando o cluster devolveu nada.",
  args: {
    n: tool.schema.number().int().min(1).max(PERFIS.length).optional(),
  },
  async execute(args, ctx) {
    const e = estado(ctx.sessionID);
    const usar = Math.max(1, Math.min(args.n ?? e.tamanho ?? DEFAULT_N, PERFIS.length));
    const perfis = PERFIS.slice(0, usar);

    const t0 = Date.now();
    // Uma chamada real: "prontidao" declarada sem chamar nada e mentira.
    const probe = await perguntarAgente(
      perfis[0],
      "Responda apenas com a palavra: PRONTO",
      { orcamento: 512 },
    );
    const fila: string[] = [];
    for (const p of perfis) fila.push(`  ${p.id.padEnd(13)} ${p.nome}`);

    const ligado = e.tamanho > 0;
    const texto =
      `${probe.ok ? "PRONTO" : "INDISPONIVEL"} — relay respondeu em ${fmtMs(probe.ms)}\n` +
      `modelo: ${MODELO}\n` +
      `agentes: ${usar}${ligado ? " (ligados neste comite)" : ""}\n` +
      `perfis:\n${fila.join("\n")}\n` +
      (probe.ok ? "" : `\nERRO: ${probe.erro}\n`) +
      (ligado
        ? "\nO comite esta armed. Mandar a pergunta no chat."
        : "\nPara ligar: /cluster 10");

    return {
      title: probe.ok ? `cluster: ${usar} prontos` : "cluster: indisponivel",
      output: texto,
      metadata: { ok: probe.ok, n: usar, ms: Date.now() - t0 },
    };
  },
});

// ── Comando ───────────────────────────────────────────────────────────────
//
// `command.execute.before` roda antes do comando ser despachado. Aqui nao
// executamos o pedido: deixamos o comite armed e devolvemos as instrucoes
// para o modelo responder "pronto, mande o prompt".
//
// Uma unica fonte de verdade de estado: `sessoes`. Ter duas (uma no mapa
// `ESTADO`, outra em `sessoes`) ja Causou divergencia nesta construcao.

export default async () => {
  // Garante que o estado exista para cada sessao que passar pelo plugin.
  return {
    tool: {
      cluster_consultar,
      cluster_prontidao,
    },

    "chat.params": async (input, output) => {
      const e = estado(input.sessionID);
      // Informa o modelo principal que existe um comite ligado. Sem isto o
      // modelo nao sabe que o comite existe, o usuario digita o prompt e
      // recebe UMA resposta — os 10 agentes nunca sao chamados.
      if (e.tamanho > 0) {
        output.options["cluster_armed"] =
          `COMITE LIGADO: ${e.tamanho} agentes ${MODELO} em prontidao. ` +
          `Para usar, chame a tool cluster_consultar (n=${e.tamanho}) com o ` +
          `pedido do usuario e o material relevante.`;
      }
    },

    "command.execute.before": async (input, output) => {
      if (input.command !== "cluster") return;
      const arg = (input.arguments ?? "").trim();
      const partes = arg.split(/\s+/);
      const sub = partes[0];

      // /cluster status | off | N | (vazio = ligar 10)
      let n = DEFAULT_N;
      let acao = "ligar";
      if (sub === "off" || sub === "0") acao = "desligar";
      else if (sub === "status") acao = "status";
      else if (sub === "prontidao" || sub === "ready") acao = "prontidao";
      // Modo rapido: medido 2026-10-01 — 10 agentes sobre arquivo real
      // levaram de 30s a 9 MINUTOS conforme a saude do relay. Para uso
      // diario isso e impraticavel. `rapido` usa as 3 lentes de maior
      // retorno (correcao, seguranca, contrato) e cabe em segundos.
      else if (sub === "rapido" || sub === "fast" || sub === "quick") {
        acao = "ligar";
        n = 3;
      } else if (sub && /^\d+$/.test(sub)) n = Math.max(1, Math.min(Number(sub), PERFIS.length));

      if (acao === "desligar") {
        estado(input.sessionID).tamanho = 0;
        estado(input.sessionID).ligadoEm = 0;
        output.parts = [
          { type: "text", text: "Comite desligado. Respostas normais a partir de agora." },
        ];
        return;
      }

      if (acao === "status") {
        const e = estado(input.sessionID);
        output.parts = [
          {
            type: "text",
            text: e.tamanho > 0
              ? `Comite LIGADO com ${e.tamanho} agente(s) desde ${new Date(e.ligadoEm).toLocaleTimeString()}.`
              : "Comite desligado. Use /cluster 10 para ligar.",
          },
        ];
        return;
      }

      // Liga e ja verifica prontidao de verdade (uma chamada real ao relay).
      const t0 = Date.now();
      const probe = await perguntarAgente(
        PERFIS[0],
        "Responda apenas com a palavra: PRONTO",
        { orcamento: 512 },
      );
      const fila = PERFIS.slice(0, n).map((p) => `  - ${p.nome}`).join("\n");

      if (!probe.ok) {
        const e = estado(input.sessionID);
        e.tamanho = 0;
        e.ligadoEm = 0;
        output.parts = [
          {
            type: "text",
            text:
              `NAO FOI POSSIVEL ARMAR O COMITE.\n${probe.erro}\n\n` +
              `Nada foi ligado. Verifique rede / cota do relay.`,
          },
        ];
        return;
      }

      const ligado = estado(input.sessionID);
      ligado.tamanho = n;
      ligado.ligadoEm = Date.now();

      output.parts = [
        {
          type: "text",
          text:
            `COMITE ARMADO: ${n} agentes (${MODELO}) prontos em ${fmtMs(Date.now() - t0)}.\n` +
            `Relay respondeu, chave aceita, lente viva.\n\n` +
            `PERFIS:\n${fila}\n\n` +
            `Ja estou esperando o prompt. Mande o trabalho e eu consulto os ${n} ` +
            `de uma vez, com uma lente diferente para cada.\n\n` +
            `TEMPO ESPERADO: ${n <= 3 ? "~10-40s (comite rapido)" : `~${n * 15}s a ${n * 60}s, ` +
              `conforme a saude do relay`}.\n` +
            (n <= 3
              ? `Para comite completo (10 lentes): /cluster 10`
              : `Para checagem rapida: /cluster rapido`),
        },
      ];
    },
  };
};