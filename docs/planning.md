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
- [x] Fix bool("false")==True no critic.py (aprovado deve ser booleano real)
- [x] Validar confianca entre 0.0 e 1.0 no critic.py
- [x] Retry com mensagem corretiva quando tipo errado

### 1.0.2 Retry JSON no agent.py (ADR-0011)
- [x] Adicionar retry com max 2 tentativas para JSON invalido
- [x] Validar chaves obrigatorias (acao, justificativa)
- [x] Fallback deterministico apos retries esgotados
- [x] Registrar falha de parse na auditoria

### 1.0.3 Dependencias
- [x] Adicionar openpyxl ao requirements.txt (pre-requisito DataShield)
- [x] Adicionar pytest ao requirements.txt (pre-requisito testes)

### 1.0.4 Testes iniciais (testing.md)
- [x] Criar diretorio tests/
- [x] test_guardrails.py: input valido, curto, longo, injection
- [x] test_critic.py: bool parsing, confianca range, JSON invalido
- [x] test_validator.py: SKU inexistente, evidencia inexistente, whitelist
- [x] test_optimus.py: sem sinais, com sinais, ordenacao
- [x] test_state_types.py: criacao, serializacao, conversao

---

## Ordem de implementacao das fases 1.5, 1.5b e 1.5c

As fases tem dependencias entre si. A ordem obrigatoria e:

```text
Bloco A (infraestrutura, pode ser paralelo):
  A1: hitl.py (protocolo abstrato + HITLTerminal + HITLAutoApprove)  [1.5.3 parcial]
  A2: datashield.py (leitura + perfil)                               [1.5.1]
  A3: Fixture CSV ficticio Mondelez                                  [1.5b.6 parcial]

Bloco B (depende de A):
  B1: datashield.py (inferencia semantica Nivel 1 + normalizacao)    [1.5.2 + 1.5.4]
  B2: tools_parametrizadas.py (detectar_capacidades + analises)      [1.5b.3]
  B3: sinais.py (novos tipos de sinal)                               [1.5b.4]
  B4: optimus.py (novos tipos de proposicao)                         [1.5b.5]
  B5: state_types.py (novos campos e tipos)                          [1.5b.4 + 1.5b.5]

Bloco C (depende de A + B):
  C1: nexus.py (integrar DataShield + HITL + tools parametrizadas)   [1.5.5]
  C2: main.py (aceitar --input arquivo)                              [1.5.5]
  C3: Testes E2E com fixture CSV                                     [1.5b.6]

Bloco D (depende de C, pode ser independente do pipeline):
  D1: HITLStreamlit + app_streamlit.py                               [1.5c.1 + 1.5c.2]
  D2: Comunicacao JSON approvals/                                    [1.5c.3]
  D3: Estilo EY + export Excel                                       [1.5c.4]

Bloco E (adiado, so se Nivel 1 nao resolver):
  E1: Geracao de ETL (Nivel 2)                                       [1.5.2b]
  E2: Diagnostico de incompatibilidade (Nivel 3)                     [1.5.2c]
```

---

## Fase 1.5 - DataShield Lite (proximo)

Inferencia semantica de xlsx/csv sem schema fixo. 3 niveis de adaptacao (ADR-0020).

### 1.5.1 Leitura de arquivos
- [x] Criar `datashield.py` com funcoes DataShield (sem classe obrigatoria)
- [x] Aceitar upload de xlsx e csv (argumento CLI `--input`)
- [x] `ler_arquivo(caminho) -> pd.DataFrame` em `datashield.py`
- [x] `gerar_perfil(df) -> PerfilDataset` em `datashield.py`
- [x] `amostrar(df, n=5) -> list[dict]` em `datashield.py`

### 1.5.2 Inferencia semantica via LLM (Nivel 1)
- [x] `inferir_mapa_semantico(perfil, ...) -> MapaSemResult` em `datashield.py` (llm_tool)
- [x] Prompt conforme `docs/prompts.md` secao 8 (schema Mondelez alinhado)
- [x] Campos obrigatorios na saida: mapeamentos, confidence, warnings
- [x] JSON validate com retry (max 2 tentativas)
- [x] Confidence gate: confianca >= 0.6 (`LIMIAR_CONFIANCA_DATASHIELD`)
- [x] Detectar colunas extras nao mapeadas (lista em warnings)
- [x] Fluxo hibrido: deterministico primeiro, LLM residual
- [x] `validar_mapa_semantico` + `montar_payload_llm` (ADR-0009)
- [x] Testes mock em `tests/test_datashield_llm.py`

