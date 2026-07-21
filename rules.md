# Regras de Desenvolvimento - Sense to Respond

> Referencia humana das regras do projeto.
> Versao resumida para Cursor IDE: `.cursor/rules/spec-driven-dev.mdc`
> Todo desenvolvedor ou agente IA DEVE seguir estas regras.

---

## 1. Principio central

Este projeto segue o paradigma **spec-driven development**.

A especificacao vem antes do codigo.

Toda mudanca deve preservar o principio arquitetural:

```text
IA = LLM + Harness
```

Isso significa:

* O LLM decide proximos passos dentro de limites controlados.
* O LLM gera narrativa explicativa a partir de resultados ja calculados.
* O LLM nunca calcula numeros, metricas, desvios, impactos financeiros ou decisoes operacionais.
* Ferramentas deterministicas Python/pandas fazem todos os calculos.
* O harness controla ferramentas, estado, guardrails, auditoria, retries e limites.
* O usuario humano decide antes de qualquer acao operacional.

---

## 2. Arquivos de controle

Estes arquivos sao a fonte de verdade do desenvolvimento.

| Arquivo                             | Papel                           | Quando atualizar                                                             |
| ----------------------------------- | ------------------------------- | ---------------------------------------------------------------------------- |
| `docs/architecture.md`              | Spec da arquitetura             | ANTES de mudar arquitetura, fluxo, contratos, guardrails ou tipos de decisao |
| `docs/planning.md`                  | Checklist de implementacao      | Ao iniciar, concluir, dividir ou cancelar itens                              |
| `docs/agent.log.md`                 | Historico de decisoes e sessoes | Ao final de toda sessao significativa                                        |
| `docs/sense_to_respond_modelagem.tex` | Modelagem matematica formal   | SEMPRE que o comportamento implementado mudar (ver secao 2.1)                |
| `rules.md`                          | Regras humanas completas        | Quando regras de desenvolvimento mudarem                                     |
| `.cursor/rules/spec-driven-dev.mdc` | Regras curtas para Cursor IDE   | Sempre que `rules.md` mudar                                                  |
| `docs/contracts/state_contract.md`  | Contrato do state blackboard    | Quando campos do state mudarem                                               |
| `docs/contracts/tool_contract.md`   | Contrato de ferramentas         | Quando tools ou permissoes mudarem                                           |
| `docs/prompts.md`                   | Contratos dos prompts LLM       | Quando prompts, schemas JSON ou fallbacks mudarem                            |
| `docs/testing.md`                   | Guia de testes                  | Quando criterios de teste mudarem                                            |
| `docs/adr/`                         | Decisoes arquiteturais formais  | Quando uma decisao arquitetural relevante for tomada                         |

### 2.1 Modelagem LaTeX sempre atualizada

O arquivo `docs/sense_to_respond_modelagem.tex` (e o PDF gerado) e a
formalizacao matematica do que o repositorio **implementa**.

Regras obrigatorias:

1. Ao concluir uma mudanca de comportamento em `*.py`, contratos, prompts
   ou thresholds, atualizar o `.tex` **na mesma sessao**.
2. Recompilar o PDF (`pdflatex docs/sense_to_respond_modelagem.tex`) apos
   editar o `.tex`.
3. Modelar apenas o implementado; o planejado vai em "Proximos Passos"
   (ou equivalente), nunca como invariante.
4. Nao marcar o item como `[x]` em `planning.md` se a modelagem estiver
   desatualizada em relacao ao codigo entregue.
5. Caracteres no `.tex`: manter convencao ASCII com escapes LaTeX
   (`\'e`, `\c{c}`, etc.) alinhada ao restante do documento.

---

## 3. Fluxo obrigatorio

Antes de alterar codigo, o agente IA deve:

1. Ler `docs/architecture.md`.
2. Ler `docs/planning.md`.
3. Ler `rules.md`.
4. Ler contratos relevantes em `docs/contracts/`, se a tarefa tocar state, tools, prompts ou auditoria.
5. Identificar se a mudanca esta prevista no planning.
6. Classificar o tipo de mudanca.
7. Verificar se a spec precisa ser atualizada antes do codigo.
8. Implementar o menor incremento seguro.
9. Rodar os testes exigidos.
10. Se o comportamento do pipeline mudou, atualizar
    `docs/sense_to_respond_modelagem.tex` e recompilar o PDF (secao 2.1).
