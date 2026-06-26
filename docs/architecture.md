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
| **Config** | `config.py`, `.env` | Parametros (modelo, limiar, retries) |
| **Entrada** | `main.py` | CLI com modos `nexus` e `legado` |

## 3. Pipeline MVP

```
Input Guardrail (anti-injecao, tamanho)
  |
  v
Dominion (loop LLM + tools deterministicas)
  |-- carregar_dados
  |-- validar_demanda
  |-- validar_custos
  |
  v
Sinais estruturados (SIG-DEM-001, SIG-CUS-004, etc.)
  |
  v
Optimus (proposicoes P1, P2, P3 deterministicas)
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
  |
  v
Output Guardrail (disclaimer + citacoes)
  |
  v
Usuario decide (sem Bridge/ERP no MVP)
```

## 4. State compartilhado (blackboard)

Padrao blackboard: cada agente le campos especificos e escreve o seu.
Sem conversa livre entre LLMs.

| Campo | Escrito por | Lido por |
|---|---|---|
| `pergunta` | Nexus | Dominion |
| `dados` | Dominion (tools) | Dominion, Sinais |
| `resultados` | Dominion (tools) | Sinais, Optimus |
| `sinais[]` | Sinais | Optimus, Critic |
| `proposicoes[]` | Optimus | Validador, Critic, Fila |
| `validacao` | Validador | Nexus |
| `critica` | Critic | Nexus, Fila |
| `fila_nexus[]` | Guardrails | main.py (CLI) |
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

- `rebalancear_estoque`
- `priorizar_skus`
- `ajustar_cobertura`
- `proteger_promocao`
- `gerenciar_falta_excesso`
- `ajustar_custo`
- `ajustar_demanda`

## 7. Configuracao (.env)

| Variavel | Padrao | Descricao |
|---|---|---|
| `OPENAI_API_KEY` | - | Chave da API OpenAI |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo LLM |
| `LIMIAR_CONFIANCA_CRITIC` | `0.7` | Abaixo disso: revisao obrigatoria |
| `MAX_OPTIMUS_RETRIES` | `1` | Retries do Optimus (0 a 3) |

## 8. O que NAO esta implementado

| Componente | Status | Fase |
|---|---|---|
| DataShield Lite (xlsx/csv + LLM schema) | Planejado | MVP proximo passo |
| Kedro pipelines | Planejado | MVP/Fase 2 |
| Microsoft Agent Framework | Planejado | Fase 2 |
| Upload de arquivo real | Planejado | MVP proximo passo |
| UI cards aprovar/rejeitar | Planejado | MVP proximo passo |
| Dominion completo EY (DOI, ruptura, canal) | Planejado | Fase 2 |
| Bridge (execucao ERP/WMS) | Planejado | Fase 4 |
| MOE router dinamico | Planejado | Fase 2/3 |
| Consenso multi-agente | Planejado | Fase 3 |

## 9. Contexto de negocio

- Cliente: EY + 7D Analytics
- Proposta: `docs/7D_EY_SenseToRespond_Tec_20260625.pptx`
- Meeting notes: `docs/EY meeting.pdf`
- 5 agentes conceituais: DataShield, Dominion, Optimus, Bridge, Nexus
- Fases: MVP (8 sem) -> Fase 2 DataShield (8-14 sem) -> Fase 3 Plena -> Fase 4 Bridge

## 10. Decisoes arquiteturais registradas

Decisoes formais em `docs/adr/` (ADR-0001 a ADR-0018). Resumo:

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

## 11. Documentos de referencia

| Documento | Caminho | Descricao |
|---|---|---|
| ADRs | `docs/adr/` | Decisoes arquiteturais formais (0001-0018) |
| Contratos | `docs/contracts/` | state_contract.md, tool_contract.md |
| Prompts | `docs/prompts.md` | Contratos de prompts LLM |
| Testes | `docs/testing.md` | Guia de testes e invariantes |
| Planning | `docs/planning.md` | Checklist gradual de implementacao |
| Agent log | `docs/agent.log.md` | Historico de sessoes de desenvolvimento |
| Rules | `rules.md` | Regras de desenvolvimento e spec-driven |
| Cursor rules | `.cursor/rules/spec-driven-dev.mdc` | Regra automatica para Cursor IDE |
