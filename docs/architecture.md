# Sense to Respond - Arquitetura da Solucao

> Fonte de verdade da arquitetura. Todo codigo deve refletir o que esta neste documento.
> Atualize este arquivo ANTES de implementar mudancas arquiteturais.

## 1. Visao geral

Sistema multi-agente de IA para deteccao de sinais e geracao de proposicoes de acao
na cadeia comercial (S&OE). Dominio: consumo, foco em alimentos e bebidas.

Principio central:

```
IA = LLM + Harness
```

- O LLM decide proximo passo e gera narrativa.
- O harness controla loop, tools, guardrails, memoria, auditoria e confianca.
- Numeros sao SEMPRE calculados por tools deterministicas (Python/pandas). LLM nunca calcula.
- O LLM pode gerar scripts de ETL (rename, groupby, merge) mas nao scripts de metricas (ADR-0021).
- O humano decide antes de qualquer acao operacional (HITL obrigatorio).

**Diagramas (camadas de detalhe):**
| Nivel | Arquivo | Uso |
|---|---|---|
| Pitch | `docs/diagrams/00_apresentacao_macro.mmd` | Slide 1 - ideia em 10s |
| Meio-termo | `docs/diagrams/02_apresentacao_meio_termo.mmd` | Slide EY - agentes + HITL |
| Tecnico | `docs/diagrams/04_arquitetura_macro.mmd` | Deep-dive engenharia |

## 2. Componentes do MVP

| Componente | Arquivo(s) | Papel |
|---|---|---|
| **Nexus** | `nexus.py` | Control plane: orquestra pipeline, state, fila, guardrails |
| **Dominion** | `harness.py`, `agent.py`, `tools.py` | Loop perceive-decide-act-observe; deteccao de sinais |
| **Optimus** | `optimus.py` | Proposicoes priorizadas por impacto financeiro |
| **Validador** | `validator.py` | Validacao deterministica pos-Optimus |
| **Critic** | `critic.py` | Auditoria LLM (1 chamada, leitura only) |
| **State** | `state_types.py` | Blackboard compartilhado entre agentes |
| **Guardrails** | `guardrails.py` | Input/output guardrails, fila com flags |
| **Auditoria** | `audit.py` | Trilha de eventos timestamped |
| **Visualizacao** | `visualizacao.py` | PNG deterministico do resumo executivo (top N) |
| **Config** | `config.py`, `.env` | Parametros (modelo, limiar, retries) |
| **HITL** | `hitl.py` | Protocolo abstrato de aprovacao humana (ADR-0022) |
| **DataShield** | `datashield.py` | Leitura, mapeamento semantico, ETL, normalizacao |
| **Entrada** | `main.py` | CLI com modos `nexus` e `legado` |
| **UI Demo** | `app_streamlit.py` | Interface Streamlit para demo EY (ADR-0022) |

## 3. Pipeline MVP

