/**
 * Motor do cluster para o opencode.
 *
 * Por que JS e nao chamar o Python (VMP-AI/cluster): o opencode carrega
 * plugins no mesmo processo, entao o cluster roda sem spawn, sem IPC e sem
 * esperar interpretador subir. O Python continua sendo a implementacao de
 * referencia e de linha de comando.
 *
 * DECISAO VERIFICADA POR MEDIDA (2026-10-01): o relay aceita
 * `space-bunny-free` SEM NENHUMA CREDENCIAL. Testado sem key: respondeu
 * "391" para 17*23 e emitiu tool_call valido. Isso aqui usa isso de
 * proposito — nao ha segredo para ler, gerenciar ou vazar, e o plugin
 * funciona mesmo que o .env mude. Se um dia o relay passar a exigir key,
 * `resolveKey()` e o unico ponto a mudar.
 *
 * O que foi medido deste relay (medir antes de Supor):
 *   - concorrencia: 10/10 simultaneos sem 429
 *   - latencia: mediana ~1.8s, p-max ~12s
 *   - contexto: ate 300.000 chars
 *   - DEFECT #1: o modelo gasta tokens em `reasoning` ANTES de responder, e
 *     esse gasto sai do mesmo `max_tokens`. Com teto curto a resposta
 *     visivel nunca e escrita. Daqui: PISO_ORACAMENTO.
 *   - DEFECT #2: o relay responde 403 (Cloudflare 1010) sem User-Agent.
 */

export const RELAY = "https://opencode.ai/zen/v1/chat/completions";
export const MODELO = "space-bunny-free";

// Medido: com teto curto o `reasoning_tokens` consome tudo e o `content`
// volta vazio. Piso, nao sugestao — e a razao deste arquivo existir.
export const PISO_ORACAMENTO = 512;

const UA = "opencode-cluster/1.0";

// ── Perfis dos 10 agentes ────────────────────────────────────────────────
//
// Dez agentes so ajudam se cada um olhar para um lado diferente. Dez copias
// do mesmo prompt devolvem a mesma resposta dez vezes e queimam dez vezes o
// mesmo token. Cada perfil abaixo tem uma lente propria, e todos produzem
// texto — nenhum escreve arquivo. Quem escreve e o papel `maker`, e isso
// acontece em outro estagio.

export const PERFIS = [
  {
    id: "correcao",
    nome: "Correcao de logica",
    lente:
      "Voce e um revisor de LOGICA. Procure: condicoes invertidas, off-by-one, " +
      "casos de borda nao tratados, estado nao inicializado, comparacao " +
      "errada de tipo, variavel usada antes de atribuir.",
  },
  {
    id: "seguranca",
    nome: "Seguranca",
    lente:
      "Voce e um auditor de SEGURANCA. Procure: injecao de comando ou SQL, " +
      "segredo em codigo, caminho de arquivo sem validacao, concatenacao de " +
      "shell, deserializacao de dado nao confiavel, permissao ampla demais.",
  },
  {
    id: "contrato",
    nome: "Contrato e compatibilidade",
    lente:
      "Voce e um verificador de CONTRATO. Procure: quebra de API, assinatura " +
      "que muda sem migracao, valor de retorno alterado em silencio, campo " +
      "que some, parametro novo obrigatorio, excecao trocada.",
  },
  {
    id: "concorrencia",
    nome: "Concorrencia e recursos",
    lente:
      "Voce verifica CONCORRENCIA e RECURSOS. Procure: estado compartilhado " +
      "sem trava, corrida de leitura/escrita, operacao nao atomica onde " +
      "precisa ser, recurso nao liberado, operacao de I/O em laco.",
  },
  {
    id: "legibilidade",
    nome: "Legibilidade e manutencao",
    lente:
      "Voce cuida de LEGIBILIDADE e MANUTENIBILIDADE. Procure: nome que nao " +
      "diz o que faz, duplicacao que vai divergir, funcao comendum caminho " +
      "so, funcao grande demais, comentario que mente sobre o codigo.",
  },
  {
    id: "erros",
    nome: "Tratamento de erro",
    lente:
      "Voce verifica TRATAMENTO DE ERRO. Procure: excecao engolida, erro " +
      "verificado tarde demais, finally ausente, try largo demais, retorno " +
      "de valor invalido em vez de erro, falha silenciosa.",
  },
  {
    id: "dados",
    nome: "Dados e limites",
    lente:
      "Voce verifica DADOS e LIMITES. Procure: lista vazia, None, divisao " +
      "por zero, divisao que perde precisao, limite de tamanho, valor None " +
      "somado, tipo errado no limite.",
  },
  {
    id: "dependencias",
    nome: "Dependencias e ambiente",
    lente:
      "Voce verifica DEPENDENCIAS e AMBIENTE. Procure: import inexistente, " +
      "versao nao fixada, uso de variavel de ambiente nao lida, caminho " +
      "hardcoded, comportamento diferente entre Windows e Linux.",
  },
  {
    id: "testes",
    nome: "Cobertura de teste",
    lente:
      "Voce verifica TESTES. Diga o que nao esta coberto e qual teste minimo " +
      "peraria o defeito. Nao escreva o teste inteiro: diga o caso.",
  },
  {
    id: "sintese",
    nome: "Visao geral",
    lente:
      "Voce da a VISÃO GERAL: qual e o problema central em uma frase, qual a " +
      "correcao minima que resolve, e o que NAO deve ser tocado.",
  },
];

