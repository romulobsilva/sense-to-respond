# ADR-0012 - Auditoria sem Dados Sensiveis

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

O Sense to Respond precisa ser auditavel.

O pipeline envolve:

```text
Input Guardrail
DataShield Lite
Dominion
Sinais estruturados
Optimus
Validador
Critic
Nexus
Output Guardrail
```

Para que o sistema seja confiavel em ambiente corporativo, e necessario registrar eventos importantes, como:

```text
inicio da sessao
validacao de entrada
decisoes do LLM
execucao de tools
handoffs entre fases
validacao deterministica
auditoria do Critic
criacao da fila Nexus
aplicacao de guardrails
decisoes humanas futuras
fim da sessao
```

Entretanto, os dados processados podem conter informacoes sensiveis ou estrategicas:

```text
dados comerciais
receitas
volumes
estoques
clientes
canais
SKUs
promocoes
margens
planejamento
arquivos reais enviados pelo usuario
chaves de API
configuracoes internas
```

A auditoria precisa equilibrar dois objetivos:

```text
rastreabilidade suficiente
minimizacao de dados sensiveis
```

---

## Decisao

A auditoria deve registrar eventos e resumos seguros, mas nao deve salvar dados sensiveis desnecessarios.

Regra central:

```text
Auditar o que aconteceu, sem vazar o conteudo sensivel processado.
```

A auditoria pode registrar:

```text
session_id
request_id
timestamp
fase
evento
nome da tool
status
duracao
quantidade de linhas
quantidade de colunas
nomes de colunas
tipos inferidos
metricas agregadas
ids de sinais
ids de proposicoes
status de validacao
confidence do Critic
motivos de revisao
hash de arquivo
erros seguros
```

A auditoria nao deve registrar:

```text
OPENAI_API_KEY
conteudo de .env
dataset completo
arquivo completo do usuario
todas as linhas de uma planilha
payload LLM completo com dados sensiveis
dados pessoais desnecessarios
segredos corporativos
credenciais
tokens
cookies
senhas
chaves privadas
```

Quando for necessario rastrear um dado sensivel, preferir:

```text
hash
resumo
contagem
faixa
identificador interno controlado
amostra mascarada
```

---

## Alternativas consideradas

### Alternativa A - Auditoria completa com payloads integrais

Descricao:

```text
Salvar todas as entradas, saidas, prompts, respostas LLM, datasets e estados completos em arquivos de auditoria.
```

Vantagens:

* maxima rastreabilidade tecnica;
* facilita debug;
* permite replay completo;
* reduz necessidade de reproduzir cenarios.

Desvantagens:

* alto risco de vazamento de dados;
* pode expor informacoes comerciais sensiveis;
* pode expor dados pessoais;
* pode expor segredos se houver erro;
* aumenta volume de armazenamento;
* reduz aderencia a governanca corporativa;
* dificulta compartilhamento seguro de logs.

---

### Alternativa B - Sem auditoria

Descricao:

```text
Nao salvar eventos de execucao para evitar risco de dados sensiveis.
```

Vantagens:

* menor risco de vazamento por logs;
* menor complexidade;
* menor armazenamento.

Desvantagens:

* baixa rastreabilidade;
* dificil depurar erros;
* dificil explicar decisoes;
* dificil demonstrar governanca;
* dificil validar handoffs;
* inadequado para sistema corporativo com IA.

---

### Alternativa C - Auditoria com minimizacao de dados

Descricao:

```text
Registrar eventos, metadados, hashes, resumos e indicadores, evitando payloads completos e dados sensiveis.
```

Vantagens:

* preserva rastreabilidade;
* reduz risco de vazamento;
* melhora governanca;
* facilita debug seguro;
* adequado para MVP corporativo;
* permite auditar o fluxo sem armazenar dados completos.

Desvantagens:

* replay completo pode nao ser possivel;
* debug profundo pode exigir reproduzir com dados originais;
* exige disciplina na implementacao;
* exige testes para impedir vazamento em logs.

---

## Justificativa

A alternativa escolhida foi:

```text
Auditoria com minimizacao de dados.
```

Essa decisao preserva o principio:

```text
IA = LLM + Harness
```

O harness precisa auditar o fluxo, mas a auditoria nao deve virar uma copia paralela dos dados sensiveis.

O objetivo e permitir responder perguntas como:

```text
qual tool foi executada?
quando foi executada?
qual fase produziu determinado sinal?
qual proposicao usou qual evidencia?
o Critic aprovou?
qual foi a confianca?
houve fallback?
houve guardrail?
houve revisao obrigatoria?
```

Sem precisar armazenar:

```text
a planilha completa
os dados brutos completos
segredos
payloads sensiveis
```

