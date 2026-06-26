# ADR-0004 - Critic Read-Only

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

O pipeline do Sense to Respond gera proposicoes de acao a partir de sinais estruturados.

No MVP, a cadeia principal e:

```text id="d0g9h4"
Dominion -> Sinais -> Optimus -> Validador -> Critic -> Nexus
```

O Optimus transforma sinais em proposicoes priorizadas.

O Validador verifica deterministicamente se as proposicoes respeitam regras objetivas, como:

```text id="ksu3u4"
tipo permitido
evidencias existentes
impacto coerente
urgencia valida
SKU/canal coerentes
```

Ainda assim, existe valor em ter uma avaliacao qualitativa por LLM para verificar:

* exageros na descricao;
* incoerencia narrativa;
* baixa aderencia entre sinal e proposicao;
* problemas de explicabilidade;
* ausencia de cautela;
* afirmacoes fortes demais;
* risco de overclaiming.

Esse papel e atribuido ao Critic.

Entretanto, se o Critic pudesse criar, alterar ou aprovar proposicoes livremente, ele quebraria os invariantes do MVP, especialmente:

```text id="u1m9wb"
LLM nao calcula numeros
human-in-the-loop obrigatorio
state blackboard controlado
tools deterministicas calculam metricas
```

---

## Decisao

O Critic deve ser **read-only**.

O Critic pode:

```text id="y9xx4p"
ler sinais
ler proposicoes
avaliar coerencia textual
avaliar aderencia entre sinal e proposicao
apontar problemas
atribuir confianca
aprovar ou reprovar a consistencia geral
```

O Critic nao pode:

```text id="6s8d03"
criar proposicoes
alterar proposicoes
alterar sinais
alterar resultados numericos
alterar impacto financeiro
calcular novos valores
corrigir proposicoes silenciosamente
aprovar execucao operacional
remover human-in-the-loop
```

A saida do Critic deve ser JSON estruturado e validado:

```json id="q03wpg"
{
  "aprovado": false,
  "confianca": 0.42,
  "problemas": [
    "A proposicao P1 nao esta suficientemente suportada pelos sinais informados."
  ]
}
```

---

## Alternativas consideradas

### Alternativa A - Critic read-only

Descricao:

```text id="uyv97a"
Critic audita sinais e proposicoes, mas nao altera o state numerico nem cria novas proposicoes.
```

Vantagens:

* preserva governanca;
* reduz risco de alucinacao;
* facilita testes;
* mantem responsabilidade do Optimus clara;
* evita calculo numerico por LLM;
* facilita auditoria;
* permite bloquear ou marcar revisao sem alterar evidencias.

Desvantagens:

* Critic nao corrige automaticamente problemas simples;
* pode exigir retry do Optimus;
* pode gerar mais itens com revisao obrigatoria;
* exige que Nexus interprete corretamente baixa confianca.

---

### Alternativa B - Critic corrige proposicoes

Descricao:

```text id="hxk4gq"
Critic poderia editar proposicoes existentes para corrigir inconsistencias.
```

Vantagens:

* poderia melhorar qualidade textual;
* poderia reduzir necessidade de retry;
* poderia corrigir problemas simples rapidamente.

Desvantagens:

* mistura responsabilidades;
* dificulta rastrear origem da proposicao;
* aumenta risco de alterar impacto ou evidencia;
* pode introduzir alucinacao;
* dificulta testes;
* enfraquece papel do Validador e do Optimus.

---

### Alternativa C - Critic gera proposicoes alternativas

Descricao:

```text id="s6v29d"
Critic poderia sugerir novas proposicoes quando encontrar falhas nas existentes.
```

Vantagens:

* aumenta flexibilidade;
* pode produzir boas alternativas;
* pode enriquecer resposta final.

Desvantagens:

* transforma Critic em segundo Optimus;
* aumenta complexidade;
* pode gerar proposicoes sem calculo deterministico;
* pode violar whitelist de decisoes;
* dificulta validacao;
* aumenta risco de divergencia entre agentes.