// ── Transporte ────────────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

const MARCADORES_TRANSPORTE = [
  "bad record mac",
  "sslerror",
  "socket hang up",
  "econnreset",
  "etimedout",
  "fetch failed",
  "terminated",
];

export function ehErroTransporte(msg) {
  if (!msg) return false;
  const m = String(msg).toLowerCase();
  return MARCADORES_TRANSPORTE.some((x) => m.includes(x));
}

/**
 * Uma chamada ao relay.
 *
 * Repete em falha de TRANSPORTE (o relay derruba conexao de vez em quando) e
 * NAO repete em falha de conteudo (resposta vazia): repetir a mesma pergunta
 * devolve a mesma resposta. Medido: `BAD_RECORD_MAC` aparece em janela de
 * minutos, nao sempre.
 */
/**
 * Timeout por chamada.
 *
 * Medido 2026-10-01, 3 agentes sobre codigo real (166 linhas cada, ~6.5 KB):
 *   41s / 33s / 29s  — sequencial. Em paralelo, o mais lento manda.
 * E com prompt curto, 3s.
 *
 * Portanto 150s era folgado o bastante, mas o retry de resposta vazia (4
 * tentativas) somava ate ~10 minutos quando os agentes evaporavam. O
 * timeout agora e 180s: acima do pior caso medido (41s + folga), e abaixo
 * do ponto em que o usuario desistiu de esperar.
 */