11. Atualizar `docs/planning.md` apenas se criterios de aceite passarem.
12. Atualizar `docs/agent.log.md` ao final.
13. Se houve mudanca arquitetural, atualizar `docs/architecture.md` antes do codigo.

---

## 4. Classificacao obrigatoria da mudanca

Antes de editar qualquer arquivo, o agente IA deve classificar a solicitacao em uma das categorias abaixo.

| Categoria      | Exemplos                                                 | Atualiza `architecture.md`?            | Atualiza `planning.md`?         | Atualiza `agent.log.md`? |
| -------------- | -------------------------------------------------------- | -------------------------------------- | ------------------------------- | ------------------------ |
| `fix`          | bug local, parsing, erro de validacao                    | apenas se mudar contrato               | sim, se houver item relacionado | sim                      |
| `refactor`     | reorganizacao sem mudar comportamento                    | apenas se mudar componente ou contrato | sim                             | sim                      |
| `feature`      | nova capacidade prevista no planning                     | talvez                                 | sim                             | sim                      |
| `architecture` | novo componente, fluxo, contrato ou guardrail            | sim, antes do codigo                   | sim                             | sim                      |
| `prompt`       | mudanca em system prompt, schema JSON, retry ou fallback | sim, se alterar comportamento          | sim                             | sim                      |
| `security`     | guardrail, segredo, permissao, auditoria ou privacidade  | sim, se alterar politica               | sim                             | sim                      |
| `test`         | novos testes sem mudar comportamento                     | nao                                    | sim                             | sim                      |
| `docs`         | mudanca apenas documental                                | talvez                                 | se alterar roadmap              | sim                      |

Se a categoria for `architecture`, `prompt`, `security` ou alterar contrato de `state`, `tool`, `sinal`, `proposicao`, `guardrail` ou `auditoria`, a spec deve ser atualizada antes do codigo.

---

## 5. Definition of Ready

Um item do `docs/planning.md` so pode ser implementado se:

* esta descrito no planning com checkbox `[ ]`;
* tem objetivo claro;
* tem criterio de aceite claro;
* nao contradiz `docs/architecture.md`;
* indica entradas e saidas esperadas;
* indica quais arquivos ou componentes podem ser afetados;
* indica quais testes devem ser rodados;
* respeita os invariantes do MVP.

Se esses pontos nao existirem, o agente deve primeiro atualizar `docs/planning.md` e, se necessario, `docs/architecture.md`.

---

## 6. Definition of Done

Um item so pode ser marcado como `[x]` no `docs/planning.md` se:

* o codigo foi implementado;
* o comportamento esperado foi validado;
* os testes minimos foram executados;
* o modo `python main.py --modo nexus` continua funcionando;
* a auditoria JSON continua sendo gerada quando aplicavel;
* os guardrails continuam ativos;
* os arquivos de spec foram atualizados quando necessario;
* `docs/agent.log.md` recebeu entrada da sessao;
* limitacoes conhecidas foram documentadas.

Se a implementacao ficou parcial, nao marque `[x]`.

Use `[~]` apenas para item cancelado ou substituido, com justificativa.

---

## 7. Invariantes arquiteturais

Estes invariantes nao podem ser quebrados sem aprovacao explicita e atualizacao previa da arquitetura.

### 7.1 LLM nunca calcula numeros

O LLM pode:

* decidir proximo passo;
* classificar intencao;
* inferir schema semanticamente;
* gerar explicacao narrativa;
* auditar coerencia textual;
* apontar limitacoes.

O LLM nao pode:

* calcular impacto financeiro;
* calcular desvios percentuais;
* calcular DOI;
* calcular tendencia;
* calcular metricas de qualidade;
* calcular custo;
* alterar resultados numericos;
* inventar valores ausentes;
* gerar scripts Python que calculem metricas de negocio.

Todos os numeros devem vir de tools deterministicas.

### 7.1b LLM pode gerar ETL (ADR-0021)

O LLM pode gerar scripts de ETL para adequar a estrutura de dados:

Operacoes permitidas:

* `df.rename(columns={...})`
* `df.groupby(...).agg(...)`
* `df.merge(...)`
* `df.fillna(...)`
* `df.drop(columns=[...])`
* `df.astype(...)`
* `df.pivot_table(...)`

