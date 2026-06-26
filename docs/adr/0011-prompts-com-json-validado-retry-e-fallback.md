# ADR-0011 - Prompts com JSON Validado, Retry e Fallback

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

O projeto Sense to Respond utiliza LLMs em pontos controlados do pipeline.

Exemplos atuais ou planejados:

```text
dominion.proximo_passo
critic.auditar
datashield.inferir_mapa_semantico
nexus.classificar_intencao
final.gerar_explicacao
```

Alguns desses prompts precisam retornar saidas estruturadas em JSON para que o harness, o Nexus ou outra etapa consigam agir de forma controlada.

Exemplos:

```json
{
  "acao": "validar_demanda",
  "justificativa": "Os dados ja foram carregados e a demanda precisa ser validada."
}
```

```json
{
  "aprovado": false,
  "confianca": 0.42,
  "problemas": [
    "A proposicao P1 nao esta suficientemente suportada pelos sinais."
  ]
}
```

```json
{
  "classe": "analise_padrao_sense_to_respond",
  "confianca": 0.83,
  "justificativa": "A pergunta solicita analise de sinais e proposicoes."
}
```

O problema e que LLMs podem retornar:

* JSON invalido;
* texto antes ou depois do JSON;
* chaves faltando;
* tipos incorretos;
* valores fora de faixa;
* nomes de tools inexistentes;
* strings onde deveria haver booleano;
* lista onde deveria haver objeto;
* respostas validas sintaticamente, mas invalidas semanticamente.

Sem validacao forte, o sistema poderia executar uma acao errada, aprovar indevidamente uma critica, prosseguir com schema incorreto ou quebrar o pipeline.

---

## Decisao

Todo prompt LLM que retorna saida estruturada deve seguir o padrao:

```text
JSON validado
retry limitado
fallback seguro
auditoria do erro
```

O fluxo obrigatorio e:

```text
1. Chamar LLM.
2. Tentar parsear JSON.
3. Validar schema.
4. Validar tipos.
5. Validar faixas e whitelists.
6. Se falhar, tentar retry limitado.
7. Se ainda falhar, aplicar fallback seguro.
8. Registrar evento de auditoria.
```

Nunca usar diretamente a resposta bruta do LLM como decisao operacional.

Nunca converter valores de forma permissiva quando isso puder mudar o significado.

Exemplo proibido:

```python
aprovado = bool(aprovado_raw)
```

Motivo:

```text
bool("false") retorna True em Python.
```

Exemplo correto:

```python
if not isinstance(aprovado_raw, bool):
    raise ValueError("Campo aprovado deve ser bool real.")
```

---

## Alternativas consideradas

### Alternativa A - Confiar no prompt

Descricao:

```text
Escrever no prompt que o LLM deve responder apenas JSON valido e confiar que ele obedecera.
```

Vantagens:

* simples;
* pouco codigo;
* rapido para prototipo.

Desvantagens:

* LLM pode descumprir;
* nao ha garantia de tipo;
* nao ha garantia de whitelist;
* pode quebrar o harness;
* risco de execucao errada;
* inadequado para MVP governado.

---

### Alternativa B - Parse simples sem retry

Descricao:

```text
Tentar fazer json.loads uma vez e falhar se o JSON estiver invalido.
```

Vantagens:

* mais seguro que confiar apenas no prompt;
* simples;
* evita executar resposta totalmente invalida.

Desvantagens:

* baixa robustez;
* falhas pequenas quebram o fluxo;
* nao recupera respostas corrigiveis;
* nao valida semantica;
* pode aceitar tipos errados.

---

### Alternativa C - JSON validado com retry e fallback

Descricao:

```text
Validar JSON, schema, tipos, whitelists e faixas. Tentar retry limitado quando houver erro. Se falhar, usar fallback seguro.
```

Vantagens:

* robusto;
* auditavel;
* reduz risco de acao indevida;
* preserva controle do harness;
* permite recuperar erros simples;
* protege o pipeline;
* adequado para uso corporativo.

Desvantagens:

* exige mais codigo;
* exige testes;
* exige schemas documentados;
* exige fallback por prompt.

---

## Justificativa

A alternativa escolhida foi:

```text
JSON validado com retry e fallback seguro.
```

Essa decisao preserva o principio:

```text
IA = LLM + Harness
```

O LLM pode sugerir, classificar, inferir ou auditar, mas o harness precisa validar qualquer saida antes de permitir que ela afete o fluxo.

A confiabilidade do sistema nao deve depender apenas da obediencia textual do modelo.

---

## Prompts afetados

### `dominion.proximo_passo`

Saida esperada:

```json
{
  "acao": "carregar_dados",
  "justificativa": "Preciso carregar os dados antes das validacoes."
}
```

Validacoes:

```text
acao deve ser string
justificativa deve ser string
acao deve estar na whitelist da fase ou ser "fim"
acao nao pode ser tool inexistente
acao nao pode estar fora do ToolRegistry
acao nao pode repetir tool se repeatable=False
```

Fallback seguro:

```text
se dados ainda nao foram carregados -> carregar_dados
se dados ja foram carregados e nao ha acao valida -> fim
```

---

### `critic.auditar`

Saida esperada:

```json
{
  "aprovado": false,
  "confianca": 0.42,
  "problemas": [
    "A proposicao P1 nao esta suficientemente suportada pelos sinais."
  ]
}
```

Validacoes:

```text
aprovado deve ser bool real
confianca deve ser int ou float entre 0.0 e 1.0
problemas deve ser list[str]
Critic nao pode retornar proposicoes
Critic nao pode retornar impactos alterados
```

Fallback seguro:

```json
{
  "aprovado": false,
  "confianca": 0.0,
  "problemas": [
    "Critic falhou ao retornar JSON valido."
  ]
}
```

---

### `datashield.inferir_mapa_semantico`

Saida esperada:

```json
{
  "temporal": [],
  "canal": [],
  "produto": [],
  "metricas": [],
  "dimensoes": [],
  "confidence": 0.72,
  "warnings": []
}
```

Validacoes:

```text
campos obrigatorios presentes
confidence entre 0.0 e 1.0
warnings deve ser list[str]
source_column deve existir no DataFrame
canonical_name deve pertencer ao schema canonico permitido
metricas deve ter pelo menos um item para prosseguir
listas devem conter objetos validos
```

Fallback seguro:

```text
bloquear normalizacao automatica
pedir confirmacao ou mapeamento humano
nao executar Dominion sobre arquivo real sem schema confirmado
```

---

### `nexus.classificar_intencao`

Saida esperada:

```json
{
  "classe": "analise_padrao_sense_to_respond",
  "confianca": 0.83,
  "justificativa": "A pergunta solicita analise de sinais e proposicoes."
}
```

Validacoes:

```text
classe deve estar na whitelist
confianca entre 0.0 e 1.0
justificativa deve ser string
classificacao nao pode ativar Bridge
classificacao nao pode ativar MOE dinamico no MVP
```

Fallback seguro:

```text
usar classe "analise_padrao_sense_to_respond" quando entrada for valida e escopo for claro
usar classe "pergunta_fora_escopo" quando houver incerteza relevante
```

---

## Regras gerais de validacao

Toda saida JSON deve validar:

```text
sintaxe JSON
objeto raiz esperado
chaves obrigatorias
ausencia de chaves perigosas
tipos esperados
faixas numericas
whitelists
consistencia com state
consistencia com fase atual
```

Campos numericos devem validar:

```text
tipo int ou float
nao NaN
nao infinito
faixa permitida
```

Campos booleanos devem validar:

```text
tipo bool real
nao aceitar string "true"
nao aceitar string "false"
nao aceitar 0/1 se o contrato exigir bool
```

Campos de lista devem validar:

```text
tipo list
tipo de cada item
lista vazia permitida ou proibida conforme schema
```

Campos de string devem validar:

```text
tipo str
nao vazio quando obrigatorio
tamanho maximo quando aplicavel
valor dentro de whitelist quando aplicavel
```

---

## Retry

O retry deve ser limitado.

Padrao recomendado:

```text
max_retries = 2
```

Retry deve ocorrer quando:

```text
JSON invalido
texto fora do JSON
chaves obrigatorias ausentes
tipo incorreto
valor fora de faixa
acao fora da whitelist
classe fora da whitelist
source_column inexistente
```

Retry nao deve ocorrer indefinidamente.

Retry nao deve alterar os invariantes do projeto.

Retry nao deve permitir que o LLM calcule numeros.

---

## Prompt de retry

Quando houver retry, o prompt deve informar o erro de forma objetiva.

Exemplo:

```text
Sua resposta anterior nao passou na validacao.

Erro:
- Campo "aprovado" deve ser bool real, mas veio como string.

Retorne novamente apenas JSON valido no schema exigido.
Nao inclua texto fora do JSON.
Nao calcule numeros.
Nao crie campos novos.
```

Nao enviar dados adicionais desnecessarios no retry.

Nao ampliar permissao por causa de erro do LLM.

---

## Fallback

Fallback e obrigatorio para prompts estruturados.

O fallback deve ser seguro.

Exemplos de fallback seguro:

```text
encerrar loop com "fim"
marcar Critic como reprovado com confianca 0.0
bloquear DataShield por schema incerto
classificar pergunta como fora de escopo
marcar revisao obrigatoria
```

Exemplos de fallback proibido:

```text
aprovar automaticamente
assumir confidence alta
executar tool nao validada
prosseguir com schema incerto
ignorar erro de JSON
converter string em bool automaticamente
```