---

## Eventos obrigatorios de auditoria

A auditoria deve registrar, quando aplicavel:

```text
sessao_inicio
input_guardrail_ok
input_guardrail_bloqueado
datashield_inicio
datashield_perfil_gerado
datashield_schema_inferido
datashield_schema_confirmado
datashield_schema_bloqueado
handoff_datashield_dominion
llm_decisao
llm_json_parse_error
llm_json_schema_error
llm_json_retry
llm_json_fallback
tool_inicio
tool_fim
tool_erro
sinais_extraidos
optimus_proposicoes_geradas
validator_ok
validator_falha
critic_inicio
critic_fim
critic_fallback
nexus_fila_criada
output_guardrail_aplicado
sessao_fim
```

Eventos futuros, quando houver UI:

```text
usuario_aprovou
usuario_rejeitou
usuario_pediu_contexto
usuario_comentou
```

---

## Campos recomendados por evento

Cada evento deve conter, quando possivel:

```text
timestamp
session_id
request_id
event_type
phase
component
status
message_safe
metadata_safe
```

Campos opcionais:

```text
tool_name
prompt_name
prompt_version
model_name
attempt
duration_ms
input_summary
output_summary
error_type
error_safe_message
handoff_from
handoff_to
state_keys_before
state_keys_after
```

---

## Exemplo de evento seguro

```json
{
  "timestamp": "2026-06-25T20:10:00Z",
  "session_id": "sess_123",
  "event_type": "tool_fim",
  "phase": "dominion",
  "component": "harness",
  "tool_name": "validar_demanda",
  "status": "ok",
  "duration_ms": 142,
  "metadata_safe": {
    "linhas_processadas": 1200,
    "colunas_usadas": ["sku", "canal", "volume_real", "volume_plano"],
    "sinais_gerados": 4
  }
}
```

---

## Exemplo de evento proibido

```json
{
  "event_type": "tool_fim",
  "dataset_completo": [
    {"cliente": "Cliente Real", "receita": 123456.78, "sku": "SKU123"}
  ],
  "openai_api_key": "sk-..."
}
```

Esse tipo de registro e proibido.

---

## Auditoria de DataShield

DataShield pode registrar:

```text
nome do arquivo ou hash
extensao
numero de linhas
numero de colunas
nomes das colunas
tipos inferidos
percentual de nulos por coluna
quantidade de linhas amostradas
confidence geral do mapa semantico
warnings
status de confirmacao humana
```

DataShield nao deve registrar:

```text
dataset completo
amostra integral com dados sensiveis
payload completo enviado ao LLM se contiver valores sensiveis
valores pessoais identificaveis
todos os valores distintos de colunas de alta cardinalidade
```

---

## Auditoria de prompts LLM

Para prompts LLM, registrar:

```text
prompt_name
prompt_version
modelo
tentativa
status
schema_validado
fallback_aplicado
tokens aproximados, se disponivel
```

Nao registrar, por padrao:

```text
prompt completo com dados sensiveis
resposta completa se contiver dados sensiveis
dataset completo
segredos
```

Quando for necessario guardar `json_bruto`, aplicar regra de seguranca:

```text
guardar apenas se nao contiver dado sensivel
ou guardar versao sanitizada
ou guardar apenas resumo do erro
```

---

## Auditoria de tools

Para tools, registrar:

```text
tool_name
phase
inicio
fim
duracao
status
campos de entrada resumidos
campos de saida resumidos
quantidade de sinais/proposicoes geradas
erro seguro, se houver
```

Nao registrar:

```text
DataFrame completo
listas grandes de registros
arquivos completos
segredos
```

---

## Auditoria de handoffs

Para handoffs, registrar:

```text
origem
destino
timestamp
payload_chaves
quantidade_itens
ids_relevantes
status
```

Exemplo:

```json
{
  "event_type": "handoff",
  "handoff_from": "Optimus",
  "handoff_to": "Validador",
  "metadata_safe": {
    "payload_chaves": ["proposicoes", "sinais"],
    "qtd_proposicoes": 3,
    "qtd_sinais": 4,
    "proposicao_ids": ["P1", "P2", "P3"],
    "sinal_ids": ["S1", "S2", "S3", "S4"]
  }
}
```

---

## Mascaramento

Quando houver risco de dado sensivel, aplicar mascaramento.

Exemplos:

```text
email -> ***@dominio.com
telefone -> (***) ****-****
documento -> ***.***.***-**
cliente -> cliente_hash_abc123
arquivo -> arquivo_hash_abc123
```

Para dados comerciais, preferir:

```text
faixas
agregados
contagens
hashes
```

Em vez de valores brutos detalhados.

---

## Retencao de logs

