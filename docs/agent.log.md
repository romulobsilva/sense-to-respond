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
