# Prompt Contracts - Sense to Respond

> Contrato oficial dos prompts LLM do projeto.
> Prompts sao parte da arquitetura.
> Qualquer mudanca em prompt, schema JSON, retry ou fallback deve atualizar este documento, `docs/architecture.md`, `docs/planning.md` e `docs/agent.log.md`.

---

## 1. Principio central

O LLM pode raciocinar, escolher a proxima acao dentro de limites, inferir significado semantico e gerar narrativa.

O LLM nao pode calcular numeros.

```text id="1jk9p8"
LLM = decisao controlada + interpretacao + auditoria textual
Tools = calculos deterministicos
Harness = controle, validacao, retry, fallback e auditoria
```

---

## 2. Invariantes de prompts

Todos os prompts devem respeitar:

1. O LLM nunca calcula impacto financeiro.
2. O LLM nunca calcula desvio percentual.
3. O LLM nunca calcula DOI.
4. O LLM nunca calcula tendencia.
5. O LLM nunca inventa dados ausentes.
6. O LLM nunca cria evidencia que nao exista no state.
7. O LLM nunca executa acao operacional.
8. O LLM nunca remove human-in-the-loop.
9. O LLM nunca ignora guardrails.
10. Saidas estruturadas devem ser JSON validado.
11. Falhas de JSON devem ter retry limitado.
12. Depois dos retries, deve haver fallback seguro.
13. Mudancas de prompt devem ser testadas.
14. O LLM pode gerar scripts ETL (rename, groupby, merge) mas nao scripts de metricas (ADR-0021).
15. Scripts ETL gerados devem passar por revisao humana antes de execucao.

---

## 3. Tipos de prompts

### 3.1 Prompt de decisao

Usado quando o LLM escolhe a proxima acao dentro de uma whitelist.

Exemplo:

```text id="lpuev5"
proximo_passo Dominion
```

Caracteristicas:

* Saida em JSON.
* Acao deve estar em whitelist.
* Deve escolher uma acao por vez.
* Nao pode criar nome novo de tool.
* Nao pode chamar tool fora da fase.
* Nao pode repetir tool proibida.
* Deve justificar brevemente a escolha.

---

### 3.2 Prompt de explicacao

Usado quando o LLM transforma resultados deterministicos em texto claro.

Exemplo:

```text id="5ku1pp"
gerar_explicacao
```

Caracteristicas:

* Entrada deve conter resultados ja calculados.
* LLM pode citar numeros fornecidos.
* LLM nao pode recalcular nem corrigir numeros.
* LLM deve diferenciar evidencia, interpretacao e limitacao.
* LLM deve evitar linguagem de execucao automatica.

---

### 3.3 Prompt de auditoria

Usado quando o LLM avalia coerencia entre sinais e proposicoes.

Exemplo:

```text id="j7g1n0"
Critic
```

Caracteristicas:

* Saida em JSON.
* Critic e read-only.
* Critic nao cria proposicoes.
* Critic nao altera impacto.
* Critic nao altera sinais.
* Critic aponta problemas, exageros e limitacoes.
* Critic retorna confianca entre 0.0 e 1.0.

---

### 3.4 Prompt de inferencia semantica

Usado quando o LLM infere o significado de colunas de um arquivo.

Exemplo planejado:

```text id="6y8rxf"
DataShield Lite - inferir_mapa_semantico
```

Caracteristicas:

* Saida em JSON.
* Entrada deve ser amostra limitada e perfil de colunas.
* Nao enviar dataset completo.
* LLM infere papeis semanticos, nao calcula metricas.
* Resultado precisa passar por validacao.
* Avanco depende de confidence gate e/ou confirmacao humana.

---

### 3.5 Prompt de classificacao de intencao

Usado futuramente para rotear perguntas ou escolher fluxo.

Exemplo planejado:

```text id="85mcvw"
classificar_intencao_usuario
```

Caracteristicas:

* Saida em JSON.
* Deve escolher entre classes previamente definidas.
* Nao deve ativar MOE dinamico no MVP.
* Deve respeitar planning e architecture.

---

## 4. Contrato obrigatorio de cada prompt

Todo prompt documentado deve ter:

| Campo            | Descricao                                                           |
| ---------------- | ------------------------------------------------------------------- |
| `prompt_name`    | Nome unico                                                          |
| `prompt_version` | Versao semantica do prompt                                          |
| `arquivo`        | Arquivo onde esta implementado                                      |
| `funcao`         | Funcao ou metodo que usa o prompt                                   |
| `objetivo`       | O que o prompt deve fazer                                           |
| `tipo`           | decisao, explicacao, auditoria, inferencia semantica, classificacao |
| `entrada`        | Dados enviados ao LLM                                               |
| `saida`          | Formato esperado                                                    |
| `schema_json`    | Schema esperado quando aplicavel                                    |
| `max_retries`    | Numero maximo de retries                                            |
| `fallback`       | Comportamento seguro em caso de falha                               |
| `proibicoes`     | O que o LLM nao pode fazer                                          |
| `testes`         | Casos minimos de teste                                              |
| `riscos`         | Principais riscos do prompt                                         |

---

## 5. Prompt atual: `dominion.proximo_passo`

### 5.1 Identificacao

```text id="hstz4w"
prompt_name: dominion.proximo_passo
prompt_version: 1.0.0
arquivo: agent.py
funcao: AgenteOpenAI.proximo_passo
tipo: decisao
```

---

### 5.2 Objetivo

Escolher exatamente uma proxima acao do loop Dominion com base na pergunta do usuario e no state atual.

---

### 5.3 Entrada

O prompt recebe:

```text id="3pk0l1"
pergunta_usuario
state serializado
acoes ja executadas
se dados foram carregados
resultados deterministicos ja disponiveis
```

---

### 5.4 Saida esperada

JSON obrigatorio:

```json id="yl6f16"
{
  "acao": "carregar_dados",
  "justificativa": "Preciso carregar os dados antes das validacoes."
}
```

ou:

```json id="87cq7z"
{
  "acao": "fim",
  "justificativa": "Todas as validacoes pedidas ja foram feitas."
}
```

---

### 5.5 Schema

Campos obrigatorios:

| Campo           | Tipo  | Regra                                |
| --------------- | ----- | ------------------------------------ |
| `acao`          | `str` | Deve estar na whitelist ou ser `fim` |
| `justificativa` | `str` | Frase curta, sem numeros inventados  |

Whitelist atual (dados simulados):

```text id="m3u092"
carregar_dados
validar_demanda
validar_custos
fim
```

Whitelist planejada (dados reais Mondelez - ADR-0019):

```text
carregar_csv
analisar_sellout
analisar_sellin
analisar_doi
fim
```

Quando ToolRegistry for implementado, essa lista deve vir do registry.

---

### 5.6 Proibicoes

O LLM nao pode:

```text id="cxsd4u"
criar nome de tool
executar mais de uma tool por vez
calcular resultado
dizer que validou algo sem tool correspondente
repetir tool ja executada, salvo permissao explicita
ignorar dados vazios
```

---

### 5.7 Retry e fallback

Regras recomendadas:

```text id="up5urf"
max_retries: 2
```

Retry deve acontecer quando:

```text id="0hlgwv"
JSON invalido
chaves obrigatorias ausentes
acao fora da whitelist
tipo errado em algum campo
```

Fallback seguro:

```text id="g8pe6l"
se dados vazios -> carregar_dados
se dados carregados e acao invalida -> fim
```

Todo fallback deve ser registrado em auditoria.

---

### 5.8 Testes minimos

Testar:

```text id="l1x0nj"
JSON valido com acao permitida
JSON invalido
acao desconhecida
justificativa ausente
acao nao string
fim correto
fallback com dados vazios
fallback com dados carregados
```

---

## 6. Prompt atual: `final.gerar_explicacao`

### 6.1 Identificacao

```text id="yyha9p"
prompt_name: final.gerar_explicacao
prompt_version: 1.0.0
arquivo: agent.py
funcao: AgenteOpenAI.gerar_explicacao
tipo: explicacao
```

---

### 6.2 Objetivo

Gerar explicacao clara para o usuario com base em resultados deterministicos e proposicoes ja produzidas.

---

### 6.3 Entrada

