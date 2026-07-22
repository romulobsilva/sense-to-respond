# ADR-0026 - Chat PBI analitico via MAF + MCP (paralelo ao batch)

---

## Status

Aceito

---

## Data

2026-07-22

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O caminho batch S&OE (ADR-0025) e deterministico: catalogo DAX +
`ExecuteQuery` -> sinais -> Optimus -> PDF. Isso nao cobre perguntas
exploratorias em linguagem natural ("DOI no dia 7 de julho?", "tem
estoque suficiente no curto prazo?").

No Cursor, o mesmo semantic model ja responde bem via tools MCP
(`GetSemanticModelSchema`, `GenerateQuery`, `ExecuteQuery`). O produto
precisa dessa usabilidade **fora** do IDE, sem misturar chat com o
relatorio oficial de priorizacao.

Riscos a controlar:

* GenerateQuery no caminho critico do PDF (instavel / nao reproduzivel);
* acoplar o nucleo do chat a Streamlit/React;
* LLM inventar DOI/impacto sem tool;
* vazar tokens/resultados tabulares em `ultima_sessao.json` (ADR-0012);
* redesenhar o Nexus batch para caber conversa livre.

---

## Decisao

### D1 - Modo paralelo, nao substituto

```text
--modo nexus  -> batch S&OE (ADR-0025; intacto)
--modo chat   -> chat analitico PBI (esta ADR)
--modo legado -> harness legado (inalterado)
```

Chat **nao** ranqueia proposicoes S&OE, **nao** gera PDF Optimus e
**nao** dispara Bridge. Atalho "rode o batch a partir do chat" fica
fora do MVP.

### D2 - Backend: Microsoft Agent Framework + MCP Power BI

* Agente: Microsoft Agent Framework (MAF) + cliente OpenAI/Azure.
* Tools primarias (paridade Cursor):
  1. `GetSemanticModelSchema`
  2. `ExecuteQuery`
  3. `GenerateQuery` (somente `--modo chat`)
* Transport preferido: MCP Streamable HTTP
  (`https://api.fabric.microsoft.com/v1/mcp/powerbi`) com Bearer
  (`PBI_ACCESS_TOKEN` / Entra).
* Fallback documentado: tools locais (`@ai_function`) sobre
  `RestPowerBIClient` para `ExecuteQuery` quando MCP indisponivel;
  nesse fallback `GenerateQuery` nao esta disponivel e o agente deve
  declarar limitacao. CI usa mock de tools (sem OAuth).

### D3 - Nucleo UI-agnostic

```text
chat_pbi.run(pergunta, ...) -> ChatResult
```

`ChatResult` (contrato):

```text
answer_markdown: str
tables: list[dict]          # opcional, tipado
citations: list[dict]       # tools / artifact_id / query ids
meta: dict                  # sessao_id, transport, ...
bloqueado: bool
motivo: str
```

* CLI (`main.py`) so imprime `answer_markdown` (+ meta resumida).
* React/API (fase 2+) consome o mesmo `ChatResult`; nucleo sem
  dependencia de Streamlit/React.

### D4 - Resposta estruturada

A resposta deve ser Markdown estruturado (narrativa + tabela(s) de
metricas e/ou SKUs + conclusao), nao um paragrafo solto. Numeros so
vindos das tools. Input guardrail reutiliza `verificar_input`.

### D6 - Playbook eficiente + completude (qualquer pergunta NL)

O agente segue um caminho geral (nao FAQ por pergunta):

1. Intencao da pergunta
2. Schema/contexto (incl. resolver data sem ano via modelo)
3. Preferir DAX manual + `ExecuteQuery` (estabilidade)
4. `GenerateQuery` so como fallback (max 1x)
5. Narrativa estruturada

Completude (paridade chat Cursor): perguntas de cobertura/estoque/risco
exigem (A) KPI agregado, (B) detalhe SKU sob pressao, (C) conclusao
parcial/sim/nao. Ideal: 1 `ExecuteQuery` com 2 DAX (ROW + TOPN).

Hints do catalogo YAML (`PBI_CATALOG_PATH`) sao injetados como atalho
de medidas/queries; o chat continua podendo gerar DAX ad hoc.

### D5 - Auditoria

Sessao de chat grava eventos em `auditoria/` (tipos `chat_*`), sem
embutir dumps tabulares grandes em `ultima_sessao.json` do batch e sem
tokens. Dump opcional separado se necessario (mesmo padrao ADR-0012).

---

## Alternativas consideradas

### Alternativa A - So REST ExecuteQuery no chat (sem MCP/MAF)

Mais barata, mas perde GenerateQuery/schema e a usabilidade vista no
Cursor. Mantida apenas como fallback.

### Alternativa B - Misturar chat no pipeline Nexus/Optimus

Descartada: quebra reproducibilidade do relatorio e ADR-0001/0003.

### Alternativa C - UI Streamlit no MVP do chat

Descartada para o nucleo; casca trocavel. MVP = CLI; UI rica = fase 2+.

---

## Justificativa

Preserva o batch deterministico (ADR-0025) e entrega paridade de
experiencia com o chat MCP do Cursor, com nucleo reutilizavel para
React depois.

---

## Consequencias positivas

* Fronteira clara chat vs batch.
* GenerateQuery isolado no modo exploratorio.
* Testes CI com mock; smoke live com MCP/REST.
* UI futura sem reescrever o agente.

## Consequencias negativas / trade-offs

* Auth MCP/Entra e o maior risco operacional.
* Dependencia nova: `agent-framework` (+ `mcp`).
* Fallback REST tem paridade parcial (sem GenerateQuery nativo).

---

## Invariantes preservados

* [x] Spec antes do codigo
* [x] IA = LLM + Harness
* [x] LLM nao calcula numeros (numeros via tools MCP/REST)
* [x] Pipeline sequencial do batch intacto
* [x] State blackboard do batch intacto
* [x] Critic read-only (fora do chat)
* [x] HITL obrigatorio para decisao operacional (batch)
* [x] Bridge fora do MVP
* [x] Auditoria sem dataset completo / sem tokens

---

## Impacto em arquitetura

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/contracts/powerbi_catalog_contract.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `docs/agent.log.md`
* [x] Codigo: `chat_pbi.py` + CLI (planning 1.7b)

---

## Criterios de aceite (MVP CLI)

* [x] `python main.py --modo chat --pergunta "..."` (mock CI / MCP live).
* [x] Resposta Markdown estruturada (KPIs + SKUs quando couber).
* [x] Nucleo devolve `ChatResult`; CLI so imprime.
* [x] GenerateQuery disponivel no chat MCP; proibido no batch.
* [x] Batch `--fonte pbi` continua passando testes atuais.
* [x] Testes mock sem OAuth no CI.
* [x] Sem dependencia de React/Streamlit no nucleo.
* [x] Smoke live MCP manual (estoque curto prazo; `model=gpt-5.4`,
  DOI ~28,8d + tabela SKUs understock; 2026-07-22).

### Backlog pos-MVP (esta ADR)

* [ ] REPL com historico multi-turno (`AgentSession` em RAM)
* [ ] UI React/API sobre `ChatResult`
* [ ] DefaultAzureCredential / Entra sem Bearer manual

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard (batch)
ADR-0007 - Guardrails em tres camadas
ADR-0012 - Auditoria sem dados sensiveis
ADR-0025 - Dual ingress planilha vs PBI (batch)
```

---

## Observacoes

Env relevantes:

```text
PBI_ARTIFACT_ID
PBI_ACCESS_TOKEN          # Bearer Fabric/PBI API
CHAT_PBI_TRANSPORT        # mcp | rest | mock (default: mcp)
PBI_MCP_URL               # default Fabric MCP endpoint
CHAT_OPENAI_MODEL         # default gpt-5.4 (chat only; batch usa OPENAI_MODEL)
```
