# ADR-0002 - LLM Nao Calcula Numeros

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

O projeto Sense to Respond usa LLMs para apoiar analises de S&OE, deteccao de sinais e geracao de proposicoes de acao.

Entretanto, o dominio envolve metricas operacionais e financeiras sensiveis, como:

```text id="axigbf"
demanda real
demanda modelada
desvio percentual
custo modelado
custo DRE
impacto financeiro
urgencia
DOI
risco de ruptura
tendencia
```

Em um contexto corporativo, estes valores precisam ser:

* rastreaveis;
* reproduziveis;
* auditaveis;
* explicaveis;
* calculados de forma deterministica;
* livres de alucinacao numerica.

LLMs podem errar contas, arredondar indevidamente, misturar valores do contexto ou inventar numeros plausiveis. Por isso, o uso do LLM para calculos numericos representa risco de governanca.

---

## Decisao

O projeto adota a regra:

```text id="7yhhwt"
LLM nunca calcula numeros.
```

O LLM pode:

```text id="kuwnzo"
decidir a proxima acao dentro de uma whitelist
classificar intencao
inferir schema semanticamente
gerar explicacao narrativa
auditar coerencia textual
apontar limitacoes
sugerir cautelas
```

O LLM nao pode:

```text id="b7b2av"
calcular impacto financeiro
calcular desvio percentual
calcular DOI
calcular tendencia
calcular custo
calcular severidade numerica
calcular score de prioridade
alterar valores numericos calculados
inventar valores ausentes
usar numeros nao presentes no contexto
```

Todos os numeros usados como evidencia, metrica, impacto, score ou criterio de decisao devem ser calculados por tools deterministicas em Python/pandas ou por outro mecanismo deterministico aprovado na arquitetura.

---

## Alternativas consideradas

### Alternativa A - LLM pode calcular numeros simples

Descricao:

```text id="w5koi0"
Permitir que o LLM calcule desvios, percentuais ou impactos quando a conta for simples.
```

Vantagens:

* implementacao mais rapida;
* menos tools necessarias;
* maior flexibilidade para perguntas ad hoc;
* menor quantidade inicial de codigo.

Desvantagens:

* risco de alucinacao numerica;
* baixa auditabilidade;
* dificuldade de reproducao;
* dificuldade de teste;
* risco de decisoes incorretas;
* fragilidade perante TI, auditoria e governanca.

---

### Alternativa B - LLM calcula, mas Validador revisa

Descricao:

```text id="zqlg03"
Permitir que o LLM calcule e depois usar um validador deterministico para revisar os valores.
```

Vantagens:

* combina flexibilidade do LLM com alguma validacao;
* poderia acelerar prototipos;
* permitiria mais liberdade em analises exploratorias.

Desvantagens:

* duplica logica;
* exige validar todos os numeros gerados pelo LLM;
* aumenta complexidade;
* pode deixar passar erro se validador estiver incompleto;
* incentiva prompts a produzir numeros, contrariando governanca.

---

### Alternativa C - Tools calculam todos os numeros

Descricao:

```text id="ufzvr4"
Somente tools deterministicas calculam metricas, desvios, impactos e scores. O LLM apenas seleciona tools, explica resultados e audita coerencia.
```

Vantagens:

* resultados reproduziveis;
* maior seguranca;
* maior auditabilidade;
* testes objetivos;
* separacao clara de responsabilidades;
* melhor alinhamento com arquitetura corporativa;
* reduz risco de alucinacao numerica.

Desvantagens:

* exige mais codigo;
* exige modelagem de tools;
* menor flexibilidade inicial;
* novas analises exigem novas funcoes deterministicas.

---

## Justificativa

A alternativa escolhida foi:

```text id="vam7x4"
Tools calculam todos os numeros.
```

Essa decisao preserva o principio central:

```text id="d3l8by"
IA = LLM + Harness
```

O LLM atua como componente de raciocinio controlado, interpretacao e auditoria textual, mas nao como calculadora.

Essa separacao e essencial porque o MVP gera proposicoes que podem influenciar decisoes operacionais e financeiras. Portanto, cada valor precisa poder ser rastreado ate:

```text id="i4u9ft"
dado de entrada
tool executada
formula aplicada
resultado produzido
sinal gerado
proposicao associada
auditoria correspondente
```

---

## Consequencias positivas

* Reduz risco de alucinacao numerica.
* Aumenta confianca em metricas e impactos.
* Facilita testes unitarios.
* Facilita auditoria.
* Facilita explicacao para area de TI.
* Melhora separacao entre raciocinio e calculo.
* Permite reproduzir resultados.
* Evita que prompts virem fonte de logica numerica.
* Ajuda a cumprir governanca de IA.
* Torna o Critic mais simples, pois ele audita coerencia e nao recalcula.

---

## Consequencias negativas ou trade-offs

* Mais tools precisam ser implementadas.
* Cada nova metrica exige codigo deterministico.
* Analises exploratorias ficam menos livres.
* O desenvolvimento inicial pode ser mais lento.
* O LLM precisa receber resultados ja calculados.
* Prompts devem ser cuidadosamente redigidos para nao solicitar contas.

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

