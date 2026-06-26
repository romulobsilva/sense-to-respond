# ADR-0010 - Implementacao Parcial Nao Marca Done

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

O projeto Sense to Respond segue spec-driven development.

O desenvolvimento e guiado por:

```text
docs/architecture.md
docs/planning.md
docs/agent.log.md
rules.md
.cursor/rules/spec-driven-dev.mdc
```

O arquivo `docs/planning.md` funciona como checklist operacional do projeto.

Ele indica:

* o que ja foi implementado;
* o que esta em andamento;
* o que ainda falta;
* quais fases existem;
* quais entregas fazem parte do MVP;
* quais itens ficam para fases futuras.

Em um fluxo com agentes IA no Cursor, existe o risco de o modelo marcar um item como concluido mesmo quando:

* apenas parte do codigo foi implementada;
* testes nao foram rodados;
* testes falharam;
* documentacao nao foi atualizada;
* arquitetura foi alterada sem spec;
* imports ficaram quebrados;
* feature foi criada, mas nao integrada;
* comportamento antigo foi quebrado;
* houve mock ou placeholder nao documentado;
* a implementacao ficou incompleta.

Isso cria uma falsa sensacao de progresso e compromete a rastreabilidade do projeto.

---

## Decisao

Um item so pode ser marcado como concluido em `docs/planning.md` quando estiver realmente pronto.

Regra central:

```text
Implementacao parcial nao marca [x].
```

Se a implementacao estiver incompleta, o agente IA deve:

```text
nao marcar o item como [x]
registrar o estado parcial em docs/agent.log.md
adicionar subitens pendentes em docs/planning.md
garantir que o pipeline existente continue funcionando
documentar limitacoes conhecidas
informar quais testes passaram e quais nao foram executados
```

Status permitido:

```text
[ ] item nao iniciado ou pendente
[x] item concluido e testado
[~] item cancelado, substituido ou deliberadamente pausado com justificativa
```

O simbolo `[x]` significa:

```text
codigo implementado
criterios de aceite cumpridos
testes minimos executados
documentacao atualizada quando necessario
sem regressao conhecida no pipeline principal
```

---

## Alternativas consideradas

### Alternativa A - Marcar como done quando o codigo principal foi escrito

Descricao:

```text
Marcar [x] assim que a maior parte do codigo estiver implementada, mesmo sem testes completos ou documentacao final.
```

Vantagens:

* progresso aparente mais rapido;
* menos burocracia;
* adequado para prototipos descartaveis.

Desvantagens:

* cria falso status de conclusao;
* dificulta gestao do projeto;
* esconde pendencias;
* aumenta risco de regressao;
* prejudica outro LLM que continue o trabalho;
* quebra spec-driven development.

---

### Alternativa B - Usar comentarios soltos no codigo para pendencias

Descricao:

```text
Deixar TODOs no codigo e marcar o item como concluido no planning.
```

Vantagens:

* rapido;
* pendencias ficam proximas do codigo;
* util para detalhes pequenos.

Desvantagens:

* TODOs podem ser esquecidos;
* planning fica incorreto;
* outro agente pode nao ver a pendencia;
* nao ha rastreabilidade clara;
* nao serve para pendencias arquiteturais.

---

### Alternativa C - Nao marcar done enquanto houver pendencia relevante

Descricao:

```text
Manter o item como pendente ate criterios de aceite e testes passarem. Registrar implementacao parcial no planning e no agent.log.
```

Vantagens:

* status confiavel;
* melhor rastreabilidade;
* melhor continuidade entre sessoes;
* reduz risco de regressao;
* favorece desenvolvimento incremental;
* adequado para uso com LLMs no Cursor.

Desvantagens:

* exige mais disciplina;
* pode parecer que o progresso e menor;
* exige registrar pendencias com clareza.

---

## Justificativa

A alternativa escolhida foi:

```text
Nao marcar done enquanto houver pendencia relevante.
```

