# State Contract - Sense to Respond

> Contrato oficial do state compartilhado.
> Este documento define o blackboard usado entre DataShield, Dominion, Optimus, Validador, Critic e Nexus.
> Qualquer mudanca neste contrato exige atualizar `docs/architecture.md`, `docs/planning.md` e `docs/agent.log.md`.

---

## 1. Principio central

O projeto usa o padrao **state blackboard**.

Isso significa que os componentes nao conversam livremente entre si em linguagem natural no MVP.

Eles compartilham informacao por meio de um objeto de estado comum, chamado neste documento de `state`.

```text
DataShield -> state -> Dominion -> state -> Optimus -> state -> Validador -> state -> Critic -> state -> Nexus
```

O state e a fonte de verdade da execucao corrente.

---

## 2. Invariantes do state

Estas regras nao podem ser quebradas sem mudanca previa de arquitetura.

1. O campo `pergunta` nao deve ser alterado depois de criado.
2. Dados brutos ou canonicos so podem ser escritos por DataShield ou Dominion.
3. Resultados numericos so podem ser escritos por tools deterministicas.
4. Sinais devem ser derivados de resultados deterministicos.
5. Proposicoes devem ser derivadas de sinais.
6. O Validador nao cria proposicoes.
7. O Critic nao cria proposicoes.
8. O Critic nao altera sinais, impactos ou resultados.
9. Nexus monta a fila final, mas nao altera evidencias numericas.
10. Handoffs devem ser append-only.
11. Auditoria deve registrar mudancas relevantes de fase.
12. Nenhum componente deve apagar evidencias anteriores sem registrar evento de auditoria.

---

## 3. Campos principais do state

| Campo              | Tipo esperado         | Escrito por         | Lido por               | Pode sobrescrever?                         |                    |                 |
| ------------------ | --------------------- | ------------------- | ---------------------- | ------------------------------------------ | ------------------ | --------------- |
| `pergunta`         | `str`                 | Nexus               | Todos                  | Nao                                        |                    |                 |
| `dados`            | `DadosState`          | DataShield/Dominion | Dominion/Sinais        | Sim, apenas por fase autorizada            |                    |                 |
| `resultados`       | `ResultadosState`     | Dominion/tools      | Sinais/Relator         | Sim, por merge controlado                  |                    |                 |
| `sinais`           | `list[Sinal]`         | Sinais/Dominion     | Optimus/Critic/Nexus   | Nao, apenas append ou regeneracao auditada |                    |                 |
| `proposicoes`      | `list[Proposicao]`    | Optimus             | Validador/Critic/Nexus | Sim, apenas em retry Optimus               |                    |                 |
| `validacao`        | `ResultadoValidacao   | None`               | Validador              | Nexus                                      | Sim, por tentativa |                 |
| `critica`          | `ResultadoCritica     | None`               | Critic                 | Nexus                                      | Sim, por tentativa |                 |
| `fila_nexus`       | `list[ItemFilaNexus]` | Nexus/Guardrails    | UI/main                | Sim, ao final da execucao                  |                    |                 |
| `resumo_executivo` | `dict`                | Nexus/Optimus       | UI/main/LLM contexto   | Sim, ao final apos fila                    |                    |                 |
| `acoes_executadas` | `list[str]`           | Harness             | Harness/Auditoria      | Append-only                                |                    |                 |
| `handoffs`         | `list[Handoff]`       | Nexus               | Auditoria              | Append-only                                |                    |                 |
| `auditoria`        | `AuditTrail           | dict                | None`                  | Audit/Harness/Nexus                        | main.py/UI         | Sim, por sessao |

---

## 4. Campos para DataShield Lite (ADR-0019, ADR-0020)