Operacoes proibidas em scripts gerados:

* `(actual - plan) / plan * 100` (desvio percentual)
* `inventory / daily_demand` (DOI)
* `delta * preco_unitario` (impacto financeiro)
* Qualquer formula de negocio ou KPI

Garantias obrigatorias:

* Humano revisa e aprova script antes de execucao.
* Execucao em sandbox (sem rede, disco limitado).
* Validacao estatica contra operacoes proibidas.
* Schema checker pos-execucao.
* Script salvo com hash e timestamp para auditoria.

### 7.2 MVP usa pipeline sequencial

No MVP, o fluxo e sequencial e controlado. Com dual ingress (ADR-0025):

```text
[A] DataShield Lite -> Dominion CSV
[B] Dominion PBI (catalogo DAX + MCP ExecuteQuery)   # PoC 1.7a
        -> Optimus -> Validador -> Critic -> Nexus -> PDF
```

Rotulos:

* PBI unificado = caminho [B].
* Planilha / schema cru = caminho [A] (+ Popa so no backlog pos-PoC).

Regras do caminho PBI (batch):

* So `ExecuteQuery` com DAX do catalogo versionado.
* Proibido depender de `GenerateQuery` no relatorio.
* Troca Mondelez futura = novo YAML + `PBI_ARTIFACT_ID` (backlog).
* Nao hardcodar tabelas do modelo de teste (Agua) no Nexus.
* Nao reimplementar medidas DAX em Python como fallback padrao.

Nao implementar no MVP sem atualizacao previa da spec:

* MOE router dinamico;
* consenso multi-agente;
* agentes paralelos autonomos;
* conversa livre entre agentes em linguagem natural;
* execucao automatica em ERP/WMS/TMS;
* Bridge operacional;
* itens do **Backlog pos-PoC PBI** em `planning.md` (antes da PoC 1.7a.2).

### 7.3 State blackboard

Agentes e fases compartilham informacao via state blackboard.

Proibido:

* passar conclusoes criticas apenas por conversa textual;
* apagar evidencias anteriores sem auditoria;
* alterar campos fora da responsabilidade da fase;
* mudar contrato do state sem atualizar `docs/contracts/state_contract.md`.

### 7.4 Human-in-the-loop

Toda proposicao operacional precisa de revisao humana no MVP.

O sistema pode recomendar, priorizar e explicar.

O sistema nao pode executar acao operacional diretamente.

### 7.5 Critic read-only

O Critic:

* audita proposicoes contra sinais;
* retorna aprovado, confianca e problemas;
* nao cria proposicoes;
* nao altera sinais;
* nao altera impactos;
* nao decide acao operacional.

---

## 8. Regras de codigo Python

### 8.1 Tipagem

* Toda funcao publica deve ter type hints em parametros e retorno.
* Evitar `Any` em novas APIs publicas.
* Criar `TypedDict`, `dataclass` ou tipos especificos quando necessario.
* Nao enfraquecer tipos existentes sem justificativa.

### 8.2 Strings

* Usar aspas duplas para strings.
* Preferir `.join()` ou f-strings a concatenacoes longas.
* Evitar strings magicas duplicadas.

### 8.3 Caracteres

* Codigo-fonte, comentarios, docstrings e logs devem usar ASCII.
* Documentos `.md` podem usar portugues, mas prefira ASCII em blocos que serao copiados para codigo, prompts ou logs.

### 8.4 Documentacao

* Toda funcao publica deve ter docstring.
* Comentarios devem explicar logica nao-obvia.
* Nao adicionar comentarios que apenas repetem o codigo.

### 8.5 Erros

* Nao usar `except:` sem tipo.
* Nao silenciar excecoes.
* Toda entrada externa deve ser validada.
* Erros esperados devem retornar estrutura clara ou excecao especifica.
* Fallbacks devem ser auditados.

---

## 9. Regras de tools

Tools sao deterministicas.

Tools calculam; LLM nao calcula.

Toda tool deve ter:

* nome unico;
* fase autorizada;
* descricao;
* entradas requeridas;
* saidas produzidas;
* indicacao se pode repetir;
* nivel de risco;
* teste minimo.

Proibido em tools deterministicas:

* chamada LLM;
* mutacao silenciosa do state;
* calculo dentro de prompt;
* retorno sem validacao;
* leitura de segredo sem necessidade;
* gravacao de dados reais em logs.

Toda execucao de tool deve ser auditavel com:

* inicio;
* fim;
* duracao;
* resumo de entrada;
* resumo de saida;
* erro estruturado, se falhar.

---

## 10. Regras de prompts LLM

Prompts sao parte da arquitetura.

Ao alterar prompt, o agente deve:

* documentar a mudanca em `docs/prompts.md`;
* validar schema de saida quando aplicavel;
* manter retry limitado;
* manter fallback seguro;
* impedir calculo numerico pelo LLM;
* atualizar testes de JSON valido e invalido;
* registrar a mudanca em `docs/agent.log.md`.

Prompts nao podem pedir ao LLM para calcular:

* impacto financeiro;
* DOI;
* desvios;
* metricas;
* custo;
* tendencia;
* valores de decisao.

Saidas JSON devem ter:

* schema documentado;
* chaves obrigatorias;
* validacao de tipos;
* validacao de faixa para campos numericos;
* retry quando JSON invalido;
* fallback seguro quando retries falharem.

---

## 11. Regras de DataShield Lite

DataShield Lite pode usar LLM para:

* inferencia semantica de schema (mapeamento de colunas);
* geracao de scripts ETL (apenas operacoes estruturais, ADR-0021);
* diagnostico de incompatibilidade de dados.

DataShield Lite nao pode:

* alterar valores numericos;
* imputar dados sem tool deterministica;
* prosseguir sem schema confirmado ou confidence gate aprovado;
* enviar dataset completo ao LLM;
* registrar dados sensiveis em logs;
* inferir decisoes operacionais;
* gerar scripts que calculem metricas de negocio.

DataShield Lite deve:

* ler `csv` e `xlsx` com tools deterministicas;
* gerar perfil de colunas com pandas;
* enviar ao LLM apenas amostra limitada e perfil das colunas;
* retornar mapa semantico em JSON validado;
* exigir confirmacao humana quando configurado;
* normalizar dataset para schema canonico;
* registrar handoff DataShield -> Dominion;
* registrar eventos em auditoria.

### 11.1 Niveis de adaptacao (ADR-0020)

DataShield opera em 3 niveis progressivos:

* **Nivel 1**: mapeamento puro (LLM retorna JSON, humano confirma, nenhum codigo gerado).
* **Nivel 2**: ETL gerado (LLM gera script Python, humano revisa, sandbox executa).
* **Nivel 3**: diagnostico de incompatibilidade (LLM identifica gaps, humano decide).

O nivel e determinado pela confianca do mapeamento e cobertura de campos obrigatorios.

---

## 12. Regras de guardrails

Guardrails existem em tres camadas.

### 12.1 Input guardrail

Deve executar antes de qualquer chamada LLM.

Verifica:

* tamanho minimo;
* tamanho maximo;
* padroes de prompt injection;
* entradas vazias ou invalidas.

### 12.2 Harness guardrail

Durante a execucao:

* tools em whitelist;
* maximo de iteracoes;
* proibicao de repetir tool quando `repeatable=False`;
* validacao de JSON;
* retry limitado;
* fallback seguro;
* auditoria de decisoes.

### 12.3 Output guardrail

Antes da resposta final:

* disclaimer obrigatorio;
* evidencias/citacoes deterministicamente geradas;
* flag de revisao obrigatoria quando necessario;
* linguagem sem execucao automatica;
* sem remover human-in-the-loop.

---

## 13. Regras de auditoria

A auditoria deve registrar eventos relevantes com timestamp.

Eventos esperados:

* sessao_inicio;
* input_guardrail;
* llm_decisao;
* tool_inicio;
* tool_fim;
* handoff;
* validacao_deterministica;
* critic_auditoria;
* fila_nexus;
* resumo_executivo;
* visualizacao_png (path do PNG do top N em output/);
* output_guardrail;
* relatorio_pdf (HTML/PDF do analista em output/);
* user_decision, quando houver UI;
* sessao_fim.

Artefatos em `output/` (PNG, HTML, PDF) sao permitidos como apresentacao
do `resumo_executivo` e da explicacao pos-guardrail. Nao substituem
disclaimer, evidencias nem HITL (ADR-0014). Plotagem e montagem do
relatorio sao deterministicas quanto a numeros/ranking; o LLM so
fornece narrativa ja gerada, sem recalcular impactos.

