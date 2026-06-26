# ADR-0003 - State Blackboard sem Conversa Livre entre Agentes

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

O projeto Sense to Respond possui uma arquitetura conceitual multi-agente, com componentes especializados:

```text
DataShield
Dominion
Optimus
Bridge
Nexus
```

Esses componentes precisam compartilhar informacoes ao longo do pipeline.

Uma alternativa seria permitir que agentes conversassem livremente em linguagem natural, trocando justificativas, hipoteses e conclusoes ate chegar a uma resposta final.

Entretanto, o MVP tem requisitos fortes de:

* rastreabilidade;
* governanca;
* auditoria;
* reproducibilidade;
* controle de custo;
* separacao de responsabilidades;
* facilidade de teste;
* seguranca contra alucinacao;
* human-in-the-loop.

Por isso, a arquitetura precisa de um mecanismo de comunicacao mais controlado do que conversa livre entre agentes.

---

## Decisao

O MVP deve usar o padrao **state blackboard**.

Isso significa que agentes e fases compartilham informacao por meio de um objeto de estado estruturado, chamado `state`.

Fluxo conceitual:

```text
DataShield
  escreve perfil, mapa semantico e dataset canonico no state

Dominion
  le dados do state
  escreve resultados deterministicos no state

Sinais
  le resultados deterministicos
  escreve sinais estruturados no state

Optimus
  le sinais
  escreve proposicoes no state

Validador
  le sinais e proposicoes
  escreve validacao no state

Critic
  le sinais e proposicoes
  escreve critica no state

Nexus
  le validacao, critica e proposicoes
  escreve fila final no state
```

No MVP, fica proibido:

```text
conversa livre entre agentes em linguagem natural
debate multi-agente
mensagens privadas entre agentes fora do state
consenso textual iterativo
troca de conclusoes nao auditadas
```

Toda passagem relevante entre fases deve ser registrada como handoff auditavel.

---

## Alternativas consideradas

### Alternativa A - State blackboard estruturado

Descricao:

```text
Todos os componentes leem e escrevem campos especificos do state. O state funciona como fonte de verdade da execucao.
```

Vantagens:

* auditavel;
* previsivel;
* testavel;
* adequado para pipeline sequencial;
* permite contratos claros;
* reduz ambiguidade;
* facilita replay de execucao;
* evita que informacoes importantes fiquem apenas em texto livre.

Desvantagens:

* menos flexivel;
* exige modelagem de tipos;
* exige contratos de state;
* exige manutencao de schemas.

---

### Alternativa B - Conversa livre entre agentes

Descricao:

```text
Agentes trocam mensagens em linguagem natural ate construir uma conclusao ou recomendacao.
```

Vantagens:

* mais flexivel;
* mais parecido com colaboracao humana;
* permite debate e revisao cruzada;
* pode ser util em fases futuras.

Desvantagens:

* dificil de auditar;
* dificil de testar;
* dificil de reproduzir;
* maior risco de alucinacao;
* maior risco de perda de evidencias;
* maior custo de tokens;
* mais dificil garantir que LLM nao calcula numeros;
* nao adequado ao MVP.

---

### Alternativa C - Handoff textual livre entre fases

Descricao:

```text
Cada fase gera um resumo textual que e passado para a proxima.
```

Vantagens:

* simples de implementar;
* facil de ler;
* reduz necessidade de tipos inicialmente.

Desvantagens:

* perde estrutura;
* dificulta validacao;
* dificulta auditoria;
* pode omitir dados importantes;
* dificulta rastrear proposicoes ate sinais;
* aumenta risco de ambiguidade.

---

## Justificativa

A alternativa escolhida foi o **state blackboard estruturado**.

Essa decisao preserva o principio:

```text
IA = LLM + Harness
```

O LLM pode interpretar e gerar narrativa, mas as evidencias, sinais, proposicoes, validacoes e criticas precisam estar em campos estruturados.

O state blackboard permite que cada componente tenha responsabilidade clara:

```text
Dominion detecta
Sinais estruturam
Optimus propoe
Validador confere
Critic audita
Nexus prioriza
Humano decide
```

Essa separacao melhora rastreabilidade e reduz o risco de que uma decisao operacional seja baseada apenas em texto livre gerado por LLM.

---

## Consequencias positivas

* Facilita auditoria.
* Facilita testes unitarios e de integracao.
* Facilita rastrear proposicoes ate sinais.
* Facilita aplicar guardrails.
* Evita mensagens ocultas entre agentes.
* Reduz risco de conclusoes sem evidencia.
* Permite replay de uma execucao.
* Permite validar contratos de entrada e saida.
* Facilita evolucao para DataShield Lite.
* Facilita integracao futura com UI e fila Nexus.

---

## Consequencias negativas ou trade-offs

