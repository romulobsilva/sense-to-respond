# ADR-0005 - DataShield Lite antes do Dominion

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

O MVP tecnico atual do Sense to Respond consegue executar o fluxo agentic com dados simulados ou previamente estruturados.

O fluxo atual permitido e:

```text id="qcgz7x"
Input Guardrail
  -> Dominion
  -> Sinais estruturados
  -> Optimus
  -> Validador deterministico
  -> Critic LLM read-only
  -> Fila Nexus
  -> Output Guardrail
```

Entretanto, para aproximar o MVP da proposta comercial, o sistema precisa aceitar arquivos reais do usuario, como:

```text id="gb4hqa"
csv
xlsx
planilhas de sell-out
planilhas de sell-in
dados de estoque
dados de canal
dados de planejamento
```

Esses arquivos podem ter nomes de colunas diferentes, formatos distintos e granularidades variadas.

Exemplos de colunas possiveis:

```text id="rd0ts5"
semana
periodo
mes
cod_produto
sku
produto
canal
regional
volume
volume_real
vol_cx
receita
sellout
estoque
doi
plano
forecast
```

Se o Dominion receber dados sem normalizacao, o risco aumenta:

* colunas podem ser interpretadas errado;
* metricas podem ser confundidas com dimensoes;
* SKU pode ser confundido com descricao;
* periodo pode ser lido como texto comum;
* canal pode estar ausente ou com outro nome;
* analises podem rodar sobre campos errados;
* proposicoes podem ser geradas sobre evidencias frageis.

Por isso, antes de expandir o Dominion para arquivos reais, e necessario introduzir uma etapa de preparacao e governanca dos dados.

---

## Decisao

Adicionar **DataShield Lite** como etapa anterior ao Dominion.

Fluxo alvo do MVP:

```text id="l97ejf"
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

O DataShield Lite sera responsavel por:

```text id="yts7qa"
ler arquivos csv/xlsx
gerar perfil das colunas
gerar amostra limitada
inferir mapa semantico com LLM
validar o JSON retornado pelo LLM
aplicar confidence gate
exigir confirmacao humana quando necessario
normalizar dataset para schema canonico
registrar handoff DataShield -> Dominion
```

O LLM no DataShield Lite pode apenas inferir significado semantico de colunas.

O LLM nao pode:

```text id="nij3ot"
alterar valores numericos
calcular metricas
calcular impacto financeiro
calcular desvios
imputar dados
decidir proposicoes
executar analises de Dominion
enviar dataset completo ao modelo
```

---

## Alternativas consideradas

### Alternativa A - Dominion le arquivos diretamente

Descricao:

```text id="rawggd"
Permitir que o Dominion leia arquivos csv/xlsx diretamente e tente identificar colunas dentro das proprias tools de analise.
```

Vantagens:

* implementacao inicial mais rapida;
* menos uma etapa no pipeline;
* menor quantidade de arquivos novos.

Desvantagens:

* mistura responsabilidades;
* Dominion ficaria responsavel por dados e analise;
* maior risco de schema errado;
* maior dificuldade de teste;
* maior dificuldade de reuso;
* menor governanca de dados;
* nao separa ingestao de deteccao de sinais.

---

### Alternativa B - Usuario informa manualmente todo o schema

Descricao:

```text id="du98ox"
O usuario precisa mapear manualmente todas as colunas antes da analise.
```

Vantagens:

* baixo uso de LLM;
* maior controle humano;
* menor risco de inferencia errada pelo modelo.

Desvantagens:

* pior experiencia de uso;
* mais lento;
* menos escalavel;
* menos demonstravel em MVP;
* pode gerar erros manuais;
* reduz valor da camada de IA.

---

### Alternativa C - DataShield Lite com inferencia semantica controlada

Descricao:

```text id="ephd46"
DataShield Lite le o arquivo, cria perfil de colunas, envia amostra limitada ao LLM para inferir mapa semantico, valida o retorno e exige confirmacao humana quando necessario.
```

Vantagens:

* separa ingestao de analise;
* melhora governanca;
* reduz risco de schema errado;
* preserva human-in-the-loop;
* aproxima MVP de uso real;
* mantem LLM limitado a tarefa semantica;
* prepara caminho para DataShield completo;
* permite reuso de templates de mapeamento.

Desvantagens:

* aumenta complexidade;
* exige novos tipos no state;
* exige validacao de JSON;
* exige confidence gate;
* exige testes com arquivos;
* adiciona dependencia de leitura de xlsx.

---

### Alternativa D - DataShield completo desde o inicio

Descricao:

```text id="s49sbo"
Implementar diretamente uma camada completa de governanca, multiplas fontes, reconciliacao, qualidade, lineage e pipelines robustos.
```

Vantagens:

* solucao mais completa;
* melhor arquitetura de dados de longo prazo;
* mais preparada para producao corporativa.

Desvantagens:

* escopo grande demais para MVP;
* maior custo;
* maior tempo de implementacao;
* risco de atrasar demonstracao de valor;
* exige integracoes ainda nao necessarias.

---

## Justificativa

A alternativa escolhida foi:

```text id="be0flz"
DataShield Lite com inferencia semantica controlada antes do Dominion.
```

Essa decisao preserva o principio:

```text id="s85on1"
IA = LLM + Harness
```

O LLM ajuda a interpretar semanticamente o arquivo, mas nao calcula metricas nem toma decisoes.

A etapa DataShield Lite resolve um problema essencial do MVP: transformar arquivos heterogeneos em um dataset canonico minimamente confiavel para que Dominion possa detectar sinais de forma deterministica.

Essa decisao tambem preserva a separacao de responsabilidades:

```text id="auic5b"
DataShield prepara os dados
Dominion detecta sinais
Optimus gera proposicoes
Validador confere
Critic audita
Nexus prioriza
Humano decide
```

---

## Schema canonico minimo

O DataShield Lite deve normalizar os dados para um schema canonico minimo.

Campos recomendados:

```text id="moud9g"
periodo
sku
canal
volume_real
receita_real
```

Campos opcionais:

```text id="axhcnr"
volume_plano
receita_plano
estoque_atual
doi_atual
doi_minimo
regiao
categoria
cliente
promocao_flag
```

Regras:

* Dominion so deve executar analises compatíveis com colunas disponiveis.
* Analises com colunas ausentes devem ser puladas com log auditavel.
* O dataset canonico nao deve inventar colunas obrigatorias ausentes.
* O usuario deve ser informado quando uma analise nao puder ser executada por falta de dados.

---

## Contrato do mapa semantico

A inferencia semantica deve retornar JSON validado.

Formato esperado:

```json id="w64sfq"
{
  "temporal": [
    {
      "canonical_name": "periodo",
      "source_column": "semana",
      "confidence": 0.92,
      "role": "temporal"
    }
  ],
  "canal": [
    {
      "canonical_name": "canal",
      "source_column": "canal_venda",
      "confidence": 0.88,
      "role": "dimension"
    }
  ],
  "produto": [
    {
      "canonical_name": "sku",
      "source_column": "cod_produto",
      "confidence": 0.91,
      "role": "product"
    }
  ],
  "metricas": [
    {
      "canonical_name": "volume_real",
      "source_column": "vol_cx",
      "confidence": 0.86,
      "role": "metric"
    }
  ],
  "dimensoes": [],
  "confidence": 0.87,
  "warnings": []
}
```

Campos obrigatorios:

```text id="px89az"
temporal
canal
produto
metricas
dimensoes
confidence
warnings
```

Cada mapeamento deve conter:

```text id="fuv51m"
canonical_name
source_column
confidence
role
```

Regras:

* `source_column` deve existir no DataFrame.
* `canonical_name` deve pertencer ao schema canonico permitido.
* `confidence` deve estar entre 0.0 e 1.0.
* `warnings` deve ser lista de strings.
* `metricas` deve conter ao menos um item para prosseguir.
* Se colunas essenciais estiverem ausentes, Dominion deve receber capacidades reduzidas.

---

## Confidence gate

Regra padrao:

```text id="v48ia3"
confidence >= 0.60:
    pode prosseguir se modo automatico permitir

confidence < 0.60:
    bloquear avanco automatico e exigir confirmacao ou correcao humana
