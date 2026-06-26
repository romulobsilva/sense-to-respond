# ADR-0015 - UI MVP Aprova/Rejeita, mas Nao Executa

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

O MVP do Sense to Respond gera sinais, proposicoes e uma fila Nexus para revisao humana.

Em uma etapa de interface minima, o usuario deve conseguir visualizar:

```text
sinais detectados
proposicoes priorizadas
impacto financeiro estimado
urgencia
evidencias
confianca
motivo de revisao obrigatoria
limitacoes dos dados
```

Tambem deve poder interagir com cada item da fila.

Acoes esperadas na UI:

```text
aprovar proposicao
rejeitar proposicao
pedir mais contexto
registrar comentario
visualizar evidencias
visualizar auditoria resumida
```

Entretanto, o MVP ainda nao possui Bridge operacional nem integracao segura com ERP, WMS, TMS, sistemas de pedido, estoque, forecast ou email operacional.

Portanto, a UI nao deve executar acoes operacionais. Ela deve apenas registrar decisoes humanas sobre as proposicoes.

---

## Decisao

A UI do MVP deve ser uma interface de revisao e decisao humana, nao uma interface de execucao operacional.

A UI pode:

```text
mostrar fila Nexus
mostrar proposicoes candidatas
mostrar sinais e evidencias
mostrar impacto e urgencia calculados
mostrar critic.confianca
mostrar validacao
mostrar motivo de revisao obrigatoria
permitir aprovar
permitir rejeitar
permitir pedir mais contexto
permitir comentario humano
registrar decisao humana em auditoria
```

A UI nao pode:

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
enviar comando para sistema externo
acionar Bridge operacional
simular execucao real sem rotulo claro de simulacao
```

No MVP, "aprovar" significa:

```text
registrar que o usuario aprovou a proposicao para avaliacao/acao externa ao sistema
```

Nao significa:

```text
executar automaticamente a acao recomendada
```

---

## Fluxo permitido da UI MVP

Fluxo recomendado:

```text
Nexus monta fila
  -> UI exibe cards
  -> usuario revisa evidencias
  -> usuario aprova, rejeita ou pede contexto
  -> UI registra decisao em auditoria
  -> nenhuma acao operacional e executada