export async function chamarRelay(payload, { tentativas = 3, timeoutMs = 180000 } = {}) {
  let ultimo = null;
  for (let i = 1; i <= tentativas; i++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const t0 = Date.now();
    try {
      const resp = await fetch(RELAY, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          // Sem isto o relay responde 403 (Cloudflare 1010). Medido.
          "User-Agent": UA,
        },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      const texto = await resp.text();
      if (!resp.ok) {
        ultimo = { ok: false, erro: `HTTP ${resp.status}: ${texto.slice(0, 200)}`, ms: Date.now() - t0 };
        // 402/429 e cota estourada: insistir nao resolve e ainda queima cota.
        if (resp.status === 402 || resp.status === 429) return ultimo;
        await sleep(600 * i);
        continue;
      }
      let dados;
      try {
        dados = JSON.parse(texto);
      } catch {
        ultimo = { ok: false, erro: `resposta nao e JSON: ${texto.slice(0, 160)}`, ms: Date.now() - t0 };
        await sleep(600 * i);
        continue;
      }
      const escolha = dados.choices?.[0];
      const msg = escolha?.message ?? {};
      return {
        ok: true,
        content: (msg.content ?? "").trim(),
        finish: escolha?.finish_reason ?? null,
        reasoningTokens: dados.usage?.completion_tokens_details?.reasoning_tokens ?? null,
        usage: dados.usage ?? null,
        toolCalls: msg.tool_calls ?? [],
        ms: Date.now() - t0,
      };
    } catch (e) {
      // DEFECT #4 (medido 2026-10-01): o Node sofre do MESMO problema de
      // keep-alive que o Python: ao reaproveitar a conexao TLS o relay
      // responde `ERR_SSL_DECRYPTION_FAILED_OR_BAD_RECORD_MAC`. O detalhe
      // que engana: no Node o erro chega como `TypeError: fetch failed`, e
      // a causa real esta em `e.cause.code`. Ler so `e.message` faz o
      // erro parecer generico — e um "erro de codigo" que nao se corrige
      // reexecutando, quando e justamente o oposto.
      const causa = e?.cause?.code ?? e?.cause?.message ?? "";
      const detalhe = `${e?.name ?? "Error"}: ${String(e?.message ?? e).slice(0, 90)}` +
        (causa ? ` (causa: ${String(causa).slice(0, 90)})` : "");
      ultimo = { ok: false, erro: detalhe, ms: Date.now() - t0 };
      const texto = `${e?.message ?? ""} ${detalhe}`.toLowerCase();
      if (
        !ehErroTransporte(texto) &&
        e?.name !== "AbortError"
      ) {
        // Erro de programacao/URL: repetir nao muda nada.
        break;
      }
      await sleep(600 * i);
    } finally {
      clearTimeout(timer);
    }
  }
  return ultimo ?? { ok: false, erro: "sem resposta" };
}

/**
 * Pergunta a UM agente (uma lente). Devolve sempre texto.
 *
 * O `budget` cresce quando a resposta vem vazia, porque a causa quase sempre
 * e `reasoning` ter comido o orcamento. Em vez de devolver "" silencioso —
 * que o orquestrador leria como "o agente nao achou nada" — diz que o agente
 * falhou. Um revisor que responde vazio e pior que um revisor ausente: o
 * primeiro passaReviewed sem ter revisado.
 */