### 1.5.2b Geracao de ETL (Nivel 2 - ADR-0021) -- ADIADO para apos validacao do Nivel 1
- [ ] `gerar_script_etl(perfil, schema_canonico, diagnostico) -> dict` em `datashield.py` (llm_tool)
- [ ] Whitelist de operacoes pandas (rename, groupby, merge, fillna, drop, astype)
- [ ] `validar_script_etl(script: str, whitelist) -> bool` em `datashield.py` (validacao estatica)
- [ ] Revisao humana obrigatoria via HITL antes de execucao
- [ ] `executar_script_etl(script: str, df: pd.DataFrame) -> pd.DataFrame` em sandbox
- [ ] `validar_schema_pos_etl(df_resultado, schema_canonico) -> bool` em `datashield.py`

### 1.5.2c Diagnostico de incompatibilidade (Nivel 3) -- ADIADO para apos validacao do Nivel 1
- [ ] `diagnosticar_incompatibilidade(perfil, mapa, schema_canonico) -> dict` em `datashield.py`
- [ ] Retornar: campos_presentes, campos_ausentes, cobertura_pct, sugestao
- [ ] Humano decide via HITL se prossegue com cobertura parcial ou para

### 1.5.3 Human-in-the-loop (ADR-0022)
- [ ] Criar `hitl.py` com `InterfaceHITL` (ABC), `PedidoAprovacao`, `DecisaoHumana`
- [ ] `HITLTerminal` em `hitl.py`: usa `input()` para pedir decisao
- [ ] `HITLAutoApprove` em `hitl.py`: aprova tudo (para testes pytest)
- [ ] Exibir mapa inferido formatado no terminal para usuario confirmar
- [ ] Aceitar correcoes manuais (ex: trocar nome de coluna mapeada)
- [ ] So avancar apos `decisao != None`

### 1.5.4 Normalizacao
- [ ] `normalizar_dataset(df, mapa) -> pd.DataFrame` em `datashield.py` (deterministic_tool)
- [ ] Renomear colunas conforme mapa confirmado
- [ ] Manter colunas extras como estao (nao descartar)
- [ ] `salvar_template(mapa, caminho) -> None` em `datashield.py` (io_tool)
- [ ] `carregar_template(caminho) -> dict` em `datashield.py` (io_tool)
- [ ] Reutilizar template automaticamente se hash das colunas bater

### 1.5.5 Integracao com Nexus
- [ ] `nexus.py`: adicionar etapa DataShield antes de Dominion
- [ ] `nexus.py`: aceitar `hitl: InterfaceHITL` como parametro do construtor
- [ ] `main.py`: aceitar `--input caminho` para arquivo CSV/XLSX
- [ ] `main.py`: instanciar HITL conforme `HITL_MODE` do .env
- [ ] State: `schema_confirmado`, `dataset_canonico`, `nivel_adaptacao`, `capacidades`
- [ ] Handoff `DataShield -> Dominion` registrado na auditoria
- [ ] Se `--input` nao fornecido, usar dados simulados (modo legado)

---

## Fase 1.5b - Dados reais Mondelez (ADR-0019)

Integrar CSV real Mondelez S&OE com tools parametrizadas.

### 1.5b.1 Carregar CSV Mondelez
- [ ] `carregar_csv(caminho) -> pd.DataFrame` em `datashield.py` (io_tool, reutiliza ler_arquivo)
- [ ] Validar que arquivo existe e extensao e csv/xlsx
- [ ] Armazenar no state como `dataset_csv`

### 1.5b.2 Mapeamento do CSV Mondelez
- [ ] Mapa semantico para colunas do CSV Mondelez (confianca esperada > 0.90)
- [ ] Validar contra schema canonico definido em `architecture.md` secao 12
- [ ] Testar com DataShield Nivel 1 (mapeamento puro, sem ETL)

### 1.5b.3 Tools parametrizadas
Todas em `tools_parametrizadas.py` (novo arquivo):

