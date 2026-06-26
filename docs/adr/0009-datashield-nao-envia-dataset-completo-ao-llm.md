# ADR-0009 - DataShield Nao Envia Dataset Completo ao LLM

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

O DataShield Lite sera responsavel por receber arquivos tabulares do usuario, como `csv` e `xlsx`, gerar um perfil dos dados, inferir semanticamente o schema e normalizar o dataset para um formato canonico antes do Dominion.

Essa etapa pode usar LLM para inferir o significado de colunas, por exemplo:

```text
semana -> periodo
cod_produto -> sku
canal_venda -> canal
vol_cx -> volume_real
receita_liq -> receita_real
```

Entretanto, arquivos reais podem conter dados sensiveis, comerciais ou estrategicos, como:

```text
precos
receitas
volumes
clientes
canais
estoque
margens
promocoes
codigos internos
informacoes de planejamento
```

Enviar o dataset completo ao LLM aumentaria riscos de privacidade, custo, latencia, vazamento de informacao e uso indevido de dados.

Por isso, o DataShield Lite deve enviar ao LLM apenas o minimo necessario para inferencia semantica.

---

## Decisao

O DataShield Lite nao deve enviar dataset completo ao LLM.

O LLM pode receber apenas:

```text
nomes das colunas
tipos inferidos
percentual de nulos
quantidade de valores unicos
minimos e maximos quando seguro
amostra pequena e limitada de valores
pergunta do usuario
schema canonico permitido
warnings de qualidade
```

O LLM nao pode receber:

```text
dataset completo
todas as linhas do arquivo
todos os valores de uma coluna
dados pessoais desnecessarios
segredos
chaves de API
arquivos brutos
conteudo de .env
payloads grandes
dados comerciais completos sem necessidade
```

A inferencia semantica deve ser feita a partir de perfil e amostra limitada.

---

## Regra operacional

A regra padrao e:

```text
DataShield le o arquivo com Python/pandas.
DataShield gera perfil deterministico.
DataShield cria amostra limitada.
LLM recebe apenas perfil + amostra limitada.
LLM retorna mapa semantico em JSON.
Validador deterministico valida o mapa.
Usuario confirma quando necessario.
Dataset canonico e criado por tool deterministica.
Dominion recebe dataset canonico.
```

O LLM nunca deve manipular diretamente o DataFrame completo.

---

## Alternativas consideradas

### Alternativa A - Enviar dataset completo ao LLM

Descricao:

```text
Enviar todas as linhas e colunas do arquivo ao LLM para que ele entenda os dados livremente.
```

Vantagens:

* maior contexto para o LLM;
* menos necessidade de perfil deterministico;
* implementacao conceitualmente simples.

Desvantagens:

* alto risco de privacidade;
* alto custo de tokens;
* maior latencia;
* risco de expor dados sensiveis;
* risco de o LLM calcular ou interpretar indevidamente valores;
* baixa aderencia a governanca corporativa;
* dificil auditar o que foi realmente usado.

---

### Alternativa B - Nao usar LLM no DataShield

Descricao:

```text
Usar apenas regras deterministicas para mapear colunas.
```

Vantagens:

* menor risco de privacidade;
* maior previsibilidade;
* menos custo de inferencia;
* facil de testar.

Desvantagens:

* menos flexivel;
* exige muitas regras manuais;
* lida mal com colunas heterogeneas;
* pior experiencia de usuario;
* reduz valor da camada semantica.

---

### Alternativa C - Enviar perfil e amostra limitada

Descricao:

```text
Gerar perfil de colunas com pandas e enviar ao LLM apenas metadados e amostra limitada.
```

Vantagens:

* reduz risco de privacidade;
* reduz custo;
* preserva utilidade semantica do LLM;
* melhora auditabilidade;
* evita dataset completo no prompt;
* permite validacao posterior;
* adequada para MVP corporativo.

Desvantagens:

