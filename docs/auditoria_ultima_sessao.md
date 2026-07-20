# Auditoria: interpretacao de `ultima_sessao.json`

Documento de referencia para ler o diario da pipeline Sense-to-Respond persistido em `auditoria/ultima_sessao.json` (ou no caminho passado via `--audit-out`).

Implementacao: `audit.py` (`AuditTrail` / `EventoAuditoria`).
Politica de minimizacao de dados: [ADR-0012](adr/0012-auditoria-sem-dados-sensiveis.md).

---

## 1. O que e este arquivo

E um **diario estruturado de uma unica execucao** do harness/Nexus:

- raiz com `sessao_id` + lista `eventos`;
- cada evento e um marco da pipeline com envelope comum;
- a ordem de `eventos` e **cronologica** (inicio -> fim);
- nao substitui o state blackboard em memoria; e o artefato persistido para auditoria pos-run.

Geracao tipica:

```bash
python main.py --modo nexus --input data/mondelez_s2r_base_diaria.csv \
  --audit-out auditoria/ultima_sessao.json
```

`sessao_id` tem formato `YYYYMMDD-HHMMSS-<8 hex>` (UTC + sufixo aleatorio).

---

## 2. Envelope comum (todo evento)

| Chave | Tipo | Significado |
|-------|------|-------------|
| `tipo` | string | Nome do marco (origem semantica do registro) |
| `dados` | object | Payload especifico daquele marco |
| `iteracao` | int \| null | Numero de retry/loop HITL ou loop legado; muitas vezes `null` no modo Nexus |
| `timestamp` | string ISO-8601 | Momento UTC do registro |

Regra de leitura: **use `tipo` para decidir o schema de `dados`**. Nao misture chaves de tipos diferentes.

---

## 3. Raiz do JSON

| Chave | Significado |
|-------|-------------|
| `sessao_id` | ID unico da execucao |
| `eventos` | Sequencia cronologica dos marcos |

---

## 4. Tipos de evento (modo Nexus / MVP)

Ordem tipica numa sessao bem-sucedida com CSV de entrada:

```text
datashield_perfil
hitl_decisao
handoff (datashield -> dominion)
dominion_mondelez
handoff (varios)
validacao_deterministica
handoff
critic_auditoria
handoff
fila_nexus
resumo_executivo
visualizacao_png
llm_explicacao
output_guardrail
relatorio_pdf
sessao_fim
```

`handoff` se repete; os demais tipos em geral aparecem uma vez (exceto retries).

### 4.1 `datashield_perfil`

Perfil semantico do arquivo de entrada (DataShield).

| Chave em `dados` | Significado |
|------------------|-------------|
| `arquivo` | Caminho do dataset lido |
| `linhas` / `colunas` | Dimensao do arquivo |
| `confianca` | Confianca do mapeamento semantico (0–1) |
| `mapeadas` / `nao_mapeadas` | Colunas reconhecidas vs nao reconhecidas |
| `warnings` | Avisos do perfilador |
| `origem` | Como o perfil foi obtido (ex.: `deterministico`) |
| `gate_ok` | Se o gate de qualidade do mapeamento passou |

Nao contem o dataset completo (ADR-0012).

### 4.2 `hitl_decisao`

Decisao humana (HITL) em um ponto de aprovacao.

| Chave em `dados` | Significado |
|------------------|-------------|
| `tipo` | Tipo de decisao (ex.: `mapeamento_semantico`) |
| `decisao` | Resultado (`aprovado`, `rejeitado`, etc.) |
| `comentario` | Texto opcional do operador |
| `decidido_por` | Quem decidiu (ex.: `terminal_user`, auto-approve) |

### 4.3 `handoff`

Passagem de estado entre etapas/agentes. Pode ocorrer varias vezes.