Essa decisao preserva o principio:

```text
Spec before code
```

e tambem preserva a confiabilidade do `docs/planning.md`.

O planning deve ser fonte de verdade operacional.

Se ele indicar `[x]`, qualquer humano ou LLM deve poder assumir que o item esta pronto.

Se o item estiver parcial, isso precisa estar visivel.

---

## Definition of Done

Um item so pode ser marcado como `[x]` se todos os pontos aplicaveis forem verdadeiros:

```text
codigo implementado
criterios de aceite cumpridos
testes minimos passaram
python main.py --modo nexus continua funcionando
modo legado continua funcionando, se afetado
documentacao atualizada, se aplicavel
architecture.md atualizado antes do codigo, se houve mudanca arquitetural
contracts atualizados, se houve mudanca de contrato
agent.log.md atualizado
sem imports quebrados
sem codigo morto relevante
sem placeholder nao documentado
sem regressao conhecida
```

---

## Definition of Partial

Uma implementacao deve ser considerada parcial quando qualquer uma das condicoes abaixo ocorrer:

```text
feature existe mas nao esta integrada
codigo foi criado mas nao testado
testes obrigatorios nao foram rodados
testes obrigatorios falharam
documentacao obrigatoria nao foi atualizada
mudanca de contrato nao foi refletida nos docs
pipeline principal quebrou
fallback ainda nao foi implementado
validacao ainda nao foi implementada
auditoria ainda nao foi implementada
guardrail ainda nao foi implementado
ha TODO essencial para funcionamento
ha mock temporario sem registro
```

Nesses casos, o item deve permanecer `[ ]`.

---

## Como registrar implementacao parcial

Quando uma implementacao ficar parcial, atualizar `docs/agent.log.md` com:

```text
### Implementacao parcial

Objetivo:
- ...

O que foi feito:
- ...

O que falta:
- ...

Arquivos alterados:
- ...

Testes executados:
- ...

Testes nao executados:
- ...

Riscos:
- ...

Proximo passo recomendado:
- ...
```

Tambem atualizar `docs/planning.md` com subitens claros.

Exemplo:

```markdown
- [ ] Implementar DataShield Lite
  - [x] Criar leitura de CSV
  - [x] Criar perfil de colunas
  - [ ] Criar inferencia semantica com LLM
  - [ ] Criar validacao do mapa semantico
  - [ ] Integrar ao Nexus
  - [ ] Criar testes E2E
```

---

## Regras para placeholders

Placeholders sao permitidos apenas se:

```text
forem explicitamente temporarios
nao forem confundidos com implementacao final
nao quebrarem o pipeline
estiverem registrados no planning
estiverem registrados no agent.log.md
tiverem criterio claro de substituicao
```

Exemplo aceitavel:

```python
def inferir_mapa_semantico_mock(...):
    """Temporary mock used only while LLM schema inference is not implemented."""
```

Exemplo nao aceitavel:

```python
def inferir_mapa_semantico(...):
    return {"confidence": 1.0}
```

sem documentar que e mock ou placeholder.

---

## Regras para testes nao executados

Se um teste obrigatorio nao foi executado, o agente deve registrar o motivo.

Exemplo:

```text
pytest nao executado porque ainda nao ha suite configurada.
python main.py --modo legado nao executado porque a mudanca nao afeta modo legado.
teste com xlsx nao executado porque fixture ainda nao foi criada.
```

Nao e permitido escrever:

```text
Tudo testado.
```

se os testes nao foram realmente executados.

---

## Regras para planning.md

O `docs/planning.md` deve refletir o estado real.

Regras:

* `[x]` somente para item concluido e validado;
* `[ ]` para pendente ou parcial;
* `[~]` para cancelado, substituido ou pausado com justificativa;
* subitens devem ser adicionados quando a tarefa for grande;
* nao agrupar entregas grandes em um unico checkbox;
* nao remover pendencias sem justificativa;
* nao marcar como concluido apenas porque o codigo compila.

