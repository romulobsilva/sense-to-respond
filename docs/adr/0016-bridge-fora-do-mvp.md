# ADR-0016 - Bridge Fora do MVP

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

A arquitetura conceitual do Sense to Respond inclui o componente **Bridge**.

O Bridge representa a camada futura responsavel por conectar proposicoes aprovadas a sistemas operacionais, como:

```text
ERP
WMS
TMS
sistemas de estoque
sistemas de pedidos
sistemas de planejamento
sistemas de precificacao
sistemas de comunicacao operacional
```

Na visao completa, o Bridge poderia executar ou encaminhar acoes aprovadas, por exemplo:

```text
criar pedido
alterar cobertura
acionar reposicao
registrar ajuste de plano
enviar recomendacao para sistema externo
abrir tarefa operacional
```

Entretanto, o MVP atual tem outro objetivo: detectar sinais, gerar proposicoes, validar, auditar, priorizar e apresentar uma fila para decisao humana.

O MVP ainda nao possui todos os elementos necessarios para execucao operacional segura, como:

```text
controle granular de permissao
autenticacao corporativa completa
RBAC por tipo de acao
dry-run obrigatorio
simulacao de impacto
rollback operacional
integracao segura com sistemas externos
monitoramento pos-execucao
trilhas de aprovacao formal
gestao de excecoes
```

Por isso, habilitar Bridge no MVP aumentaria desnecessariamente o risco tecnico, operacional e de governanca.

---

## Decisao

O Bridge fica fora do MVP.

No MVP, o sistema pode:

```text
detectar sinais
calcular metricas
gerar proposicoes candidatas
validar proposicoes
auditar coerencia
montar fila Nexus
exibir evidencias
registrar decisao humana
```

No MVP, o sistema nao pode:

```text
executar acao em ERP
executar acao em WMS
executar acao em TMS
alterar estoque
criar pedido
alterar forecast
alterar plano
alterar preco
enviar email operacional automatico
acionar sistemas externos
marcar proposicao como executada
```

A saida do MVP deve terminar em:

```text
fila Nexus para revisao humana
```

Nao em:

```text
execucao operacional automatica
```

---

## Fronteira do MVP

### Dentro do MVP

```text
DataShield Lite
Dominion
Sinais estruturados
Optimus
Validador deterministico
Critic read-only
Nexus
Fila de revisao humana
Output guardrail
Auditoria
UI minima de aprovacao/rejeicao sem execucao
```

### Fora do MVP

```text
Bridge operacional
integracao ERP
integracao WMS
integracao TMS
execucao automatica
criacao de pedido
alteracao de estoque
alteracao de forecast
envio automatico de email operacional
workflow de aprovacao corporativo completo
rollback operacional
```

---

## Alternativas consideradas

### Alternativa A - Implementar Bridge no MVP

Descricao:

```text
Adicionar execucao operacional desde a primeira versao demonstravel.
```

Vantagens:

* maior impacto demonstrativo;
* aproxima a solucao de automacao ponta a ponta;
* pode reduzir tempo entre deteccao e acao;
* comunica maior autonomia.

Desvantagens:

* risco operacional alto;
* aumenta complexidade;
* exige integracoes reais;
* exige permissao e seguranca;
* exige rollback;
* exige homologacao corporativa;
* exige testes de alto risco;
* pode atrasar o MVP;
* pode criar expectativa de autonomia prematura.

---

### Alternativa B - Implementar Bridge simulado

Descricao:

```text
Criar um Bridge fake que simula execucao sem alterar sistemas reais.
```

Vantagens:

* permite demonstrar fluxo futuro;
* nao altera sistemas reais;
* pode ajudar apresentacoes comerciais.

Desvantagens:

* pode confundir usuario;
* pode ser interpretado como execucao real;
* adiciona escopo ao MVP;
* exige rotulos claros de simulacao;
* pode desviar foco de DataShield, Dominion e Optimus.

---

### Alternativa C - Deixar Bridge fora do MVP

Descricao:

```text
O MVP termina em fila Nexus para revisao humana. Bridge fica para fase futura.
```

Vantagens:

* reduz risco;
* preserva governanca;
* acelera entrega do MVP;
* facilita testes;
* evita integracoes prematuras;
* mantem human-in-the-loop;
* torna escopo mais claro;
* permite validar valor antes de automatizar execucao.

Desvantagens:

* menor automacao imediata;
* usuario precisa executar a acao fora do sistema;
* demonstracao pode parecer menos autonoma;
* fase futura sera necessaria para fechar o ciclo operacional.

---

## Justificativa

A alternativa escolhida foi:

```text
Bridge fora do MVP.
```

Essa decisao preserva os principios:

```text
Human-in-the-loop obrigatorio
Sem execucao operacional automatica
IA = LLM + Harness
```

O MVP deve provar primeiro que consegue:

```text
entender dados
detectar sinais relevantes
gerar proposicoes rastreaveis
validar coerencia
priorizar oportunidades
explicar evidencias
apoiar decisao humana
```

Somente depois disso faz sentido discutir execucao operacional via Bridge.

---

## Consequencias positivas

* Reduz risco operacional.
* Evita integracoes prematuras.
* Mantem escopo do MVP controlado.
* Facilita auditoria.
* Facilita testes.
* Preserva human-in-the-loop.
* Evita prometer automacao que ainda nao existe.
* Permite focar em DataShield Lite, Dominion e Optimus.
* Facilita aceitacao em ambiente corporativo.
* Cria caminho claro para fase futura.

---

## Consequencias negativas ou trade-offs

* O MVP nao executa acoes automaticamente.
* O usuario precisa agir fora do sistema.
* A demonstracao nao mostra ciclo fechado ate ERP/WMS/TMS.
* Uma fase futura sera necessaria para Bridge.
* Pode ser necessario explicar comercialmente que a solucao atual e apoio a decisao.

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

```text
Nenhum invariante foi violado. Esta ADR reforca explicitamente que Bridge e execucao operacional ficam fora do MVP.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/testing.md`
* [x] `docs/agent.log.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text
A arquitetura deve declarar que Bridge e componente futuro. O MVP termina em fila Nexus para revisao humana.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `nexus.py`
* [x] `guardrails.py`
* [x] `main.py`
* [x] `state_types.py`
* [x] `audit.py`
* [ ] `agent.py`
* [ ] `harness.py`
* [ ] `optimus.py`
* [ ] `validator.py`
* [ ] `critic.py`
* [ ] `tools.py`

Impacto:

```text
Nenhum arquivo deve implementar execucao operacional no MVP. Nexus deve apenas montar fila, registrar revisao e expor proposicoes para decisao humana.
```

Arquivos proibidos no MVP sem nova ADR:

```text
bridge.py
erp_client.py
wms_client.py
tms_client.py
order_executor.py
stock_executor.py
```

Esses nomes so devem ser criados em fase futura com ADR especifica, contratos, testes e aprovacao explicita.

---

## Impacto em state

Campos permitidos no MVP:

```text
proposicoes
fila_nexus
validacao
critica
decisao_humana
status_decisao
comentario_humano
```

Campos proibidos no MVP:

```text
acao_executada_erp
pedido_criado
estoque_alterado
forecast_alterado
bridge_status_executado
execucao_operacional_id
```

Se houver campo `acoes_executadas`, ele deve representar apenas tools internas executadas pelo harness, nao acoes de negocio.

---

## Impacto em prompts

Prompts devem evitar linguagem de execucao.

Permitido:

```text
"Esta proposicao deve ser revisada por um responsavel."
"Recomenda-se avaliar a realocacao do estoque."
"Item priorizado para decisao humana."
```

Proibido:

```text
"Estoque realocado."
"Pedido criado."
"Forecast ajustado."
"Acao enviada ao ERP."
"Execucao concluida."
```

O LLM nao pode prometer ou simular execucao operacional.

---

## Impacto em UI

A UI do MVP pode:

```text
mostrar fila
mostrar cards de proposicoes
mostrar evidencias
permitir aprovar
permitir rejeitar
permitir pedir mais contexto
registrar comentario
registrar decisao humana
```

A UI do MVP nao pode:

```text
executar Bridge
chamar ERP
chamar WMS
chamar TMS
criar pedido
alterar estoque
alterar forecast
enviar email operacional automatico
```

Botao "aprovar" no MVP significa:

```text
registrar aprovacao humana
```

Nao significa:

```text
executar a acao automaticamente
```

---

## Impacto em auditoria

Auditoria pode registrar:

```text
proposicao_criada
fila_nexus_criada
usuario_aprovou
usuario_rejeitou
usuario_pediu_contexto
comentario_humano
```

Auditoria nao deve registrar no MVP:

```text
pedido_criado
estoque_alterado
acao_enviada_erp
acao_executada_wms
forecast_alterado
email_operacional_enviado
```

Se houver simulacao futura, o evento deve conter explicitamente:

```text
simulacao=true
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [x] output nao afirma execucao operacional
* [x] fila Nexus e criada
* [x] aprovacao humana nao chama Bridge
* [x] nao existe chamada ERP/WMS/TMS no fluxo MVP
* [x] guardrail bloqueia linguagem de execucao
* [x] auditoria nao registra acao operacional executada