```

Estados possiveis para um item:

```text
pendente_revisao
aprovado_humano
rejeitado_humano
contexto_solicitado
bloqueado_por_validacao
bloqueado_por_baixa_confianca
```

Estados proibidos no MVP:

```text
executado
pedido_criado
estoque_alterado
forecast_alterado
acao_enviada_ao_erp
email_operacional_enviado
```

---

## Alternativas consideradas

### Alternativa A - UI apenas leitura

Descricao:

```text
A UI mostra os resultados, mas nao permite interacao.
```

Vantagens:

* simples;
* baixo risco;
* facil de implementar;
* nao exige persistencia de decisoes.

Desvantagens:

* reduz valor do Nexus;
* nao captura feedback humano;
* dificulta demonstrar fila decisoria;
* nao prepara evolucao futura para Bridge.

---

### Alternativa B - UI aprova/rejeita e registra decisao

Descricao:

```text
A UI permite aprovar, rejeitar, pedir contexto e comentar, mas nao executa nenhuma acao operacional.
```

Vantagens:

* preserva human-in-the-loop;
* melhora demonstracao do MVP;
* registra decisao humana;
* prepara dados para evolucao futura;
* mantem baixo risco operacional;
* nao exige integracao com sistemas externos.

Desvantagens:

* aprovacao nao gera execucao automatica;
* usuario ainda precisa agir fora do sistema;
* pode haver expectativa de automacao maior.

---

### Alternativa C - UI aprova e executa

Descricao:

```text
A UI permite aprovar uma proposicao e executar automaticamente a acao em sistema externo.
```

Vantagens:

* maior automacao;
* maior impacto demonstrativo;
* reduz tempo entre decisao e acao.

Desvantagens:

* alto risco operacional;
* exige Bridge;
* exige controle de permissao;
* exige rollback;
* exige integracao segura;
* exige auditoria mais robusta;
* fora do escopo do MVP.

---

## Justificativa

A alternativa escolhida foi:

```text
UI aprova/rejeita e registra decisao, mas nao executa.
```

Essa decisao preserva o principio:

```text
Human-in-the-loop obrigatorio no MVP
```

e tambem preserva:

```text
Sem Bridge/ERP/WMS/TMS no MVP
```

A UI deve demonstrar o valor do sistema como camada de inteligencia e priorizacao, sem introduzir risco de execucao operacional prematura.

---

## Consequencias positivas

* Mantem risco operacional baixo.
* Permite demonstrar fila Nexus.
* Registra decisoes humanas.
* Melhora rastreabilidade.
* Preserva governanca.
* Prepara evolucao futura para Bridge.
* Permite coletar feedback do usuario.
* Facilita auditoria de aprovacao/rejeicao.
* Evita execucao automatica indevida.
* Mantem MVP tecnicamente viavel.

---

## Consequencias negativas ou trade-offs

* A aprovacao nao executa a acao.
* O usuario precisa agir fora do sistema.
* Pode haver expectativa comercial de automacao maior.
* Sera necessaria fase futura para Bridge.
* A UI precisa deixar claro o significado de "aprovar".
* Pode exigir registro persistente de decisoes.

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
Nenhum invariante foi violado. A UI apenas registra decisoes humanas e nao executa acoes operacionais.
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
A arquitetura deve declarar que a UI minima do MVP e uma interface de revisao humana, nao uma camada de execucao operacional.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `nexus.py`
* [x] `state_types.py`
* [x] `audit.py`
* [x] `guardrails.py`
* [x] `main.py`
* [ ] `optimus.py`
* [ ] `validator.py`
* [ ] `critic.py`
* [ ] `agent.py`
* [ ] `harness.py`

Novo arquivo possivel:

```text
app.py
```

ou:

```text
ui.py
```

Responsabilidade da UI:

```text
exibir fila
exibir evidencias
capturar decisao humana
registrar evento de auditoria
nao executar acao operacional
```

---

## Impacto em state

Campos recomendados para itens da fila:

```text
status_decisao
decisao_humana
comentario_humano
usuario_decisor
timestamp_decisao
motivo_decisao
```

Valores permitidos para `decisao_humana`:

```text
aprovado
rejeitado
contexto_solicitado
pendente
```

Valores proibidos no MVP:

```text
executado
enviado_erp
pedido_criado
estoque_alterado
```

Regra:

```text
A aprovacao humana no MVP nao altera o status para executado.
```

---

## Impacto em auditoria

Eventos recomendados:

```text
ui_fila_visualizada
ui_item_visualizado
usuario_aprovou
usuario_rejeitou
usuario_pediu_contexto
usuario_comentou
```

Metadados seguros:

```text
proposicao_id
status_anterior
status_novo
usuario_id, se disponivel
timestamp
comentario_sanitizado, se houver
```

Eventos proibidos no MVP:

```text
acao_executada_erp
pedido_criado
estoque_alterado
forecast_alterado
email_operacional_enviado
```

---

## Impacto em prompts

A UI nao deve depender de prompt LLM para decidir se uma acao pode ser executada.

O LLM pode ajudar a explicar:

```text
por que esta proposicao foi priorizada
quais evidencias sustentam a proposicao
quais limitacoes existem
```

O LLM nao pode:

```text
aprovar pelo usuario
executar acao
enviar comando operacional
alterar status para executado
```

---

## Impacto em testes

Testes exigidos:

* [x] fila Nexus aparece com itens;
* [x] item pode ser aprovado;
* [x] item pode ser rejeitado;
* [x] item pode pedir mais contexto;
* [x] aprovacao registra auditoria;
* [x] rejeicao registra auditoria;
* [x] pedido de contexto registra auditoria;
* [x] aprovacao nao executa Bridge;
* [x] aprovacao nao altera estoque;
* [x] aprovacao nao cria pedido;
* [x] UI nao mostra linguagem de execucao automatica.

Comandos minimos:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Se houver UI Streamlit:

```bash
python -m py_compile app.py
```

ou teste manual registrado em `docs/agent.log.md`.

---

## Criterios de aceite

* [ ] UI exibe fila Nexus.
* [ ] UI exibe evidencias por proposicao.
* [ ] UI mostra status de revisao.
* [ ] UI permite aprovar sem executar.
* [ ] UI permite rejeitar.
* [ ] UI permite pedir contexto.
* [ ] UI registra decisao humana em auditoria.
* [ ] UI nao chama Bridge.
* [ ] UI nao altera sistemas externos.
* [ ] Output deixa claro que aprovacao nao executa automaticamente.
* [ ] Testes minimos passam.

---

## Plano de migracao

Implementar em etapas:

```text
1. Definir campos de decisao humana no state.
2. Criar funcao para atualizar status da fila.
3. Criar eventos de auditoria de decisao humana.
4. Criar UI minima com cards.
5. Exibir evidencias, impacto, urgencia e confianca.
6. Adicionar botoes aprovar/rejeitar/pedir contexto.
7. Garantir que botoes apenas registram decisao.
8. Criar testes ou checklist manual.
9. Atualizar docs/planning.md.
10. Registrar em docs/agent.log.md.
```

---

## Plano de rollback

Se a UI introduzir risco de execucao operacional:

```text
1. Remover botoes de acao.
2. Manter apenas visualizacao.
3. Reintroduzir aprovar/rejeitar apenas como registro interno.
4. Criar teste para impedir chamada Bridge.
5. Registrar correcao em agent.log.md.
```

Rollback proibido:

```text
aprovar e executar automaticamente
simular execucao real sem rotulo de simulacao
chamar ERP/WMS/TMS no MVP
registrar status executado no MVP
```

---

## Riscos

| Risco                                         | Probabilidade | Impacto    | Mitigacao                          |
| --------------------------------------------- | ------------- | ---------- | ---------------------------------- |
| Usuario interpretar aprovacao como execucao   | Media         | Alto       | Texto claro na UI e disclaimer     |
| Desenvolvedor conectar Bridge cedo demais     | Media         | Alto       | Regras Cursor, ADR e testes        |
| UI registrar status "executado" indevidamente | Media         | Alto       | Whitelist de status permitidos     |
| Comentarios humanos conterem dados sensiveis  | Media         | Medio/Alto | Sanitizacao e auditoria segura     |
| UI virar fonte de decisao fora do state       | Media         | Medio      | Atualizar state e auditoria sempre |

---

## Decisoes relacionadas

```text
ADR-0007 - Guardrails em tres camadas
ADR-0008 - Human-in-the-loop obrigatorio no MVP
ADR-0012 - Auditoria sem dados sensiveis
ADR-0014 - Output com evidencias, disclaimer e revisao
```

---

## Observacoes

Esta ADR permite uma UI util sem antecipar Bridge.

Linguagem recomendada:

```text
A UI do MVP permite revisar, aprovar, rejeitar e pedir mais contexto, registrando a decisao humana sem executar a acao operacional.
```

Evitar:

```text
A UI aprova e aplica a decisao automaticamente.
```
