---
description: Coloca 10 agentes space-bunny em prontidao (so esperando o prompt)
---
Verifica e ativa o pool de 10 agentes, deixando todos prontos para o prompt.

!`python "./VMP-AI/cluster/cluster_cli.py" standby`

Acima está o estado do pool. Interprete assim:

- Se todos os slots estão `pronto`: o cluster esta operacional e esperando
  seu comando. Diga isso de forma curta e ofereca o proximo passo
  (`/cluster <arquivo> <tarefa>` para rodar o pipeline completo).
- Se algum slot falhou: **diga qual e por que** (credencial, cota esgotada,
  rede). Nao diga "pronto" com slots caidos — isso seria mentira.
- Se o cache esta `frio`: o prompt cache ainda nao foi aquecido neste
  processo; o primeiro uso paga caro, os seguintes desperdam.

Nao execute o pipeline agora. Este comando so deixa pronto.