Auditoria nao deve conter:

* chaves de API;
* dados reais sensiveis;
* dumps completos de dataset;
* informacoes pessoais desnecessarias.

Quando dados sensiveis forem inevitaveis, registrar apenas resumo, hash ou identificador controlado.

---

## 14. Regras de seguranca

O agente IA nunca deve:

* criar chave real de API;
* expor `OPENAI_API_KEY`;
* commitar `.env`;
* salvar dados reais de cliente em `docs/`, `tests/` ou `auditoria/`;
* remover disclaimer obrigatorio;
* remover revisao humana;
* habilitar Bridge sem spec e aprovacao;
* adicionar envio automatico de email;
* adicionar execucao operacional automatica;
* logar dados sensiveis sem necessidade.

Arquivos de exemplo devem usar dados ficticios.

---

## 15. Regras para implementacao parcial

Se uma implementacao ficar parcial, o agente deve:

* nao marcar item como `[x]`;
* registrar no `docs/agent.log.md` o que foi feito e o que falta;
* adicionar subitens `[ ]` em `docs/planning.md`;
* garantir que o pipeline existente continue funcionando;
* nao deixar imports quebrados;
* nao deixar codigo morto sem justificativa;
* nao deixar testes falhando sem registrar.

---

## 16. Git: analise pelo agente, commit/push pelo humano

Os agentes **podem e devem** analisar o que poderia ou deveria ir ao
repositorio Git, para informar o usuario. A **execucao** de `git commit`
e `git push` e sempre do humano no terminal.

### 16.1 O que o agente deve fazer

1. Inspecionar mudancas (`git status`, `git diff`, `git log` recente).
2. Explicar o que foi alterado e o impacto.
3. Avaliar o que incluir ou excluir do commit.
4. Sugerir mensagem de commit organizada, no estilo do repo
   (`feat:` / `fix:` / `docs:`), contando a historia das modificacoes.
5. Entregar comandos prontos (`git add` seletivo, `git commit` com
   HEREDOC, `git push`) para o usuario colar e executar.

### 16.2 O que o agente nao deve fazer

* Executar `git commit`, `git push`, `git commit --amend` ou force push.
* Sugerir `git add -A` / `git add .` sem listar arquivos explicitamente.
* Incluir na sugestao de stage: `.env`, chaves/API, `.cursor/mcp.json`
  com credenciais, `auditoria/*.json` de sessao, `output/*` (png/pdf/html),
  lixo LaTeX (`.aux` `.log` `.toc` `.out`), dados de cliente ou PII.

Em duvida sobre um arquivo: perguntar ao usuario antes de sugerir o stage.

### 16.3 Formato da entrega ao usuario

1. Resumo das mudancas + recomendacao.
2. Texto da mensagem de commit sugerida.
3. Bloco de comandos copiaveis.
4. Lembrete de que o usuario executa no terminal.

Regra Cursor: `.cursor/rules/git-human-commit.mdc`.

---

## 16b. Limite de escopo por sessao

O agente IA deve evitar alterar mais de 5 arquivos de codigo em uma unica iteracao sem autorizacao explicita.

Antes de alterar muitos arquivos, deve apresentar:

* objetivo;
* arquivos afetados;
* motivo;
* riscos;
* testes que serao rodados.

Mudancas grandes devem ser quebradas em passos pequenos.

---

## 17. Stop and ask

O agente deve parar e pedir confirmacao antes de:

* mudar contrato do state;
* mudar contrato de tool;
* mudar contrato de prompt;
* adicionar novo tipo de decisao;
* alterar guardrails;
* remover human-in-the-loop;
* habilitar execucao operacional;
* implementar MOE router;
* implementar consenso multi-agente;
* tocar mais de 5 arquivos de codigo;
* alterar comportamento fora do planning;
* gerar ou executar script ETL em producao;
* alterar protocolo HITL ou implementacoes de InterfaceHITL.

---

## 18. Testes minimos

Antes de considerar uma tarefa concluida:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Se alterou modo legado:

```bash
python main.py --modo legado
```

Se alterou tool:

* testar entrada valida;
* testar entrada invalida;
* testar output;
* testar auditoria.

Se alterou prompt:

* testar JSON valido;
* testar JSON invalido;
* testar retry;
* testar fallback.

Se alterou guardrail:

* testar caso permitido;
* testar caso bloqueado.

Se alterou Dual Ingress / PBI MCP (ADR-0025):
* atualizar `docs/contracts/powerbi_catalog_contract.md` se o YAML mudar;
* nao marcar backlog pos-PoC como feito na PoC 1.7a.2;
* nao commitar tokens/auth de `.cursor/mcp.json`;
* fixtures JSON para CI sem OAuth.

Se alterou DataShield:

* testar arquivo valido;
* testar arquivo invalido;
* testar schema ambiguo;
* testar bloqueio sem confirmacao.

---

## 19. Commits

Commits devem incluir spec, codigo e testes relacionados.

Formato da mensagem:

```text
tipo: descricao curta
```

Tipos permitidos:

* `feat`
* `fix`
* `refactor`
* `docs`
* `test`
* `chore`

Exemplos:

```text
feat: adiciona datashield lite com inferencia semantica
fix: valida booleano do critic de forma estrita
docs: atualiza contrato de tools
test: adiciona testes de guardrails
```

---

## 20. Branches

Quando aplicavel:

* `main`: codigo estavel e testado;
* `feat/xxx`: novas features;
* `fix/xxx`: correcoes;
* `docs/xxx`: documentacao;
* `test/xxx`: testes.

---

## 21. Atualizacao dos arquivos de controle

### `docs/architecture.md`

Atualizar antes de:

* novo componente;
* novo fluxo;
* novo contrato;
* novo guardrail;
* novo tipo de decisao;
* nova responsabilidade de agente;
* mudanca em DataShield, Dominion, Optimus, Critic, Nexus ou Bridge.

### `docs/planning.md`

Atualizar quando:

* item for concluido;
* item for dividido;
* novo item for identificado;
* item for cancelado;
* criterio de aceite mudar.

### `docs/agent.log.md`

Atualizar ao final de toda sessao significativa.

Deve incluir:

* contexto;
* decisoes tomadas;
* arquivos alterados;
* testes realizados;
* proximos passos;
* limitacoes ou pendencias.

### `.cursor/rules/spec-driven-dev.mdc`

Atualizar sempre que `rules.md` mudar.

Manter curto, imperativo e abaixo de 50 linhas sempre que possivel.

---

## 22. Regras de HITL (ADR-0022, ADR-0023)

### 22.1 Protocolo abstrato

O HITL usa a classe abstrata `InterfaceHITL` com implementacoes plugaveis:

* `HITLTerminal`: desenvolvimento (input no terminal)
* `HITLArquivo`: async (polling de JSON em approvals/)
* `HITLStreamlit`: demo EY (interface web)
* `HITLAutoApprove`: testes automatizados (aprova tudo)

Nexus recebe `hitl` como dependencia injetada. Nao ha acoplamento direto a UI.

### 22.2 Arquivo JSON de aprovacao

Cada decisao HITL e salva em `approvals/{tipo}_{timestamp}.json` com:

* `id`, `tipo`, `timestamp`, `status`
* `dados` (detalhes do pedido)
* `decisao` (aprovado/rejeitado/editado/postergado)
* `comentario`, `decidido_por`, `decidido_em`

### 22.3 Regras de seguranca HITL

* Nao incluir dados sensiveis nos JSONs de aprovacao.
* Nao permitir aprovacao automatica em producao (apenas em testes).
* Registrar toda decisao HITL na auditoria.
* Decisoes HITL sao append-only (nao apagar historico).

## 23. Regras de interface Streamlit

* Streamlit e apenas para demo e operacao local.
* Pipeline e UI sao processos separados, comunicam via JSON.
* Streamlit nao deve conter logica de negocio.
* Streamlit nao deve calcular metricas.
* Streamlit exibe dados que ja estao no state.
* Cores e estilo devem seguir identidade visual EY quando aplicavel.
* Nao expor dados sensiveis na interface.

## 24. Regra final

Se houver conflito entre uma sugestao do LLM e a spec, a spec vence.

Se a spec estiver incompleta, o agente deve propor atualizacao da spec antes de implementar.

Se houver risco de quebrar seguranca, auditoria, governanca ou human-in-the-loop, o agente deve parar e pedir confirmacao.
