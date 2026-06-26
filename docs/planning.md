# Sense to Respond - Plano de Implementacao

> Checklist gradual do inicio ate Fase 2.
> Marque [x] conforme cada item for concluido e commitado.
> Atualize este arquivo a cada sprint ou ciclo de desenvolvimento.

---

## Fase 0 - Fundacao (concluida)

Prototipo inicial: harness com loop LLM + tools deterministicas.

- [x] Estrutura do repositorio (agent.py, harness.py, tools.py, audit.py)
- [x] Loop perceive-decide-act-observe com LLM
- [x] Tools deterministicas: carregar_dados, validar_demanda, validar_custos
- [x] Auditoria JSON com sessao_id e timestamps
- [x] Fallback deterministico quando LLM retorna acao invalida
- [x] Bloqueio de tool ja executada
- [x] Config via .env (OPENAI_API_KEY, OPENAI_MODEL)
- [x] CLI via main.py
- [x] Dados simulados em memoria (DataFrames fixos)

---

## Fase 1 - MVP Nexus (concluida parcialmente)

Arquitetura multi-agente com validador, critic e fila human-in-the-loop.

### 1.1 State compartilhado (blackboard)
- [x] state_types.py com Sinal, Proposicao, ResultadoValidacao, ResultadoCritica
- [x] ItemFilaNexus com flag revisao_obrigatoria
- [x] Funcoes criar_state_inicial, registrar_handoff
- [x] Serializacao sinais/proposicoes para prompt LLM
- [x] Funcoes de conversao state -> objetos tipados

### 1.2 Dominion (extracao de sinais)
- [x] sinais.py: extrair sinais dos resultados deterministicos
- [x] Classificacao de severidade (alta/media/baixa)
- [x] IDs unicos por sinal (SIG-DEM-001, SIG-CUS-004)
- [x] Harness refatorado para expor executar_dominion()

### 1.3 Optimus (proposicoes)
- [x] optimus.py: gerar proposicoes a partir dos sinais
- [x] Calculo deterministico de impacto financeiro
- [x] Urgencia derivada da severidade
- [x] Aceita feedback de validador/critic para retry
- [x] Whitelist de tipos de decisao MVP

### 1.4 Validador deterministico
- [x] validator.py: valida proposicoes contra sinais
- [x] Verifica: SKU existe, evidencia existe, impacto coerente, tipo na whitelist
- [x] Retorna erros estruturados

### 1.5 Critic LLM
- [x] critic.py: auditoria em 1 chamada LLM
- [x] JSON obrigatorio com retry (max 2 tentativas)
- [x] Retorna aprovado/confianca/problemas
- [x] Registra na auditoria

### 1.6 Guardrails
- [x] guardrails.py: input guardrail (tamanho, anti-injecao)
- [x] Output guardrail (disclaimer, citacoes, flag confianca)
- [x] Fila com revisao obrigatoria automatica

### 1.7 Nexus orquestrador
- [x] nexus.py: pipeline Dominion -> Optimus -> Validador -> Critic -> Fila
- [x] Retry Optimus (max 1x configuravel)
- [x] Handoffs registrados na auditoria
- [x] Integracao com agent.py existente

### 1.8 Config e CLI
- [x] LIMIAR_CONFIANCA_CRITIC e MAX_OPTIMUS_RETRIES no .env
- [x] main.py com --modo nexus e --modo legado
- [x] Fila exibida no terminal com flags

### 1.9 Spec-Driven Development
- [x] docs/architecture.md - spec da solucao
- [x] docs/planning.md - este checklist
- [x] docs/agent.log.md - historico rastreavel
- [x] rules.md - regras de desenvolvimento
- [x] .cursor/rules/spec-driven-dev.mdc - regra Cursor IDE

---

## Fase 1.0 - Hardening (pre-requisito para DataShield)

Correcoes de seguranca e qualidade exigidas por ADR-0011 e ADR-0006.

### 1.0.1 Fix Critic parsing (ADR-0011)
- [ ] Fix bool("false")==True no critic.py (aprovado deve ser booleano real)
- [ ] Validar confianca entre 0.0 e 1.0 no critic.py
- [ ] Retry com mensagem corretiva quando tipo errado

### 1.0.2 Retry JSON no agent.py (ADR-0011)
- [ ] Adicionar retry com max 2 tentativas para JSON invalido
- [ ] Validar chaves obrigatorias (acao, justificativa)
- [ ] Fallback deterministico apos retries esgotados
- [ ] Registrar falha de parse na auditoria

### 1.0.3 Dependencias
- [ ] Adicionar openpyxl ao requirements.txt (pre-requisito DataShield)
- [ ] Adicionar pytest ao requirements.txt (pre-requisito testes)

### 1.0.4 Testes iniciais (testing.md)
- [ ] Criar diretorio tests/
- [ ] test_guardrails.py: input valido, curto, longo, injection
- [ ] test_critic.py: bool parsing, confianca range, JSON invalido
- [ ] test_validator.py: SKU inexistente, evidencia inexistente, whitelist
- [ ] test_optimus.py: sem sinais, com sinais, ordenacao
- [ ] test_state_types.py: criacao, serializacao, conversao

---

## Fase 1.5 - DataShield Lite (proximo)

Inferencia semantica de xlsx/csv sem schema fixo.

### 1.5.1 Leitura de arquivos
- [ ] Aceitar upload de xlsx e csv (argumento CLI ou diretorio)
- [ ] Ler arquivo com pandas (xlsx: openpyxl; csv: auto-detect separator)
- [ ] Amostrar N primeiras linhas + headers
- [ ] Calcular stats basicos por coluna (tipo, nulos, unicos)