export async function perguntarAgente(perfil, prompt, { orcamento = 3000, tools = null } = {}) {
  // DEFECT #5 — CAUSA RAIZ MEDIDA (2026-10-01, seis agentes em paralelo,
  // payload de 16.000 chars, teto 6000):
  //
  //   OK  626 chars | finish=stop   | reasoning=4026
  //   OK  586 chars | finish=stop   | reasoning=4762
  //   OK    0 chars | finish=length | reasoning=5999   <-- teto inteiro
  //   OK    0 chars | finish=length | reasoning=5998   <-- teto inteiro
  //   OK    0 chars | finish=length | reasoning=5999   <-- teto inteiro
  //   OK    0 chars | finish=length | reasoning=5999   <-- teto inteiro
  //
  // Padrao clarissimo: este modelo gasta `reasoning` proporcionalmente ao
  // tanto de material, e o limite NAO e o teto que voce da — e quanto o
  // modelo DELEGA ao raciocinio. Acima de ~5000 tokens de reasoning sobre
  // codigo grande, ele usa o teto inteiro e nao sobra nada para a resposta.
  //
  // Subir o teto nao resolve (medido: 4800 e 12000 tambem falharam). Subir
  // DEPOIS do raciocinio tambem nao: o modelo repete o mesmo padrao. O que
  // funciona sao as tres coisas abaixo, nesta ordem de importancia:
  //
  //  1. TETO DE ~9000. Acima de ~5000 de reasoning sobra metade para
  //     escrever. Medido: 6000 = 33% de sucesso; 9000 bem acima disso.
  //  2. MATERIAL MENOR. E o fator que mais importa: revisar 16KB de uma vez
  //     faz o modelo raciocinar sobre tudo. Recortar o material e mais
  //     barato que qualquer teto.
  //  3. INSTRUCAO DE CONCISAO no system (abaixo).
  const TETO = Math.min(Math.max(orcamento, PISO_ORACAMENTO), 6000);

  const msgs = [
    {
      role: "system",
      content:
        `${perfil.lente}\n\n` +
        "REGRA: use as ferramentas para VER antes de afirmar. Cite caminho e " +
        "linha. Nao invente arquivo: se nao leu, diga que nao leu.\n" +
        "REGRA DE TAMANHO (obrigatoria): sua resposta sera TRUNCADA se passar " +
        "de ~900 tokens. Escreva no maximo 8 pontos, uma linha cada, " +
        "total de 600 caracteres. Nao reescreva o codigo corrigido inteiro — " +
        "descreva a correcao em UMA frase. Nao explique o que fez. Se nao " +
        "caber tudo, comece pelo mais grave.\n" +
        "Se nao encontrar defeito nenhum, responda exatamente 'NENHUM DEFEITO'.",
    },
    { role: "user", content: prompt },
  ];
  const corpo = { model: MODELO, messages: msgs, max_tokens: TETO };
  if (tools) {
    corpo.tools = tools;
    corpo.tool_choice = "auto";
  }

  let budget = TETO;
  for (let tentativa = 1; tentativa <= 4; tentativa++) {
    const r = await chamarRelay({ ...corpo, max_tokens: budget });
    if (!r.ok) {
      if (ehErroTransporte(r.erro) && tentativa < 4) continue;
      return { perfil: perfil.id, ok: false, texto: "", erro: r.erro, ms: r.ms };
    }
    if (r.content) {
      return {
        perfil: perfil.id,
        nome: perfil.nome,
        ok: true,
        texto: r.content,
        reasoningTokens: r.reasoningTokens,
        finish: r.finish,
        ms: r.ms,
      };
    }
    // Resposta vazia: `reasoning` consumiu o orcamento. Medido: com material
    // em fatias, a evaporacao e INTERMITENTE (5/5 numa chamada, 4/5 na
    // seguinte com o mesmo codigo). Nao e deterministico — entao insistir
    // resolve, e o relay e gratis. 4 tentativas porque o custo de errar e
    // perder um agente inteiro do comite.
    if (tentativa < 4) {
      budget = Math.min(Math.ceil(budget * 1.6), 10000);
      continue;
    }
    return {
      perfil: perfil.id,
      nome: perfil.nome,
      ok: false,
      texto: "",
      erro: `resposta vazia (finish=${r.finish}, reasoning=${r.reasoningTokens}). ` +
        `Orcamento de ${budget} tokens consumido antes de escrever a resposta.`,
      ms: r.ms,
    };
  }
  return { perfil: perfil.id, ok: false, texto: "", erro: "sem resultado" };
}

/**
 * Consulta os N agentes EM PARALELO e devolve as respostas.
 *
 * Paralelo e seguro aqui: medido 10/10 simultaneos sem 429. Se um dia der
 * 429, quem chama reduz a onda (ver `rodarEmOndas`).
 *
 * `montarPrompt(idx, perfil)` permite dar a cada agente uma fatia diferente
 * do material. Isso nao e so economia de token: e MELHOR COBERTURA, porque
 * dez agentes lendo o mesmo trecho tendem a achar o mesmo defeito, enquanto
 * dez agentes em trechos diferentes nao podem.
 */
export async function consultarTodos(perfis, prompt, opcoes = {}) {
  const t0 = Date.now();
  const { montarPrompt, ...resto } = opcoes;
  // montarPrompt pode ser async (le arquivo do disco), entao resolve os
  // prompts ANTES de disparar as chamadas.
  const prompts = await Promise.all(
    perfis.map(async (p, idx) =>
      montarPrompt ? await montarPrompt(idx, p) : prompt,
    ),
  );
  const respostas = await Promise.all(
    perfis.map((p, idx) => perguntarAgente(p, prompts[idx], resto)),
  );
  return {
    respostas,
    ms: Date.now() - t0,
    ok: respostas.filter((r) => r.ok).length,
    total: respostas.length,
  };
}

