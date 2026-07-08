# ADR-0021 - LLM Pode Gerar Codigo ETL mas Nao Codigo de Metrica

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

O invariante "LLM nao calcula numeros" (ADR-0002) proibe o LLM de calcular metricas,
desvios, DOI e impactos financeiros. Porem, com a introducao de datasets variados (ADR-0020,
Nivel 2), surge a necessidade de **adequar a estrutura dos dados** antes das analises.

Operacoes como renomear colunas, pivotar tabelas e agregar por dimensao sao **ETL**
(Extract, Transform, Load), nao calculo de metricas de negocio.

A pergunta e: o LLM pode gerar script Python para essas operacoes?

---

## Decisao

O LLM **pode** gerar scripts Python para operacoes de ETL (adequacao estrutural de dados).
O LLM **nao pode** gerar scripts que calculem metricas de negocio.

### Operacoes permitidas para LLM gerar

```text
df.rename(columns={...})
df.groupby(...).agg(...)
df.pivot_table(...)
df.merge(...)
df.fillna(...)
df.drop(columns=[...])
df.astype(...)
df[colunas_selecionadas]
```

### Operacoes proibidas para LLM gerar

```text
df["delta_pct"] = (actual - plan) / plan * 100
df["impacto_financeiro"] = delta * preco
df["doi"] = inventory / daily_demand
df["tendencia"] = ...
df["score"] = ...
Qualquer formula de negocio ou KPI
```

### Garantias obrigatorias para codigo gerado

1. Humano revisa e aprova antes de executar
2. Execucao em sandbox (sem acesso a rede, disco limitado)
3. Whitelist de operacoes pandas permitidas
4. Validacao estatica do script (proibir calculos de metricas)
5. Schema checker pos-execucao (verifica que output tem formato esperado)
6. Script salvo com hash e timestamp para auditoria

---

## Alternativas consideradas

### Alternativa A - Proibir LLM de gerar qualquer codigo

Vantagens:

* zero risco de codigo malicioso
* invariante mais simples

Desvantagens:

* datasets com estrutura diferente nao podem ser processados
* usuario precisaria escrever scripts manualmente

### Alternativa B - Permitir ETL com revisao humana e sandbox

Vantagens:

* datasets variados podem ser processados
* humano sempre no loop
* fronteira clara: ETL sim, metrica nao
* sandbox limita danos

Desvantagens:

* complexidade de sandbox
* risco residual de codigo incorreto (mitigado por revisao humana)

---

## Justificativa

Alternativa B permite flexibilidade sem violar o invariante central.
A fronteira e clara e testavel: se o script faz `rename`, `groupby`, `merge` = ETL permitido.
Se faz `(actual - plan) / plan * 100` = metrica proibida.

---

## Consequencias positivas

* Pipeline processa datasets com estruturas variadas
* Invariante central preservado (LLM nao calcula metricas)
* Fronteira clara e documentada
* Auditoria completa do codigo gerado

---

## Consequencias negativas ou trade-offs

* Exige sandbox de execucao
* Exige validacao estatica de scripts
* Exige revisao humana de codigo
* Aumenta complexidade do DataShield

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
O invariante "LLM nao calcula numeros" e REFINADO, nao violado.
O LLM pode gerar operacoes de ETL (rename, groupby, merge, fillna).
O LLM NAO pode gerar operacoes que calculem metricas de negocio.
A fronteira e: ETL = adequacao estrutural. Metrica = calculo de negocio.
```

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`

---

## Impacto em codigo

* [x] novo arquivo: `datashield.py`
* [x] `tools.py`

---

## Impacto em testes

* [x] testes unitarios
* [x] testes de integracao

Detalhar:

```text
Testar que scripts gerados contem apenas operacoes permitidas.
Testar que scripts com calculos de metricas sao rejeitados.
Testar execucao em sandbox com script aprovado.
Testar que output do script respeita schema canonico.
```

---

## Criterios de aceite

* [ ] rules.md documenta fronteira ETL vs metrica
* [ ] architecture.md descreve as operacoes permitidas e proibidas
* [ ] Validacao estatica implementada (ou planejada)
* [ ] Testes de fronteira ETL/metrica criados
* [ ] Humano sempre revisa script antes de executar

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros (refinado por esta ADR)
ADR-0020 - DataShield com 3 niveis de adaptacao
ADR-0008 - Human-in-the-loop obrigatorio
```
