# ADR-0022 - HITL via Protocolo Abstrato com Implementacao Streamlit

---

## Status

Aceito

---

## Data

2026-07-08

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O MVP define human-in-the-loop (HITL) como obrigatorio (ADR-0008), mas nao especifica
**como** o humano interage com o sistema. A interacao ocorre em 4 momentos:

- **M1**: Confirmar mapeamento semantico (DataShield)
- **M2**: Revisar script ETL gerado (DataShield Nivel 2)
- **M3**: Revisar fila Nexus (aprovar/rejeitar proposicoes)
- **M4**: Decidir sobre incompatibilidade de dados (DataShield Nivel 3)

Para demo EY, e necessaria uma interface visual profissional.

---

## Decisao

O HITL deve ser implementado com um **protocolo abstrato** (`InterfaceHITL`) e
**implementacoes concretas** plugaveis:

```text
InterfaceHITL (classe abstrata)
  |
  +-- HITLTerminal     (desenvolvimento, input() no terminal)
  |
  +-- HITLArquivo      (async, polling de arquivo JSON)
  |
  +-- HITLStreamlit    (demo EY, interface web local)
  |
  +-- HITLAutoApprove  (testes automatizados, aprova tudo)
```

### Decisoes de design

1. **Comunicacao pipeline-UI**: via arquivos JSON em disco (`approvals/`)
2. **Interface principal para demo**: Streamlit (Python puro, visual moderno)
3. **Cada decisao HITL salva em JSON**: com timestamp, decisao, autor, comentario
4. **Nexus recebe `hitl` como dependencia injetada**: sem acoplamento a UI
5. **Telas Streamlit**: upload, mapeamento, progresso, fila Nexus, audit trail

### Estrutura de um pedido de aprovacao

```text
PedidoAprovacao:
  tipo: str (mapeamento_semantico, script_etl, fila_nexus, incompatibilidade)
  resumo: str
  detalhes: dict
  decisao: DecisaoHumana | None
  comentario: str | None
```

### Decisoes possiveis

```text
DecisaoHumana:
  APROVADO
  REJEITADO
  EDITADO
  POSTERGADO
```

---

## Alternativas consideradas

### Alternativa A - Apenas terminal (input)

Vantagens:

* zero dependencia
* rapido de implementar

Desvantagens:

* experiencia ruim para demo EY
* nao funciona para usuarios nao tecnicos

### Alternativa B - Apenas Streamlit

Vantagens:

* interface visual

Desvantagens:

* acoplamento direto do pipeline a Streamlit
* nao funciona para testes automatizados

### Alternativa C - Protocolo abstrato com implementacoes plugaveis

Vantagens:

* desacoplamento total
* cada fase usa a implementacao adequada
* testavel com HITLAutoApprove

Desvantagens:

* mais codigo de abstracoes
* comunicacao via arquivo JSON adiciona polling

---

## Justificativa

Alternativa C permite usar HITLTerminal em desenvolvimento, HITLStreamlit em demo e
HITLAutoApprove em testes, sem alterar o Nexus.

---

## Consequencias positivas

* Demo EY com interface visual profissional
* Cada decisao HITL auditavel em JSON
* Pipeline desacoplado da interface
* Testes automatizados sem UI
* Facil trocar implementacao sem mudar pipeline

---

## Consequencias negativas ou trade-offs

* Dependencia de Streamlit para demo
* Polling de arquivo JSON (latencia de ~1s)
* Mais arquivos de aprovacao para gerenciar

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
O HITL e reforcado, nao enfraquecido. Cada interacao humana e registrada em JSON auditavel.
```

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

---

## Impacto em codigo

* [ ] `agent.py`
* [ ] `audit.py`
* [x] `config.py`
* [ ] `critic.py`
* [ ] `guardrails.py`
* [ ] `harness.py`
* [x] `main.py`
* [x] `nexus.py`
* [ ] `optimus.py`
* [ ] `sinais.py`
* [x] `state_types.py`
* [ ] `tools.py`
* [ ] `validator.py`
* [x] novo arquivo: `hitl.py`
* [x] novo arquivo: `app_streamlit.py`

---

## Impacto em testes

* [x] testes unitarios
* [x] testes de integracao

Detalhar:

```text
Testar HITLAutoApprove: pipeline roda sem intervencao
Testar HITLTerminal com mock de input()
Testar fluxo JSON: gerar pedido, simular decisao, verificar leitura
Testar que Nexus funciona com qualquer implementacao de InterfaceHITL
```

---

## Criterios de aceite

* [ ] InterfaceHITL abstrata criada em hitl.py
* [ ] HITLTerminal implementado
* [ ] HITLAutoApprove implementado (testes)
* [ ] HITLStreamlit implementado (demo)
* [ ] Nexus aceita hitl como parametro
* [ ] Decisoes HITL salvas em JSON auditavel
* [ ] pipeline nexus roda com HITLAutoApprove sem intervencao

---

## Decisoes relacionadas

```text
ADR-0008 - Human-in-the-loop obrigatorio
ADR-0015 - UI MVP aprova/rejeita mas nao executa
ADR-0023 - Comunicacao pipeline-UI via JSON
```