```

Mesmo com confidence alto, o sistema deve permitir que o usuario revise o mapeamento.

Em modo `no-interactive`:

```text id="b5k9fb"
confidence alta -> prossegue
confidence baixa -> bloqueia com erro controlado
```

Em modo interativo:

```text id="vfc81y"
mostrar mapa semantico
mostrar warnings
pedir confirmacao humana
permitir correcao futura do mapeamento
```

---

## Consequencias positivas

* Permite uso de arquivos reais no MVP.
* Separa ingestao de dados da deteccao de sinais.
* Reduz risco de Dominion interpretar colunas erradas.
* Mantem LLM em tarefa semantica controlada.
* Preserva regra de que LLM nao calcula numeros.
* Melhora auditabilidade do pipeline.
* Prepara reuso de templates de mapeamento.
* Permite evoluir para DataShield completo.
* Melhora demonstrabilidade comercial do MVP.
* Permite registrar qualidade e completude dos dados.

---

## Consequencias negativas ou trade-offs

* Aumenta complexidade do pipeline.
* Exige novos arquivos de codigo.
* Exige novos tipos no state.
* Exige validacao rigorosa de JSON.
* Exige testes com arquivos csv/xlsx.
* Pode bloquear analises quando schema for ambiguo.
* Pode exigir confirmacao humana adicional.
* Pode aumentar latencia por uma chamada LLM.
* Exige cuidado para nao enviar dados sensiveis ao LLM.

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

```text id="qij0xd"
Nenhum invariante foi violado. DataShield Lite adiciona uma etapa antes do Dominion, mas mantem pipeline sequencial, harness, state blackboard e human-in-the-loop.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`

Impacto:

```text id="n03uj4"
A arquitetura deve inserir DataShield Lite antes do Dominion e documentar que sua responsabilidade e ingestao, perfil, inferencia semantica, confirmacao e normalizacao para schema canonico.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `state_types.py`
* [x] `nexus.py`
* [x] `main.py`
* [x] `tools.py`
* [x] `audit.py`
* [x] `guardrails.py`
* [ ] `agent.py`
* [ ] `harness.py`
* [ ] `sinais.py`
* [ ] `optimus.py`
* [ ] `validator.py`
* [ ] `critic.py`

Novos arquivos previstos:

```text id="w2rfsz"
datashield.py
datashield_tools.py
datashield_schema.py
```

Arquivos opcionais futuros:

```text id="lqhmim"
tool_registry.py
tests/test_datashield_tools.py
tests/test_datashield_schema.py
tests/fixtures/sellout_simples.csv
tests/fixtures/sellout_schema_ambiguo.csv
```

Impacto:

```text id="oefy3f"
Nexus deve chamar DataShield Lite quando houver arquivo de entrada. DataShield deve produzir dataset canonico e schema confirmado. Dominion deve consumir dataset canonico quando disponivel.
```

---

## Impacto em state

Novos campos planejados:

```text id="rzp9z4"
datashield
schema_confirmado
dataset_canonico
mapa_semantico
perfil_dados
templates_mapeamento
```

Responsabilidades:

```text id="eu0pij"
DataShield escreve esses campos.
Nexus verifica se schema esta confirmado.
Dominion le dataset_canonico.
Auditoria registra o handoff DataShield -> Dominion.
```

Regra:

```text id="lymjcd"
Dominion nao deve rodar sobre arquivo real se schema_confirmado=False.
```

---

## Impacto em tools

Tools planejadas para DataShield Lite:

```text id="mz4v5w"
ler_arquivo
gerar_perfil_dataframe
amostrar_dataframe
inferir_mapa_semantico
validar_mapa_semantico
normalizar_dataset
salvar_template_mapeamento
carregar_template_mapeamento
```

Classificacao:

```text id="v71ewy"
ler_arquivo -> io_tool
gerar_perfil_dataframe -> deterministic_tool
amostrar_dataframe -> deterministic_tool
inferir_mapa_semantico -> llm_tool
validar_mapa_semantico -> deterministic_tool
normalizar_dataset -> deterministic_tool
salvar_template_mapeamento -> io_tool
carregar_template_mapeamento -> io_tool
```

Regras:

* `inferir_mapa_semantico` nao pode calcular metricas.
* `normalizar_dataset` nao pode alterar valores numericos.
* `gerar_perfil_dataframe` nao pode enviar dataset completo ao LLM.
* `validar_mapa_semantico` deve bloquear colunas inexistentes.
* `ler_arquivo` deve aceitar apenas extensoes permitidas.

---

## Impacto em prompts

Prompt planejado:

```text id="ejpyst"
datashield.inferir_mapa_semantico
```

O prompt deve receber apenas:

```text id="n89w3z"
nomes de colunas
tipos inferidos
percentual de nulos
quantidade de valores unicos
amostra limitada
pergunta do usuario
schema canonico permitido
```

O prompt nao deve receber:

```text id="i1proh"
dataset completo
segredos
dados pessoais desnecessarios
arquivos brutos
payloads grandes
```

Saida:

