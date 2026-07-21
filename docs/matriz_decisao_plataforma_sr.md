# Matriz de decisão — Sense to Respond

> Decisões de plataforma (determinístico / não-determinístico) e do problema SR.
> Uso: alinhamento interno / reunião EY. Atualizar quando uma decisão for fechada.

---

## A) Parte determinística: Kedro vs scripts Python

| Critério | Scripts Python (atual) | Kedro |
|---|---|---|
| **O que é** | Funções/pandas no repo (`tools_*`, Nexus) | Pipelines + Data Catalog + params por ambiente |
| **Prós** | Rápido; já funciona; fácil de debugar; baixo overhead | Catálogo versionado; multi-fonte; envs (dev/prod); governança de dados |
| **Contras** | Escala mal com muitas fontes; menos "produto de dados" | Setup e curva de aprendizado; overkill com 1 CSV |
| **Quando escolher** | MVP / 1-2 fontes / demo | 3+ fontes (Nielsen, EDI, ERP) ou time de dados formal |
| **Recomendação prática** | **Manter scripts agora**; introduzir Kedro quando multi-fonte for requisito real | |

---

## B) Parte não-determinística: Microsoft Agent Framework vs scripts Python

| Critério | Scripts Python (`agent.py` / Nexus) | Microsoft Agent Framework |
|---|---|---|
| **O que é** | LLM + harness próprio | SDK MS: Agent, workflows, middleware, OTel |
| **Prós** | Controle total; alinhado ao que já roda; zero migração | Padrão MS/Azure; telemetria; handoffs; AG-UI depois |
| **Contras** | Menos "selo plataforma"; mais código de orquestração | Retrabalho de casca; não melhora cálculo S&OE; API ainda em evolução |
| **Quando escolher** | Validar domínio e HITL | Deploy Foundry / observabilidade / time .NET+Python |
| **Recomendação prática** | **Continuar Python agora**; MAF como evolução da casca LLM, sem reescrever tools | |

---

## C) Problema SR — modelo semântico

| Opção | Direto da base (schema fixo / dicionário) | A partir do profiling (+ LLM/HITL) |
|---|---|---|
| **Prós** | Determinístico; estável; auditável; barato | Flexível a CSV "torto"; menos fricção com fontes novas |
| **Contras** | Quebra se o arquivo mudar nomes/colunas | Risco de mapa errado; precisa HITL; menos previsível |
| **Híbrido (recomendado)** | Schema canônico + defaults | Profiling detecta; LLM sugere; **humano confirma** (DataShield N1) |

**Resposta curta:** não é "ou/ou". **Profiling deriva candidatos; o modelo semântico canônico é a verdade; HITL fecha o mapa.**

---

## D) Camada de mapeamento semântico → inputs do pipeline?

| Opção | Sem camada (código acoplado às colunas) | Com camada de mapeamento (DataShield) |
|---|---|---|
| **Prós** | Simples no começo | Pipeline só vê schema canônico; troca de fonte sem reescrever Dominion |
| **Contras** | Cada fonte nova vira if/else no domínio | Mais um passo + HITL |
| **Recomendação** | — | **Sim, manter/ter a camada** (mapa + dataset canônico). Desacopla ingestão da análise |

---

## E) Ranqueamento dos signals: determinístico / não-determinístico / semi?

| Modo | Como funciona | Prós | Contras |
|---|---|---|---|
| **Determinístico** | Score fixo: NR × peso_tipo, cotas DOI/forward, limiares | Auditável; repetível; anti-overfit; testável | Menos "inteligência narrativa" no ranking |
| **Não-determinístico (LLM ranqueia)** | Modelo ordena/prioriza | Pode captar nuance de texto | Não reprodutível; risco de inventar ordem; ruim para compliance |
| **Semi-determinístico** | Tools calculam score e top-N; LLM **só explica/reordena apresentação** com restrição (não muda R$ nem cria item) | Melhor UX; números intactos | Precisa deixar claro que o ranking "oficial" é o determinístico |

**Recomendação:**

- **Ranking oficial = determinístico** (fila / resumo / auditoria).
- **Semi = opcional na narrativa** ("destaque estes 3"), sem alterar impacto nem o conjunto.

---

## Síntese (agora vs depois)

| Decisão | Opção preferida (agora) | Revisitável quando... |
|---|---|---|
| Kedro vs Python | **Python** | Multi-fonte / governança de dados |
| MAF vs Python | **Python** | Azure/Foundry / OTel / AG-UI |
| Modelo semântico | **Híbrido:** profiling → mapa → HITL → canônico | Schema 100% fixo por cliente |
| Camada de mapeamento | **Sim** | — |
| Ranking | **Determinístico** (+ semi só na explicação) | Se compliance exigir 100% sem LLM na UI |

---

## Alinhamento com o desenho S2R (determinístico vs não-determinístico)

- **Determinístico (verde):** profiling, signals, score/ranking oficial.
- **Não-determinístico (azul):** sugestão de mapa semântico, narrativa/summary; HITL nos passos de schema/mapa.
- Se o slide mostrar dois nós de "ranking" (um verde e um azul): o verde = **score oficial**; o azul = **apresentação/LLM**. Renomear no slide para não parecer dois rankings oficiais.

---

## Status das decisões

| ID | Decisão | Status | Data | Notas |
|---|---|---|---|---|
| A | Kedro vs Python | Proposta | 2026-07-14 | Preferir Python até multi-fonte |
| B | MAF vs Python | Proposta | 2026-07-14 | Preferir Python; MAF na evolução |
| C | Modelo semântico | Proposta | 2026-07-14 | Híbrido profiling + HITL |
| D | Camada de mapeamento | Proposta | 2026-07-14 | Sim (DataShield) |
| E | Ranking signals | Proposta | 2026-07-14 | Determinístico oficial; semi só na narrativa |