* o LLM pode ter menos contexto;
* schemas muito ambiguos podem exigir confirmacao humana;
* exige criar ferramenta de profiling;
* exige politica clara de amostragem.

---

## Justificativa

A alternativa escolhida foi:

```text
Enviar apenas perfil e amostra limitada ao LLM.
```

Essa decisao preserva o principio:

```text
IA = LLM + Harness
```

O LLM ajuda na interpretacao semantica das colunas, mas nao recebe o dataset completo, nao calcula metricas e nao decide oportunidades.

A separacao correta e:

```text
Python/pandas le e perfila os dados.
LLM infere significado das colunas.
Validador confere o mapa.
Humano confirma se necessario.
Python/pandas normaliza o dataset.
Dominion calcula sinais.
```

---

## Politica de amostragem

A amostra enviada ao LLM deve ser pequena e configuravel.

Padrao recomendado:

```text
max_linhas_amostra: 20
max_valores_distintos_por_coluna: 10
max_colunas: todas as colunas, mas apenas metadados e amostra limitada
```

Para cada coluna, o perfil pode conter:

```text
nome da coluna
tipo inferido
percentual de nulos
quantidade de valores unicos
exemplos limitados de valores
minimo e maximo, quando numerico e seguro
media ou mediana apenas se necessario e seguro
```

Se houver risco de sensibilidade, a amostra deve ser mascarada, resumida ou omitida.

---

## Dados sensiveis

O DataShield deve tratar com cautela colunas que parecam conter:

```text
nome de pessoa
email
telefone
documento
endereco
cliente identificavel
contrato
chave interna sensivel
observacao livre
```

Para essas colunas, o padrao deve ser:

```text
nao enviar valores brutos ao LLM
enviar apenas tipo, percentual de nulos e alguns metadados seguros
mascarar exemplos quando necessario
```

Exemplo:

```text
email_cliente -> exemplo mascarado: ***@dominio.com
cpf -> exemplo mascarado: ***.***.***-**
telefone -> exemplo mascarado: (***) ****-****
```

---

## Proibicoes

O DataShield Lite nao pode:

```text
enviar dataset completo ao LLM
enviar todas as linhas de uma planilha
enviar todas as categorias de uma coluna de alta cardinalidade
enviar dados pessoais desnecessarios
enviar valores sensiveis sem mascaramento
salvar prompt completo com dados sensiveis em logs
salvar resposta LLM com dados sensiveis em auditoria
usar LLM para limpar ou alterar valores numericos
usar LLM para imputar dados ausentes
usar LLM para calcular metricas
```

---

## Regras de auditoria

A auditoria pode registrar:

```text
nome do arquivo ou hash
numero de linhas
numero de colunas
nomes das colunas
tipos inferidos
percentual geral de completude
quantidade de linhas amostradas
confidence do mapa semantico
warnings
status de confirmacao humana
```

A auditoria nao deve registrar:

```text
dataset completo
amostra integral se houver dado sensivel
segredos
valores comerciais completos
payload completo enviado ao LLM quando contiver dados sensiveis
```