| Chave em `dados` | Significado |
|------------------|-------------|
| `origem` | Etapa que envia |
| `destino` | Etapa que recebe |
| `payload_chaves` | **Nomes** dos objetos transferidos — nao o conteudo integral |

Fluxo tipico nesta sessao de exemplo:

```text
datashield -> dominion
datashield -> dominion_mondelez
dominion -> state
dominion -> optimus
optimus -> validador
validador -> critic
```

Para reconstruir o pipeline, leia a sequencia de `handoff` e ignore o tamanho do JSON.

### 4.4 `dominion_mondelez`

Resultado resumido da analise deterministica S&OE (Dominion).

| Chave em `dados` | Significado |
|------------------|-------------|
| `capacidades` | Analises executadas (ex.: `sellout`, `sellin`, `doi`) |
| `chaves_resultados` | Blocos gerados (`analise_*`, `resumo_categorias`, etc.) |
| `total_desvios` | Contagem agregada de desvios detectados |

Os DataFrames/resultados completos ficam no state; a auditoria guarda o **indice** do que foi produzido.

### 4.5 `validacao_deterministica`

Validacao de schema/regras das proposicoes (antes do Critic).

| Chave em `dados` | Significado |
|------------------|-------------|
| `tentativa` | Numero da tentativa de validacao |
| `ok` | Se passou sem erros |
| `erros` | Lista de falhas (vazia se OK) |

### 4.6 `critic_auditoria`

Auditoria LLM das proposicoes (Critic, leitura-only).

| Chave em `dados` | Significado |
|------------------|-------------|
| `aprovado` | Se o Critic aceitou o lote |
| `confianca` | Score de confianca do Critic |
| `problemas` | Issues apontados |
| `modelo` | Modelo LLM usado no Critic |

### 4.7 `fila_nexus`

Fila HITL de proposicoes para revisao humana.

| Chave em `dados` | Significado |
|------------------|-------------|
| `total` | Quantidade de proposicoes enfileiradas |
| `revisao_obrigatoria` | Quantas exigem revisao obrigatoria |
| `itens` | Lista de itens da fila |

Cada item em `itens[]` tipicamente inclui:

| Campo | Significado |
|-------|-------------|
| `proposicao` | Objeto da proposicao Optimus |
| `prioridade` | Prioridade na fila |
| `revisao_obrigatoria` | Flag de revisao obrigatoria |
| `motivo_revisao` | Motivo textual quando aplicavel |

Este bloco pode ser grande (centenas de itens). Para ranking executivo, prefira `resumo_executivo`.

### 4.8 `resumo_executivo`

Ranking **deterministico** estratificado (fonte oficial do top N).

| Chave em `dados` | Significado |
|------------------|-------------|
| `top_doi` | Top N por impacto DOI / estoque |
| `top_forward` | Top N por risco/gap de plano forward |
| `top_oportunidades` | Top N de captura de oportunidade |
| `n_doi` / `n_forward` / `n_oportunidades` | Tamanho pedido de cada top |
| `total_candidatos_doi` | Universo de candidatos DOI antes do corte |
| `total_candidatos_forward` | Universo de candidatos forward |
| `total_candidatos_oportunidade` | Universo de candidatos oportunidade |
| `diversidade_doi` | Cotas ruptura/overstock no estrato DOI |
| `diversidade_forward` | Cotas ruptura/overstock no estrato forward |

`diversidade_*` tipicamente contem:

| Campo | Significado |
|-------|-------------|
| `n_ruptura` / `n_overstock` | Quantos entraram no top por polaridade |
| `candidatos_ruptura` / `candidatos_overstock` | Quantos candidatos existiam por polaridade |

Cada item dos tops tipicamente traz:

| Campo | Significado |
|-------|-------------|
| `proposicao_id` | ID (ex.: `P2`) |
| `tipo` | Tipo de acao (ex.: `rebalancear_estoque_doi`) |
| `titulo` | Titulo legivel |
| `skus` | SKUs afetados |
| `impacto_financeiro` | Impacto em NR (valor bruto) |
| `impacto_priorizado` | Impacto apos pesos/prioridade do Optimus |
| `urgencia_horas` | Urgencia em horas |
| `descricao` | Justificativa operacional |
| `polaridade` | `ruptura` ou `overstock` (quando aplicavel) |

**Regra critica:** a ordem oficial do ranking e esta. O LLM nao redefine a ordem.

### 4.9 `llm_explicacao`

Explicacao narrativa gerada pelo LLM sobre o contexto agregado.

| Chave em `dados` | Significado |
|------------------|-------------|
| `modelo` | Modelo usado (ex.: `gpt-4.1-mini`) |
| `pergunta` | Prompt/pergunta enviada ao agente |
| `tamanho_contexto` | Tamanho do contexto em caracteres |
| `tamanho_resposta` | Tamanho da resposta em caracteres |
| `contexto_resultados` | Texto agregado enviado ao LLM (resumos, alertas, tendencia, top proposicoes) |
| `resposta_completa` | Texto interpretativo devolvido pelo LLM |

O LLM **explica** o contexto (incluindo o texto do resumo executivo). Nao e a fonte de verdade do ranking.

### 4.10 `visualizacao_png`

Export grafico deterministico do resumo executivo (top N).

| Chave em `dados` | Significado |
|------------------|-------------|
| `caminho` | Path do PNG gerado em `output/` |
| `sessao_id` | ID da sessao |
| `n_doi` / `n_forward` / `n_oportunidades` | Itens plotados por bloco |
| `ok` | Se a geracao concluiu com sucesso |
| `erro` | Mensagem segura se falhou (sem stack/dump) |

Nao contem dataset nem lista completa de proposicoes — so metadados do arquivo.

### 4.11 `output_guardrail`

Guardrail de saida (disclaimer / limiar de confianca).

| Chave em `dados` | Significado |
|------------------|-------------|
| `disclaimer_aplicado` | Se o disclaimer foi anexado a saida |
| `confianca_critic` | Confianca do Critic usada no gate |
| `limiar` | Limiar minimo configurado |

### 4.12 `relatorio_pdf`

Relatorio analista HTML->PDF (WeasyPrint).

| Chave em `dados` | Significado |
|------------------|-------------|
| `ok` | Se o PDF foi gerado |
| `html_ok` | Se o HTML intermediario foi gravado |
| `caminho` / `caminho_pdf` | Path do PDF |
| `caminho_html` | Path do HTML |
| `sessao_id` | ID da sessao |
| `erro` | Mensagem segura se PDF/HTML falhou |

### 4.13 `sessao_fim`

Encerramento da sessao.

| Chave em `dados` | Significado |
|------------------|-------------|
| `sucesso` | Se a pipeline terminou com sucesso |
| `fase` | Fase do produto (ex.: `nexus_mvp`) |
| `total_eventos` | Contagem de eventos ate o registro (pode excluir o proprio `sessao_fim`) |
| `handoffs` | Quantidade de handoffs na sessao |

---

## 5. Tipos adicionais (podem aparecer em outras sessoes)

Nem toda sessao gera todos os tipos abaixo. Eles existem no codigo e devem ser interpretados quando presentes.

### 5.1 Modo Nexus (falhas / retries)

| `tipo` | Quando | Chaves relevantes em `dados` |
|--------|--------|------------------------------|
| `datashield_erro` | Falha ao ler/perfilar arquivo | `arquivo`, `erro` |
| `datashield_gate` | Gate semantico falhou | `gate_ok`, detalhes do bloqueio |
| `optimus_retry` | Retry apos validador ou Critic | `motivo` (`validador` \| `critic`), contexto do retry |

### 5.2 Modo legado (`--modo legado` / harness)

