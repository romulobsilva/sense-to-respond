# ADRs - Architecture Decision Records

Este diretorio contem os registros de decisoes arquiteturais do projeto Sense to Respond.

ADR significa **Architecture Decision Record**.

Cada ADR registra uma decisao relevante de arquitetura, seu contexto, alternativas consideradas, justificativa, consequencias, impactos, riscos e criterios de aceite.

---

## 1. Como usar este diretorio

Antes de implementar qualquer mudanca arquitetural, o agente IA ou desenvolvedor deve:

1. Ler `docs/architecture.md`.
2. Ler `docs/planning.md`.
3. Ler `rules.md`.
4. Consultar este indice.
5. Verificar se ja existe ADR relacionada.
6. Se a mudanca contradiz uma ADR aceita, criar nova ADR antes de codar.
7. Se a mudanca apenas detalha uma ADR existente, atualizar a documentacao relacionada.
8. Registrar a sessao em `docs/agent.log.md`.

---

## 2. Regra central

Se houver conflito entre uma sugestao do LLM e uma ADR aceita, a ADR vence.

Se a ADR estiver desatualizada, ela deve ser substituida formalmente por nova ADR.

Nao alterar comportamento arquitetural importante apenas no codigo.

---

## 3. Status possiveis

Cada ADR deve ter um dos seguintes status:

```text
Proposto
Aceito
Substituido
Cancelado
```

### Proposto

A decisao ainda esta em avaliacao.

Nao deve ser tratada como regra definitiva.

### Aceito

A decisao esta vigente.

Deve ser seguida por codigo, docs, prompts, testes e regras do Cursor.

### Substituido

A decisao foi superada por outra ADR.

A ADR substituta deve ser indicada.

### Cancelado

A decisao foi descartada e nao deve guiar implementacao.

---

## 4. Indice de ADRs

| ADR      | Titulo                                                    | Status   | Tema central                                           |
| -------- | --------------------------------------------------------- | -------- | ------------------------------------------------------ |
| ADR-0000 | Template de Decisao Arquitetural                          | Template | Modelo para novas ADRs                                 |
| ADR-0001 | Pipeline Sequencial no MVP                                | Aceito   | MVP usa pipeline sequencial, sem MOE/consenso          |
| ADR-0002 | LLM Nao Calcula Numeros                                   | Aceito   | Numeros sempre calculados por tools deterministicas    |
| ADR-0003 | State Blackboard sem Conversa Livre entre Agentes         | Aceito   | Componentes compartilham informacao via state          |
| ADR-0004 | Critic Read-Only                                          | Aceito   | Critic audita, mas nao altera proposicoes              |
| ADR-0005 | DataShield Lite antes do Dominion                         | Aceito   | Arquivos reais passam por preparacao antes do Dominion |
| ADR-0006 | ToolRegistry como Fonte Unica das Tools                   | Proposto | Centralizar lista e metadados das tools                |
| ADR-0007 | Guardrails em Tres Camadas                                | Aceito   | Input, harness e output guardrails                     |
| ADR-0008 | Human-in-the-Loop Obrigatorio no MVP                      | Aceito   | MVP recomenda, humano decide                           |
| ADR-0009 | DataShield Nao Envia Dataset Completo ao LLM              | Aceito   | LLM recebe apenas perfil e amostra limitada            |
| ADR-0010 | Implementacao Parcial Nao Marca Done                      | Aceito   | Planning so marca `[x]` quando pronto e testado        |
| ADR-0011 | Prompts com JSON Validado, Retry e Fallback               | Aceito   | Saidas estruturadas de LLM exigem validacao            |
| ADR-0012 | Auditoria sem Dados Sensiveis                             | Aceito   | Logs registram eventos seguros, nao datasets completos |
| ADR-0013 | Dominion Executa Apenas Analises Compativeis com os Dados | Aceito   | Analises dependem das colunas disponiveis              |
| ADR-0014 | Output com Evidencias, Disclaimer e Revisao               | Aceito   | Resposta final deve ser rastreavel e segura            |
| ADR-0015 | UI MVP Aprova/Rejeita, mas Nao Executa                    | Aceito   | UI registra decisao humana, sem executar acao          |
| ADR-0016 | Bridge Fora do MVP                                        | Aceito   | Execucao operacional fica para fase futura             |
| ADR-0017 | MOE e Consenso Apenas em Fase Futura                      | Aceito   | Roteamento dinamico e consenso fora do MVP             |
| ADR-0018 | DataShield Lite Nao Substitui Governanca de Dados         | Aceito   | DataShield Lite e limitado ao MVP                      |
| ADR-0019 | Dados Reais Mondelez Substituem Simulados no Dominion     | Aceito   | CSV real com tools parametrizadas                      |
| ADR-0020 | DataShield com 3 Niveis de Adaptacao                      | Aceito   | Mapeamento, ETL gerado, diagnostico incompatibilidade  |
| ADR-0021 | LLM Pode Gerar ETL mas Nao Metrica                       | Aceito   | Fronteira: ETL permitido, calculo de negocio proibido  |
| ADR-0022 | HITL via Protocolo Abstrato com Streamlit                 | Aceito   | InterfaceHITL plugavel, demo com Streamlit             |
| ADR-0023 | Comunicacao Pipeline-UI via JSON                          | Aceito   | Arquivos JSON em approvals/ para HITL assincrono       |
| ADR-0024 | Portabilidade Multi-Dominio                               | Aceito   | Thresholds, NR, schema, forward configuraveis          |
| ADR-0025 | Dois Caminhos Planilha vs PBI/MCP                         | Aceito   | Catalogo DAX; PoC Agua; Mondelez PBI no backlog        |
| ADR-0026 | Chat PBI analitico via MAF + MCP                          | Aceito   | `--modo chat`; gpt-5.4; ExecuteQuery-first; smoke OK   |