```text id="8w1y84"
pergunta original
resultados deterministicos
proposicoes Optimus
resumo_executivo (top_doi / top_forward / top_oportunidades)
validacao, se disponivel
critica, se disponivel
```

---

### 6.4 Saida esperada

Texto em portugues, objetivo, com:

```text id="unw1tc"
achados principais alinhados ao RESUMO EXECUTIVO
polaridades ruptura vs overstock ja calculadas
dual framing (ruptura + oportunidade) quando presente no contexto
numeros ja calculados
SKUs, canais e percentuais fornecidos no contexto
limitacoes
alertas de revisao
proximos passos sugeridos para humano
```

O LLM deve citar o ranking do resumo; nao reordenar por conta propria.
DOI critico + plano curto = ruptura primaria e, se listado, oportunidade dual.

---

### 6.5 Proibicoes

O LLM nao pode:

```text id="zemsgv"
calcular numeros novos
alterar impacto financeiro
omitir revisao obrigatoria
transformar proposicao em ordem de execucao
afirmar causalidade sem evidencia
dizer que acao foi executada
remover disclaimer aplicado pelo output guardrail
```

---

### 6.6 Guardrail posterior

A resposta deste prompt deve passar por output guardrail, que adiciona:

```text id="4okzzh"
disclaimer obrigatorio
citacoes/evidencias deterministicamente geradas
flag de confianca/revisao
```

---

### 6.7 Testes minimos

Testar:

```text id="9kqd0m"
resposta nao altera numeros fornecidos
resposta cita limitacoes quando ha critic com baixa confianca
resposta nao remove human-in-the-loop
resposta passa pelo output guardrail
```

---

## 7. Prompt atual: `critic.auditar`

### 7.1 Identificacao

```text id="9on4q1"
prompt_name: critic.auditar
prompt_version: 1.0.0
arquivo: critic.py
funcao: CriticAgent.auditar
tipo: auditoria
```

---

### 7.2 Objetivo

Auditar proposicoes geradas pelo Optimus contra sinais estruturados produzidos pelo Dominion.

---

### 7.3 Entrada

```text id="ul9i0t"
sinais serializados
proposicoes serializadas
```

---

### 7.4 Saida esperada

JSON obrigatorio:

```json id="bfwnln"
{
  "aprovado": true,
  "confianca": 0.85,
  "problemas": []
}
```

ou:

```json id="6707mi"
{
  "aprovado": false,
  "confianca": 0.42,
  "problemas": [
    "A proposicao P1 cita impacto maior que o suportado pelos sinais."
  ]
}
```

---

### 7.5 Schema

| Campo       | Tipo        | Regra                       |
| ----------- | ----------- | --------------------------- |
| `aprovado`  | `bool`      | Deve ser booleano real      |
| `confianca` | `float`     | Entre 0.0 e 1.0             |
| `problemas` | `list[str]` | Lista de problemas ou vazia |

---

### 7.6 Proibicoes

Critic nao pode:

```text id="6tdfws"
gerar nova proposicao
alterar proposicao existente
alterar impacto financeiro
alterar sinal
calcular valor novo
inventar evidencia
aprovar acao operacional
```

---

### 7.7 Retry e fallback

```text id="5a0iy7"
max_retries: 2
```

Retry quando:

```text id="o33bzt"
JSON invalido
chaves faltando
tipo errado
confianca fora de 0.0 a 1.0
```

Fallback seguro:

```text id="8j0mqc"
aprovado=False
confianca=0.0
problemas=["Critic falhou ao retornar JSON valido."]
```

---

### 7.8 Testes minimos

Testar:

```text id="jmv62q"
JSON valido aprovado
JSON valido reprovado
JSON invalido
aprovado como string
confianca fora de faixa
problemas nao lista
retry
fallback
```

---

## 8. Prompt: `datashield.inferir_mapa_semantico` (Nivel 1)

### 8.1 Identificacao

```text
prompt_name: datashield.inferir_mapa_semantico
prompt_version: 1.0.0
arquivo: datashield.py
funcao: inferir_mapa_semantico
tipo: inferencia semantica
status: implementado (Nivel 1 hibrido)
```

---

### 8.2 Objetivo