---

### Alternativa D - Sem Critic

Descricao:

```text id="gzaewb"
Usar apenas Validador deterministico e remover Critic do MVP.
```

Vantagens:

* menor custo;
* menor complexidade;
* menos dependencia de LLM;
* comportamento mais previsivel.

Desvantagens:

* perde avaliacao qualitativa;
* perde deteccao de overclaiming textual;
* perde checagem semantica entre sinais e proposicoes;
* reduz qualidade da resposta final;
* pode deixar passar problemas que nao sao puramente estruturais.

---

## Justificativa

A alternativa escolhida foi:

```text id="qbfkap"
Critic read-only
```

Essa decisao equilibra seguranca e qualidade.

O Validador deterministico cobre regras objetivas.

O Critic adiciona uma camada qualitativa, mas sem poder alterar o estado decisorio.

Assim, o Critic funciona como auditor semantico, nao como executor nem gerador.

Essa separacao preserva o principio:

```text id="95g5ip"
IA = LLM + Harness
```

Tambem preserva o fluxo:

```text id="f1agni"
Optimus propoe
Validador verifica
Critic audita
Nexus prioriza
Humano decide
```

---

## Consequencias positivas

* Mantem o papel do Critic claro.
* Reduz risco de alucinacao.
* Evita que o LLM altere numeros.
* Preserva rastreabilidade entre sinais e proposicoes.
* Facilita testes de schema JSON.
* Facilita auditoria.
* Permite fallback seguro se Critic falhar.
* Permite marcar revisao obrigatoria quando confianca e baixa.
* Evita que Critic vire um segundo gerador de decisoes.
* Preserva human-in-the-loop.

---

## Consequencias negativas ou trade-offs

* Critic nao corrige problemas automaticamente.
* Problemas encontrados podem exigir retry do Optimus.
* Pode aumentar quantidade de itens em revisao obrigatoria.
* Exige que Nexus interprete critic corretamente.
* Exige validacao rigorosa da saida JSON.
* Exige fallback seguro quando o LLM falha.

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

```text id="qgo21m"
Nenhum invariante foi violado. Esta ADR formaliza o Critic como auditor read-only.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `docs/prompts.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`

Impacto:

```text id="49i0l4"
A arquitetura deve deixar claro que Critic e uma etapa de auditoria semantica read-only, posterior ao Validador e anterior ao Nexus.
```

---

## Impacto em codigo

Arquivos ou componentes afetados:

* [x] `critic.py`
* [x] `nexus.py`
* [x] `validator.py`
* [x] `optimus.py`
* [x] `state_types.py`
* [x] `guardrails.py`
* [x] `audit.py`
* [ ] `agent.py`
* [ ] `harness.py`
* [ ] `main.py`

Impacto:

```text id="3s2q3c"
critic.py deve validar JSON de saida, garantir tipos estritos e retornar apenas ResultadoCritica. Nexus deve usar a critica para revisao obrigatoria, retry controlado ou marcacao de confianca, nunca para executar acao.
```

Novos arquivos previstos:

```text id="vpkw8q"
Nenhum arquivo novo obrigatorio para esta ADR.
```

---

## Impacto em prompts

Prompt afetado:

```text id="j9lqlj"
critic.auditar
```

O prompt deve instruir o LLM a:

```text id="0syzu8"
auditar coerencia
avaliar suporte dos sinais
apontar problemas
retornar JSON
nao criar proposicoes
nao alterar impacto
nao calcular numeros
nao aprovar execucao operacional
```

Saida obrigatoria:

```json id="av004e"
{
  "aprovado": true,
  "confianca": 0.85,
  "problemas": []
}
```

Regras de validacao:

```text id="dwcqac"
aprovado deve ser bool real
confianca deve ser float entre 0.0 e 1.0
problemas deve ser list[str]
json_bruto pode ser armazenado para auditoria segura
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] teste de JSON valido aprovado
* [x] teste de JSON valido reprovado
* [x] teste de JSON invalido
* [x] teste de `aprovado` como string
* [x] teste de `confianca` fora de faixa
* [x] teste de `problemas` nao lista
* [x] teste de retry
* [x] teste de fallback
* [x] teste garantindo que Critic nao altera proposicoes