---

## Auditoria

Toda falha de JSON deve registrar evento de auditoria.

Eventos recomendados:

```text
llm_json_parse_error
llm_json_schema_error
llm_json_retry
llm_json_fallback
```

Cada evento deve conter:

```text
prompt_name
prompt_version
tentativa
tipo_erro
mensagem_segura
fallback_aplicado
timestamp
```

Nao registrar:

```text
segredos
dataset completo
payload sensivel
conteudo integral se contiver dados reais sensiveis
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/agent.log.md`
* [ ] `docs/contracts/state_contract.md`

Impacto:

```text
A arquitetura deve declarar que saidas estruturadas de LLM nao sao confiaveis ate passarem por validacao, retry e fallback.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `agent.py`
* [x] `critic.py`
* [x] `harness.py`
* [x] `guardrails.py`
* [x] `audit.py`
* [x] `nexus.py`
* [ ] `datashield.py`
* [ ] `datashield_schema.py`
* [ ] `tool_registry.py`

Impacto:

```text
agent.py deve validar resposta de proximo_passo.
critic.py deve validar ResultadoCritica com tipos estritos.
DataShield futuro deve validar mapa semantico.
harness.py deve aplicar retry e fallback quando acao LLM for invalida.
```

---

## Impacto em testes

Testes obrigatorios:

```text
JSON valido
JSON invalido
texto antes/depois do JSON
chaves faltando
tipo incorreto
bool como string
confidence fora de faixa
acao fora da whitelist
classe fora da whitelist
source_column inexistente
retry funcionando
fallback seguro
auditoria de erro
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

* [ ] Todo prompt estruturado tem schema documentado.
* [ ] Todo prompt estruturado tem validacao de JSON.
* [ ] Todo prompt estruturado tem validacao de tipos.
* [ ] Todo prompt estruturado tem validacao de faixas.
* [ ] Todo prompt estruturado tem retry limitado.
* [ ] Todo prompt estruturado tem fallback seguro.
* [ ] Erros de JSON sao auditados.
* [ ] `critic.aprovado` exige bool real.
* [ ] `dominion.proximo_passo` rejeita tool fora da whitelist.
* [ ] `datashield.inferir_mapa_semantico` bloqueia schema invalido.
* [ ] Testes minimos passam.

---

## Plano de migracao

Implementar em etapas:

```text
1. Criar helpers de parse e validacao JSON.
2. Aplicar primeiro ao Critic.
3. Corrigir parsing de booleano do Critic.
4. Aplicar ao `AgenteOpenAI.proximo_passo`.
5. Integrar com auditoria.
6. Criar testes de JSON valido/invalido.
7. Aplicar o mesmo padrao ao DataShield quando for implementado.
8. Atualizar docs/prompts.md.
9. Atualizar docs/testing.md.
10. Registrar em docs/agent.log.md.
```

---

## Plano de rollback

Se a validacao nova quebrar comportamento existente:

```text
1. Manter validacao estrita.
2. Ajustar prompt ou schema.
3. Nao voltar para parsing permissivo.
4. Usar fallback seguro temporario.
5. Registrar implementacao parcial no agent.log.md.
```

Rollback proibido:

```text
remover validacao
aceitar bool como string
aceitar tool fora da whitelist
prosseguir com JSON invalido
```

---

## Riscos

| Risco                             | Probabilidade | Impacto     | Mitigacao                        |
| --------------------------------- | ------------- | ----------- | -------------------------------- |
| LLM retornar JSON invalido        | Alta          | Medio       | Retry limitado e fallback        |
| String "false" virar True         | Media         | Alto        | Validacao de bool real           |
| Tool fora da whitelist ser aceita | Media         | Alto        | Validacao contra ToolRegistry    |
| Confidence fora de faixa passar   | Media         | Medio       | Validar 0.0 <= confidence <= 1.0 |
| Retry aumentar custo              | Media         | Baixo/Medio | Limitar max_retries              |
| Fallback permissivo demais        | Media         | Alto        | Fallback sempre conservador      |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0004 - Critic read-only
ADR-0006 - ToolRegistry como fonte unica das tools
ADR-0007 - Guardrails em tres camadas
ADR-0009 - DataShield nao envia dataset completo ao LLM
```

---

## Observacoes

JSON valido sintaticamente nao significa JSON confiavel.

Exemplo de JSON sintaticamente valido, mas semanticamente invalido:

```json
{
  "aprovado": "false",
  "confianca": 1.7,
  "problemas": "nenhum"
}
```

Esse caso deve falhar.

Linguagem recomendada:

```text
Toda saida estruturada de LLM deve ser validada antes de afetar o state ou o fluxo.
```

Evitar:

```text
O prompt garante que o modelo sempre retornara JSON correto.
```