```
Input Guardrail (anti-injecao, tamanho)
  |
  v
DataShield Lite (3 niveis de adaptacao - ADR-0020)
  |-- Nivel 1: mapeamento semantico (LLM infere, humano confirma)
  |-- Nivel 2: ETL gerado (LLM gera script, humano revisa, sandbox executa)
  |-- Nivel 3: diagnostico de incompatibilidade (humano decide)
  |-- HITL: aprovacao via protocolo abstrato (ADR-0022)
  |
  v
Dominion (tools deterministicas parametrizadas)
  |-- detectar_capacidades(mapa)
  |-- analisar_sellout(df, mapa)
  |-- analisar_sellin(df, mapa)
  |-- analisar_doi(df, mapa)
  |-- (roda apenas analises compativeis com dados disponiveis - ADR-0013)
  |
  v
Sinais estruturados (desvio_sellout, desvio_sellin, doi_fora_politica, etc.)
  |
  v
Optimus (proposicoes deterministicas por impacto financeiro)
  |
  v
Validador deterministico
  |-- SKU existe nos sinais?
  |-- Evidencia SIG-xxx existe?
  |-- impacto_financeiro == impacto_calculado?
  |-- tipo na whitelist MVP?
  |
  v
Critic LLM (1 chamada, audita coerencia)
  |-- Proposicao contradiz sinal?
  |-- Conclusao exagerada?
  |-- Retorna confianca 0-1
  |
  v
Retry Optimus (max 1x se validador ou critic falhar)
  |
  v
Fila Nexus (ranqueada por impacto R$ e urgencia horas)
  |-- Flag REVISAO OBRIGATORIA se confianca < limiar
  |-- HITL: aprovacao via Streamlit ou terminal (ADR-0022)
  |
  v
Resumo executivo estratificado (top N DOI / forward / oportunidades)
  |
  v
Visualizacao PNG (deterministica; plota o top N do run)
  |-- output/recomendacoes_<sessao_id>.png
  |
  v
Output Guardrail (disclaimer + citacoes)
  |
  v
Usuario decide (sem Bridge/ERP no MVP)
```

### 3.1 Modo legado (sem DataShield)

Quando nenhum arquivo e fornecido, o pipeline usa dados simulados em memoria:

```
Input Guardrail -> Dominion (dados simulados) -> Sinais -> Optimus -> ... -> Usuario
```

## 4. State compartilhado (blackboard)

Padrao blackboard: cada agente le campos especificos e escreve o seu.
Sem conversa livre entre LLMs.

| Campo | Escrito por | Lido por |
|---|---|---|
| `pergunta` | Nexus | Dominion |
| `dados` | Dominion (tools) | Dominion, Sinais |
| `dataset_csv` | DataShield | Dominion |
| `mapa_semantico` | DataShield | Dominion, Nexus |
| `schema_confirmado` | DataShield/HITL | Nexus, Dominion |
| `capacidades` | Dominion | Dominion, Nexus |
| `nivel_adaptacao` | DataShield | Nexus, Auditoria |
| `script_etl_aprovado` | DataShield/HITL | Dominion |
| `resultados` | Dominion (tools) | Sinais, Optimus |
| `sinais[]` | Sinais | Optimus, Critic |
| `proposicoes[]` | Optimus | Validador, Critic, Fila |
| `validacao` | Validador | Nexus |
| `critica` | Critic | Nexus, Fila |
| `fila_nexus[]` | Guardrails | main.py (CLI), Streamlit |
| `artefatos_visuais[]` | Nexus/visualizacao | main.py, Auditoria |
| `handoffs[]` | Nexus | Auditoria |
| `auditoria` | Audit | main.py (JSON) |

## 5. Guardrails (3 camadas)

### 5.1 Input Guardrail
- Pergunta: min 10 chars, max 2000 chars
- Anti-injecao: regex contra prompt injection
- Bloqueio ANTES de qualquer chamada LLM

### 5.2 Harness Guardrail (durante loop)
- Tool whitelist por fase
- Nao repetir tool ja executada
- Max iteracoes Dominion (padrao 10)
- JSON obrigatorio com retry
- Max 1 retry Optimus (configuravel)

### 5.3 Output Guardrail
- Disclaimer obrigatorio em toda resposta
- Citacoes dos sinais deterministicos
- Flag "revisao obrigatoria" se confianca < limiar
- Sem acao ERP/WMS no MVP

## 6. Tipos de decisao MVP (whitelist)

### 6.1 Tipos originais (dados simulados)

- `rebalancear_estoque`
- `priorizar_skus`
- `ajustar_cobertura`
- `proteger_promocao`
- `gerenciar_falta_excesso`
- `ajustar_custo`
- `ajustar_demanda`

### 6.2 Tipos adicionais (dados reais Mondelez - ADR-0019)

- `ajustar_plano_sellout`
- `ajustar_plano_sellin`
- `rebalancear_estoque_doi`
- `investigar_desvio_canal`
- `questionar_premissa_plano`
- `capturar_oportunidade`
- `investigar_desvio_persistente`