---

## Regras para agent.log.md

Toda sessao significativa deve registrar:

```text
contexto
mudanca solicitada
classificacao da mudanca
arquivos alterados
decisoes tomadas
testes executados
resultado dos testes
pendencias
proximos passos
```

Se a implementacao foi parcial, isso deve ficar explicito.

O `agent.log.md` deve permitir que outro LLM continue o trabalho sem depender do chat anterior.

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/testing.md`
* [ ] `docs/architecture.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text
O processo de desenvolvimento passa a exigir que status de conclusao reflita implementacao, teste e documentacao. Planejamento nao pode ser usado como lista de desejos ja concluida.
```

---

## Impacto em codigo

Nenhum impacto direto obrigatorio em codigo.

Impacto indireto:

```text
codigo parcial nao deve ser tratado como feature concluida
imports quebrados nao podem permanecer
mocks devem ser nomeados e documentados
fallbacks temporarios devem ser registrados
```

---

## Impacto em testes

Testes exigidos para marcar um item como `[x]`:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Se aplicavel:

```bash
python main.py --modo legado
pytest
```

O resultado deve ser registrado no `docs/agent.log.md`.

---

## Criterios de aceite

Esta ADR esta aplicada quando:

* [x] `rules.md` declara que implementacao parcial nao marca done.
* [x] `.cursor/rules/spec-driven-dev.mdc` instrui o LLM a atualizar planning apenas quando criterios passarem.
* [x] `docs/testing.md` define testes minimos.
* [x] `docs/agent.log.md` registra pendencias quando existirem.
* [x] `docs/planning.md` usa checkboxes de forma confiavel.
* [x] Outro LLM consegue continuar o trabalho lendo apenas docs do projeto.

---

## Plano de migracao

Para aplicar esta ADR:

```text
1. Revisar docs/planning.md.
2. Identificar itens marcados como [x] sem evidencia suficiente.
3. Dividir itens grandes em subitens.
4. Mover pendencias para subitens [ ].
5. Registrar ajuste em docs/agent.log.md.
6. Garantir que rules.md e .cursor/rules/*.mdc contenham esta regra.
```

---

## Plano de rollback

Nao ha rollback desejado para permitir falsos positivos no planning.

Se um item foi marcado indevidamente como `[x]`:

```text
1. Reabrir o item como [ ].
2. Adicionar subitens pendentes.
3. Registrar correcao em agent.log.md.
4. Rodar testes necessarios quando a implementacao for concluida.
```

---

## Riscos

| Risco                                     | Probabilidade | Impacto    | Mitigacao                                  |
| ----------------------------------------- | ------------- | ---------- | ------------------------------------------ |
| LLM marcar item como concluido sem teste  | Media         | Alto       | Regra Cursor + agent.log obrigatorio       |
| Planning ficar otimista demais            | Media         | Medio/Alto | Definition of Done clara                   |
| Pendencias ficarem escondidas em TODOs    | Media         | Medio      | Subitens no planning                       |
| Outro LLM assumir que feature esta pronta | Media         | Alto       | Status confiavel e log detalhado           |
| Testes nao executados serem omitidos      | Media         | Alto       | Registrar testes nao executados com motivo |

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0006 - ToolRegistry como fonte unica das tools
ADR-0007 - Guardrails em tres camadas
ADR-0008 - Human-in-the-loop obrigatorio no MVP
ADR-0009 - DataShield nao envia dataset completo ao LLM
```

---

## Observacoes

Esta ADR e especialmente importante para desenvolvimento com LLMs no Cursor.

Um agente IA pode gerar muito codigo rapidamente, mas isso nao significa que a tarefa esta pronta.

Linguagem recomendada:

```text
Implementado parcialmente; manter item aberto ate testes e criterios de aceite passarem.
```

Evitar:

```text
Concluido, falta apenas testar.
```
