---
description: Liga um comite de N agentes de IA em paralelo (padrao 10)
agent: build
---

Use $ARGUMENTS assim:

- **vazio, ou um numero de 1 a 10** → liga o comite com essa quantidade de
  agentes e responde o que happenedo. O plugin verifica o relay de verdade
  antes de dizer que esta pronto.
- **rapido** (ou fast/quick) → liga so **3 agentes** (correcao, seguranca,
  contrato). Use para checagem do dia a dia: responde em segundos, enquanto
  que 10 agentes podem levar minutos.
- **off** ou **0** → desliga o comite.
- **status** → informa se esta ligado.
- **prontidao** → roda a verificacao de prontidao sem mudar o estado.

Quando ligar com sucesso, responda curto: quantos agentes ligaram, que modelo
usam, e que ja esta esperando o prompt. Nao repita a lista de perfis — o
proprio plugin ja devolve isso no texto do comando, e repetir consome contexto
sem acrescentar nada.