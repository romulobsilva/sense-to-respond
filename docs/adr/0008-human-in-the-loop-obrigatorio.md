# ADR-0008 - Human-in-the-Loop Obrigatorio no MVP

---

## Status

Aceito

---

## Data

2026-06-25

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O Sense to Respond tem como objetivo detectar sinais comerciais e operacionais e gerar proposicoes de acao para apoiar decisoes em processos de S&OE.

As proposicoes podem envolver temas como:

```text id="up4isg"
rebalancear estoque
priorizar SKUs
ajustar cobertura
proteger promocao
gerenciar falta ou excesso
ajustar custo
ajustar demanda
```

Mesmo quando essas proposicoes sao bem fundamentadas, elas podem influenciar decisoes com impacto financeiro, comercial e operacional.

No MVP, ainda nao ha integracao operacional com sistemas como:

```text id="ppvv81"
ERP
WMS
TMS
sistemas de pedidos
sistemas de estoque
sistemas de precificacao
ferramentas de email automatico
```

Tambem ainda nao ha Bridge operacional implementado.

Portanto, o sistema deve se limitar a recomendar, priorizar, explicar e organizar proposicoes para decisao humana.

---

## Decisao

No MVP, **human-in-the-loop e obrigatorio**.

O sistema pode:

```text id="1hhhrw"
detectar sinais
calcular desvios com tools deterministicos
gerar proposicoes candidatas
priorizar proposicoes
explicar evidencias
apontar confianca e limitacoes
montar fila Nexus
sugerir proximos passos para revisao humana
```

O sistema nao pode:

```text id="p75uwq"
executar acao operacional automaticamente
alterar estoque
criar pedido
alterar forecast
alterar plano de demanda
alterar preco
enviar comando para ERP/WMS/TMS
enviar email operacional automatico
aprovar proposicao automaticamente
afirmar que uma acao foi executada
```

Toda proposicao deve ser apresentada como candidata para revisao humana.

Linguagem obrigatoria:

```text id="s7qmd9"
proposicao
recomendacao candidata
item para revisao
acao sugerida para aprovacao humana
```

Evitar linguagem como:

```text id="eiijli"
acao executada
pedido criado
estoque ajustado
forecast alterado
decisao aplicada
```

---

## Alternativas consideradas

### Alternativa A - Execucao automatica desde o MVP

Descricao:

```text id="t9glg5"
Permitir que o sistema execute automaticamente acoes em sistemas operacionais quando a confianca for alta.
```

Vantagens:

* maior automacao;
* potencial reducao de tempo de resposta;
* demonstracao mais impactante de autonomia;
* menor trabalho manual.

Desvantagens:

* risco operacional alto;
* exige integracoes seguras;
* exige controle de permissao;
* exige rollback operacional;
* exige auditoria robusta;
* exige validacao juridica e corporativa;
* nao adequado ao MVP;
* pode gerar impactos financeiros incorretos.

---

### Alternativa B - Aprovação automatica apenas para baixo risco

Descricao:

```text id="6j4kms"
Permitir execucao automatica apenas para acoes classificadas como baixo risco.
```

Vantagens:

* equilibrio parcial entre automacao e controle;
* poderia acelerar pequenas decisoes;
* reduz carga humana em casos simples.

Desvantagens:

* ainda exige definir risco operacional;
* ainda exige integracao com sistemas;
* ainda exige logs de aprovacao;
* ainda pode causar erro cumulativo;
* aumenta complexidade do MVP;
* risco de classificar incorretamente uma acao como baixo risco.

---

### Alternativa C - Human-in-the-loop obrigatorio

Descricao:

```text id="hphdlh"
O sistema gera proposicoes, mas todas passam por revisao humana antes de qualquer acao operacional.
```

Vantagens:

* reduz risco operacional;
* melhora aceitacao corporativa;
* facilita auditoria;
* permite validar valor do MVP sem integracao operacional;
* preserva governanca;
* reduz responsabilidade do sistema;
* permite aprendizado com decisoes humanas;
* prepara evolucao segura para Bridge.

Desvantagens:

* menor automacao imediata;
* exige usuario para aprovar ou rejeitar;
* tempo de resposta ainda depende de decisao humana;
* pode parecer menos autonomo.

---

## Justificativa

A alternativa escolhida foi:

```text id="vxm8d0"
Human-in-the-loop obrigatorio no MVP.
```

Essa decisao preserva o principio:

```text id="lwbvv7"
IA = LLM + Harness
```

O LLM e as tools ajudam a detectar, explicar e priorizar.

O humano decide.

