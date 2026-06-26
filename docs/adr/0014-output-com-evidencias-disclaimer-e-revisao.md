# ADR-0014 - Output com Evidencias, Disclaimer e Revisao

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

O Sense to Respond gera proposicoes de acao a partir de sinais estruturados.

O fluxo do MVP termina em uma resposta ao usuario e em uma fila Nexus para revisao humana.

Essa resposta final pode conter:

```text
achados principais
sinais detectados
proposicoes priorizadas
impactos financeiros
urgencia
limitacoes
confianca
motivos de revisao
```

Como essas informacoes podem influenciar decisoes comerciais e operacionais, a resposta final precisa ser controlada.

Riscos do output:

```text
omitir evidencias
afirmar execucao automatica
remover disclaimer
nao sinalizar baixa confianca
nao informar validacao falha
transformar proposicao em ordem
exagerar causalidade
esconder limitacoes dos dados
```

Por isso, o output final nao deve ser apenas uma resposta livre do LLM.

Ele deve passar por output guardrail.

---

## Decisao

Toda resposta final do MVP deve conter, quando aplicavel:

```text
evidencias
disclaimer
status de revisao humana
limitacoes
sinais de baixa confianca
motivos de revisao obrigatoria
```

A resposta final deve deixar claro que:

```text
as proposicoes sao candidatas
nenhuma acao operacional foi executada automaticamente
a decisao final cabe ao usuario humano
os resultados dependem dos dados disponiveis
```

O output guardrail deve ser aplicado depois da geracao textual do LLM e antes da resposta ao usuario.

---

## Regra operacional

Fluxo recomendado:

```text
1. Nexus monta fila de proposicoes.
2. Validador informa se proposicoes sao estruturalmente validas.
3. Critic informa aprovacao, confianca e problemas.
4. LLM gera explicacao usando apenas resultados calculados.
5. Output Guardrail revisa e complementa a resposta.
6. Resposta final inclui disclaimer, evidencias e revisao quando necessario.
```

O LLM pode gerar a narrativa.

O Output Guardrail deve garantir os elementos obrigatorios.

---

## Elementos obrigatorios do output

### 1. Disclaimer

Toda resposta final deve conter disclaimer.

Exemplo:

```text
Aviso: estas proposicoes sao recomendacoes candidatas para revisao humana. Nenhuma acao operacional foi executada automaticamente.
```

---

### 2. Evidencias

Toda proposicao deve apontar para sinais ou resultados que a sustentam.

Exemplo:

```text
Evidencias: S1, S3
```

ou:

```text
Baseado nos sinais de desvio de demanda e custo modelado identificados pelo Dominion.
```

Regra:

```text
Nao apresentar proposicao sem evidencia rastreavel.
```

---

### 3. Revisao obrigatoria

A resposta deve sinalizar revisao obrigatoria quando houver:

```text
Critic reprovado
Critic com baixa confianca
Validador deterministico com erro
proposicao de alto impacto
dados insuficientes
schema DataShield nao confirmado
analise pulada por ausencia de coluna
proposicao sem evidencia suficiente
```

Exemplo:

```text
[REVISAO OBRIGATORIA] Esta proposicao exige avaliacao humana antes de qualquer acao.
```

---

### 4. Limitacoes

A resposta deve informar limitacoes relevantes.

Exemplos:

```text
A analise de ruptura nao foi executada porque o dataset nao possui estoque_atual ou doi_atual.
```

```text
O mapeamento semantico teve confianca baixa e requer confirmacao.
```

```text
As conclusoes dependem dos dados carregados nesta execucao.
```

---

### 5. Linguagem de proposicao

A resposta deve usar linguagem de apoio a decisao.

Permitido:

```text
recomenda-se avaliar
proposicao candidata
sugere-se revisar
item para aprovacao humana
prioridade sugerida
```

Proibido:

```text
acao executada
pedido criado
estoque ajustado
forecast alterado
promocao protegida automaticamente
decisao aplicada
```

---

## Alternativas consideradas

### Alternativa A - Resposta livre do LLM

