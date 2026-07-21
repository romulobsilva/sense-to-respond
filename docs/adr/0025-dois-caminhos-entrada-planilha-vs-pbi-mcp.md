# ADR-0025 - Dois Caminhos de Entrada: Planilha (DataShield) vs PBI (MCP/DAX)

---

## Status

Aceito

---

## Data

2026-07-21

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O desenho de produto Sense to Respond prevê dois ingressos até a mesma
máquina de insights (sinais → Optimus → Critic → fila → PDF):

1. Cliente com **planilha / schema cru** → DataShield + HITL
   (e, no desenho futuro, Popa/catálogo de governança).
2. Cliente com **modelo Power BI unificado/confiável** → leitura via
   MCP Power BI (`ExecuteQuery`) com **catálogo DAX** versionado.

O MVP atual implementa bem o caminho (1) com CSV Mondelez e tools
pandas. O caminho (2) foi validado manualmente no Cursor com um
semantic model de teste (Água), não Mondelez. O PBI Mondelez será
publicado **posteriormente**; a arquitetura deve permitir **trocar
artifact_id + arquivo de catálogo** sem redesenhar o Nexus.

Riscos a controlar:

* misturar chat exploratório com batch de relatório;
* depender de `GenerateQuery` (instável) no caminho crítico;
* hardcodar tabelas do modelo Água no orquestrador;
* reimplementar medidas DAX em Python "porque o MCP falhou";
* ambiguidade no fluxograma (MCP só quando dado não unificado).

---

## Decisao

### D1 - Dois ingressos, um motor

```text
Ingresso A (planilha):  DataShield (+ HITL) -> Dominion CSV/tools
Ingresso B (PBI ok):    Dominion PBI (MCP + catalogo DAX)
                              |
                              v
                    Sinais -> Optimus -> Validador -> Critic
                              -> Fila -> Resumo -> PNG/PDF
```

No batch, o Nexus **não** usa agente conversacional para decidir
queries. Usa catálogo pré-definido.

### D2 - MCP = ExecuteQuery + catálogo

* Caminho crítico do relatório: apenas `ExecuteQuery` com DAX do
  catálogo.
* `GenerateQuery` fica fora do batch (opcional só em modo chat/IDE).
* Números vêm do semantic model (DAX). Harness não reimplementa a
  métrica de negócio em Python como fallback padrão.

### D3 - Catálogo trocável (PoC Água → Mondelez depois)

```text
PBI_ARTIFACT_ID + PBI_CATALOG_PATH
```

* PoC: modelo Água + `catalogs/agua_io_*.yaml` (ou equivalente).
* Evolução: modelo Mondelez publicado + `catalogs/mondelez_s2r_*.yaml`.
* Mesmo connector e mesma fase Dominion PBI.

### D4 - Escopo PoC vs backlog pos-PoC

**Na PoC (permitido implementar após esta ADR + contratos):**

* Connector fino + catálogo Água.
* CLI/flag de fonte (`csv` vs `pbi`).
* `resultados_pbi` no state → sinais PoC → PDF reutilizado.
* Testes com fixtures JSON (sem OAuth no CI).

**Backlog pos-PoC (ver planning Fase 1.7a):**

* Catálogo DAX Mondelez S&OE (DOI/SO/SI) quando PBI for publicado.
  **Status:** feito (`catalogs/mondelez_s2r_v1.yaml`, Q1–Q3).
* Cobertura executiva Forward/Oportunidades no caminho PBI
  (`premissa_forward_furada`, `forward_oportunidade` via Q4/Q5).
  **Status:** planning **1.7a.3** (aproximação snapshot vs CSV
  `analisar_forward`; não exige ADR nova enquanto a regra permanecer
  documentada no catálogo).
* Popa / persistência de dataset / governança enterprise.
* Entrega omnichannel (e-mail/WhatsApp) e loop de feedback.
* HITL assíncrono da fila no caminho PBI.
* Connector HTTP Fabric standalone (fora do MCP do Cursor), se
  necessário para cron/CI.
* Unificação completa de tipos de sinal Água ↔ Mondelez.
* Atualização completa da modelagem LaTeX (caps. formais) além da
  nota em Próximos Passos.

---

## Alternativas consideradas

### Alternativa A - So chat MCP (sem batch)

Descartada para o relatório de priorização: não reproduzível.

### Alternativa B - Python reimplementa KPIs se DAX falhar

Descartada como padrão: diverge do modelo PBI. Permitido apenas
extrato tabular + regra **já documentada no catálogo**, nunca
tradutor genérico de DAX.

### Alternativa C - Um unico caminho CSV ate Mondelez PBI existir

Atraz a validação do desenho dual. PoC Água desbloqueia o fio MCP
agora.

---

## Justificativa

Alinha código ao fluxograma de produto, preserva invariantes
(ADR-0001, 0002, 0003, 0008), e isola a troca Mondelez em
**configuração de catálogo**, não em novo orquestrador.

---

## Consequencias positivas

* Dual path explícito na spec.
* PoC testável sem esperar PBI Mondelez.
* Swap futuro barato (YAML + artifact_id).

## Consequencias negativas / trade-offs

* Dois Dominions conceituais (CSV vs PBI) até convergirem formatos
  de `resultados`.
* Catálogo Água não cobre S&OE Mondelez; precisa de segundo YAML
  depois.
* Dependência de auth MCP/Fabric no smoke manual.

---

## Invariantes preservados

* [x] Spec antes do codigo
* [x] IA = LLM + Harness
* [x] LLM nao calcula numeros
* [x] Pipeline sequencial no MVP
* [x] State blackboard
* [x] Critic read-only
* [x] HITL obrigatorio para decisao operacional
* [x] Bridge fora do MVP
* [x] Auditoria sem dataset completo

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/contracts/powerbi_catalog_contract.md` (novo)
* [x] `rules.md`
* [x] `docs/testing.md`
* [x] `docs/agent.log.md`
* [x] `docs/sense_to_respond_modelagem.tex` (nota + backlog)
* [ ] Codigo PoC (somente apos contratos; ver planning 1.7a)

---

## Criterios de aceite (spec)

* [x] ADR registra dual path e swap de catálogo.
* [x] Backlog pos-PoC listado (nao misturado com escopo PoC).
* [x] Contrato de catálogo existe.
* [ ] Codigo PoC: fora deste ADR (planning 1.7a).

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0005 - DataShield Lite antes do Dominion (caminho planilha)
ADR-0012 - Auditoria sem dados sensiveis
ADR-0013 - Dominion executa analises compativeis
ADR-0019 - Dados reais Mondelez (CSV); PBI Mondelez = evolucao
ADR-0024 - Portabilidade multi-dominio (Theta + catalogs PBI)
```

---

## Observacoes

Linguagem recomendada no fluxograma:

```text
PBI unificado = Dominion via MCP: catalogo DAX (ExecuteQuery)
Planilha / schema cru = DataShield + HITL (+ Popa no backlog)
```

Evitar:

```text
MCP so quando o dado nao esta unificado
```