| `tipo` | Significado resumido |
|--------|----------------------|
| `sessao_inicio` | Abertura da sessao legado |
| `estado_snapshot` | Snapshot resumido do state em uma iteracao |
| `tool_inicio` / `tool_fim` | Inicio/fim de execucao de tool |
| `llm_decisao` | Decisao de acao pedida pelo LLM no loop |
| `harness_fim_loop` | LLM pediu fim do loop |
| `harness_bloqueio` | Acao bloqueada pelo harness |
| `harness_correcao` | Acao corrigida pelo harness |
| `loop_limite` | Atingiu `max_iteracoes` |
| `loop_fim` | Encerramento do loop de tools |

---

## 6. Regras de interpretacao (evitar erros comuns)

1. **Ranking oficial vs narrativa**
   - Oficial: `resumo_executivo` (deterministico, estratificado, com diversidade).
   - Narrativa: `llm_explicacao.resposta_completa` (pode parafrasear; nao e ranking).

2. **Handoff nao carrega payload**
   - `payload_chaves` lista nomes (`sinais`, `proposicoes`, etc.), nao os objetos.

3. **Fila != top executivo**
   - `fila_nexus` tem todas as proposicoes elegiveis a revisao.
   - `resumo_executivo` e o recorte priorizado para decisao.

4. **Critic vs Validador**
   - `validacao_deterministica`: regras/schema sem LLM.
   - `critic_auditoria`: revisao LLM read-only.

5. **Tamanho do arquivo**
   - O JSON pode ficar grande por `fila_nexus.itens` e por `llm_explicacao.contexto_resultados`.
   - Para inspecao humana, filtre por `tipo` antes de abrir o payload inteiro.

6. **Privacidade (ADR-0012)**
   - A auditoria nao deve conter dataset completo, chaves de API, `.env` ou PII.
   - Se um campo parecer dump sensivel, trate como incidente de conformidade, nao como feature.

7. **`iteracao`**
   - No Nexus costuma ser `null`.
   - No legado indica a volta do loop perceive/act.

8. **`total_eventos` em `sessao_fim`**
   - Pode ser `len(eventos) - 1` se o fim for registrado depois da contagem; use `len(eventos)` no arquivo salvo para contagem absoluta.

---

## 7. Como ler uma sessao em uma frase

Exemplo (sessao bem-sucedida com CSV Mondelez):

> DataShield mapeou o CSV → HITL aprovou → Dominion gerou analises → Optimus/Validador/Critic passaram → proposicoes na fila → resumo estratificado deterministico → LLM narrou o contexto → guardrail + fim com sucesso.

Checklist rapido de saude:

| Pergunta | Onde olhar |
|----------|------------|
| O mapeamento passou? | `datashield_perfil.gate_ok` + `hitl_decisao` |
| Quantos desvios? | `dominion_mondelez.total_desvios` |
| Validacao OK? | `validacao_deterministica.ok` |
| Critic OK? | `critic_auditoria.aprovado` / `confianca` |
| O que priorizar? | `resumo_executivo.top_*` |
| PNG do top N? | `visualizacao_png.caminho` / `artefatos_visuais` |
| Relatorio PDF? | `relatorio_pdf.caminho` / `artefatos_visuais` |
| O que o LLM disse? | `llm_explicacao.resposta_completa` |
| Sessao fechou bem? | `sessao_fim.sucesso` |

---

## 8. Referencias

| Artefato | Papel |
|----------|-------|
| `audit.py` | Serializacao e persistencia |
| `nexus.py` | Registro dos eventos do MVP |
| `agent.py` | `llm_explicacao` / `llm_decisao` |
| `critic.py` | `critic_auditoria` |
| `main.py --audit-out` | Caminho de saida |
| [ADR-0012](adr/0012-auditoria-sem-dados-sensiveis.md) | O que pode/nao pode ir na auditoria |
| [architecture.md](architecture.md) | Papel da auditoria no pipeline |
| [testing.md](testing.md) | Expectativas de auditoria em testes |
