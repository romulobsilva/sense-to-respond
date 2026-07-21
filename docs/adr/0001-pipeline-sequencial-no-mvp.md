# ADR-0001 - Pipeline Sequencial no MVP

---

## Status

Aceito

---

## Data

2026-06-25

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O projeto Sense to Respond foi concebido como uma arquitetura multi-agente para detectar sinais comerciais e gerar proposicoes de acao em processos de S&OE.

A visao conceitual da solucao possui cinco componentes:

```text
DataShield
Dominion
Optimus
Bridge
Nexus
```

Entretanto, o MVP precisa priorizar:

* previsibilidade;
* auditabilidade;
* baixo risco operacional;
* menor custo de inferencia;
* facilidade de teste;
* aderencia a governanca corporativa;
* human-in-the-loop;
* ausencia de execucao automatica em sistemas operacionais.

Durante a discussao arquitetural, foi avaliada a possibilidade de implementar agentes que conversam livremente, MOE router dinamico, execucao paralela e consenso multi-agente.

Essas capacidades foram consideradas mais adequadas para fases futuras, nao para o MVP.

---

## Decisao

O MVP do Sense to Respond deve usar um **pipeline sequencial governado por harness**, com comunicacao por **state blackboard**.

Fluxo aceito para o MVP:

```text
Input Guardrail
  -> DataShield Lite
  -> Dominion
  -> Sinais estruturados
  -> Optimus
  -> Validador deterministico
  -> Critic LLM read-only
  -> Fila Nexus
  -> Output Guardrail
  -> Usuario humano decide
```

No estado atual do MVP tecnico, DataShield Lite ainda pode estar planejado. Enquanto ele nao estiver implementado, o fluxo permitido e:

```text
Input Guardrail
  -> Dominion
  -> Sinais estruturados
  -> Optimus
  -> Validador deterministico
  -> Critic LLM read-only
  -> Fila Nexus
  -> Output Guardrail
```

Nao implementar no MVP sem nova ADR e atualizacao previa da arquitetura:

```text
MOE router dinamico
consenso multi-agente
agentes paralelos autonomos
conversa livre entre agentes em linguagem natural
Bridge operacional
execucao automatica em ERP/WMS/TMS
```

---

## Alternativas consideradas

### Alternativa A - Pipeline sequencial governado por harness

Descricao:

```text
Cada fase executa em ordem definida. O Nexus orquestra o fluxo, o harness controla ferramentas, o state blackboard transporta informacao e a auditoria registra handoffs.
```

Vantagens:

* simples de implementar;
* facil de auditar;
* facil de testar;
* reduz risco de comportamento emergente;
* preserva human-in-the-loop;
* reduz custo de chamadas LLM;
* favorece explicabilidade;
* adequado para MVP corporativo.

Desvantagens:

* menos flexivel;
* nao explora paralelismo entre agentes;
* nao resolve divergencias por consenso formal;
* depende de fluxo previamente definido.

---

### Alternativa B - Multiagente conversacional livre

Descricao:

```text
Agentes especializados conversam entre si em linguagem natural ate chegar a uma conclusao.
```

Vantagens:

* maior flexibilidade;
* melhor para exploracao aberta;
* permite revisoes cruzadas ricas;
* pode simular discussao entre especialistas.

Desvantagens:

* mais dificil de auditar;
* mais caro;
* mais imprevisivel;
* maior risco de alucinacao;
* maior dificuldade para garantir que LLM nao calcule numeros;
* mais dificil de validar em ambiente corporativo;
* nao adequado para o MVP.

---

### Alternativa C - MOE router dinamico

Descricao:

```text
Um roteador decide dinamicamente quais agentes executar, em que ordem e com quais ferramentas.
```

Vantagens:

* melhor escalabilidade futura;
* fluxo mais adaptativo;
* evita executar agentes desnecessarios;
* pode atender perguntas variadas.

Desvantagens:

* aumenta complexidade;
* exige contrato forte de roteamento;
* exige mais testes;
* pode dificultar previsibilidade;
* aumenta risco de divergencia entre planejamento e execucao;
* mais adequado para Fase 2/3.

---

### Alternativa D - Consenso multi-agente

Descricao:

```text
Agentes produzem respostas independentes e passam por uma camada de consenso para resolver divergencias.
```

Vantagens:

* robustez teorica maior;
* pode reduzir conclusoes isoladas frageis;
* permite ponderar opinioes especializadas.

Desvantagens:

* exige protocolo de consenso;
* exige paralelismo ou multiplas rodadas;
* aumenta custo;
* dificulta auditoria;
* nao e necessario para o primeiro MVP, pois Validador + Critic read-only ja cobrem parte da validacao.

---

## Justificativa

A alternativa escolhida foi o **pipeline sequencial governado por harness**.

Essa decisao e adequada porque o MVP precisa demonstrar valor com seguranca e rastreabilidade antes de introduzir mecanismos mais dinamicos.

O pipeline sequencial preserva o principio:

```text
IA = LLM + Harness
```

Tambem garante que:

* o LLM nao calcule numeros;
* ferramentas deterministicas facam os calculos;
* cada handoff seja auditavel;
* cada fase tenha responsabilidade clara;
* proposicoes sejam validadas antes da fila;
* usuario humano aprove ou rejeite recomendacoes;
* Bridge fique fora do MVP.

O MVP deve privilegiar confianca operacional em vez de autonomia ampla.

---

## Consequencias positivas

