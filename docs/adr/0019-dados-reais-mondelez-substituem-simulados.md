# ADR-0019 - Dados Reais Mondelez Substituem Simulados no Dominion

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

O MVP atual usa DataFrames fixos em memoria (dados simulados) para demonstrar o pipeline.
A EY forneceu dados reais de S&OE da Mondelez em CSV (`data/mondelez_s2r_base_diaria.csv`)
com 1440 linhas, 25 colunas e metricas de sell-out, sell-in, DOI, inventario por
pais/canal/categoria/marca.

Alem disso, foram fornecidos:

- `docs/S&OE - Analyst Questions Script.xlsx`: perguntas de negocio e alertas
- `docs/MDLZ_SOE WACAM_Dashboard Documentacion Tecnica_v01.pdf`: modelo semantico Power BI

Para demo EY, o pipeline precisa consumir o CSV real em vez de dados simulados.

---

## Decisao

O Dominion deve ser capaz de consumir dados do CSV Mondelez real, passando por DataShield Lite
para mapeamento semantico. As tools de analise devem ser **parametrizadas** (recebem `df` e `mapa`
como argumentos) em vez de assumir nomes fixos de colunas.

Novas tools de analise:

```text
analisar_sellout(df, mapa) -> desvio sell-out vs plano
analisar_sellin(df, mapa)  -> desvio sell-in vs plano
analisar_doi(df, mapa)     -> DOI vs politica
detectar_capacidades(mapa) -> lista de analises possiveis
```

O Dominion roda **apenas** as analises para as quais o dataset tem dados (ADR-0013).

---

## Alternativas consideradas

### Alternativa A - Manter dados simulados e adicionar CSV como extra

Vantagens:

* sem risco de quebrar pipeline existente

Desvantagens:

* nao demonstra valor real para EY
* duplica logica de analise

### Alternativa B - Substituir simulados por CSV real com tools parametrizadas

Vantagens:

* demonstra valor com dados reais
* tools reutilizaveis para outros datasets
* alinhado com DataShield Lite

Desvantagens:

* exige refatoracao de tools existentes
* exige mapeamento semantico funcional

---

## Justificativa

A alternativa B foi escolhida. O CSV Mondelez tem colunas explicitas que facilitam o mapeamento.
Tools parametrizadas permitem reutilizar a mesma logica para outros clientes/datasets.
O modo legado com dados simulados pode ser mantido como fallback.

---

## Consequencias positivas

* Demo EY com dados reais
* Tools reutilizaveis para outros datasets
* Valida DataShield Lite com caso concreto
* Novos tipos de sinal: `desvio_sellout`, `desvio_sellin`, `doi_fora_politica`
* Novos tipos de proposicao: `ajustar_plano_sellout`, `rebalancear_estoque_doi`

---

## Consequencias negativas ou trade-offs

* Refatoracao de tools existentes (`validar_demanda`, `validar_custos`)
* Novos testes necessarios
* Dependencia de DataShield Lite funcional para mapeamento

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
Nenhum. Tools continuam deterministicas. LLM continua sem calcular.
```

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [x] `docs/testing.md`
* [ ] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

---

## Impacto em codigo

* [ ] `agent.py`
* [ ] `audit.py`
* [ ] `config.py`
* [ ] `critic.py`
* [ ] `guardrails.py`
* [ ] `harness.py`
* [x] `main.py`
* [x] `nexus.py`
* [x] `optimus.py`
* [x] `sinais.py`
* [x] `state_types.py`
* [x] `tools.py`
* [ ] `validator.py`
* [x] novo arquivo: `datashield.py`

---

## Impacto em testes

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [x] `python main.py --modo legado`
* [x] testes unitarios
* [x] testes com arquivo real ou fixture

Detalhar:

```text
Criar fixture CSV ficticio com mesmas colunas do Mondelez.
Testar cada tool parametrizada com entrada valida e invalida.
Testar detectar_capacidades com mapeamentos parciais.
```

---

## Criterios de aceite

* [ ] architecture.md atualizado
* [ ] planning.md com nova fase 1.5b
* [ ] Tools parametrizadas implementadas
* [ ] Pipeline roda com CSV Mondelez real
* [ ] Modo legado continua funcionando
* [ ] Testes com fixture CSV passam
* [ ] agent.log.md atualizado

---

## Decisoes relacionadas

```text
ADR-0005 - DataShield Lite antes do Dominion
ADR-0013 - Dominion executa analises compativeis com dados
ADR-0018 - DataShield Lite nao substitui governanca
```

---

## Observacoes

O CSV Mondelez tem colunas com nomes explicitos em ingles (SellOut_Actual_Ton, DOI_Actual_Days).
O mapeamento semantico para este dataset especifico deve ter confianca alta (>0.90).

### Addendum 2026-07-21 (ADR-0025)

Esta ADR cobre o ingresso **CSV** Mondelez. O semantic model Power BI
Mondelez (quando publicado) entra pelo caminho PBI/MCP com **novo
catalogo DAX**, sem invalidar o CSV. Ate la, a PoC usa outro modelo
(Agua) so para validar o fio MCP. Ver backlog pos-PoC em planning 1.7a.