Quando necessario, registrar apenas resumo seguro.

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/agent.log.md`

Impacto:

```text
A arquitetura deve explicitar que DataShield Lite usa LLM apenas para inferencia semantica com perfil e amostra limitada, nunca com dataset completo.
```

---

## Impacto em codigo

Arquivos previstos ou afetados:

* [x] `datashield.py`
* [x] `datashield_tools.py`
* [x] `datashield_schema.py`
* [x] `audit.py`
* [x] `guardrails.py`
* [x] `nexus.py`
* [x] `main.py`
* [x] `state_types.py`

Impacto:

```text
DataShield deve criar funcoes deterministicas para perfil e amostragem segura. A funcao que chama LLM deve receber apenas payload reduzido e validado.
```

---

## Impacto em prompts

Prompt afetado:

```text
datashield.inferir_mapa_semantico
```

O prompt deve declarar:

```text
Voce recebera apenas perfil e amostra limitada.
Nao presuma que todos os valores foram enviados.
Nao calcule metricas.
Nao altere dados.
Nao impute valores.
Retorne apenas mapa semantico em JSON.
```

---

## Impacto em testes

Testes exigidos:

* [x] teste de amostra com limite de linhas;
* [x] teste de limite de valores distintos por coluna;
* [x] teste de coluna sensivel mascarada;
* [x] teste de auditoria sem dataset completo;
* [x] teste de payload LLM sem DataFrame completo;
* [x] teste de arquivo grande gerando apenas perfil compacto;
* [x] teste de schema ambiguo exigindo confirmacao;
* [x] teste de confidence baixo bloqueando avanco automatico.

Comando minimo:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Quando DataShield estiver implementado:

```bash
python main.py --modo nexus --input tests/fixtures/sellout_simples.csv
```

---

## Criterios de aceite

* [ ] DataShield gera perfil deterministico.
* [ ] DataShield gera amostra limitada.
* [ ] Payload enviado ao LLM nao contem dataset completo.
* [ ] Colunas sensiveis sao mascaradas ou omitidas.
* [ ] Auditoria nao salva dataset completo.
* [ ] Prompt do DataShield proibe calculo e alteracao de dados.
* [ ] JSON de mapa semantico e validado.
* [ ] Confidence gate e aplicado.
* [ ] Usuario confirma quando necessario.
* [ ] Dataset canonico e criado por tool deterministica.
* [ ] Dominion recebe apenas dataset canonico confirmado.

---

## Plano de migracao

Implementar junto com DataShield Lite:

```text
1. Criar funcao de profiling de DataFrame.
2. Criar funcao de amostragem segura.
3. Criar mascara simples para colunas sensiveis.
4. Criar payload compacto para LLM.
5. Criar prompt de inferencia semantica.
6. Validar JSON retornado.
7. Registrar auditoria segura.
8. Testar que dataset completo nao aparece no payload.
9. Integrar com Nexus.
```

---

## Plano de rollback

Se houver risco de vazamento de dados:

```text
1. Desabilitar chamada LLM do DataShield.
2. Exigir mapeamento manual do usuario.
3. Manter leitura e perfil deterministico.
4. Bloquear normalizacao automatica.
5. Registrar incidente ou alerta em agent.log.md.
```

Se a amostragem estiver grande demais:

```text
1. Reduzir max_linhas_amostra.
2. Reduzir max_valores_distintos_por_coluna.
3. Mascarar colunas suspeitas.
4. Rodar testes de payload.
```

---

## Riscos

| Risco                                           | Probabilidade | Impacto | Mitigacao                                           |
| ----------------------------------------------- | ------------- | ------- | --------------------------------------------------- |
| Dataset completo ser enviado ao LLM por erro    | Media         | Alto    | Teste de payload e funcao unica de montagem         |
| Coluna sensivel nao ser detectada               | Media         | Alto    | Heuristicas + opcao de mascarar mais agressivamente |
| Amostra insuficiente para inferir schema        | Media         | Medio   | Confidence gate e confirmacao humana                |
| Auditoria salvar dados sensiveis                | Media         | Alto    | Auditoria com resumo e sem dumps                    |
| Desenvolvedor passar DataFrame direto ao prompt | Media         | Alto    | Regras Cursor, tests e ADR                          |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0005 - DataShield Lite antes do Dominion
ADR-0007 - Guardrails em tres camadas
ADR-0008 - Human-in-the-loop obrigatorio no MVP
```

---

## Observacoes

Esta ADR nao impede que o sistema use dados reais.

Ela apenas define que dados reais devem ser tratados por tools deterministicas, e que o LLM deve receber apenas contexto minimo necessario.

Linguagem recomendada:

```text
DataShield envia ao LLM apenas perfil e amostra limitada para inferencia semantica de schema.
```

Evitar:

```text
DataShield envia a planilha completa para o LLM analisar.
```