Inferir o papel semantico das colunas de um arquivo tabular para
normalizacao ao schema canonico (Mondelez ou `SCHEMA_PATH`).
O LLM nao calcula metricas e nao altera valores.

Fluxo hibrido:
1. Match deterministico (exact case-insensitive)
2. LLM apenas para colunas nao mapeadas / baixa cobertura
3. Validacao deterministica do JSON
4. Confidence gate + HITL

---

### 8.3 Entrada permitida

O prompt pode receber:

```text
nomes de colunas
tipos inferidos
percentual de nulos
quantidade de valores unicos
amostra limitada de valores (max 5 por coluna)
lista de colunas canonicas permitidas (com descricao)
colunas ja mapeadas pelo match deterministico (opcional)
```

O prompt nao pode receber:

```text
dataset completo
dados sensiveis integrais
arquivos brutos
segredos
```

---

### 8.4 Saida esperada

JSON obrigatorio (alinhado ao schema Mondelez / `SCHEMA_CANONICO_*`):

```json
{
  "mapeamentos": [
    {
      "canonical_name": "Date",
      "source_column": "semana",
      "confidence": 0.92,
      "role": "temporal"
    },
    {
      "canonical_name": "Channel",
      "source_column": "canal_venda",
      "confidence": 0.88,
      "role": "dimension"
    },
    {
      "canonical_name": "SKU_Code",
      "source_column": "cod_produto",
      "confidence": 0.91,
      "role": "product"
    },
    {
      "canonical_name": "SellOut_Actual_Ton",
      "source_column": "vol_cx",
      "confidence": 0.86,
      "role": "metric"
    }
  ],
  "confidence": 0.87,
  "warnings": []
}
```

---

### 8.5 Schema

Campos obrigatorios no JSON raiz:

```text
mapeamentos
confidence
warnings
```

Cada item de `mapeamentos` deve conter:

```text
canonical_name
source_column
confidence
role
```

`role` permitido: `temporal`, `dimension`, `product`, `metric`, `tag`, `other`.

Regras:

```text
confidence (raiz e item) deve estar entre 0.0 e 1.0
source_column deve existir no DataFrame
canonical_name deve pertencer ao schema canonico permitido
mapeamentos deve ter pelo menos um item valido para prosseguir
warnings deve ser list[str]
um canonical_name nao pode ser alvo de duas source_column
```

Apos validacao, o harness converte para mapa flat
`{source_column: canonical_name}` consumido por `normalizar_dataset`.

---

### 8.6 Confidence gate

```text
LIMIAR_CONFIANCA_DATASHIELD default = 0.6

Se confidence >= 0.6:
    pode prosseguir (HITL ainda confirma no fluxo interativo).

Se confidence < 0.6:
    bloquear avanco automatico (HITLAutoApprove);
    no modo interativo, exigir confirmacao/correcao humana.
```

---

### 8.7 Proibicoes

O LLM nao pode:

```text
renomear coluna inexistente
criar coluna nova no DataFrame
alterar valor numerico
imputar dado
calcular metrica
decidir proposicao operacional
prosseguir sem validacao deterministica
receber dataset completo
```

---

### 8.8 Testes minimos

Testar com mock:

```text
schema claro
schema ambiguo
source_column inexistente
confidence baixa
confidence fora de faixa
mapeamentos vazios
JSON invalido
warnings nao lista
retry
fallback deterministico
payload sem dataset completo
```

---

## 8b. Prompt planejado: `datashield.gerar_script_etl` (ADR-0021)

### 8b.1 Identificacao

```text
prompt_name: datashield.gerar_script_etl
prompt_version: 0.1.0
arquivo planejado: datashield.py
funcao planejada: gerar_script_etl
tipo: geracao de ETL
status: planejado
```

---

### 8b.2 Objetivo

Gerar script Python/pandas para adequar a estrutura de um dataset ao schema canonico.
O script deve conter apenas operacoes de ETL (rename, groupby, merge, fillna, drop, astype).
O script NAO pode conter calculos de metricas de negocio.

---

### 8b.3 Entrada permitida

```text
nomes de colunas do dataset
tipos inferidos
schema canonico esperado
diagnostico de gaps (quais campos faltam, quais sobram)
amostra limitada de valores
```