## 7. Configuracao (.env)

### 7.1 Variaveis principais

| Variavel | Padrao | Descricao |
|---|---|---|
| `OPENAI_API_KEY` | - | Chave da API OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo LLM |
| `LIMIAR_CONFIANCA_CRITIC` | `0.7` | Abaixo disso: revisao obrigatoria |
| `MAX_OPTIMUS_RETRIES` | `1` | Retries do Optimus (0 a 3) |
| `HITL_MODE` | `terminal` | Interface HITL: `terminal`, `arquivo`, `streamlit`, `auto` |
| `STREAMLIT_PORT` | `8501` | Porta do Streamlit quando HITL_MODE=streamlit |

### 7.2 Thresholds de dominio (ADR-0024)

Configuraveis por cliente/setor. Defaults calibrados para Mondelez FMCG.

| Variavel | Padrao | Descricao |
|---|---|---|
| `DOI_RUPTURA_DIAS` | `15.0` | DOI abaixo disso: risco de ruptura |
| `DOI_OVERSTOCK_DIAS` | `40.0` | DOI acima disso: risco de overstock |
| `LIMIAR_DESVIO_PCT` | `5.0` | Desvio% minimo para gerar proposicao |
| `LIMIAR_DESVIO_SEVERO_PCT` | `10.0` | Desvio% para severidade alta |
| `LIMIAR_DOI_GAP_MEDIA` | `7.0` | Gap DOI para severidade media |
| `LIMIAR_DOI_GAP_ALTA` | `15.0` | Gap DOI para severidade alta |
| `LIMIAR_TENDENCIA_ESTAVEL_PCT` | `3.0` | Variacao% abaixo disso: estavel |
| `LIMIAR_PREMISSA_FURADA_PCT` | `15.0` | Divergencia% forward para alerta |
| `LIMIAR_ACELERACAO_PCT` | `5.0` | Variacao pp entre semanas para ritmo |
| `LIMIAR_DESVIO_PERSISTENTE_MESES` | `3` | Meses minimos para desvio persistente |
| `JANELA_RECENTE_DIAS` | `30` | Janela: snapshot SO/SI/DOI + tendencia/forward |
| `FORWARD_MARKER` | `nan` | Marcador de dados forward: `nan`, `zero` |
| `PESO_QUESTIONAR_PREMISSA` | `1.5` | Peso de ordenacao (fila+Optimus); nao altera R$ |
| `PESO_CAPTURAR_OPORTUNIDADE` | `1.4` | Peso de ordenacao oportunidade forward |
| `PESO_INVESTIGAR_DESVIO_PERSISTENTE` | `1.1` | Peso de ordenacao desvio persistente |
| `SCHEMA_PATH` | - | Caminho para JSON de schema alternativo |

**Priorizacao (Optimus + fila Nexus, mesmo score):**
`I_prio = impacto_financeiro * peso_tipo`. Defaults acima via
`DomainThresholds`. Impacto financeiro bruto inalterado; peso so na
ordenacao. Demais tipos usam peso 1.0.

**Fronteira forward:**
- DOI < `DOI_RUPTURA_DIAS` + SO acima = **ruptura** (risco primario).
- Se alem disso o plano forward esta subdimensionado
  (`divergencia_forward < -LIMIAR_PREMISSA_FURADA`), gera **dual framing**:
  mantem ruptura e emite tambem `capturar_oportunidade` (subir SI para
  capturar demanda). A oportunidade pura (sem ruptura) continua exigindo
  DOI em `[DOI_RUPTURA, DOI_OVERSTOCK]`.

**Gate DOI overstock (anti falso-positivo historico):**
`rebalancear_estoque_doi` com gap > 0 e suprimido se tendencia
`melhorando`, ou se tendencia `estavel` e `|SO desvio%| < LIMIAR_DESVIO`.