---

## 5. ADRs fundamentais do MVP

As ADRs mais importantes para qualquer agente IA no Cursor sao:

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM Nao Calcula Numeros
ADR-0003 - State Blackboard sem Conversa Livre entre Agentes
ADR-0004 - Critic Read-Only
ADR-0007 - Guardrails em Tres Camadas
ADR-0008 - Human-in-the-Loop Obrigatorio no MVP
ADR-0016 - Bridge Fora do MVP
ADR-0017 - MOE e Consenso Apenas em Fase Futura
```

Essas decisoes definem os limites principais do MVP.

---

## 6. ADRs relacionadas a DataShield

As ADRs ligadas ao DataShield Lite sao:

```text
ADR-0005 - DataShield Lite antes do Dominion
ADR-0009 - DataShield Nao Envia Dataset Completo ao LLM
ADR-0013 - Dominion Executa Apenas Analises Compativeis com os Dados
ADR-0018 - DataShield Lite Nao Substitui Governanca de Dados
ADR-0019 - Dados Reais Mondelez Substituem Simulados no Dominion
ADR-0020 - DataShield com 3 Niveis de Adaptacao
ADR-0021 - LLM Pode Gerar ETL mas Nao Metrica
```

Essas decisoes deixam claro que DataShield Lite:

* prepara arquivos tabulares;
* usa LLM apenas para inferencia semantica;
* nao envia dataset completo ao LLM;
* nao substitui governanca corporativa completa;
* deve produzir dataset canonico antes do Dominion;
* opera em 3 niveis (mapeamento, ETL, diagnostico);
* pode gerar scripts ETL (nao metricas) com revisao humana.

---

## 7. ADRs relacionadas a governanca de LLM

As ADRs ligadas ao uso seguro de LLM sao:

```text
ADR-0002 - LLM Nao Calcula Numeros
ADR-0004 - Critic Read-Only
ADR-0007 - Guardrails em Tres Camadas
ADR-0011 - Prompts com JSON Validado, Retry e Fallback
ADR-0012 - Auditoria sem Dados Sensiveis
ADR-0014 - Output com Evidencias, Disclaimer e Revisao
ADR-0021 - LLM Pode Gerar ETL mas Nao Metrica
```

Essas decisoes garantem que o LLM seja usado como componente controlado, nao como executor livre.

---

## 7b. ADRs relacionadas ao HITL

As ADRs ligadas ao human-in-the-loop sao:

```text
ADR-0008 - Human-in-the-Loop Obrigatorio no MVP
ADR-0015 - UI MVP Aprova/Rejeita, mas Nao Executa
ADR-0022 - HITL via Protocolo Abstrato com Streamlit
ADR-0023 - Comunicacao Pipeline-UI via JSON
```

Essas decisoes definem que:

* o humano decide antes de qualquer acao operacional;
* a interface usa protocolo abstrato com implementacoes plugaveis;
* a comunicacao pipeline-UI e via arquivos JSON auditaveis;
* a demo EY usa Streamlit como interface visual.

---

## 8. ADRs relacionadas ao desenvolvimento no Cursor

As ADRs que mais afetam o comportamento de LLMs no Cursor sao:

```text
ADR-0006 - ToolRegistry como Fonte Unica das Tools
ADR-0010 - Implementacao Parcial Nao Marca Done
ADR-0011 - Prompts com JSON Validado, Retry e Fallback
ADR-0012 - Auditoria sem Dados Sensiveis
```

Essas decisoes ajudam a evitar:

* listas duplicadas;
* implementacoes parciais marcadas como concluidas;
* parsing permissivo de JSON;
* logs com dados sensiveis;
* drift entre codigo, prompts e spec.

---

## 9. Como criar uma nova ADR

Para criar uma nova ADR:

1. Copiar `docs/adr/0000-template.md`.
2. Renomear com o proximo numero disponivel.
3. Usar nome curto e descritivo.

Exemplo:

```text
docs/adr/0019-nome-da-decisao.md
```

4. Preencher todas as secoes relevantes.
5. Definir status inicial como `Proposto`.
6. Atualizar este `README.md`.
7. Atualizar `docs/architecture.md`, se a decisao alterar arquitetura.
8. Atualizar `docs/planning.md`, se a decisao alterar roadmap.
9. Registrar em `docs/agent.log.md`.

---

## 10. Quando criar nova ADR

Criar nova ADR quando a mudanca envolver:

```text
novo componente arquitetural
mudanca de fluxo principal
mudanca no papel de um agente/fase
mudanca de contrato do state
mudanca de contrato de tool
mudanca de contrato de prompt
mudanca de guardrail
mudanca de politica de auditoria
mudanca no human-in-the-loop
habilitacao de Bridge
habilitacao de MOE
habilitacao de consenso multi-agente
mudanca em uso de dados sensiveis
mudanca na relacao LLM vs tools deterministicas
```

Nao e necessario criar ADR para:

```text
correcao local de bug
refatoracao sem mudanca de comportamento
ajuste pequeno de texto
teste adicional
formatacao
documentacao que nao altera decisao
```

---

## 11. Como substituir uma ADR

Se uma decisao antiga precisar mudar:

1. Criar nova ADR.
2. Na nova ADR, indicar qual ADR esta sendo substituida.
3. Alterar status da ADR antiga para `Substituido`.
4. Adicionar referencia para a nova ADR.
5. Atualizar este `README.md`.
6. Atualizar `architecture.md`, `planning.md` e `agent.log.md`.

Nao editar silenciosamente uma ADR aceita para mudar uma decisao historica.

A ADR antiga deve preservar o historico da decisao.

---

## 12. Ordem recomendada de leitura

Para entender rapidamente a arquitetura do MVP, ler nesta ordem:

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM Nao Calcula Numeros
ADR-0003 - State Blackboard sem Conversa Livre entre Agentes
ADR-0004 - Critic Read-Only
ADR-0007 - Guardrails em Tres Camadas
ADR-0008 - Human-in-the-Loop Obrigatorio no MVP
ADR-0016 - Bridge Fora do MVP
ADR-0017 - MOE e Consenso Apenas em Fase Futura
ADR-0005 - DataShield Lite antes do Dominion
ADR-0018 - DataShield Lite Nao Substitui Governanca de Dados
```

