# ADR-0023 - Comunicacao Pipeline-UI via Arquivos JSON de Aprovacao

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

A ADR-0022 define que o HITL usa protocolo abstrato com implementacoes plugaveis.
E necessario definir o **mecanismo concreto** de comunicacao entre o pipeline Python
e a interface de usuario (Streamlit ou outra).

Opcoes avaliadas: filas em memoria, WebSocket, banco de dados, arquivos em disco.

---

## Decisao

A comunicacao entre pipeline e UI sera feita via **arquivos JSON em disco** no
diretorio `approvals/`.

### Protocolo

```text
1. Pipeline gera arquivo JSON com status "pendente"
   -> approvals/{tipo}_{timestamp}.json

2. Pipeline entra em polling (1s intervalo)

3. UI (Streamlit) le arquivo e exibe pedido ao usuario

4. Usuario decide (aprovar/rejeitar/editar/postergar)

5. UI grava decisao no mesmo arquivo JSON

6. Pipeline detecta campo "decisao" preenchido e continua
```

### Estrutura do arquivo JSON

```text
{
  "id": "hitl_mapeamento_semantico_1720450981",
  "tipo": "mapeamento_semantico",
  "timestamp": "2026-07-08T14:23:01",
  "status": "pendente",
  "resumo": "Confirme o mapeamento de colunas",
  "dados": { ... },
  "decisao": null,
  "comentario": null,
  "decidido_por": null,
  "decidido_em": null
}
```

### Apos decisao humana

```text
{
  "id": "hitl_mapeamento_semantico_1720450981",
  "tipo": "mapeamento_semantico",
  "timestamp": "2026-07-08T14:23:01",
  "status": "resolvido",
  "resumo": "Confirme o mapeamento de colunas",
  "dados": { ... },
  "decisao": "aprovado",
  "comentario": "OK, Promocao_Flag pode ser ignorada",
  "decidido_por": "analista_ey_01",
  "decidido_em": "2026-07-08T14:23:45"
}
```

### Tipos de pedido reconhecidos

```text
mapeamento_semantico
script_etl
fila_nexus
incompatibilidade_dados
```

---

## Alternativas consideradas

### Alternativa A - WebSocket bidirecional

Vantagens:

* comunicacao em tempo real
* sem polling

Desvantagens:

* mais complexo
* dependencia de biblioteca WebSocket
* nao gera arquivo auditavel por padrao

### Alternativa B - SQLite como fila

Vantagens:

* transacional
* multi-processo seguro

Desvantagens:

* mais complexo que JSON
* dependencia extra
* overhead para MVP

### Alternativa C - Arquivos JSON em disco

Vantagens:

* simples de implementar
* auditavel (arquivos ficam no disco)
* funciona com qualquer UI
* facil de inspecionar manualmente
* sem dependencia extra

Desvantagens:

* polling (latencia de ~1s)
* race condition teorica (mitigavel com lock)
* acumula arquivos no disco (limpeza periodica)

---

## Justificativa

Alternativa C foi escolhida por simplicidade, auditabilidade e ausencia de dependencias.
O polling de 1s e aceitavel para demo. Os arquivos JSON servem como audit trail natural.

---

## Consequencias positivas

* Arquivos JSON sao a auditoria natural das decisoes humanas
* Qualquer UI pode consumir/produzir esses arquivos
* Facil de depurar (basta ler os JSONs)
* Sem dependencia de infra (sem Redis, sem banco)

---

## Consequencias negativas ou trade-offs

* Latencia de ~1s por polling
* Diretorio `approvals/` precisa de limpeza periodica
* Race condition em cenarios multi-processo (mitigavel)

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
Nenhum. Os arquivos JSON reforcam auditabilidade e HITL.
```

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [x] `docs/testing.md`
* [ ] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

---

## Impacto em codigo

* [x] novo arquivo: `hitl.py`
* [x] novo arquivo: `app_streamlit.py`
* [x] `nexus.py`
* [x] `.gitignore` (adicionar `approvals/` ou `approvals/*.json`)

---

## Impacto em testes

* [x] testes unitarios
* [x] testes de integracao

Detalhar:

```text
Testar geracao de arquivo JSON com campos corretos
Testar leitura de decisao apos edicao do arquivo
Testar timeout de polling (limite maximo de espera)
Testar cleanup de arquivos antigos
```

---

## Criterios de aceite

* [ ] Diretorio approvals/ criado automaticamente
* [ ] JSON gerado com todos os campos obrigatorios
* [ ] Streamlit le e exibe pedidos pendentes
* [ ] Streamlit grava decisao no JSON
* [ ] Pipeline detecta decisao e continua
* [ ] Arquivos JSON servem como audit trail

---

## Decisoes relacionadas

```text
ADR-0008 - Human-in-the-loop obrigatorio
ADR-0012 - Auditoria sem dados sensiveis
ADR-0022 - HITL via protocolo abstrato com Streamlit
```