```text
detectar_capacidades(mapa: dict) -> list[str]
  Retorna: ["sellout", "sellin", "doi"] ou subconjunto
  Arquivo: tools_parametrizadas.py

analisar_sellout(df: pd.DataFrame, mapa: dict) -> dict
  Retorna: {"desvios": [...], "resumo": {...}}
  Cada desvio: {"sku", "pais", "canal", "categoria", "marca",
                "actual", "plan", "desvio_pct", "nr_impacto"}
  Arquivo: tools_parametrizadas.py

analisar_sellin(df: pd.DataFrame, mapa: dict) -> dict
  Retorna: mesma estrutura de analisar_sellout
  Arquivo: tools_parametrizadas.py

analisar_doi(df: pd.DataFrame, mapa: dict) -> dict
  Retorna: {"desvios": [...], "resumo": {...}}
  Cada desvio: {"sku", "pais", "canal", "doi_actual", "doi_policy",
                "gap_dias", "nr_impacto"}
  Arquivo: tools_parametrizadas.py
```

### 1.5b.4 Novos sinais
Em `sinais.py` (funcao `extrair_sinais_de_resultados` expandida):
- [ ] Tipo `desvio_sellout` com severidade calculada por threshold (>10% alta, >5% media, resto baixa)
- [ ] Tipo `desvio_sellin` com mesma logica de severidade
- [ ] Tipo `doi_fora_politica` com severidade (gap > 15 dias alta, > 7 media, resto baixa)
- [ ] Cada sinal inclui dimensoes: `pais`, `canal`, `categoria`, `marca`

### 1.5b.5 Novas proposicoes
Em `optimus.py` (funcao `gerar_proposicoes` expandida):
- [ ] `ajustar_plano_sellout` -- gerada quando desvio_sellout > threshold
- [ ] `ajustar_plano_sellin` -- gerada quando desvio_sellin > threshold
- [ ] `rebalancear_estoque_doi` -- gerada quando doi_fora_politica
- [ ] `investigar_desvio_canal` -- gerada quando sell-in e sell-out divergem
- [ ] Impacto financeiro: `abs(desvio_pct) * nr_impacto` (deterministico)

Em `state_types.py`:
- [ ] Adicionar novos tipos a `TIPOS_DECISAO_MVP`
- [ ] Adicionar novos campos opcionais ao dataclass `Sinal` (pais, canal, categoria, marca)

Em `validator.py`:
- [ ] Atualizar whitelist para incluir novos tipos

### 1.5b.6 Testes
- [ ] `tests/fixtures/mondelez_ficticio.csv`: 20 linhas, 15 colunas, 2 paises, 2 canais, dados fake
- [ ] `tests/test_tools_parametrizadas.py`: entrada valida, invalida, mapa parcial, df vazio
- [ ] `tests/test_datashield.py`: perfil, mapa, normalizacao
- [ ] `tests/test_sinais_mondelez.py`: novos tipos de sinal
- [ ] `tests/test_optimus_mondelez.py`: novos tipos de proposicao
- [ ] E2E: `python main.py --modo nexus --input tests/fixtures/mondelez_ficticio.csv`

---

## Fase 1.5c - HITL Streamlit para demo EY (ADR-0022, ADR-0023)

Interface visual para human-in-the-loop. Pode ser desenvolvida em paralelo ao Bloco C.

### 1.5c.1 Protocolo HITL Streamlit
Em `hitl.py` (mesmo arquivo do protocolo abstrato):
- [ ] `HITLStreamlit`: gera JSON em `approvals/`, faz polling ate decisao
- [ ] Polling com intervalo configuravel via `config.py` (padrao 1s)
- [ ] Timeout maximo de espera configuravel (padrao 300s)
- [ ] Fallback: se timeout, retornar `DecisaoHumana.POSTERGADO`

### 1.5c.2 App Streamlit
Em `app_streamlit.py` (novo arquivo):
- [ ] Tela 1: Upload e preview do dataset (st.file_uploader + st.dataframe)
- [ ] Tela 2: Mapeamento semantico com tabela editavel e botoes aprovar/rejeitar
- [ ] Tela 3: Progresso do pipeline (le state/progress.json, exibe barra)
- [ ] Tela 4: Fila Nexus com cards de proposicao (aprovar/rejeitar/postergar por item)
- [ ] Tela 5: Audit trail (le auditoria JSON, exibe timeline)