### 7.2b Resumo executivo e filtro de ruido

Bloco deterministico estratificado por topico (script do analista).
Nao substitui a fila HITL completa.

| Variavel | Padrao | Descricao |
|---|---|---|
| `TOP_N_DOI` | `5` | Top N estoque/DOI (`rebalancear_estoque_doi`) |
| `TOP_N_FORWARD` | `5` | Top N plano forward (`questionar_premissa_plano`) |
| `TOP_N_OPORTUNIDADES` | `5` | Top N oportunidades (`capturar_oportunidade`) |
| `LIMIAR_PERSISTENTE_IMPACTO` | `100.0` | Min \|impacto\| para enfileirar desvio persistente |
| `LIMIAR_PERSISTENTE_DESVIO_PCT` | `5.0` | Min \|media desvio%\| para enfileirar persistente |

CLI: `--top-doi N` / `--top-forward N` / `--top-opps N`.

Dentro de DOI e de forward, o N e repartido entre polaridades
(ruptura vs overstock) para NR alto de um padrao nao eliminar o outro.
Legado: `TOP_N_RISCOS` / `--top-riscos` replica N para DOI e FORWARD.

Filtro persistente: nao gera proposicao se
`|impacto| < LIMIAR_PERSISTENTE_IMPACTO` **e**
`|media_desvio%| < LIMIAR_PERSISTENTE_DESVIO_PCT`.

Saida em `state.resumo_executivo` (`top_doi`, `top_forward`,
`top_oportunidades`, com sublistas de polaridade quando aplicavel).

Apos o resumo, `visualizacao.plotar_resumo_executivo` gera PNG em
`output/recomendacoes_<sessao_id>.png` a partir das listas top N do run
(tamanho e conteudo variam com N e com o CSV de entrada). Nao usa LLM;
nao recalcula impacto nem ordem. Path registrado em
`state.artefatos_visuais` e na auditoria (`visualizacao_png`).

### 7.3 Portabilidade multi-dominio (ADR-0024)

O pipeline e **parametrico nos dados mas rigido no dominio** por default.
Para novo cliente/setor, ajustar:

1. `DomainThresholds` via `.env` (thresholds de DOI, desvio, janela, pesos).
2. Schema canonico via `SCHEMA_PATH` (JSON com colunas esperadas).
3. `FORWARD_MARKER` se dados forward usam zero ao inves de NaN.

Nenhuma mudanca de codigo necessaria para novo cliente FMCG.

## 8. O que NAO esta implementado

| Componente | Status | Fase | ADR |
|---|---|---|---|
| DataShield Lite Nivel 1 (hibrido) | Implementado | Fase 1.5.2 | ADR-0005/0020 |
| DataShield Lite (3 niveis) | Parcial (N1 ok; N2/N3 planejado) | Fase 1.5 | ADR-0020 |
| HITL Streamlit (demo EY) | Planejado | Fase 1.5c | ADR-0022 |
| Tools parametrizadas Mondelez | Planejado | Fase 1.5b | ADR-0019 |
| Sandbox para ETL gerado | Planejado | Fase 1.5 N2 | ADR-0021 |
| Dominion expandido (DOI, canal) | Planejado | Fase 1.6 | - |
| Kedro pipelines | Planejado | Fase 2 | - |
| Microsoft Agent Framework | Planejado | Fase 2 | - |
| Bridge (execucao ERP/WMS) | Planejado | Fase 4 | ADR-0016 |
| MOE router dinamico | Planejado | Fase 2/3 | ADR-0017 |
| Consenso multi-agente | Planejado | Fase 3 | ADR-0017 |

## 9. Contexto de negocio

- Cliente: EY + 7D Analytics
- Proposta: `docs/7D_EY_SenseToRespond_Tec_20260625.pptx`
- Meeting notes: `docs/EY meeting.pdf`
- 5 agentes conceituais: DataShield, Dominion, Optimus, Bridge, Nexus
- Fases: MVP (8 sem) -> Fase 2 DataShield (8-14 sem) -> Fase 3 Plena -> Fase 4 Bridge