Essa separacao e essencial porque o MVP ainda nao possui todos os controles necessarios para execucao autonoma em ambiente corporativo, como:

```text id="uuytkr"
controle granular de permissao
integracao operacional segura
rollback de acoes
simulacao previa obrigatoria
aprovacao formal
monitoramento pos-execucao
gestao de excecoes
```

Portanto, o MVP deve ser um sistema de apoio a decisao, nao um sistema de execucao autonoma.

---

## Consequencias positivas

* Reduz risco operacional.
* Facilita demonstracao segura do MVP.
* Melhora alinhamento com governanca de IA.
* Mantem controle humano sobre decisoes comerciais.
* Evita execucao prematura em sistemas criticos.
* Facilita auditoria.
* Reduz exigencia de integracoes na primeira fase.
* Permite aprender com aprovacoes e rejeicoes humanas.
* Prepara dados para evolucao futura do Bridge.
* Evita overclaiming tecnico e comercial.

---

## Consequencias negativas ou trade-offs

* Menor automacao imediata.
* Necessidade de interface ou fila de revisao.
* Dependencia de usuario para agir.
* Tempo de resposta operacional ainda pode ter atraso.
* Valor percebido depende da qualidade da fila e das explicacoes.
* Fase futura sera necessaria para execucao via Bridge.

---

## Invariantes preservados

* [x] Spec antes do codigo
* [x] IA = LLM + Harness
* [x] LLM nao calcula numeros
* [x] Tools deterministicas calculam metricas
* [x] State blackboard
* [x] Sem conversa livre entre agentes no MVP
* [x] Sem MOE dinamico no MVP
* [x] Sem consenso multi-agente no MVP
* [x] Human-in-the-loop obrigatorio
* [x] Critic read-only
* [x] Auditoria obrigatoria
* [x] Sem Bridge/ERP/WMS/TMS no MVP

Explique qualquer invariante afetado:

```text id="5zlecy"
Nenhum invariante foi violado. Esta ADR formaliza que toda proposicao do MVP exige revisao humana antes de qualquer execucao.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text id="uwtmrr"
A arquitetura deve declarar que o MVP termina em fila Nexus para revisao humana. Bridge operacional e execucao automatica ficam fora do MVP.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `nexus.py`
* [x] `guardrails.py`
* [x] `optimus.py`
* [x] `validator.py`
* [x] `critic.py`
* [x] `state_types.py`
* [x] `main.py`
* [x] `audit.py`
* [ ] `agent.py`
* [ ] `harness.py`
* [ ] `tools.py`

Impacto:

```text id="0de9ff"
Nexus deve montar fila de revisao, nao executar acoes. Output guardrail deve garantir disclaimer e linguagem de proposicao. Nenhum componente deve chamar Bridge ou sistemas operacionais no MVP.
```

Novos arquivos previstos:

```text id="x9upn3"
Nenhum arquivo novo obrigatorio para esta ADR.
```

---

## Impacto em state

Campos relacionados:

```text id="mn1ud8"
proposicoes
validacao
critica
fila_nexus
handoffs
auditoria
```

Regras:

* `proposicoes` representam candidatas, nao acoes executadas.
* `fila_nexus` representa itens para revisao humana.
* `revisao_obrigatoria` deve ser verdadeiro quando houver baixa confianca, validacao falha ou alto impacto.
* Nenhum campo do state deve indicar execucao operacional no MVP.
* Se existir campo `acoes_executadas`, ele deve representar apenas tools internas executadas, nao acoes de negocio.

---

## Impacto em prompts

Prompts afetados:

```text id="zf1itc"
final.gerar_explicacao
critic.auditar
dominion.proximo_passo
datashield.inferir_mapa_semantico
```

Regras de linguagem:

O LLM pode escrever:

```text id="4h58ea"
"Recomenda-se revisar a possibilidade de rebalancear estoque do SKU X."
```

O LLM nao pode escrever:

```text id="6oq7eb"
"Estoque do SKU X rebalanceado com sucesso."
```

O LLM pode escrever:

```text id="3b6vuc"
"Esta proposicao deve ser avaliada por um responsavel antes de qualquer acao operacional."
```

O LLM nao pode escrever:

```text id="dfhthm"
"Acao aprovada automaticamente devido a alta confianca."
```

---

## Impacto em UI

Quando houver UI minima, cada item da fila Nexus deve permitir:

```text id="hbk1yi"
aprovar
rejeitar
pedir mais contexto
registrar comentario
visualizar evidencias
visualizar confianca
visualizar motivo de revisao obrigatoria
```

A UI nao deve, no MVP:

```text id="o95g0f"
executar no ERP
alterar estoque automaticamente
enviar pedido automaticamente
enviar email operacional automatico
```

Se houver botao de aprovacao, ele deve registrar apenas decisao humana no MVP, nao executar Bridge.

---

## Impacto em auditoria

A auditoria deve registrar:

```text id="f4hymd"
fila_nexus_criada
item_revisao_obrigatoria
motivo_revisao
usuario_aprovou, quando houver UI
usuario_rejeitou, quando houver UI
usuario_pediu_contexto, quando houver UI
```

A auditoria nao deve registrar:

```text id="n1bi1v"
acao operacional executada
pedido criado
estoque alterado
forecast alterado
```

no MVP, salvo se for explicitamente simulado e identificado como simulacao.

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] teste de fila Nexus criada
* [x] teste de revisao obrigatoria para baixa confianca
* [x] teste de revisao obrigatoria para validacao falha
* [x] teste de output com disclaimer
* [x] teste de ausencia de chamadas Bridge
* [x] teste de ausencia de linguagem de execucao
* [x] teste de proposicoes com status pendente
* [x] teste de auditoria sem acao operacional executada

Detalhar:

```text id="r6f41o"
A suite deve falhar se o output final afirmar que uma acao operacional foi executada automaticamente.
```

---

## Criterios de aceite

* [x] Fila Nexus e gerada.
* [x] Proposicoes aparecem como candidatas.
* [x] Output contem disclaimer.
* [x] Baixa confianca gera revisao obrigatoria.
* [x] Validacao falha gera revisao obrigatoria.
* [x] Alto impacto gera revisao obrigatoria.
* [x] Nenhuma acao operacional e executada.
* [x] Bridge nao e chamado no MVP.
* [x] Prompts nao prometem execucao.
* [x] Auditoria registra fila e motivos de revisao.
* [x] Usuario humano e o ponto final de decisao.

---

## Plano de migracao

Esta decisao ja e o comportamento esperado do MVP.

Para reforcar:

```text id="cov8w5"
1. Revisar output guardrail.
2. Garantir disclaimer obrigatorio.
3. Garantir linguagem de proposicao, nao execucao.
4. Garantir que Nexus gera fila e nao executa.
5. Garantir que Bridge nao aparece no fluxo do MVP.
6. Criar testes contra linguagem de execucao.
7. Atualizar docs/testing.md.
8. Registrar em agent.log.md.
```

---

## Plano de rollback

Nao ha rollback desejado para remover human-in-the-loop no MVP.

Se alguma implementacao introduzir execucao automatica:

```text id="jy7kvh"
1. Remover chamada operacional.
2. Converter acao em item de fila Nexus.
3. Registrar alerta em agent.log.md.
4. Criar teste para impedir regressao.
```

Se no futuro for desejado Bridge:

```text id="9wju0e"
1. Criar nova ADR.
2. Atualizar architecture.md.
3. Atualizar planning.md.
4. Definir permissoes.
5. Definir simulacao e dry-run.
6. Definir aprovacao humana.
7. Definir rollback operacional.
8. Implementar testes de alto risco.
```

---

## Riscos

| Risco                                         | Probabilidade | Impacto    | Mitigacao                                |
| --------------------------------------------- | ------------- | ---------- | ---------------------------------------- |
| Output sugerir que acao foi executada         | Media         | Alto       | Output guardrail e testes de linguagem   |
| Usuario interpretar proposicao como ordem     | Media         | Medio/Alto | Disclaimer claro e status pendente       |
| Desenvolvedor adicionar Bridge cedo demais    | Media         | Alto       | Regras Cursor, planning e ADR            |
| UI aprovar e executar sem controle            | Baixa/Media   | Alto       | UI MVP registra decisao, nao executa     |
| Proposicao de alto impacto passar sem revisao | Media         | Alto       | Regra de revisao obrigatoria por impacto |

---

## Decisoes relacionadas

```text id="rjqt9h"
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard sem conversa livre
ADR-0004 - Critic read-only
ADR-0005 - DataShield Lite antes do Dominion
ADR-0007 - Guardrails em tres camadas
```

---

## Observacoes

Human-in-the-loop nao significa ausencia de IA.

Significa que a IA organiza, calcula, interpreta e prioriza, mas nao substitui a responsabilidade humana por decisoes operacionais.

Linguagem recomendada:

```text id="b8q9ys"
O MVP gera proposicoes priorizadas para revisao humana.
```

Evitar:

```text id="t2hewz"
O MVP executa decisoes automaticamente.
```
