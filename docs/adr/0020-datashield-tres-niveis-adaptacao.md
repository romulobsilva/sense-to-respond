# ADR-0020 - DataShield com 3 Niveis de Adaptacao

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

O DataShield Lite (ADR-0005) foi concebido para inferir schema semantico de arquivos CSV/XLSX.
Porem, datasets reais apresentam 3 cenarios de complexidade crescente:

- **C1**: Colunas extras nao mapeadas (ex: `Promocao_Flag`)
- **C2**: Nomes diferentes para os mesmos conceitos (ex: `Ventas_Plan_Ton` em vez de `SellOut_Plan_Ton`)
- **C3**: Dataset completamente novo (ex: Nielsen sell-out com colunas incompativeis)

O DataShield precisa lidar com esses cenarios sem quebrar o pipeline.

---

## Decisao

DataShield opera em **3 niveis de adaptacao**, escolhidos automaticamente com base na
complexidade do gap entre o dataset recebido e o schema canonico:

```text
Nivel 1 - Mapeamento puro (90% dos casos)
  LLM retorna JSON de mapeamento coluna -> campo canonico
  Tools aplicam rename/select deterministico
  Humano confirma mapeamento
  Nenhum codigo gerado

Nivel 2 - Transformacao estrutural (9% dos casos)
  LLM gera script ETL (rename + pivot + aggregate)
  Humano revisa e aprova o script
  Harness executa script aprovado em sandbox
  Codigo gerado mas limitado a ETL (sem metricas)

Nivel 3 - Dataset incompativel (1% dos casos)
  LLM identifica incompatibilidade
  Retorna diagnostico + sugestao
  Humano decide se prossegue ou nao
  Pipeline roda parcialmente ou nao roda
```

A escolha do nivel e feita pelo DataShield com base na confianca do mapeamento
e na cobertura de campos canonicos obrigatorios.

---

## Alternativas consideradas

### Alternativa A - Apenas mapeamento (Nivel 1 sempre)

Vantagens:

* simples
* sem geracao de codigo

Desvantagens:

* nao resolve C3 (datasets incompativeis)
* pipeline falha silenciosamente quando faltam campos

### Alternativa B - 3 niveis progressivos

Vantagens:

* resolve todos os cenarios
* humano sempre no loop
* degradacao graceful (nao quebra, faz menos)

Desvantagens:

* nivel 2 exige sandbox e revisao de codigo
* mais complexo de implementar

---

## Justificativa

Alternativa B permite que o pipeline seja resiliente a datasets variados sem violar invariantes.
O Nivel 2 (ETL gerado) respeita a fronteira: LLM gera ETL, nao metrica.
O Nivel 3 evita que o pipeline force analises sem dados.

---

## Consequencias positivas

* Pipeline resiliente a datasets variados
* Degradacao graceful em vez de falha
* Humano sempre decide em cada nivel
* Dominion detecta capacidades e roda apenas analises possiveis

---

## Consequencias negativas ou trade-offs

* Nivel 2 exige sandbox de execucao
* Nivel 2 exige revisao humana de codigo
* Nivel 3 pode frustrar usuario (pipeline nao roda completo)
* Mais testes necessarios

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
O invariante "LLM nao calcula numeros" e refinado pela ADR-0021.
LLM pode gerar ETL (rename, groupby) mas nao metricas.
```

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/prompts.md`
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
* [x] `tools.py`
* [ ] `validator.py`
* [x] novo arquivo: `datashield.py`

---

## Impacto em testes

* [x] testes unitarios
* [x] testes de integracao
* [x] testes com arquivo real ou fixture

Detalhar:

```text
Testar cada nivel com fixtures:
- Nivel 1: CSV com colunas extras
- Nivel 2: CSV com nomes diferentes que exige ETL
- Nivel 3: CSV incompativel que gera diagnostico
```

---

## Criterios de aceite

* [ ] architecture.md descreve os 3 niveis
* [ ] planning.md tem subitens por nivel
* [ ] Nivel 1 funciona com CSV Mondelez
* [ ] Nivel 2 gera script ETL revisavel
* [ ] Nivel 3 retorna diagnostico sem quebrar pipeline
* [ ] Humano confirma em todos os niveis
* [ ] Testes com fixtures passam

---

## Decisoes relacionadas

```text
ADR-0005 - DataShield Lite antes do Dominion
ADR-0009 - DataShield nao envia dataset completo ao LLM
ADR-0018 - DataShield Lite nao substitui governanca
ADR-0019 - Dados reais Mondelez substituem simulados
ADR-0021 - LLM pode gerar ETL mas nao metrica
```