Descricao:

```text
Permitir que o LLM gere a resposta final sem camada adicional de output guardrail.
```

Vantagens:

* implementacao simples;
* texto mais natural;
* menor quantidade de codigo.

Desvantagens:

* risco de omitir disclaimer;
* risco de afirmar execucao;
* risco de esconder baixa confianca;
* risco de overclaiming;
* risco de perder evidencias;
* inadequado para ambiente corporativo.

---

### Alternativa B - Resposta totalmente templateada

Descricao:

```text
Gerar a resposta final apenas por template deterministico, sem LLM.
```

Vantagens:

* maxima previsibilidade;
* facil de testar;
* baixo risco de linguagem indevida.

Desvantagens:

* texto menos natural;
* menor capacidade explicativa;
* menor adaptabilidade;
* pode reduzir valor percebido pelo usuario.

---

### Alternativa C - LLM gera narrativa e Output Guardrail aplica controles

Descricao:

```text
LLM gera explicacao com base em resultados deterministicos. Output Guardrail garante disclaimer, evidencias, revisao e linguagem segura.
```

Vantagens:

* combina clareza textual com controle;
* preserva governanca;
* reduz risco de resposta indevida;
* permite narrativa compreensivel;
* mantem human-in-the-loop;
* facilita testes dos elementos obrigatorios.

Desvantagens:

* exige camada adicional;
* exige testes de output;
* pode adicionar redundancia no texto;
* exige manutencao de regras de linguagem.

---

## Justificativa

A alternativa escolhida foi:

```text
LLM gera narrativa e Output Guardrail aplica controles.
```

Essa decisao preserva o principio:

```text
IA = LLM + Harness
```

O LLM pode explicar os achados, mas a resposta final precisa obedecer regras de seguranca, governanca e rastreabilidade.

A resposta final e parte do sistema de controle, nao apenas uma mensagem estetica.

---

## Consequencias positivas

* Reduz risco de overclaiming.
* Reduz risco de afirmar execucao automatica.
* Mantem human-in-the-loop visivel.
* Aumenta rastreabilidade das proposicoes.
* Ajuda o usuario a entender evidencias.
* Ajuda a comunicar limitacoes dos dados.
* Facilita auditoria.
* Facilita testes de regressao de linguagem.
* Melhora alinhamento com governanca corporativa.

---

## Consequencias negativas ou trade-offs

* Respostas podem ficar mais longas.
* Pode haver repeticao de disclaimer.
* Exige testes especificos.
* Exige manutencao das regras de output.
* Pode reduzir naturalidade em alguns casos.
* Pode exigir formatacao consistente na UI.

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

```text
Nenhum invariante foi violado. Esta ADR reforca human-in-the-loop, evidencias e output seguro.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/testing.md`
* [x] `docs/prompts.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/agent.log.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`

Impacto:

```text
A arquitetura deve declarar que a resposta final passa por Output Guardrail antes de ser apresentada ao usuario.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `guardrails.py`
* [x] `nexus.py`
* [x] `agent.py`
* [x] `critic.py`
* [x] `validator.py`
* [x] `state_types.py`
* [x] `main.py`
* [ ] `audit.py`
* [ ] `optimus.py`
* [ ] `sinais.py`

Impacto:

```text
guardrails.py deve garantir disclaimer, revisao obrigatoria e linguagem segura. Nexus deve fornecer contexto de validacao, critic e evidencias para o output.
```

---

## Impacto em prompts

Prompt afetado:

```text
final.gerar_explicacao
```

O prompt pode gerar:

```text
explicacao dos achados
interpretacao dos sinais
resumo das proposicoes
limitacoes conhecidas
```

O prompt nao pode:

```text
afirmar execucao operacional
criar numero novo
remover disclaimer
omitir baixa confianca
apagar revisao obrigatoria
alterar impacto financeiro
```

Mesmo que o prompt falhe, o Output Guardrail deve corrigir a resposta final quando possivel ou marcar revisao.

---

## Impacto em state

Campos usados pelo output:

```text
pergunta
resultados
sinais
proposicoes
validacao
critica
fila_nexus
handoffs
limitacoes_dados
analises_puladas
```

Regras:

* output deve usar evidencias existentes;
* output nao deve criar novas proposicoes;
* output nao deve alterar sinais;
* output nao deve alterar impactos;
* output pode anexar disclaimer e flags.

---

## Impacto em auditoria

Registrar evento:

```text
output_guardrail_aplicado
```

Metadados seguros recomendados:

```text
disclaimer_adicionado
revisao_obrigatoria
motivos_revisao
qtd_proposicoes
qtd_evidencias
critic_confianca
validator_ok
```

Nao registrar:

```text
dataset completo
prompt completo com dados sensiveis
segredos
```

---

## Impacto em testes

Testes exigidos:

* [x] output contem disclaimer;
* [x] output nao afirma execucao automatica;
* [x] output marca revisao obrigatoria quando Critic tem baixa confianca;
* [x] output marca revisao obrigatoria quando Validator falha;
* [x] output inclui evidencias de proposicoes;
* [x] output menciona limitacoes quando analises forem puladas;
* [x] output nao inventa numeros;
* [x] output nao remove human-in-the-loop;
* [x] auditoria registra output_guardrail_aplicado.

Comandos minimos:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

---

## Criterios de aceite

* [ ] Output Guardrail adiciona disclaimer.
* [ ] Output Guardrail preserva evidencias.
* [ ] Output Guardrail sinaliza revisao obrigatoria.
* [ ] Output final nao afirma execucao.
* [ ] Output final menciona limitacoes relevantes.
* [ ] Output final nao inventa numeros.
* [ ] Output final respeita human-in-the-loop.
* [ ] Testes de output passam.
* [ ] Auditoria registra aplicacao do output guardrail.

---

## Plano de migracao

Para reforcar esta ADR:

```text
1. Revisar `guardrails.py`.
2. Garantir disclaimer obrigatorio.
3. Criar funcao para detectar linguagem de execucao.
4. Criar funcao para anexar revisao obrigatoria.
5. Garantir que evidencias sejam incluidas.
6. Integrar validacao e critic ao output.
7. Criar testes de output.
8. Rodar E2E Nexus.
9. Registrar em agent.log.md.
```

---

## Plano de rollback

Nao ha rollback desejado para remover output guardrail.

Se a regra ficar restritiva demais:

```text
1. Ajustar a regra especifica.
2. Manter disclaimer.
3. Manter human-in-the-loop.
4. Manter revisao obrigatoria quando necessario.
5. Criar teste de regressao.
```

Rollback proibido:

```text
remover disclaimer
permitir output sem evidencias
permitir afirmacao de execucao automatica
ocultar revisao obrigatoria
```

---

## Riscos

| Risco                              | Probabilidade | Impacto    | Mitigacao                                    |
| ---------------------------------- | ------------- | ---------- | -------------------------------------------- |
| LLM afirmar execucao               | Media         | Alto       | Output guardrail e testes de linguagem       |
| Disclaimer ser omitido             | Media         | Medio/Alto | Regra obrigatoria no guardrail               |
| Evidencias nao aparecerem          | Media         | Medio      | Validator e teste de evidencias              |
| Baixa confianca nao ser sinalizada | Media         | Alto       | Nexus passa critic para output               |
| Output ficar longo demais          | Media         | Baixo      | Criar formato resumido com evidencias claras |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0004 - Critic read-only
ADR-0007 - Guardrails em tres camadas
ADR-0008 - Human-in-the-loop obrigatorio no MVP
ADR-0012 - Auditoria sem dados sensiveis
ADR-0013 - Dominion executa apenas analises compativeis com os dados
```

---

## Observacoes

O output final e uma interface de governanca.

Ele deve ser claro, util e seguro.

Linguagem recomendada:

```text
A resposta final apresenta proposicoes candidatas, evidencias, limitacoes e necessidade de revisao humana.
```

Evitar:

```text
A resposta final confirma que as acoes foram executadas.
```