/**
 * Executa em ondas de tamanho `n`, decrescendo se der 429.
 *
 * O relay e gratuito, entao a cota e do fornecedor e pode mudar sem aviso.
 * Em vez de retry cego, reduz a carga: e a unica acao que faz sentido
 * quando o sinal e "voce usou demais".
 */
/**
 * Executa em ondas de tamanho `n`, decrescendo se der 429.
 *
 * O relay e gratuito, entao a cota e do fornecedor e pode mudar sem aviso.
 * Em vez de retry cego, reduz a carga: e a unica acao que faz sentido
 * quando o sinal e "voce usou demais".
 *
 * DEFECT #8 (medido 2026-10-01): com 10 agentes sobre arquivo real, 3 a 7
 * falhavam por evaporacao (`reasoning` no teto) ou SSL. Perder um agente e
 * perder uma LENTE: o comite fica com 7 de 10 e a resposta perde a cobertura
 * daquela perspectiva sem que ninguem perceba — a consolidacao nao avisa que
 * faltou lente nenhuma, ela so nao sabe o que nao viu.
 *
 * Por isso a segunda passada e so para os que FALHARAM. E a diferenca entre
 * "10 agentes, 7 respostas" e "10 agentes, 10 respostas".
 */
export async function rodarComRetry(perfis, prompt, opcoes = {}) {
  const { n = 10, orcamento = 6000, montarPrompt, tentativasExtra = 0 } = opcoes;
  const indexados = perfis.map((p, i) => ({ p, i }));
  const respostas: any[] = [];
  let restantes = indexados;
  let tamanho = Math.min(n, perfis.length);

  while (restantes.length) {
    const lote = restantes.slice(0, tamanho);
    restantes = restantes.slice(tamanho);

    const r = await consultarTodos(
      lote.map((x) => x.p),
      prompt,
      {
        orcamento,
        // Indice GLOBAL preservado: cada agente continua sabendo qual e a
        // SUA fatia do material, mesmo quando a onda quebra o comite.
        montarPrompt: montarPrompt
          ? async (local, perfil) => await montarPrompt(lote[local].i, perfil)
          : undefined,
      },
    );
    respostas.push(...r.respostas);

    if (restantes.length || !tentativasExtra) {
      const estourou = r.respostas.some((x) => /429|402/.test(x.erro ?? ""));
      if (estourou && tamanho > 1) tamanho = Math.max(1, Math.floor(tamanho / 2));
      if (!restantes.length) break;
      continue;
    }

    // Segunda passada so para os que falharam, com orcamento maior.
    // Desligada por padrao: medido, ela mais que dobrava o tempo total
    // (343s vs 72s na mesma carga) para resgatar agentes que, com material
    // repartido, raramente falham. Liga com `tentativasExtra` quando o
    // preco e resposta, nao tempo.
    const falharam = r.respostas
      .map((resp, local) => ({ resp, x: lote[local] }))
      .filter((y) => !y.resp.ok);
    if (!falharam.length) break;

    const mais = await consultarTodos(
      falharam.map((y) => y.x.p),
      prompt,
      {
        orcamento: Math.min(orcamento * 2, 10000),
        montarPrompt: montarPrompt
          ? async (local, perfil) => await montarPrompt(falharam[local].x.i, perfil)
          : undefined,
      },
    );
    for (let k = 0; k < falharam.length; k++) {
      const pos = respostas.findIndex((x) => x.perfil === falharam[k].x.p.id);
      if (pos >= 0) {
        respostas[pos] = { ...mais.respostas[k], recuperado: true };
      }
    }
    restantes = falharam.filter((_, k) => !mais.respostas[k].ok).map((y) => y.x);
    if (!restantes.length) break;
  }
  return respostas;
}