O MVP deve evitar definir politica definitiva de retencao sem contexto corporativo.

Regra provisoria:

```text
logs locais devem ser tratados como artefatos sensiveis
logs de exemplo devem conter apenas dados ficticios
logs reais nao devem ser commitados
auditoria real deve ficar fora do repositorio
```

Arquivos ou diretorios de auditoria real devem ser adicionados ao `.gitignore`, quando aplicavel.

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/agent.log.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text
A arquitetura deve declarar que auditoria e obrigatoria, mas com minimizacao de dados e sem registrar datasets completos ou segredos.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `audit.py`
* [x] `guardrails.py`
* [x] `harness.py`
* [x] `nexus.py`
* [x] `main.py`
* [x] `critic.py`
* [x] `agent.py`
* [ ] `datashield.py`
* [ ] `datashield_tools.py`
* [ ] `datashield_schema.py`

Impacto:

```text
audit.py deve oferecer funcoes para registrar eventos seguros. Chamadas de auditoria devem passar resumos, nao objetos grandes ou dados sensiveis.
```

---

## Impacto em testes

Testes obrigatorios:

```text
auditoria cria eventos serializaveis em JSON
auditoria registra timestamp
auditoria registra tool_inicio e tool_fim
auditoria registra handoffs
auditoria nao contem OPENAI_API_KEY
auditoria nao contem conteudo de .env
auditoria nao contem DataFrame completo
auditoria nao contem dataset completo
auditoria usa resumo seguro para arquivos
auditoria registra fallback de LLM
auditoria registra guardrail bloqueado
```

Comandos minimos:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Se houver suite:

```bash
pytest
```

---

## Criterios de aceite

* [ ] Auditoria registra eventos principais do pipeline.
* [ ] Auditoria usa timestamps.
* [ ] Auditoria registra handoffs.
* [ ] Auditoria registra erros de LLM e fallbacks.
* [ ] Auditoria registra guardrails.
* [ ] Auditoria nao salva dataset completo.
* [ ] Auditoria nao salva segredos.
* [ ] Auditoria nao salva `.env`.
* [ ] Auditoria nao salva chave de API.
* [ ] Logs reais nao sao commitados.
* [ ] Testes verificam ausencia de dados sensiveis.

---

## Plano de migracao

Para reforcar esta ADR:

```text
1. Revisar audit.py.
2. Criar funcao de sanitizacao de payloads.
3. Criar funcao de resumo seguro de state.
4. Criar funcao de resumo seguro de DataFrame.
5. Atualizar chamadas de auditoria para usar resumos.
6. Garantir que arquivos reais de auditoria estejam no .gitignore.
7. Criar testes contra vazamento de segredo.
8. Criar testes contra dump completo de dataset.
9. Registrar mudanca em docs/agent.log.md.
```

---

## Plano de rollback

Se for detectado vazamento em auditoria:

```text
1. Parar uso do log afetado.
2. Remover dado sensivel do arquivo local.
3. Adicionar regra de sanitizacao.
4. Criar teste de regressao.
5. Registrar incidente em agent.log.md sem repetir o dado sensivel.
```

Rollback proibido:

```text
remover auditoria completamente
continuar salvando payload sensivel
ignorar vazamento em logs
commitar logs reais no repositorio
```

---

## Riscos

| Risco                                                 | Probabilidade | Impacto | Mitigacao                                     |
| ----------------------------------------------------- | ------------- | ------- | --------------------------------------------- |
| Dataset completo ser salvo por engano                 | Media         | Alto    | Funcoes de resumo seguro e testes             |
| Chave de API aparecer em log                          | Baixa/Media   | Alto    | Sanitizacao e testes de segredo               |
| Prompt com dados sensiveis ser auditado integralmente | Media         | Alto    | Registrar apenas prompt_name/version e resumo |
| Debug ficar mais dificil sem payload completo         | Media         | Medio   | Usar hashes, ids e resumos suficientes        |
| Logs reais serem commitados                           | Media         | Alto    | `.gitignore` e regra Cursor                   |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0005 - DataShield Lite antes do Dominion
ADR-0007 - Guardrails em tres camadas
ADR-0009 - DataShield nao envia dataset completo ao LLM
ADR-0011 - Prompts com JSON validado, retry e fallback
```

---

## Observacoes

Auditoria segura nao significa auditoria fraca.

O objetivo e registrar eventos suficientes para explicar o fluxo, sem transformar logs em copia dos dados sensiveis.

Linguagem recomendada:

```text
A auditoria registra eventos, metadados e resumos seguros, sem salvar datasets completos ou segredos.
```

Evitar:

```text
A auditoria guarda todo o state e todos os prompts completos para debug.
```