| Campo | Tipo esperado | Escrito por | Lido por | Observacao |
| --- | --- | --- | --- | --- |
| `datashield` | `DataShieldResult` ou `None` | DataShield | Nexus/Dominion | Resultado consolidado da etapa |
| `schema_confirmado` | `bool` | DataShield/HITL | Nexus/Dominion | Dominion nao deve rodar com arquivo real se `False` |
| `dataset_canonico` | `pd.DataFrame` ou `None` | DataShield | Dominion | Dataset normalizado |
| `dataset_csv` | `pd.DataFrame` ou `None` | DataShield | DataShield/Dominion | Dataset bruto carregado do CSV |
| `mapa_semantico` | `SemanticMap` ou `None` | DataShield | Dominion/Nexus | Mapeamento de colunas |
| `perfil_dados` | `DataProfile` ou `None` | DataShield | Nexus | Perfil estatistico das colunas |
| `templates_mapeamento` | `list[str]` | DataShield | DataShield/Nexus | Caminhos ou ids de templates reutilizaveis |
| `nivel_adaptacao` | `int` (1, 2 ou 3) | DataShield | Nexus/Auditoria | Nivel de adaptacao usado (ADR-0020) |
| `capacidades` | `list[str]` | Dominion | Dominion/Nexus | Analises possiveis com os dados disponiveis |
| `script_etl_gerado` | `str` ou `None` | DataShield | HITL/Nexus | Script ETL gerado pelo LLM (Nivel 2) |
| `script_etl_aprovado` | `bool` | HITL | DataShield/Nexus | Se o humano aprovou o script ETL |
| `diagnostico_incompatibilidade` | `dict` ou `None` | DataShield | HITL/Nexus | Diagnostico de gaps (Nivel 3) |

## 4b. Campos para HITL (ADR-0022, ADR-0023)

| Campo | Tipo esperado | Escrito por | Lido por | Observacao |
| --- | --- | --- | --- | --- |
| `hitl_pendentes` | `list[PedidoAprovacao]` | Nexus/DataShield | HITL/UI | Pedidos de aprovacao pendentes |
| `hitl_resolvidos` | `list[PedidoAprovacao]` | HITL/UI | Nexus/Auditoria | Decisoes humanas com timestamp e autor |

---

## 5. Tipos conceituais

### 5.1 `DadosState`

Representa dados carregados ou normalizados.

No MVP inicial pode conter:

```text
baseline
modelado
dre
```

Com DataShield Lite deve poder conter:

```text
arquivo_origem
dataset_bruto
dataset_canonico
schema_confirmado
mapa_semantico
```

Regra:

* Dados reais nao devem ser serializados integralmente para prompt LLM.
* Logs devem conter apenas resumo, dimensoes, nomes de colunas e estatisticas agregadas.

---

### 5.2 `ResultadosState`

Representa outputs deterministicos das tools.

Exemplos atuais:

```text
comparacao_demanda
inconsistencias_demanda
comparacao_custos
explicacao
explicacao_llm_bruta
```

Exemplos futuros:

```text
desvio_plano
desequilibrio_canal
risco_ruptura_doi
tendencia_semanal
aceleracao_canal
```

Regra:

* Resultados numericos devem vir de tools Python/pandas.
* O LLM pode explicar os resultados, mas nao recalcular valores.

---

### 5.3 `Sinal`

Um sinal e uma evidencia estruturada produzida a partir de resultados deterministicos.

Campos minimos atuais:

```text
sinal_id
tipo
sku
canal
metrica
valor
referencia
desvio_pct
severidade
```

Campos futuros recomendados:

```text
periodo
pais
regiao
canal
categoria
marca
cliente
dimensoes
tendencia
semanas_consecutivas
origem_resultado
```

Novos tipos de sinal (dados reais Mondelez - ADR-0019):

```text
desvio_sellout
desvio_sellin
doi_fora_politica
estoque_acima_cobertura
tendencia_sellout
tendencia_temporal
premissa_forward_furada
forward_oportunidade
desvio_persistente
```

Campos para portabilidade (ADR-0024):

```text
nr_impacto           -- Net Revenue real (USD) calculado pela tool
so_ritmo             -- desacelerando / acelerando / estavel
so_aceleracao_pct    -- variacao percentual do ritmo SO
meses_desvio_persistente   -- meses consecutivos com mesmo sinal de desvio
media_desvio_persistente_pct  -- media do desvio nesses meses
```

Regras:

* `sinal_id` deve ser unico dentro da sessao.
* Todo sinal deve apontar para resultado deterministico de origem.
* `desvio_pct` deve ser calculado por tool.
* `severidade` deve seguir regra documentada.
* Sinais nao devem conter texto opinativo sem base numerica.

