---
description: Ativa 10 agentes space-bunny e executa o pipeline completo
agent: build
---
Execute o pipeline de 10 agentes sobre o alvo informado.

**Alvo:** $1
**Tarefa:** $2

Informe quantos etapas quer rodar (padrao: todas):

!`python "./VMP-AI/cluster/cluster_cli.py" run --alvo "$1" --tarefa "$2"`

Acima está a SAÍDA REAL da execucao do cluster de 10 agentes. Cada bloco é o
handoff de um agente, na ordem em que rodaram:

- `researcher` → fatos e riscos, antes de qualquer codigo
- `reader` → estrutura, contratos e o ponto minimo de mudanca
- `maker` → implementa (grava o arquivo via write_file)
- `critic` x3 → 3 revisoes em paralelo com lentes distintas
  (correcao, seguranca/contrato, concorrencia/manutenibilidade)
- `fixer` → corrige os defeitos apontados
- `optimizer` → limpeza final sem mudar comportamento

Sua tarefa agora:

1. Leia os artefatos em `./VMP-AI/cluster/runs/`
   (o diretorio mais recente) para ver a saida COMPLETA de cada agente — o
   comando acima resume, mas o handoff JSON tem tudo.
2. Verifique se o que os agentes gravaram esta realmente no arquivo alvo
   ($1). Nao confie no resumo: leia o arquivo.
3. Se algum agente falhou, diga qual papel falhou e por que. Nao esconda.
4. Apresente o diff final e o que cada papel contribuiu.

Nao faca refatoracao por conta propria. O trabalho ja foi feito pelos agentes;
seu papel aqui e conferir e reportar.