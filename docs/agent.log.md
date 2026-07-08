# Agent Log - Historico de Conversas e Decisoes

> Registro rastreavel de todas as iteracoes de desenvolvimento.
> Atualize este arquivo ao final de cada sessao de chat significativa.
> Formato: data, contexto, decisoes, artefatos produzidos.

---

## Sessao 1 - 2026-06-25 (tarde) - Arquitetura inicial

### Contexto
- Usuario solicitou montar estrutura agente + harness para Sense to Respond
- Fontes: `docs/EY meeting.pdf`, `docs/7D_EY_SenseToRespond_Tec_20260625.pptx`
- Referencia: Microsoft Agent Framework + Kedro
- Repo existente: prototipo com agent.py, harness.py, tools.py, audit.py

### Documentos analisados
- **EY meeting.pdf** (10 pags): Meeting notes com EY, 2 blocos (Network Design + Sense to Respond)
  - Sense to Respond focado em consumo/alimentos (Mondelez)
  - Trigger: sell-out (Nielsen, Mtrix)
  - Demo desejada: agente que le telas e gera insights
  - Solucao as a service, usam Copilot
- **7D_EY_SenseToRespond_Tec_20260625.pptx** (17 slides): Proposta tecnica completa
  - 5 agentes: DataShield, Dominion, Optimus, Bridge, Nexus
  - 4 fases: MVP -> DataShield completo -> Capacidade plena -> Bridge
  - MVP: Dominion + Optimus + Nexus simplificado
  - Exemplo SKU 4521: desvio -31%, ruptura em 6 dias, rebalanceamento 360 cx

### Diagramas criados
1. Visao macro 5 componentes (DataShield, Dominion, Optimus, Bridge, Nexus)
2. Fluxo funcional MVP (slides 15-16)
3. Mapeamento MAF + Kedro + Harness
4. Guardrails (flowchart - mindmap deu erro de sintaxe)
5. Roadmap de fases
6. Tipos de decisao MVP (slide 17)

### Decisoes tomadas
- Pipeline sequencial no MVP (sem MOE)
- LLM nunca calcula numeros
- Harness = papel do Nexus
- DataShield usa LLM para inferencia semantica de schema
- Human-in-the-loop obrigatorio no MVP

---

## Sessao 2 - 2026-06-25 (tarde) - Discussao MOE vs pipeline

### Contexto
- Usuario questionou se a arquitetura deveria ter agentes que criticam e conversam (MOE)
- Referencia: artigo PolicyPulse (Observe -> Reason -> Act) e Harness Engineering

### Decisoes tomadas
- MVP = pipeline fixo (DataShield -> Dominion -> Optimus) sem MOE
- Agentes compartilham info via state (blackboard), nao por conversa NL
- Validador deterministico pos-Optimus (sem LLM, zero custo extra)
- Critic LLM opcional: 1 chamada de auditoria (leitura only)
- Max 1 retry Optimus se validador/critic falhar
- MOE router dinamico fica para Fase 2/3

### Checklist acordado
```
Obrigatorio no MVP:
  [x] State compartilhado entre agentes
  [x] Validador deterministico pos-Optimus
  [x] Output guardrail (disclaimer, citacoes)
  [x] Human-in-the-loop na fila Nexus
  [x] Audit trail de cada handoff

Recomendado no MVP:
  [x] Critic LLM como auditor (1 chamada)
  [x] Max 1 retry Optimus
  [x] Flag revisao obrigatoria se confianca < threshold

Fase 2/3:
  [ ] MOE router dinamico
  [ ] Agentes paralelos
  [ ] Consenso
```

---

## Sessao 3 - 2026-06-25 (tarde) - Implementacao MVP

### Artefatos criados
| Arquivo | Descricao |
|---|---|
| `state_types.py` | Blackboard: Sinal, Proposicao, ItemFilaNexus, handoffs |
| `guardrails.py` | Input/output guardrails, fila com flags |
| `sinais.py` | Extracao de sinais dos resultados Dominion |
| `optimus.py` | Proposicoes deterministicas com impacto financeiro |
| `validator.py` | Validador deterministico (SKU, evidencia, impacto, whitelist) |
| `critic.py` | Critic LLM: 1 chamada, JSON validate com retry |
| `nexus.py` | Orquestrador: Dominion -> Optimus -> Validador -> Critic -> Fila |