---

### 5.4 `Proposicao`

Uma proposicao e uma recomendacao operacional candidata, ainda sujeita a revisao humana.

Campos minimos atuais:

```text
proposicao_id
tipo
titulo
descricao
impacto_financeiro
impacto_calculado
urgencia_horas
skus
evidencias
```

Novos tipos de proposicao (dados reais Mondelez - ADR-0019):

```text
ajustar_plano_sellout
ajustar_plano_sellin
rebalancear_estoque_doi
investigar_desvio_canal
questionar_premissa_plano
capturar_oportunidade
investigar_desvio_persistente
```

Regras:

* `tipo` deve pertencer a whitelist definida em `state_types.TIPOS_DECISAO_MVP`.
* Toda proposicao deve citar ao menos uma evidencia existente em `sinais`.
* `impacto_financeiro` deve ser igual ou justificadamente derivado de `impacto_calculado`.
* `impacto_calculado` deve ser calculado deterministicamente.
* Proposicao nao e acao executada.
* Proposicao precisa passar por Validador, Critic e fila Nexus.

---

### 5.5 `ResultadoValidacao`

Resultado produzido pelo Validador deterministico.

Campos:

```text
ok
erros
```

Regras:

* `ok=True` somente se todas as proposicoes forem validas.
* `erros` deve listar problemas objetivos.
* Validador nao deve chamar LLM.
* Validador nao deve criar nem corrigir proposicoes silenciosamente.

---

### 5.6 `ResultadoCritica`

Resultado produzido pelo Critic LLM em modo read-only.

Campos:

```text
aprovado
confianca
problemas
json_bruto
```

Regras:

* `aprovado` deve ser booleano real.
* `confianca` deve estar entre 0.0 e 1.0.
* `problemas` deve ser lista de strings.
* Critic nao pode criar proposicoes.
* Critic nao pode alterar impactos.
* Critic nao pode alterar sinais.
* Critic pode apenas apontar incoerencias, exageros e limitacoes.

---

### 5.7 `ItemFilaNexus`

Representa item da fila human-in-the-loop.

Campos:

```text
proposicao
prioridade
revisao_obrigatoria
motivo_revisao
```

Regras:

* A fila deve ser ordenada por impacto financeiro e urgencia.
* Itens com confianca abaixo do limiar devem exigir revisao.
* Itens com validacao deterministica falha devem exigir revisao.
* Itens de alto impacto devem exigir revisao.
* Nenhum item da fila deve ser executado automaticamente no MVP.

---

### 5.8 `Handoff`

Representa passagem auditavel entre fases.

Campos recomendados:

```text
origem
destino
payload_chaves
timestamp
```

Exemplos:

```text
DataShield -> Dominion
Dominion -> state
Dominion -> Optimus
Optimus -> Validador
Validador -> Critic
Critic -> Nexus
Nexus -> Output Guardrail
```

Regras:

* Handoffs devem ser append-only.
* Todo handoff relevante deve ser registrado tambem na auditoria.
* Handoff deve registrar chaves do payload, nao necessariamente o payload completo.

---

### 5.9 `resumo_executivo`

Dict deterministico montado apos a fila (script do analista).

Campos:

```text
top_doi                 -- list[dict] rebalancear_estoque_doi (cota ruptura/overstock)
top_forward             -- list[dict] questionar_premissa_plano (cota ruptura/overstock)
top_oportunidades       -- list[dict] capturar_oportunidade (inclui dual framing)
n_doi / n_forward / n_oportunidades
total_candidatos_*
diversidade_doi         -- cotas e contagens por polaridade
diversidade_forward
```

Cada item do top inclui: proposicao_id, tipo, titulo, skus,
impacto_financeiro, impacto_priorizado, urgencia_horas, descricao,
e polaridade (quando DOI/forward).

Regras:

* Nao substitui `fila_nexus`.
* LLM so cita; nao recalcula ranking.
* Dual framing: oportunidade com DOI critico coexiste com ruptura.

---

## 6. Responsabilidade por campo

### 6.1 Nexus

Pode escrever:

```text
pergunta
fila_nexus
resumo_executivo
handoffs
auditoria
```

Pode coordenar:

```text
datashield
dados
resultados
sinais
proposicoes
validacao
critica
```

Nao deve:

```text
calcular numeros
criar sinais manualmente sem tool
alterar impactos financeiros
executar acoes operacionais
```

---

### 6.2 DataShield

Pode escrever:

```text
datashield
dados
dataset_canonico
schema_confirmado
mapa_semantico
perfil_dados
templates_mapeamento
```

Nao deve:

```text
calcular decisoes
gerar proposicoes
alterar valores numericos
executar Dominion sem schema confirmado
```

---

### 6.3 Dominion

Pode escrever:

```text
resultados
acoes_executadas
```

Pode produzir dados para:

```text
sinais
```

Nao deve:

```text
gerar proposicoes finais
priorizar decisoes
aprovar acoes
```

---

### 6.4 Sinais

Pode escrever:

```text
sinais
```

Nao deve:

```text
inventar sinal sem resultado deterministico
alterar resultado de origem
criar proposicao
```

---

### 6.5 Optimus

Pode escrever:

```text
proposicoes
optimus_tentativas
```

Nao deve:

```text
alterar sinais
alterar resultados do Dominion
aprovar proposicoes
executar acoes
```

---

### 6.6 Validador

Pode escrever:

```text
validacao
```

Nao deve:

```text
chamar LLM
gerar proposicoes
corrigir impacto silenciosamente
apagar proposicoes
```

---

### 6.7 Critic

Pode escrever:

```text
critica
```

Nao deve:

```text
gerar proposicoes
alterar proposicoes
alterar sinais
alterar resultados
calcular numeros
```

---

### 6.8 Output Guardrail

Pode escrever:

```text
resultados.explicacao
```

Pode anexar:

```text
disclaimer
citacoes/evidencias
flag de revisao
```

Nao deve:

```text
remover evidencias
remover disclaimer
transformar proposicao em ordem de execucao
```

---

## 7. Regras para alteracao do state

Qualquer novo campo no state deve ter:

```text
nome
tipo esperado
fase que escreve
fases que leem
se pode sobrescrever
criterio de auditoria
teste minimo
```

Antes de adicionar campo novo:

1. Atualizar este documento.
2. Atualizar `docs/architecture.md`.
3. Atualizar `docs/planning.md`, se aplicavel.
4. Atualizar `state_types.py`.
5. Criar ou atualizar testes.
6. Registrar decisao em `docs/agent.log.md`.

---

## 8. Regras para serializacao

Todo objeto do state que precisar sair em JSON deve ter metodo ou funcao de serializacao.

Regras:

* Nao serializar DataFrame completo em auditoria.
* Nao serializar dataset real completo em prompt.
* Nao serializar segredos.
* Para logs, usar resumos.
* Para prompts, usar amostras limitadas e estatisticas agregadas.
* Para auditoria, registrar chaves, contagens e indicadores.

---

## 9. Regras para compatibilidade

Mudancas no state devem preservar compatibilidade com:

```text
python main.py --modo nexus
python main.py --modo legado
```

Quando uma mudanca quebrar compatibilidade, isso deve ser explicitamente aprovado, documentado em `docs/architecture.md` e registrado em `docs/agent.log.md`.

---

## 10. Testes minimos para mudancas no state

Se o contrato do state mudar, criar ou atualizar testes para:

```text
criacao do state inicial
serializacao de sinais
serializacao de proposicoes
conversao state -> objetos tipados
handoff append-only
auditoria associada
pipeline nexus end-to-end
```

Teste minimo obrigatorio:

```bash
python main.py --modo nexus
```

Se a mudanca afetar modo legado:

```bash
python main.py --modo legado
```

---

## 11. Checklist para agentes IA

Antes de alterar o state, responda internamente:

```text
1. Esta mudanca esta no planning?
2. Ela altera contrato publico?
3. Architecture.md precisa mudar?
4. Este documento precisa mudar?
5. Quais componentes leem o campo?
6. Quais componentes escrevem o campo?
7. O campo pode conter dado sensivel?
8. Como sera auditado?
9. Como sera testado?
10. O pipeline atual continua funcionando?
```

Se alguma resposta for incerta, parar e pedir confirmacao.