```text id="0ehfuz"
JSON validado conforme contrato em docs/prompts.md
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] teste de leitura csv
* [x] teste de leitura xlsx
* [x] teste de arquivo inexistente
* [x] teste de extensao nao suportada
* [x] teste de perfil de DataFrame
* [x] teste de mapa semantico valido
* [x] teste de mapa semantico invalido
* [x] teste de confidence baixo
* [x] teste de source_column inexistente
* [x] teste de normalizacao
* [x] teste de bloqueio sem schema confirmado
* [x] teste de handoff DataShield -> Dominion

Detalhar:

```text id="q0byuy"
Quando DataShield Lite for implementado, o pipeline atual com dados simulados deve continuar funcionando. A presenca de arquivo de entrada ativa DataShield; a ausencia de arquivo mantem fluxo atual.
```

---

## Criterios de aceite

* [ ] DataShield Lite aceita `csv`.
* [ ] DataShield Lite aceita `xlsx`.
* [ ] DataShield Lite gera perfil de colunas.
* [ ] DataShield Lite gera amostra limitada.
* [ ] DataShield Lite chama LLM apenas para inferencia semantica.
* [ ] Saida do LLM e JSON validado.
* [ ] Confidence gate implementado.
* [ ] Confirmacao humana ou bloqueio em caso de baixa confianca.
* [ ] Dataset canonico produzido.
* [ ] Valores numericos preservados.
* [ ] Handoff DataShield -> Dominion registrado.
* [ ] Dominion consome dataset canonico quando disponivel.
* [ ] Sem arquivo de entrada, fluxo atual continua funcionando.
* [ ] Auditoria nao registra dataset completo.
* [ ] Testes minimos passam.

---

## Plano de migracao

Implementar em etapas pequenas:

```text id="mqumzk"
1. Atualizar architecture.md com DataShield Lite antes do Dominion.
2. Atualizar planning.md com subtarefas detalhadas.
3. Atualizar state_contract.md com campos novos.
4. Criar datashield_tools.py com leitura, perfil e amostragem.
5. Criar validacao de mapa semantico.
6. Criar datashield.py como orquestrador da etapa.
7. Adicionar argumentos em main.py para input, sheet e modo interativo.
8. Integrar DataShield no Nexus.
9. Adaptar Dominion para consumir dataset canonico quando disponivel.
10. Criar fixtures e testes.
11. Registrar sessao em agent.log.md.
```

---

## Plano de rollback

O rollback deve preservar o fluxo atual sem arquivo.

Regra:

```text id="emyjla"
Se nenhum arquivo for fornecido, Nexus executa o fluxo atual com dados simulados ou pre-carregados.
```

Se DataShield falhar:

```text id="fcfjrg"
1. Registrar falha em auditoria.
2. Bloquear avanco para Dominion quando arquivo real estiver presente.
3. Mostrar erro controlado ao usuario.
4. Nao gerar proposicoes sobre schema incerto.
```

Para rollback tecnico:

```text id="gp2nmq"
1. Desativar chamada DataShield no Nexus.
2. Manter arquivos DataShield sem uso ou remover em branch separada.
3. Garantir que python main.py --modo nexus continua funcionando.
4. Registrar rollback em agent.log.md.
```

---

## Riscos

| Risco                                             | Probabilidade | Impacto     | Mitigacao                                       |
| ------------------------------------------------- | ------------- | ----------- | ----------------------------------------------- |
| LLM mapear coluna errada                          | Media         | Alto        | Confidence gate, validacao e confirmacao humana |
| Dataset completo ser enviado ao LLM               | Media         | Alto        | Enviar apenas perfil e amostra limitada         |
| Valores numericos serem alterados na normalizacao | Baixa/Media   | Alto        | Testes de preservacao de valores                |
| Schema ambiguo bloquear analise                   | Media         | Medio       | UI ou CLI para confirmacao/correcao             |
| Dominion rodar com schema nao confirmado          | Media         | Alto        | Bloqueio em Nexus                               |
| Arquivo real conter dado sensivel                 | Media         | Alto        | Logs com resumo, nao dump completo              |
| Dependencia xlsx falhar                           | Media         | Baixo/Medio | requirements com openpyxl e teste especifico    |

---

## Decisoes relacionadas

```text id="oxedvj"
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard sem conversa livre
ADR-0004 - Critic read-only
```

---

## Observacoes

DataShield Lite nao e DataShield completo.

DataShield Lite cobre apenas:

```text id="thl8wz"
ingestao simples
perfil de colunas
inferencia semantica
confirmacao
normalizacao
handoff
```

DataShield completo fica para fase futura e pode incluir:

```text id="du0xgc"
multiplas fontes
reconciliacao
qualidade de dados avancada
freshness
lineage
governanca
pipelines Kedro ou equivalentes
integracao com data platform corporativa
```

Linguagem recomendada:

```text id="n17sgg"
DataShield Lite prepara e normaliza arquivos tabulares antes do Dominion, com inferencia semantica controlada por LLM e validacao deterministica.
```

Evitar:

```text id="q1p38l"
DataShield decide quais oportunidades existem nos dados.
```