* Arquitetura mais simples de explicar para negocio e TI.
* Menor risco de comportamento inesperado.
* Auditoria mais clara.
* Testes mais objetivos.
* Reducao de custo de inferencia.
* Melhor alinhamento com governanca corporativa.
* Human-in-the-loop preservado.
* Facilita evolucao incremental para DataShield Lite, Dominion expandido e Optimus expandido.
* Permite demonstrar valor antes de adicionar MOE ou consenso.

---

## Consequencias negativas ou trade-offs

* Menor flexibilidade para perguntas exploratorias.
* O fluxo precisa ser definido previamente.
* Nao ha agentes paralelos no MVP.
* Nao ha consenso multi-agente formal.
* Algumas perguntas podem exigir ajustes manuais no pipeline.
* A arquitetura pode parecer menos "autonoma" do que uma arquitetura multiagente livre.

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
Nenhum invariante foi violado. A decisao reforca os invariantes do MVP.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [ ] `docs/testing.md`
* [ ] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

Impacto:

```text
A arquitetura deve deixar explicito que o MVP usa pipeline sequencial com state blackboard e que MOE router, consenso multi-agente e agentes paralelos ficam para fases futuras.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `nexus.py`
* [x] `harness.py`
* [x] `agent.py`
* [x] `state_types.py`
* [x] `optimus.py`
* [x] `validator.py`
* [x] `critic.py`
* [x] `guardrails.py`
* [x] `audit.py`
* [x] `main.py`

Impacto:

```text
O codigo deve manter Nexus como control plane e Harness como executor controlado do loop Dominion. Agentes/fases devem trocar informacao via state, nao por conversa livre em linguagem natural.
```

Novos arquivos previstos:

```text
Nenhum arquivo novo obrigatorio para esta ADR.
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [ ] testes unitarios
* [ ] testes de integracao
* [ ] testes de guardrail
* [ ] testes de prompt
* [ ] testes de auditoria
* [ ] testes com arquivo real ou fixture

Detalhar:

```text
O pipeline principal deve rodar end-to-end com dados simulados. O fluxo deve gerar sinais, proposicoes, validacao, critic, fila Nexus, output guardrail e auditoria.
```

---

## Criterios de aceite

* [x] `architecture.md` declara pipeline sequencial no MVP.
* [x] `planning.md` deixa MOE router e consenso para fases futuras.
* [x] `agent.log.md` registra a decisao.
* [x] O MVP nao implementa conversa livre entre agentes.
* [x] O MVP nao implementa MOE router dinamico.
* [x] O MVP nao implementa consenso multi-agente.
* [x] O MVP nao implementa Bridge operacional.
* [x] O MVP preserva human-in-the-loop.
* [x] O Critic e read-only.
* [x] O state blackboard e o mecanismo de comunicacao entre fases.

---

## Plano de migracao

Esta decisao ja esta refletida no MVP atual.

Para manter consistencia:

```text
1. Garantir que architecture.md descreve pipeline sequencial.
2. Garantir que planning.md mantem MOE e consenso em Fase 2/3.
3. Garantir que rules.md bloqueia implementacao dessas capacidades sem nova ADR.
4. Garantir que .cursor/rules/spec-driven-dev.mdc instrui LLMs a nao implementar MOE/consenso no MVP.
5. Registrar futuras excecoes como novas ADRs.
```

---

## Plano de rollback

Nao aplicavel no momento, pois esta decisao define o comportamento-base do MVP.

Caso seja necessario migrar para MOE ou consenso no futuro:

```text
1. Criar nova ADR substituindo esta decisao parcialmente.
2. Atualizar architecture.md.
3. Atualizar planning.md.
4. Definir contrato de roteador ou consenso.
5. Implementar testes especificos.
6. Manter pipeline sequencial como fallback.
```

---

## Riscos

| Risco                                             | Probabilidade | Impacto     | Mitigacao                                              |
| ------------------------------------------------- | ------------- | ----------- | ------------------------------------------------------ |
| Pipeline ficar rigido demais                      | Media         | Medio       | Adicionar MOE router apenas em Fase 2/3 com nova ADR   |
| Usuarios esperarem autonomia maior                | Media         | Medio       | Comunicar que MVP e human-in-the-loop                  |
| Fluxo nao responder bem a perguntas exploratorias | Media         | Baixo/Medio | Criar backlog para classificador de intencao           |
| Overclaiming comercial sobre multiagentes         | Media         | Alto        | Distinguir agentes conceituais de pipeline tecnico MVP |
| Dificuldade futura para paralelizar               | Baixa         | Medio       | Preservar contratos de state e handoff                 |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard sem conversa livre
ADR-0004 - Critic read-only
ADR-0005 - DataShield Lite antes do Dominion
```

---

## Observacoes

Esta ADR nao nega a visao multi-agente da solucao.

Ela apenas define que, no MVP tecnico, a implementacao deve ser sequencial, governada por harness e auditavel.

### Addendum 2026-07-21 (ADR-0025)

DataShield Lite e **condicional** ao ingresso planilha. O caminho PBI
unificado (catalogo DAX + MCP) tambem e sequencial e desemboca no mesmo
motor Optimus/Critic/fila/PDF. Nao altera a proibicao de MOE/consenso
no MVP. Itens pos-PoC (Popa, omnichannel, catalogo Mondelez PBI) ficam
no backlog de `planning.md` Fase 1.7a.

A linguagem recomendada para documentacao tecnica e:

```text
Pipeline agentic sequencial governado por harness, com state blackboard, tools deterministicas, validacao, Critic read-only e fila human-in-the-loop.
```

Evitar descrever o MVP tecnico como:

```text
Rede de agentes autonomos conversando livremente ate chegar a consenso.
```