### Alteracoes em arquivos existentes
| Arquivo | Mudanca |
|---|---|
| `harness.py` | Refatorado: metodo executar_dominion() separado |
| `config.py` | Novos campos: limiar_confianca_critic, max_optimus_retries |
| `main.py` | Reescrito: suporta --modo nexus e --modo legado |
| `.env.example` | Novas variaveis LIMIAR e MAX_OPTIMUS_RETRIES |

### Teste end-to-end
- Pipeline deterministico (sem LLM): 4 sinais, 3 proposicoes, validacao ok
- Pipeline completo (com LLM): 22 segundos, critic confianca 0.60
- Fila Nexus: 3 itens com REVISAO OBRIGATORIA (confianca < 0.7)
- 32 eventos de auditoria, 7 handoffs registrados

---

## Sessao 4 - 2026-06-25 (tarde) - Fluxogramas e documentacao

### Artefatos criados
- 13 fluxogramas Mermaid cobrindo toda a arquitetura
- Tabela honesta: implementado vs planejado
- Comparacao hoje (dados simulados) vs alvo EY (xlsx real)

### Decisao: Spec-Driven Development
- Adotar paradigma spec-driven para o projeto
- Criar architecture.md, planning.md, agent.log.md, rules.md
- Rules como .cursor/rules/*.mdc para Cursor IDE ler automaticamente

---

## Sessao 5 - 2026-06-25 (fim de tarde) - Spec-Driven files

### Artefatos criados
| Arquivo | Descricao |
|---|---|
| `docs/architecture.md` | Spec da solucao (fonte de verdade) |
| `docs/planning.md` | Checklist gradual com todas as fases |
| `docs/agent.log.md` | Este arquivo |
| `rules.md` | Regras de desenvolvimento (raiz) |
| `.cursor/rules/spec-driven-dev.mdc` | Regra Cursor IDE |

---

## Sessao 6 - 2026-06-25 (noite) - Spec-Driven Docs completos + Hardening

### Contexto
- Continuacao da Sessao 5: criacao de documentos de spec-driven development
- 18 ADRs criados, contratos (state/tool), prompts.md, testing.md
- Analise de aderencia da proposta tecnica ao codigo existente
- Identificacao de bugs e gaps entre specs e codigo

### Decisoes tomadas
- Criar Fase 1.0 Hardening no planning.md (pre-requisito para DataShield)
- Fix parsing booleano no critic.py (bool("false")==True era bug)
- Validar confianca 0-1 com clamping no critic.py
- Adicionar retry JSON no agent.py (ADR-0011 exige, estava faltando)
- Criar suite de testes iniciais com invariantes

### Artefatos criados/alterados
| Arquivo | Descricao |
|---|---|
| `docs/adr/0001-0018.md` | 18 ADRs formais cobrindo todas as decisoes |
| `docs/adr/README.md` | Indice e instrucoes para novos ADRs |
| `docs/contracts/state_contract.md` | Contrato do state (blackboard) |
| `docs/contracts/tool_contract.md` | Contrato de tools |
| `docs/prompts.md` | Contratos de prompts LLM |
| `docs/testing.md` | Guia de testes e invariantes |
| `docs/planning.md` | +Fase 1.0 Hardening com checklist |
| `docs/architecture.md` | +Secao 11 com docs de referencia, ADRs indexados |
| `critic.py` | Fix: parsing bool seguro + clamping confianca 0-1 |
| `agent.py` | Fix: retry JSON com max 2 tentativas + validacao chaves |
| `requirements.txt` | +openpyxl, +pytest |
| `tests/__init__.py` | Diretorio de testes criado |
| `tests/test_guardrails.py` | 12 testes: input/output guardrails, fila |
| `tests/test_critic.py` | 10 testes: bool parsing, confianca range |
| `tests/test_validator.py` | 8 testes: SKU, evidencia, whitelist, impacto |
| `tests/test_optimus.py` | 8 testes: sinais, limiar, ordenacao, invariantes |
| `tests/test_state_types.py` | 18 testes: state, serializacao, handoffs |

### Testes realizados
- 56 testes pytest passaram (0 falhas)
- Cobertura: guardrails, critic parsing, validator, optimus, state_types
- Lint: sem erros em critic.py e agent.py apos mudancas

### Proximos passos definidos
- [ ] Completar items da Fase 1.0 no planning.md
- [ ] Adicionar pytest.ini ou pyproject.toml local (config isolada)
- [ ] Iniciar Fase 1.5 DataShield Lite (leitura xlsx)

---

## Sessao 7 - 2026-07-08 (manha) - Dados Mondelez e adaptacao da arquitetura

### Contexto
- Usuario forneceu 3 arquivos de dados reais Mondelez:
  - `data/mondelez_s2r_base_diaria.csv` (1440 linhas, 25 colunas, sell-out/sell-in/DOI)
  - `docs/S&OE - Analyst Questions Script.xlsx` (perguntas de negocio e alertas)
  - `docs/MDLZ_SOE WACAM_Dashboard Documentacion Tecnica_v01.pdf` (modelo semantico Power BI)
- Analise de como conectar dados reais ao pipeline existente
- Discussao sobre adaptacao para datasets com colunas variadas

### Decisoes tomadas
- Tools de analise devem ser parametrizadas (recebem `df` e `mapa` como args)
- Dominion detecta capacidades do dataset e roda apenas analises compativeis
- Abordagem "semantic mapping + parameterized tools" (Opcao C) escolhida
- Novos tipos de sinal: `desvio_sellout`, `desvio_sellin`, `doi_fora_politica`
- Novos tipos de proposicao: `ajustar_plano_sellout`, `rebalancear_estoque_doi`

### Artefatos analisados
| Arquivo | Descricao |
|---|---|
| `data/mondelez_s2r_base_diaria.csv` | CSV com 25 colunas, 5 paises, 4 canais, 4 categorias |
| `docs/S&OE - Analyst Questions Script.xlsx` | 6+ perguntas de negocio com sub-perguntas |
| `docs/MDLZ_SOE WACAM_Dashboard...pdf` | Modelo Power BI com KPIs (STA, BEWB, DOI, DIFC) |

---

## Sessao 8 - 2026-07-08 (manha) - DataShield 3 niveis e ETL gerado

### Contexto
- Stress test da arquitetura: "e se o dataset tiver colunas diferentes?"
- 3 cenarios: coluna extra (C1), nomes diferentes (C2), dataset incompativel (C3)

### Decisoes tomadas
- DataShield opera em 3 niveis progressivos de adaptacao
- Nivel 1: mapeamento puro (JSON de/para, sem codigo gerado)
- Nivel 2: ETL gerado (LLM gera script, humano revisa, sandbox executa)
- Nivel 3: diagnostico de incompatibilidade (humano decide)
- Fronteira clara: ETL permitido para LLM gerar, metrica nao
- Whitelist de operacoes pandas para ETL: rename, groupby, merge, fillna, drop, astype
- Scripts ETL gerados passam por revisao humana e execucao em sandbox

---

## Sessao 9 - 2026-07-08 (manha) - HITL com Streamlit para demo EY

### Contexto
- Discussao sobre como o humano interage concretamente com o sistema
- 4 momentos HITL: mapeamento, script ETL, fila Nexus, incompatibilidade
- Necessidade de interface visual para demo EY

### Decisoes tomadas
- Protocolo abstrato InterfaceHITL com implementacoes plugaveis
- HITLTerminal (dev), HITLArquivo (async), HITLStreamlit (demo), HITLAutoApprove (testes)
- Comunicacao pipeline-UI via arquivos JSON em approvals/
- Streamlit escolhido para demo EY (Python puro, visual moderno)
- 5 telas: upload, mapeamento, progresso, fila Nexus, audit trail
- Nexus recebe hitl como dependencia injetada (sem acoplamento a UI)

---

## Sessao 10 - 2026-07-08 (manha) - Atualizacao de specs (spec-driven)

### Contexto
- Analise de gaps entre discussoes recentes e specs existentes
- 53 alteracoes identificadas em 10 documentos
- Execucao passo a passo seguindo principio spec-driven

### Artefatos criados/alterados
| Arquivo | Descricao |
|---|---|
| `docs/adr/0019-dados-reais-mondelez-substituem-simulados.md` | ADR: CSV real com tools parametrizadas |
| `docs/adr/0020-datashield-tres-niveis-adaptacao.md` | ADR: mapeamento, ETL gerado, diagnostico |
| `docs/adr/0021-llm-pode-gerar-etl-nao-metrica.md` | ADR: fronteira ETL vs calculo de negocio |
| `docs/adr/0022-hitl-protocolo-abstrato-streamlit.md` | ADR: InterfaceHITL plugavel, demo Streamlit |
| `docs/adr/0023-comunicacao-pipeline-ui-via-json.md` | ADR: arquivos JSON em approvals/ |
| `docs/adr/README.md` | Indice atualizado com ADRs 0019-0023 |
| `docs/architecture.md` | Pipeline com DataShield, HITL, schema Mondelez, 3 niveis |
| `docs/contracts/state_contract.md` | Novos campos DataShield, HITL, capacidades |
| `docs/contracts/tool_contract.md` | Tools parametrizadas, ETL gerado, sandbox |
| `docs/prompts.md` | Invariante ETL, whitelist novas tools, prompt gerar_script_etl |
| `rules.md` | Fronteira ETL/metrica, regras HITL, regras Streamlit |
| `.cursor/rules/spec-driven-dev.mdc` | Invariante ETL, HITL, stop-and-ask atualizado |
| `docs/planning.md` | Fase 1.0 marcada [x], novas fases 1.5b e 1.5c |
| `docs/testing.md` | Testes HITL, tools parametrizadas, ETL, fixtures |
| `docs/agent.log.md` | Sessoes 7-10 registradas |

### Testes realizados
- Nenhuma alteracao de codigo nesta sessao (apenas docs/specs)
- Verificacao manual de consistencia entre documentos

### Proximos passos definidos
- [ ] Implementar DataShield Lite (Fase 1.5)
- [ ] Implementar tools parametrizadas Mondelez (Fase 1.5b)
- [ ] Implementar HITL + Streamlit (Fase 1.5c)
- [ ] Criar fixtures CSV para testes
- [ ] Adicionar pytest.ini ou pyproject.toml local

---

## Sessao 11 - 2026-07-08 (meio-dia) - Refinamento do planning

### Contexto
- Revisao critica do planning para verificar se esta suficiente para implementacao
- 6 lacunas identificadas, 3 resolvidas no planning

### Lacunas resolvidas
1. **Ordem de implementacao**: adicionada secao "Ordem de implementacao das fases 1.5, 1.5b e 1.5c" com blocos A-E e dependencias claras
2. **Arquivos afetados por item**: cada checkbox agora indica o arquivo de destino (datashield.py, tools_parametrizadas.py, hitl.py, etc.) e a assinatura da funcao
3. **Sobreposicao 1.5b vs 1.6**: adicionada tabela comparativa explicando que 1.5b cobre analises snapshot e 1.6 cobre analises temporais/comparativas

### Lacunas adiadas (just-in-time)
4. Fixture CSV concreto -- definir ao implementar 1.5b.6
5. Retorno concreto das tools -- definido inline no planning (estrutura do dict)
6. Texto do system prompt -- definir ao implementar 1.5.2

### Artefatos alterados
| Arquivo | Descricao |
|---|---|
| `docs/planning.md` | Ordem de blocos, arquivos por item, assinaturas, retornos, desambiguacao 1.5b/1.6 |
| `docs/agent.log.md` | Sessao 11 registrada |

---

## Template para proximas sessoes

```
## Sessao N - YYYY-MM-DD - Titulo curto

### Contexto
- O que motivou a sessao

### Decisoes tomadas
- Lista de decisoes

### Artefatos criados/alterados
| Arquivo | Descricao |
|---|---|

### Testes realizados
- Resultados

### Proximos passos definidos
- Lista
```