---

## 13. Regras para LLMs no Cursor

Qualquer LLM usado no Cursor deve seguir estas regras:

```text
1. Nao contradizer ADR aceita.
2. Nao implementar Bridge no MVP.
3. Nao implementar MOE ou consenso no MVP.
4. Nao permitir LLM calcular numeros.
5. Nao permitir Critic criar proposicoes.
6. Nao enviar dataset completo ao LLM.
7. Nao marcar planning como done se implementacao estiver parcial.
8. Nao salvar dados sensiveis em auditoria.
9. Nao alterar contratos sem atualizar docs.
10. Nao executar acao operacional automaticamente.
```

Se a tarefa exigir quebrar uma dessas regras, criar nova ADR antes de codar.

---

## 14. Relacao com outros documentos

Este diretorio deve estar consistente com:

```text
docs/architecture.md
docs/planning.md
docs/agent.log.md
docs/contracts/state_contract.md
docs/contracts/tool_contract.md
docs/prompts.md
docs/testing.md
rules.md
.cursor/rules/spec-driven-dev.mdc
```

Se houver divergencia:

1. Parar.
2. Identificar qual documento esta desatualizado.
3. Corrigir a spec antes do codigo.
4. Registrar a decisao em `docs/agent.log.md`.

---

## 15. Regra final

ADRs existem para proteger a coerencia do projeto.

Elas nao devem burocratizar mudancas pequenas.

Mas toda mudanca que altere arquitetura, seguranca, governanca, contratos ou papel dos agentes deve passar por ADR.

Se uma decisao nao esta clara, documente antes de implementar.