## 10. Decisoes arquiteturais registradas

Decisoes formais em `docs/adr/` (ADR-0001 a ADR-0023). Resumo:

| ADR | Decisao | Motivo |
|---|---|---|
| 0001 | Pipeline sequencial no MVP (sem MOE) | Previsibilidade, auditabilidade, menor custo |
| 0002 | LLM nao calcula numeros | Zero alucinacao numerica |
| 0003 | Blackboard sem conversa NL entre agentes | Simplicidade, rastreabilidade |
| 0004 | Max 1 retry Optimus | Equilibrio custo vs seguranca |
| 0005 | Validador deterministico pos-Optimus | Seguranca sem debate entre agentes |
| 0006 | Critic LLM leitura-only | Auditoria sem side-effects |
| 0007 | Human-in-the-loop obrigatorio no MVP | Sem Bridge/ERP |
| 0008 | Whitelist de tipos de decisao | Prevenir acoes imprevistas |
| 0009 | Output com evidencias e disclaimer | Transparencia para o usuario |
| 0010 | Implementacao parcial nao marca done | Integridade do planning.md |
| 0011 | Prompts com JSON validado, retry e fallback | Robustez contra LLM truncado |
| 0012 | Auditoria sem dados sensiveis | Seguranca de dados |
| 0013 | Dominion executa analises compativeis | Alinhamento com dados disponiveis |
| 0014 | Output com evidencias, disclaimer e revisao | Transparencia |
| 0015 | UI MVP aprova/rejeita mas nao executa | HITL sem Bridge |
| 0016 | Bridge fora do MVP | Escopo controlado |
| 0017 | MOE e consenso apenas fase futura | Complexidade prematura |
| 0018 | DataShield Lite nao substitui governanca | Auditoria de schema |
| 0019 | Dados reais Mondelez substituem simulados | Tools parametrizadas, CSV real |
| 0020 | DataShield com 3 niveis de adaptacao | Mapeamento, ETL gerado, diagnostico |
| 0021 | LLM pode gerar ETL mas nao metrica | Fronteira ETL vs calculo de negocio |
| 0022 | HITL via protocolo abstrato com Streamlit | InterfaceHITL plugavel, demo EY |
| 0023 | Comunicacao pipeline-UI via JSON | Arquivos JSON em approvals/ |
| 0024 | Portabilidade multi-dominio | Thresholds, NR, schema, forward configuraveis |

## 11. Documentos de referencia

| Documento | Caminho | Descricao |
|---|---|---|
| ADRs | `docs/adr/` | Decisoes arquiteturais formais (0001-0024) |
| Contratos | `docs/contracts/` | state_contract.md, tool_contract.md |
| Prompts | `docs/prompts.md` | Contratos de prompts LLM |
| Testes | `docs/testing.md` | Guia de testes e invariantes |
| Planning | `docs/planning.md` | Checklist gradual de implementacao |
| Agent log | `docs/agent.log.md` | Historico de sessoes de desenvolvimento |
| Rules | `rules.md` | Regras de desenvolvimento e spec-driven |
| Cursor rules | `.cursor/rules/spec-driven-dev.mdc` | Regra automatica para Cursor IDE |

## 12. Schema canonico Mondelez (ADR-0019)

Colunas esperadas no dataset canonico apos DataShield normalizar o CSV:

| Campo canonico | Tipo | Descricao |
|---|---|---|
| `date` | date | Data do registro |
| `country` | str | Pais (Brazil, Mexico, Colombia, Peru, Chile) |
| `channel` | str | Canal (Modern Trade, Traditional, E-commerce, Wholesale) |
| `category` | str | Categoria (Chocolates, Biscuits, Gum, Beverages) |
| `brand` | str | Marca (Lacta, Oreo, Trident, Tang) |
| `sku_code` | str | Codigo do SKU |
| `sku_description` | str | Descricao do SKU |
| `sellout_actual` | float | Sell-out real (toneladas) |
| `sellout_plan` | float | Sell-out planejado (toneladas) |
| `sellin_actual` | float | Sell-in real (toneladas) |
| `sellin_plan` | float | Sell-in planejado (toneladas) |
| `doi_actual` | float | Days of Inventory real |
| `doi_policy` | float | Days of Inventory politica |
| `inventory_units` | float | Estoque em unidades |
| `sellout_actual_nr` | float | Net Revenue real (USD) |

Dimensoes para agregacao: `country`, `channel`, `category`, `brand`.

O schema e configuravel via `SCHEMA_PATH` no `.env` (ADR-0024).
Se `SCHEMA_PATH` nao for definido, o default Mondelez acima e utilizado.
O JSON de schema deve conter uma lista de objetos com `campo`, `tipo` e `descricao`.

## 13. Arquitetura HITL (ADR-0022, ADR-0023)

### 13.1 Protocolo abstrato

```
InterfaceHITL (classe abstrata)
  |-- solicitar_aprovacao(PedidoAprovacao) -> PedidoAprovacao
  |
  +-- HITLTerminal       (desenvolvimento)
  +-- HITLArquivo         (async, polling JSON)
  +-- HITLStreamlit       (demo EY)
  +-- HITLAutoApprove     (testes automatizados)
```

### 13.2 Momentos de interacao HITL

| Momento | Tipo | Quando |
|---|---|---|
| M1 | mapeamento_semantico | DataShield infere mapa de colunas |
| M2 | script_etl | DataShield Nivel 2 gera script ETL |
| M3 | fila_nexus | Pipeline completo, usuario decide proposicoes |
| M4 | incompatibilidade_dados | DataShield Nivel 3 detecta dataset incompativel |

### 13.3 Comunicacao pipeline-UI

```
Pipeline -> gera approvals/{tipo}_{timestamp}.json (status: pendente)
Pipeline -> polling (1s intervalo)
Streamlit -> le JSON, exibe ao usuario
Usuario -> decide (aprovar/rejeitar/editar/postergar)
Streamlit -> grava decisao no JSON
Pipeline -> detecta decisao, continua
```

### 13.4 Telas Streamlit (demo EY)

1. Upload e preview do dataset
2. Mapeamento semantico com aprovacao
3. Progresso do pipeline em tempo real
4. Fila Nexus com proposicoes para decisao
5. Audit trail completo

## 14. DataShield - 3 Niveis de Adaptacao (ADR-0020)

```
Nivel 1 - Mapeamento puro (90% dos casos)
  LLM retorna JSON de mapeamento
  Tools aplicam rename/select
  Humano confirma
  Nenhum codigo gerado

Nivel 2 - Transformacao ETL (9% dos casos)
  LLM gera script ETL (rename + groupby + merge)
  Humano revisa script
  Sandbox executa script aprovado
  Fronteira: ETL sim, metrica nao (ADR-0021)

Nivel 3 - Diagnostico (1% dos casos)
  LLM identifica incompatibilidade
  Retorna diagnostico + sugestao
  Humano decide se prossegue
  Pipeline roda parcialmente ou nao roda
```

### 14.1 Fronteira ETL vs Metrica (ADR-0021)

| Operacao | Tipo | LLM pode gerar? |
|---|---|---|
| `df.rename(columns={...})` | ETL | Sim |
| `df.groupby(...).agg(...)` | ETL | Sim |
| `df.merge(...)` | ETL | Sim |
| `df.fillna(...)` | ETL | Sim |
| `(actual - plan) / plan * 100` | Metrica | Nao |
| `inventory / daily_demand` | Metrica (DOI) | Nao |
| `delta * preco_unitario` | Metrica (impacto) | Nao |