### 1.5c.3 Comunicacao pipeline-UI
Em `hitl.py` (metodos de HITLStreamlit):
- [ ] Criar diretorio `approvals/` automaticamente se nao existir
- [ ] Gerar JSON com campos: `id`, `tipo`, `timestamp`, `status`, `dados`, `decisao`, `comentario`, `decidido_por`, `decidido_em`
- [ ] Streamlit le JSONs com status `pendente` e exibe
- [ ] Streamlit grava `decisao` + `decidido_em` no JSON
- [ ] Pipeline detecta `decisao != null` e continua

### 1.5c.4 Estilo e UX
Em `app_streamlit.py`:
- [ ] CSS customizado com cores EY (amarelo `#FFE600`, preto `#2E2E38`)
- [ ] Cards de proposicao com: SKU, pais, canal, impacto, confianca, evidencias
- [ ] Filtros por severidade na fila Nexus (selectbox)
- [ ] Botao "Exportar para Excel" (openpyxl, gera XLSX com fila completa)
- [ ] Layout responsivo (st.columns para demo em projetor)

### 1.5c.5 Dependencias
- [ ] Adicionar `streamlit>=1.35.0` ao `requirements.txt`
- [ ] Adicionar `plotly>=5.20.0` ao `requirements.txt`

### 1.5c.6 Testes
- [ ] `tests/test_hitl.py`: HITLAutoApprove, PedidoAprovacao, DecisaoHumana
- [ ] `tests/test_hitl_json.py`: gerar JSON, ler decisao, timeout, cleanup
- [ ] Teste manual: rodar `streamlit run app_streamlit.py` e verificar telas

---

## Fase 1.6 - Dominion expandido (analises avancadas)

Analises multi-dimensionais que vao ALEM do que a Fase 1.5b cobre.

Nota: a Fase 1.5b ja implementa as analises basicas (sellout, sellin, DOI simples).
A Fase 1.6 adiciona analises **temporais, comparativas e de tendencia** que nao
existem na 1.5b.

### 1.6.0 Priorizacao e fronteira forward (anti-overfit)
- [x] Fronteira generica: DOI < tau_ruptura + SO acima -> ruptura (nunca oportunidade)
- [x] Oportunidade so com DOI saudavel [tau_r, tau_o] + plano subdimensionado
- [x] Peso de prioridade por tipo (forward 1.5/1.4) sem alterar impacto bruto
- [x] Snapshot SO/SI/DOI filtrado por janela recente (anti-historico)
- [x] Propagar `thresholds` / janela do Nexus para sellout/sellin/doi
- [x] NR nos alertas forward para ranqueamento justo vs snapshot
- [x] Fila Nexus usa o mesmo score ponderado do Optimus
- [x] Pesos de prioridade em `DomainThresholds` / `.env`
- [x] Testes sinteticos (sem SKU/ScenarioTag hardcoded no codigo de producao)

### 1.6.1 Analises temporais e comparativas
Em `tools_parametrizadas.py` (mesmo arquivo da 1.5b):
- [ ] `analisar_tendencia(df, mapa, janela=4) -> dict` -- tendencia por SKU nas ultimas N semanas
- [ ] `analisar_aceleracao_canal(df, mapa) -> dict` -- variacao da taxa de crescimento por canal
- [ ] `analisar_desequilibrio_siso(df, mapa) -> dict` -- sell-in vs sell-out por SKU (ratio)
- [ ] `analisar_ruptura_projetada(df, mapa) -> dict` -- projeta data de ruptura com base em DOI e sell-out

### 1.6.2 Sinais enriquecidos
Em `sinais.py`:
- [ ] Sinal com campo `tendencia` (crescente/decrescente/estavel)
- [ ] Sinal com campo `semanas_consecutivas` (quantas semanas seguidas em desvio)
- [ ] Sinal com campo `taxa_variacao` (aceleracao/desaceleracao)

### 1.6.3 Diferenca entre 1.5b e 1.6