```text id="fri12l"
Nenhum invariante foi violado. Esta ADR reforca explicitamente o principal invariante numerico do projeto.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [ ] `docs/contracts/state_contract.md`

Impacto:

```text id="8ujdzp"
A arquitetura deve deixar claro que tools deterministicas sao responsaveis por metricas, impactos e valores numericos. Prompts devem ser proibidos de solicitar calculos ao LLM.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `agent.py`
* [x] `tools.py`
* [x] `optimus.py`
* [x] `sinais.py`
* [x] `validator.py`
* [x] `critic.py`
* [x] `guardrails.py`
* [x] `nexus.py`
* [ ] `harness.py`
* [ ] `audit.py`
* [ ] `main.py`
* [ ] novo arquivo

Impacto:

```text id="ab7hrh"
Prompts em agent.py e critic.py devem manter proibicao de calculo numerico. Tools e Optimus devem conter os calculos deterministicos. Validator deve verificar coerencia de impactos e evidencias.
```

Novos arquivos previstos:

```text id="azt9u9"
Nenhum arquivo novo obrigatorio para esta ADR.
```

---

## Impacto em prompts

Prompts afetados:

```text id="vffz7s"
dominion.proximo_passo
final.gerar_explicacao
critic.auditar
datashield.inferir_mapa_semantico
```

Regras:

* Prompt de decisao nao calcula resultado.
* Prompt de explicacao apenas cita numeros fornecidos.
* Prompt de auditoria nao recalcula impacto.
* Prompt de inferencia semantica nao calcula metricas.
* Todo prompt deve reforcar que numeros vem de resultados deterministicos.

---

## Impacto em tools

Toda nova tool numerica deve declarar:

```text id="6b3g7z"
formula ou regra de calculo
entradas numericas
saidas numericas
tratamento de divisao por zero
tratamento de nulos
testes de valores limite
```

Exemplos:

```text id="ckcz6a"
validar_demanda calcula delta_demanda e delta_demanda_pct
validar_custos calcula delta e delta_pct
Optimus calcula impacto_financeiro deterministicamente
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] testes unitarios para tools numericas
* [x] testes de prompts para garantir que nao calculam
* [x] testes de output para garantir que nao inventa numeros
* [x] testes de validator para impacto financeiro
* [x] testes de auditoria para rastreabilidade

Detalhar:

```text id="m33btx"
Toda mudanca que introduza nova metrica deve ter teste deterministico. Toda mudanca de prompt deve ser testada para garantir que o LLM nao gera numeros novos usados como evidencia.
```

---

## Criterios de aceite

* [x] `architecture.md` declara que LLM nunca calcula numeros.
* [x] `rules.md` declara proibicao de calculo numerico pelo LLM.
* [x] `docs/prompts.md` documenta proibicoes por prompt.
* [x] `docs/testing.md` inclui teste de invariante numerico.
* [x] Tools existentes fazem os calculos numericos.
* [x] Validator confere coerencia de impacto.
* [x] Output final usa numeros fornecidos no contexto.
* [x] Prompts nao pedem ao LLM para calcular metricas ou impactos.
* [x] Critic nao recalcula nem altera impactos.

---

## Plano de migracao

Esta decisao ja esta parcialmente refletida no MVP atual.

Para reforcar:

```text id="lugqr6"
1. Revisar prompts em agent.py e critic.py.
2. Garantir que prompts nao solicitam calculo.
3. Garantir que docs/prompts.md registra proibicoes.
4. Garantir que rules.md e .cursor/rules/*.mdc bloqueiam calculo numerico pelo LLM.
5. Criar testes para impedir regressao.
6. Ao adicionar DataShield, garantir que inferencia semantica nao altera valores numericos.
7. Ao expandir Dominion, criar tools deterministicas para DOI, tendencia e desvios.
8. Ao expandir Optimus, manter impacto financeiro deterministico.
```

---

## Plano de rollback

Nao aplicavel como rollback funcional, pois esta decisao e um invariante de seguranca.

Se algum trecho do codigo permitir calculo numerico pelo LLM:

```text id="ocvizt"
1. Remover a instrucao do prompt.
2. Criar tool deterministica correspondente.
3. Atualizar testes.
4. Registrar correcao em agent.log.md.
```

---

## Riscos

| Risco                                      | Probabilidade | Impacto    | Mitigacao                                               |
| ------------------------------------------ | ------------- | ---------- | ------------------------------------------------------- |
| Prompt induzir LLM a calcular numero       | Media         | Alto       | Revisar prompts e testar output                         |
| Explicacao final inventar valor            | Media         | Alto       | Passar apenas resultados calculados e validar linguagem |
| Nova feature implementar calculo no prompt | Media         | Alto       | Regras Cursor + docs/prompts.md                         |
| Tool numerica sem teste                    | Media         | Medio/Alto | docs/testing.md exige testes unitarios                  |
| Optimus futuro usar LLM para impacto       | Media         | Alto       | Bloquear por architecture.md e ADR                      |

---

## Decisoes relacionadas

```text id="qk02x7"
ADR-0001 - Pipeline Sequencial no MVP
ADR-0003 - State blackboard sem conversa livre
ADR-0004 - Critic read-only
ADR-0005 - DataShield Lite antes do Dominion
```

---

## Observacoes

Esta ADR nao impede o LLM de citar numeros.

O LLM pode escrever:

```text id="z5m2id"
"O custo modelado total foi R$ 55.000, conforme resultado calculado pela tool."
```

O LLM nao pode escrever:

```text id="l0ut1i"
"Calculando rapidamente, o impacto seria aproximadamente R$ 18.300."
```

Linguagem recomendada nos prompts:

```text id="e5x76d"
Use apenas numeros fornecidos nos resultados deterministicos. Nao calcule nem estime novos valores.
```
