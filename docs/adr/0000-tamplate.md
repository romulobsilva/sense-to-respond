# ADR-0000 - Template de Decisao Arquitetural

> Use este template para registrar decisoes arquiteturais relevantes.
> ADR = Architecture Decision Record.
> Cada decisao deve ser pequena, rastreavel e datada.

---

## Status

Escolha um:

```text
Proposto
Aceito
Substituido
Cancelado
```

---

## Data

```text
YYYY-MM-DD
```

---

## Responsavel

```text
Nome ou agente responsavel pela decisao
```

---

## Contexto

Descreva o problema, restricao ou oportunidade que motivou esta decisao.

Inclua:

* qual parte da arquitetura esta envolvida;
* qual problema precisa ser resolvido;
* quais restricoes existem;
* quais riscos precisam ser controlados;
* quais documentos ou requisitos motivaram a decisao.

Exemplo:

```text
O MVP precisa permitir analise de arquivos reais antes do Dominion. Hoje o sistema usa dados simulados em memoria. A proposta tecnica exige upload de arquivos e inferencia semantica. A arquitetura precisa introduzir DataShield Lite antes do Dominion sem quebrar o principio IA = LLM + Harness.
```

---

## Decisao

Descreva claramente o que foi decidido.

A decisao deve ser objetiva.

Exemplo:

```text
Adicionar DataShield Lite como etapa anterior ao Dominion. DataShield Lite sera responsavel por ler arquivos csv/xlsx, gerar perfil de colunas, inferir mapa semantico com LLM, exigir confirmacao humana quando necessario e normalizar o dataset para schema canonico.
```

---

## Alternativas consideradas

Liste as alternativas avaliadas.

### Alternativa A

```text
Descricao da alternativa.
```

Vantagens:

* ...

Desvantagens:

* ...

### Alternativa B

```text
Descricao da alternativa.
```

Vantagens:

* ...

Desvantagens:

* ...

---

## Justificativa

Explique por que a alternativa escolhida e melhor para este momento do projeto.

Considere:

* seguranca;
* simplicidade;
* auditabilidade;
* custo;
* aderencia ao MVP;
* facilidade de teste;
* compatibilidade com arquitetura existente;
* impacto em fases futuras.

Exemplo:

```text
A decisao preserva o pipeline sequencial do MVP, evita MOE dinamico prematuro e permite evoluir para dados reais com controle humano. O LLM permanece limitado a inferencia semantica de schema, sem calcular numeros ou gerar proposicoes.
```

---

## Consequencias positivas

Liste os ganhos esperados.

Exemplo:

* melhora aderencia ao MVP comercial;
* permite uso de arquivos reais;
* preserva governanca;
* torna o handoff DataShield -> Dominion auditavel;
* reduz risco de schema incorreto;
* prepara evolucao para DataShield completo.

---

## Consequencias negativas ou trade-offs

Liste custos e perdas.

Exemplo:

* aumenta complexidade do pipeline;
* exige validacao de schema;
* exige novos testes;
* pode exigir confirmacao humana;
* adiciona dependencia de `openpyxl` para arquivos xlsx.

---

## Invariantes preservados

Marque os invariantes preservados pela decisao.

* [ ] Spec antes do codigo
* [ ] IA = LLM + Harness
* [ ] LLM nao calcula numeros
* [ ] Tools deterministicas calculam metricas
* [ ] State blackboard
* [ ] Sem conversa livre entre agentes no MVP
* [ ] Sem MOE dinamico no MVP
* [ ] Sem consenso multi-agente no MVP
* [ ] Human-in-the-loop obrigatorio
* [ ] Critic read-only
* [ ] Auditoria obrigatoria
* [ ] Sem Bridge/ERP/WMS/TMS no MVP

Explique qualquer invariante afetado:

```text
N/A
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [ ] `docs/architecture.md`
* [ ] `docs/planning.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`
* [ ] `docs/testing.md`
* [ ] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

Descreva o impacto:

```text
...
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [ ] `agent.py`
* [ ] `audit.py`
* [ ] `config.py`
* [ ] `critic.py`
* [ ] `guardrails.py`
* [ ] `harness.py`
* [ ] `main.py`
* [ ] `nexus.py`
* [ ] `optimus.py`
* [ ] `sinais.py`
* [ ] `state_types.py`
* [ ] `tools.py`
* [ ] `validator.py`
* [ ] novo arquivo

Novos arquivos previstos:

```text
...
```

Descreva o impacto:

```text
...
```

---

## Impacto em testes

Testes exigidos:

* [ ] `python -m py_compile *.py`
* [ ] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [ ] testes unitarios
* [ ] testes de integracao
* [ ] testes de guardrail
* [ ] testes de prompt
* [ ] testes de auditoria
* [ ] testes com arquivo real ou fixture

Detalhar:

```text
...
```

---

## Criterios de aceite

Liste criterios objetivos para considerar a decisao implementada.

Exemplo:

* [ ] `architecture.md` atualizado antes do codigo;
* [ ] `planning.md` atualizado com novo item ou subitem;
* [ ] codigo implementado;
* [ ] testes minimos passaram;
* [ ] auditoria registra eventos novos;
* [ ] `agent.log.md` atualizado;
* [ ] pipeline anterior continua funcionando.

---

## Plano de migracao

Descreva como sair do estado atual para o novo estado.

Exemplo:

```text
1. Atualizar arquitetura.
2. Atualizar planning.
3. Criar tipos novos em state_types.py.
4. Criar tools novas.
5. Integrar ao Nexus.
6. Rodar testes.
7. Atualizar agent.log.md.
```

---

## Plano de rollback

Descreva como reverter se algo der errado.

Exemplo:

```text
Manter modo atual sem DataShield como fallback. Se DataShield falhar, o Nexus pode continuar executando com dados simulados quando nenhum arquivo for fornecido.
```

---

## Riscos

Liste riscos conhecidos.

| Risco | Probabilidade    | Impacto          | Mitigacao |
| ----- | ---------------- | ---------------- | --------- |
| ...   | baixa/media/alta | baixo/medio/alto | ...       |

---

## Decisoes relacionadas

Liste ADRs relacionadas, se existirem.

```text
ADR-0001 - ...
ADR-0002 - ...
```

---

## Observacoes

Use esta secao para detalhes adicionais.

```text
...
```