* Exige mais modelagem de tipos.
* Exige atualizacao de contrato quando campos mudam.
* Reduz flexibilidade de agentes.
* Pode exigir conversao de DataFrames para resumos ou objetos serializaveis.
* Exige cuidado para nao armazenar dados sensiveis no state ou auditoria.
* Pode ser mais trabalhoso do que passar texto livre.

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
Nenhum invariante foi violado. Esta ADR formaliza o state blackboard como mecanismo oficial de comunicacao entre fases.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `docs/contracts/state_contract.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [ ] `docs/testing.md`

Impacto:

```text
A arquitetura deve declarar explicitamente que componentes do MVP compartilham informacao por state blackboard e nao por conversa livre entre LLMs.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `state_types.py`
* [x] `nexus.py`
* [x] `harness.py`
* [x] `sinais.py`
* [x] `optimus.py`
* [x] `validator.py`
* [x] `critic.py`
* [x] `guardrails.py`
* [x] `audit.py`
* [x] `main.py`

Impacto:

```text
O codigo deve manter o state como estrutura compartilhada. Handoffs devem ser registrados de forma auditavel. Componentes nao devem depender de conversas livres entre agentes.
```

Novos arquivos previstos:

```text
docs/contracts/state_contract.md
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] testes de criacao do state inicial
* [x] testes de serializacao de sinais
* [x] testes de serializacao de proposicoes
* [x] testes de handoff append-only
* [x] testes de auditoria de handoff
* [x] testes de pipeline Nexus

Detalhar:

```text
Toda mudanca em state_types.py ou no contrato do state deve ter teste de compatibilidade com o pipeline principal.
```

---

## Criterios de aceite

* [x] `architecture.md` declara state blackboard.
* [x] `state_types.py` define objetos estruturados principais.
* [x] `Nexus` registra handoffs entre fases.
* [x] `Critic` recebe sinais e proposicoes estruturadas.
* [x] `Validador` recebe sinais e proposicoes estruturadas.
* [x] `Optimus` gera proposicoes a partir de sinais, nao de conversa textual.
* [x] O MVP nao possui conversa livre entre agentes.
* [x] O MVP nao depende de debate multiagente.
* [x] Auditoria registra passagens relevantes.

---

## Plano de migracao

Esta decisao ja esta parcialmente implementada.

Para reforcar:

```text
1. Manter `state_types.py` como fonte de tipos do blackboard.
2. Criar ou manter `docs/contracts/state_contract.md`.
3. Atualizar `architecture.md` quando novos campos forem adicionados.
4. Garantir que DataShield Lite escreva no state, nao em mensagens soltas.
5. Garantir que Dominion leia dataset canonico do state.
6. Garantir que Optimus leia sinais do state.
7. Garantir que Critic audite proposicoes e sinais do state.
8. Testar handoffs e serializacao.
```

---

## Plano de rollback

Nao ha rollback desejado para conversa livre no MVP.

Se algum desenvolvimento introduzir troca textual livre entre agentes:

```text
1. Remover dependencia de conversa livre.
2. Converter informacao trocada para campo estruturado no state.
3. Atualizar `state_contract.md`.
4. Registrar correcao em `agent.log.md`.
```

Se no futuro for desejado adicionar conversa entre agentes:

```text
1. Criar nova ADR.
2. Definir protocolo de mensagens.
3. Definir auditoria de mensagens.
4. Definir limites de custo e rodadas.
5. Definir criterio de parada.
6. Definir como mensagens viram evidencias estruturadas.
```

---

## Riscos

| Risco                                     | Probabilidade | Impacto    | Mitigacao                                         |
| ----------------------------------------- | ------------- | ---------- | ------------------------------------------------- |
| State crescer demais                      | Media         | Medio      | Criar contratos e separar resumos de dados brutos |
| Campos ficarem pouco tipados              | Media         | Medio/Alto | Migrar gradualmente para dataclasses/TypedDict    |
| Dados sensiveis irem para auditoria       | Media         | Alto       | Serializar apenas resumos e hashes                |
| LLM depender de texto livre fora do state | Media         | Alto       | Reforcar prompts e testes                         |
| Mudanca em state quebrar pipeline         | Media         | Medio      | Testes de compatibilidade e E2E Nexus             |

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0004 - Critic read-only
ADR-0005 - DataShield Lite antes do Dominion
```

---

## Observacoes

Esta ADR nao impede que, no futuro, agentes conversem entre si.

Ela apenas define que, no MVP, a comunicacao oficial e auditavel ocorre por `state`.

Linguagem recomendada:

```text
Os agentes/fases compartilham informacao por um blackboard estruturado, com handoffs auditaveis.
```

Evitar:

```text
Os agentes conversam livremente ate chegar a uma decisao.
```