| Analise | 1.5b | 1.6 |
|---|---|---|
| Desvio sell-out vs plano (snapshot) | Sim | - |
| Desvio sell-in vs plano (snapshot) | Sim | - |
| DOI vs politica (snapshot) | Sim | - |
| Tendencia temporal por SKU | - | Sim |
| Aceleracao/desaceleracao de canal | - | Sim |
| Desequilibrio sell-in vs sell-out | - | Sim |
| Ruptura projetada (forecast) | - | Sim |
| Semanas consecutivas em desvio | - | Sim |

---

## Fase 1.9 - Portabilidade multi-dominio (ADR-0024)

Remover acoplamentos ao dominio Mondelez para reutilizacao com outros clientes.

### 1.9.1 Propagar nr_impacto real (B2)
- [ ] Adicionar campo `nr_impacto: float = 0.0` ao `Sinal` em `state_types.py`
- [ ] `sinais.py`: preencher `nr_impacto` a partir do resultado da tool
- [ ] `optimus.py`: usar `sinal.nr_impacto` quando > 0 para priorizacao
- [ ] Teste: priorizacao muda quando NR real difere de toneladas

### 1.9.2 Externalizar thresholds (B1)
- [ ] Criar `DomainThresholds` dataclass em `config.py`
- [ ] Ler de variaveis `.env` com defaults Mondelez
- [ ] `tools_parametrizadas.py`: receber `thresholds` como parametro
- [ ] `sinais.py`: receber `thresholds` para calcular severidade
- [ ] `optimus.py`: receber `thresholds` para limiares de proposicao
- [ ] `nexus.py`: propagar `settings.thresholds` para todos os componentes
- [ ] Teste: com thresholds alterados, classificacao muda

### 1.9.3 Generalizar deteccao de forward (B4)
- [ ] Adicionar `forward_marker: str` a `DomainThresholds` (default "nan")
- [ ] Criar funcao `_is_forward()` em `tools_parametrizadas.py`
- [ ] Substituir `.isna()` hardcoded por `_is_forward()`
- [ ] Teste: dados forward com zero sao detectados corretamente

### 1.9.4 Schema canonico configuravel (B3)
- [ ] Adicionar `schema_path: Optional[str]` a `Settings`
- [ ] `datashield.py`: carregar schema de JSON quando `schema_path` definido
- [ ] Default: `SCHEMA_CANONICO_MONDELEZ` existente
- [ ] Teste: schema alternativo carregado e usado

---

## Fase 1.7 - Optimus expandido

5 tipos de decisao completos da apresentacao EY (slide 17).

- [ ] rebalancear_estoque: pares excesso/ruptura por regiao
- [ ] priorizar_skus: ranking por importancia estrategica
- [ ] ajustar_cobertura: DOI vs comportamento recente
- [ ] proteger_promocao: estoque vs demanda projetada promo
- [ ] gerenciar_falta_excesso: visao consolidada curto prazo

---

## Fase 1.8 - UI avancada (pos-demo)

Melhorias na interface Streamlit apos validacao da demo.

- [ ] Multiusuario com autenticacao basica
- [ ] Historico de decisoes do usuario persistido em banco
- [ ] Dashboard de KPIs com graficos Plotly
- [ ] Notificacoes quando pipeline conclui
- [ ] Modo comparativo: multiplas rodadas do pipeline

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
| 1.5 | DataShield le csv/xlsx real e usuario confirma schema via HITL |
| 1.5b | Pipeline roda com CSV Mondelez real (tools parametrizadas) |
| 1.5c | Demo EY funciona com Streamlit (upload, mapeamento, fila, audit) |
| 1.6 | Dominion detecta DOI, canal, tendencia |
| 1.9 | Thresholds, NR, schema e forward configuraveis por cliente |
| 1.7 | Optimus gera 5 tipos de proposicao EY |
| 2 | Multi-fonte com qualidade e reconciliacao |

---

## Dependencias externas por fase

| Fase | Dependencia |
|---|---|
| 0-1 | openai, pandas, python-dotenv |
| 1.0 | pytest |
| 1.5 | openpyxl (xlsx) |
| 1.5b | - (usa dependencias existentes) |
| 1.5c | streamlit, plotly |
| 1.6-1.7 | - |
| 1.8 | - (melhorias sobre Streamlit existente) |
| 2 | kedro, agent-framework, openpyxl |