Testes futuros antes de Bridge:

```text
dry-run obrigatorio
permissao por usuario
rollback
simulacao de impacto
aprovacao formal
execucao idempotente
log operacional completo
```

---

## Criterios de aceite

* [x] Bridge nao e implementado no MVP.
* [x] ERP/WMS/TMS nao sao chamados.
* [x] Proposicoes terminam em fila Nexus.
* [x] UI registra decisao, mas nao executa.
* [x] Output contem disclaimer.
* [x] Human-in-the-loop permanece obrigatorio.
* [x] Prompts nao afirmam execucao.
* [x] Auditoria nao registra execucao operacional real.
* [x] Qualquer Bridge futuro exige nova ADR.

---

## Plano de migracao

Esta ADR reforca o escopo atual.

Para garantir aderencia:

```text
1. Revisar architecture.md.
2. Revisar planning.md.
3. Garantir que Bridge esteja em fase futura.
4. Garantir que rules.md bloqueie Bridge no MVP.
5. Garantir que .cursor/rules/spec-driven-dev.mdc bloqueie execucao operacional.
6. Criar ou manter testes de ausencia de Bridge.
7. Registrar em agent.log.md.
```

---

## Plano de rollback

Nao ha rollback desejado para habilitar Bridge no MVP.

Se algum codigo introduzir Bridge prematuramente:

```text
1. Remover chamada operacional.
2. Converter acao em item de fila Nexus.
3. Registrar correcao em agent.log.md.
4. Criar teste para impedir regressao.
```

Se for necessario demonstrar Bridge simulado:

```text
1. Criar nova ADR especifica.
2. Rotular claramente como simulacao.
3. Garantir que nenhuma acao real seja executada.
4. Criar testes de simulacao.
5. Atualizar planning.md.
```

---

## Riscos

| Risco                                        | Probabilidade | Impacto    | Mitigacao                       |
| -------------------------------------------- | ------------- | ---------- | ------------------------------- |
| Desenvolvedor implementar Bridge cedo demais | Media         | Alto       | Regras Cursor, ADR e testes     |
| Usuario interpretar aprovacao como execucao  | Media         | Alto       | Disclaimer e UI clara           |
| Prompt afirmar acao executada                | Media         | Alto       | Output guardrail                |
| Simulacao ser confundida com real            | Media         | Medio/Alto | Rotulo explicito e nova ADR     |
| Escopo do MVP crescer demais                 | Media         | Alto       | Planning e ADR bloqueiam Bridge |

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0007 - Guardrails em tres camadas
ADR-0008 - Human-in-the-loop obrigatorio no MVP
ADR-0014 - Output com evidencias, disclaimer e revisao
ADR-0015 - UI MVP aprova/rejeita, mas nao executa
```

---

## Observacoes

Bridge e importante para a visao futura, mas nao para provar o valor inicial do MVP.

Linguagem recomendada:

```text
Bridge e uma fase futura. O MVP termina em fila Nexus para revisao humana.
```

Evitar:

```text
O MVP executa acoes diretamente em sistemas operacionais.
```