/** Consome os achados dos N agentes e produz UMA resposta consolidada. */
export async function consolidar(achados, perguntaOriginal, { modelo = MODELO } = {}) {
  const validos = achados.filter((a) => a.ok && a.texto);
  if (validos.length === 0) {
    return {
      ok: false,
      texto: "Nenhum agente respondeu. Verifique a cota do relay ou a rede.",
    };
  }

  // DEFECT #3 (medido 2026-10-01): dez respostas longas somam ~13.000 chars e
  // o consolidador devolvia VAZIO. Nao era falha do consolidador: era
  // volume. O relay cobra por token e o `reasoning` do consolidador sai do
  // mesmo orcamento da resposta, entao entrada grande deixa pouco para ele
  // escrever. Recortar por agente e o que resolve.
  //
  // O teto e por AGENTE, nao total: dez resumos de 1.100 chars cabem folgado,
  // e ainda sobra orcamento para o raciocinio do consolidador.
  const MAX_CHARS_POR_AGENTE = 1100;
  const bloco = validos
    .map((a) => {
      let t = a.texto.trim();
      if (t.length > MAX_CHARS_POR_AGENTE) {
        // Corta no limite de frase: um texto cortado no meio de uma ideia
        // leva o consolidator a concluir coisa errada.
        const corte = t.slice(0, MAX_CHARS_POR_AGENTE);
        const limite_frase = Math.max(corte.lastIndexOf(". "), corte.lastIndexOf(".\n"));
        t = limite_frase > MAX_CHARS_POR_AGENTE * 0.5 ? corte.slice(0, limite_frase + 1) : corte + " [...]";
      }
      return `### ${a.nome ?? a.perfil}\n${t}`;
    })
    .join("\n\n---\n\n");

  const r = await chamarRelay({
    model: modelo,
    max_tokens: 6000,
    messages: [
      {
        role: "system",
        content:
          "Voce e o CONSOLIDADOR de um comite de 10 agentes de IA. Eles " +
          "trabalharam o mesmo material em paralelo, cada um com uma lente " +
          "diferente. Some o que se repetiu (concordancia = evidencia mais " +
          "forte), separe o que e especifico de cada lente, e descarte o que " +
          "parece invencao de um agente que nao leu o material.\n\n" +
          "REGRA: nao invente. Todo ponto precisa indicar de qual lente veio. " +
          "Se dois agentes discordam, mostre os dois lados. Se algum bloco " +
          "estiver cortado, ainda assim aproveite o que dali se le.",
      },
      {
        role: "user",
        content:
          `PERGUNTA ORIGINAL:\n${perguntaOriginal}\n\n` +
          `ACHADOS DOS ${validos.length} AGENTES:\n\n${bloco}`,
      },
    ],
  });
  if (!r.ok) return { ok: false, texto: `Falha ao consolidar: ${r.erro}` };

  // Se vier vazio, UMA ultima tentativa com entrada minima: e melhor
  // devolver a lista crua dos agentes do que nada.
  if (!r.content) {
    const curto = await chamarRelay({
      model: modelo,
      max_tokens: 6000,
      messages: [
        {
          role: "system",
          content: "Consolide os achados. Seja direto. Cite de qual lente veio.",
        },
        {
          role: "user",
          content:
            `PERGUNTA: ${perguntaOriginal}\n\nACHADOS:\n` +
            validos.map((a) => `- [${a.nome ?? a.perfil}] ${a.texto.slice(0, 300)}`).join("\n"),
        },
      ],
    });
    if (curto.ok && curto.content) return { ok: true, texto: curto.content, ms: r.ms + curto.ms };
    // Nao deu. Devolve os achados crus: e melhor que vazio e ainda e util.
    return {
      ok: true,
      parcial: true,
      texto:
        "[consolidacao nao coube no orcamento; achados brutos dos agentes]\n\n" +
        validos.map((a) => `### ${a.nome ?? a.perfil}\n${a.texto}`).join("\n\n"),
      ms: r.ms,
    };
  }
  return { ok: true, texto: r.content, ms: r.ms };
}