### 1.5.2 Inferencia semantica via LLM
- [ ] Prompt com amostra de dados -> JSON mapa semantico
- [ ] Campos obrigatorios: temporal, canal, produto, metricas, completeness, confianca
- [ ] JSON validate com retry (max 2 tentativas)
- [ ] Confidence gate: confianca >= 0.6 para prosseguir

### 1.5.3 Human-in-the-loop
- [ ] Exibir mapa inferido no terminal para usuario confirmar
- [ ] Aceitar correcoes manuais (ex: trocar nome de coluna)
- [ ] So avancar apos confirmacao explicita

### 1.5.4 Normalizacao
- [ ] Aplicar mapeamento confirmado ao DataFrame
- [ ] Renomear colunas para schema canonico
- [ ] Salvar template de mapeamento para proxima carga (JSON)
- [ ] Reutilizar template automaticamente se mesmo formato

### 1.5.5 Integracao com Nexus
- [ ] DataShield como primeiro passo do pipeline (antes do Dominion)
- [ ] State: schema_confirmado, dataset_canonico
- [ ] Handoff DataShield -> Dominion registrado na auditoria

---

## Fase 1.6 - Dominion expandido

Analises multi-dimensionais alinhadas a apresentacao EY.

### 1.6.1 Novos nodes de analise
- [ ] Desvio vs plano (IBP)
- [ ] Desequilibrio de canal (sell-in vs sell-out)
- [ ] Risco de ruptura (DOI - Days of Inventory)
- [ ] Aceleracao/desaceleracao de canal
- [ ] Tendencia semanal por SKU

### 1.6.2 Sinais enriquecidos
- [ ] Sinal com campo `canal` real (nao generico)
- [ ] Sinal com campo `tendencia` (crescente/decrescente/estavel)
- [ ] Sinal com campo `semanas_consecutivas`

### 1.6.3 Tools adicionais
- [ ] analisar_desvio_plano()
- [ ] analisar_canal()
- [ ] analisar_ruptura_doi()
- [ ] analisar_tendencia()

---

## Fase 1.7 - Optimus expandido

5 tipos de decisao completos da apresentacao EY (slide 17).

- [ ] rebalancear_estoque: pares excesso/ruptura por regiao
- [ ] priorizar_skus: ranking por importancia estrategica
- [ ] ajustar_cobertura: DOI vs comportamento recente
- [ ] proteger_promocao: estoque vs demanda projetada promo
- [ ] gerenciar_falta_excesso: visao consolidada curto prazo

---

## Fase 1.8 - UI minima

Interface para human-in-the-loop.

- [ ] Definir formato: CLI interativo, web simples (Streamlit), ou API REST
- [ ] Cards de proposicao com contexto completo
- [ ] Botoes aprovar / rejeitar / pedir mais contexto
- [ ] Historico de decisoes do usuario persistido

---

## Fase 2 - DataShield completo

Multi-fonte, qualidade e reconciliacao.

### 2.1 Ingestao multi-fonte
- [ ] Nielsen sell-out (formato a definir com cliente)
- [ ] Mtrix sell-out (formato a definir com cliente)
- [ ] EDI distribuidor
- [ ] ERP pedidos e faturamento
- [ ] Auto-detect de formato (csv, excel, parquet, json)

### 2.2 Pipeline de qualidade
- [ ] Completeness por fonte
- [ ] Freshness: tempo desde ultima atualizacao
- [ ] Consistencia entre fontes
- [ ] Deteccao de anomalias estruturais
- [ ] Alertas automaticos quando fonte desatualizada

### 2.3 Reconciliacao
- [ ] Sell-in vs sell-out vs distribuidor
- [ ] Relatorio de divergencias por dimensao
- [ ] Nivel de criticidade para decisoes

### 2.4 Kedro
- [ ] Pipeline ingest_sellout
- [ ] Pipeline quality_check
- [ ] Pipeline reconciliation
- [ ] Catalogo de dados versionado
- [ ] Parametros por ambiente (dev/staging/prod)

### 2.5 Microsoft Agent Framework
- [ ] Migrar AgenteOpenAI para agent_framework.Agent
- [ ] Workflow grafo (sequential/handoff)
- [ ] Middleware MAF para guardrails
- [ ] Observabilidade OpenTelemetry

### 2.6 MOE Router (opcional)
- [ ] Nexus identifica intencao da pergunta
- [ ] Pipeline S&OE padrao vs pergunta exploratoria
- [ ] Agente Critico como agente separado (nao so guardrail)

---

## Criterios de aceite por fase

| Fase | Criterio |
|---|---|
| 0 | Harness roda end-to-end com dados simulados |
| 1 MVP | Nexus roda com validador + critic + fila com flags |
| 1.0 | Bugs de parsing corrigidos, retry no agent, testes passando |
| 1.5 | DataShield le xlsx real e usuario confirma schema |
| 1.6 | Dominion detecta DOI, canal, tendencia |
| 1.7 | Optimus gera 5 tipos de proposicao EY |
| 2 | Multi-fonte com qualidade e reconciliacao |

---

## Dependencias externas por fase

| Fase | Dependencia |
|---|---|
| 0-1 | openai, pandas, python-dotenv |
| 1.0 | pytest |
| 1.5 | openpyxl (xlsx) |
| 1.6-1.7 | - |
| 1.8 | streamlit ou fastapi (a definir) |
| 2 | kedro, agent-framework, openpyxl |