Detalhar:

```text id="uq4ulz"
A validacao deve rejeitar `aprovado` quando vier como string, por exemplo "false". Nao usar bool("false"), pois isso retorna True em Python.
```

---

## Criterios de aceite

* [x] Critic recebe sinais e proposicoes.
* [x] Critic retorna apenas `aprovado`, `confianca`, `problemas` e `json_bruto`, quando aplicavel.
* [x] Critic nao cria proposicoes.
* [x] Critic nao altera sinais.
* [x] Critic nao altera impacto financeiro.
* [x] Critic nao calcula numeros.
* [x] Critic possui fallback seguro.
* [x] Critic falho nao bloqueia pipeline sem sinalizar revisao.
* [x] Nexus usa baixa confianca para revisao obrigatoria.
* [x] Output final nao transforma critica em execucao.

---

## Plano de migracao

Para reforcar esta decisao:

```text id="m0bu03"
1. Revisar `critic.py`.
2. Corrigir parsing de `aprovado` para exigir bool real.
3. Validar `confianca` entre 0.0 e 1.0.
4. Validar `problemas` como list[str].
5. Garantir fallback com aprovado=False e confianca=0.0.
6. Garantir que Critic nao retorna proposicoes.
7. Criar testes de JSON valido, invalido e tipos errados.
8. Atualizar docs/prompts.md e docs/testing.md.
9. Registrar mudanca em agent.log.md.
```

---

## Plano de rollback

Se algum desenvolvimento permitir que Critic altere proposicoes:

```text id="klp0zp"
1. Remover alteracao direta de proposicoes.
2. Fazer Critic retornar apenas problemas.
3. Enviar problemas ao Nexus ou Optimus como feedback para retry controlado.
4. Revalidar proposicoes com Validador.
5. Registrar correcao em agent.log.md.
```

Se Critic falhar em producao ou ambiente de teste:

```text id="bpae8s"
1. Usar fallback seguro.
2. Marcar revisao obrigatoria.
3. Manter proposicoes sem execucao automatica.
4. Registrar falha em auditoria.
```

---

## Riscos

| Risco                                        | Probabilidade | Impacto    | Mitigacao                                   |
| -------------------------------------------- | ------------- | ---------- | ------------------------------------------- |
| Critic retornar JSON invalido                | Media         | Medio      | Retry limitado e fallback seguro            |
| Critic aprovar indevidamente                 | Media         | Medio/Alto | Validador deterministico antes do Critic    |
| Critic gerar sugestoes fora do schema        | Media         | Medio      | Validacao estrita de schema                 |
| `aprovado` string ser interpretado como True | Media         | Alto       | Exigir bool real, nunca usar `bool(string)` |
| Critic alterar proposicoes no futuro         | Baixa/Media   | Alto       | Testes e regras Cursor bloqueando           |

---

## Decisoes relacionadas

```text id="j8kqa7"
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard sem conversa livre
ADR-0005 - DataShield Lite antes do Dominion
```

---

## Observacoes

O Critic nao substitui o Validador.

A ordem correta e:

```text id="0rqkuz"
Validador deterministico primeiro
Critic LLM read-only depois
```

O Validador verifica regras objetivas.

O Critic avalia coerencia semantica e qualidade narrativa.

Linguagem recomendada:

```text id="z33zgs"
O Critic atua como auditor semantico read-only das proposicoes.
```

Evitar:

```text id="n7ivbi"
O Critic ajusta ou corrige as proposicoes finais.
```