O prompt nao pode receber:

```text
dataset completo
dados sensiveis integrais
```

---

### 8b.4 Saida esperada

```text
{
  "script": "def adequar_dataset(df):\n    df = df.rename(columns={...})\n    ...\n    return df",
  "operacoes": ["rename", "groupby", "drop"],
  "confianca": 0.85,
  "warnings": ["Coluna X nao tem equivalente no schema canonico"],
  "campos_ausentes": ["doi_actual", "sellin_plan"]
}
```

---

### 8b.5 Proibicoes

O LLM nao pode gerar script que:

```text
calcule desvio percentual
calcule impacto financeiro
calcule DOI
calcule tendencia
calcule score
use formulas de negocio
acesse rede ou disco fora do sandbox
importe modulos alem de pandas e numpy
```

### 8b.6 Whitelist de operacoes pandas

```text
rename
groupby
agg
merge
fillna
drop
astype
pivot_table
melt
select (df[colunas])
copy
sort_values
reset_index
```

### 8b.7 Garantias

1. Script gerado deve passar por revisao humana (HITL)
2. Script executado em sandbox
3. Validacao estatica: verificar que nao contem operacoes proibidas
4. Schema checker pos-execucao: verificar formato do output
5. Script salvo com hash e timestamp para auditoria

---

## 9. Prompt planejado: `nexus.classificar_intencao`

### 9.1 Identificacao

```text id="h55ej3"
prompt_name: nexus.classificar_intencao
prompt_version: 0.1.0
status: planejado
tipo: classificacao
```

---

### 9.2 Objetivo

Classificar pergunta do usuario para escolher fluxo permitido.

No MVP, isso nao deve virar MOE router dinamico.

---

### 9.3 Classes permitidas planejadas

```text id="gnfu32"
analise_padrao_sense_to_respond
pergunta_sobre_fila
pergunta_sobre_evidencia
pergunta_sobre_dados
pergunta_fora_escopo
```

---

### 9.4 Saida esperada

```json id="5b5mps"
{
  "classe": "analise_padrao_sense_to_respond",
  "confianca": 0.83,
  "justificativa": "A pergunta solicita analise de sinais e proposicoes."
}
```

---

### 9.5 Proibicoes

O classificador nao pode:

```text id="7s4qyb"
executar tools
gerar proposicoes
ignorar planning
ativar agentes nao implementados
habilitar Bridge
```

---

## 10. Versionamento de prompts

Toda mudanca relevante deve incrementar versao.

Regras sugeridas:

```text id="g3j6mj"
patch: mudanca textual sem alterar comportamento esperado
minor: novo campo, nova restricao ou nova validacao compativel
major: alteracao de schema, comportamento ou fallback
```

Exemplos:

```text id="7t80rf"
1.0.0 -> 1.0.1: clareza textual
1.0.0 -> 1.1.0: adiciona campo "motivo"
1.0.0 -> 2.0.0: muda schema de saida
```

---

## 11. Checklist antes de alterar prompt

Antes de editar prompt, responder:

```text id="krpf61"
1. Qual prompt sera alterado?
2. A mudanca altera comportamento ou apenas clareza?
3. O schema JSON muda?
4. O fallback muda?
5. O retry muda?
6. O LLM continua proibido de calcular numeros?
7. A mudanca exige architecture.md?
8. A mudanca exige planning.md?
9. Quais testes serao atualizados?
10. Como registrar no agent.log.md?
```

Se houver incerteza, parar e pedir confirmacao.

---

## 12. Checklist de aceite para prompts

Um prompt so esta pronto quando:

```text id="edyb31"
- contrato documentado neste arquivo;
- schema JSON documentado, se aplicavel;
- validacao implementada;
- retry limitado;
- fallback seguro;
- testes com sucesso;
- sem calculo numerico pelo LLM;
- sem violacao de human-in-the-loop;
- sem permissao fora da fase;
- agent.log.md atualizado.
```

---

## 13. Regra final

Se houver conflito entre prompt e arquitetura, a arquitetura vence.

Se houver conflito entre resposta do LLM e harness, o harness vence.

Se houver conflito entre flexibilidade e seguranca, a seguranca vence.
