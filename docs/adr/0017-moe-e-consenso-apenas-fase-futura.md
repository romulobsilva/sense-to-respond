# ADR-0017 - MOE e Consenso Apenas em Fase Futura

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

A arquitetura conceitual do Sense to Respond pode evoluir para um sistema mais dinamico, com recursos como:

```text id="3u8l3a"
MOE router
roteamento dinamico entre agentes
agentes paralelos
consenso multi-agente
debate entre especialistas
votacao de proposicoes
avaliacao cruzada entre agentes
```

Essas capacidades podem ser uteis em fases futuras, especialmente quando o sistema precisar lidar com muitos tipos de perguntas, dados heterogeneos, fontes multiplas e fluxos analiticos mais abertos.

Entretanto, o MVP atual tem foco diferente.

O MVP precisa demonstrar valor com:

```text id="kuqgne"
pipeline sequencial
harness controlado
state blackboard
tools deterministicas
validacao objetiva
Critic read-only
fila Nexus
human-in-the-loop
auditoria
```

Implementar MOE ou consenso no MVP aumentaria complexidade, custo e risco antes de estabilizar a base.

---

## Decisao

MOE router, consenso multi-agente, agentes paralelos autonomos e conversa livre entre agentes ficam fora do MVP.

No MVP, o fluxo permitido e:

```text id="7dxte1"
Input Guardrail
  -> DataShield Lite
  -> Dominion
  -> Sinais estruturados
  -> Optimus
  -> Validador deterministico
  -> Critic LLM read-only
  -> Nexus
  -> Output Guardrail
```

O MVP nao deve implementar:

```text id="f6ytyv"
MOE router dinamico
roteador inteligente de agentes
execucao paralela de agentes
consenso multi-agente
debate entre agentes
votacao entre agentes
rodadas iterativas de deliberacao
agentes conversando livremente
```

Essas capacidades ficam registradas como possibilidades de fase futura, condicionadas a nova ADR, atualizacao de arquitetura, contratos e testes especificos.

---

## Definicoes

### MOE router

Neste projeto, MOE router significa:

```text id="ezyx1d"
um componente que decide dinamicamente quais agentes, tools ou fluxos executar com base na pergunta, no estado e no contexto.
```

Nao confundir com Mixture of Experts neural interno de modelos de linguagem.

Aqui, MOE e usado no sentido arquitetural de roteamento entre especialistas.

---

### Consenso multi-agente

Consenso multi-agente significa:

```text id="lbad48"
mecanismo em que multiplos agentes produzem analises, opinioes ou proposicoes e um protocolo combina, escolhe, revisa ou resolve divergencias entre elas.
```

Pode incluir:

```text id="u8zzly"
votacao
media ponderada
critico coletivo
debate
rodadas de revisao
pontuacao por confianca
```

---

### Agentes paralelos

Agentes paralelos significam:

```text id="8zhz10"
componentes executando simultaneamente ou de forma independente, cada um produzindo resultados que depois precisam ser combinados.
```

---

## Alternativas consideradas

### Alternativa A - Implementar MOE no MVP

Descricao:

```text id="6r52mt"
Criar um roteador dinamico capaz de escolher quais agentes executar para cada pergunta.
```

Vantagens:

* maior flexibilidade;
* melhor adaptacao a perguntas variadas;
* menor execucao desnecessaria;
* arquitetura mais sofisticada.

Desvantagens:

* aumenta complexidade;
* exige contrato de roteamento;
* exige testes combinatorios;
* dificulta auditoria;
* aumenta risco de fluxo inesperado;
* pode executar agentes fora do escopo;
* nao e necessario para demonstrar valor inicial.

---

### Alternativa B - Implementar consenso no MVP

Descricao:

```text id="9e1nbb"
Permitir que varios agentes gerem analises independentes e que uma camada de consenso resolva divergencias.
```

Vantagens:

* pode aumentar robustez;
* permite revisao cruzada;
* reduz dependencia de uma unica analise;
* pode melhorar qualidade em perguntas abertas.

Desvantagens:

* aumenta custo de LLM;
* aumenta latencia;
* exige protocolo formal;
* dificulta rastreabilidade;
* pode gerar conflitos dificeis de explicar;
* pode encobrir origem de evidencias;
* nao substitui validacao deterministica.

---

### Alternativa C - Manter pipeline sequencial no MVP

Descricao:

```text id="og9bfy"
Executar fases especializadas em ordem definida, com state blackboard, validacao deterministica e Critic read-only.
```

Vantagens:

* simples;
* auditavel;
* testavel;
* alinhado a governanca;
* menor custo;
* menor risco;
* suficiente para MVP;
* facilita evolucao incremental.

Desvantagens:

* menos flexivel;
* menos adaptativo;
* nao explora paralelismo;
* nao resolve divergencias por consenso formal.

---

## Justificativa

A alternativa escolhida foi:

```text id="y3m22g"
Manter pipeline sequencial no MVP e deixar MOE/consenso para fase futura.
```

O MVP precisa primeiro estabilizar:

```text id="q3b1ah"
DataShield Lite
Dominion
Optimus
Validador
Critic
Nexus
Guardrails
Auditoria
```

Antes de adicionar dinamismo arquitetural, e necessario garantir que os contratos atuais estejam bem definidos.

MOE e consenso devem ser tratados como evolucao, nao como fundamento do primeiro MVP.

---

## Consequencias positivas

* Reduz complexidade inicial.
* Reduz custo de inferencia.
* Facilita testes.
* Facilita auditoria.
* Evita comportamento emergente.
* Mantem escopo do MVP claro.
* Preserva state blackboard.
* Preserva human-in-the-loop.
* Facilita explicacao para TI e negocio.
* Permite evoluir com seguranca em fase futura.

---

## Consequencias negativas ou trade-offs

* Menor flexibilidade para perguntas muito abertas.
* Fluxo menos adaptativo.
* Sem debate entre agentes no MVP.
* Sem consenso formal.
* Algumas perguntas podem exigir ajuste manual de fluxo.
* A arquitetura pode parecer menos sofisticada no curto prazo.

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

```text id="ccran7"
Nenhum invariante foi violado. Esta ADR reforca que MOE e consenso sao capacidades futuras, nao parte do MVP.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/agent.log.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/testing.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/contracts/tool_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text id="uf1o72"
A arquitetura deve declarar que MOE router, consenso multi-agente e agentes paralelos nao pertencem ao MVP e exigem nova ADR para implementacao futura.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] `nexus.py`
* [x] `harness.py`
* [x] `agent.py`
* [x] `state_types.py`
* [ ] `optimus.py`
* [ ] `validator.py`
* [ ] `critic.py`
* [ ] `tools.py`
* [ ] `main.py`

Arquivos que nao devem ser criados no MVP sem nova ADR:

```text id="codqez"
moe_router.py
consensus.py
multiagent_debate.py
agent_pool.py
parallel_agents.py
voting_layer.py
```

Se algum desses arquivos for criado, deve haver antes:

```text id="5yg7bb"
nova ADR
atualizacao de architecture.md
atualizacao de planning.md
contratos de entrada e saida
testes especificos
aprovacao explicita
```

---

## Impacto em state

No MVP, o state nao deve conter campos como:

```text id="raod99"
agent_votes
agent_debates
consensus_result
moe_route
parallel_agent_outputs
rounds_of_debate
```

Campos permitidos no MVP:

```text id="e5fawp"
sinais
proposicoes
validacao
critica
fila_nexus
handoffs
auditoria
```

Se, em fase futura, MOE ou consenso forem implementados, novos campos de state deverao ser documentados em `docs/contracts/state_contract.md`.

---

## Impacto em prompts

Prompts do MVP nao devem pedir:

```text id="f1hj4d"
debata com outros agentes
simule varios especialistas autonomos
faça consenso
vote entre agentes
rode agentes em paralelo
escolha dinamicamente uma arquitetura
```

Prompts podem mencionar papeis especializados apenas como contexto controlado, desde que a execucao continue no pipeline sequencial.

Exemplo permitido:

```text id="3os1wf"
"Voce e o Critic, auditor read-only das proposicoes."
```

Exemplo proibido:

```text id="jd5z40"
"Converse com os demais agentes ate chegar a um consenso."
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [x] verificar que pipeline e sequencial;
* [x] verificar que nao ha chamada de MOE router;
* [x] verificar que nao ha consenso multi-agente;
* [x] verificar que Critic nao vira consenso;
* [x] verificar que Nexus orquestra fluxo fixo;
* [x] verificar que prompts nao pedem debate entre agentes.

Testes futuros, caso MOE seja implementado:

```text id="2cs0xd"
roteamento por classe de pergunta
bloqueio de agente fora do escopo
auditoria de rota
fallback para pipeline sequencial
custo maximo por rota
```

Testes futuros, caso consenso seja implementado:

```text id="1z4j1i"
protocolo de consenso
divergencia entre agentes
votacao
rastreabilidade de evidencias
limite de rodadas
fallback quando consenso falha
```

---

## Criterios de aceite

* [x] MVP usa pipeline sequencial.
* [x] MOE router nao e implementado.
* [x] Consenso multi-agente nao e implementado.
* [x] Agentes paralelos autonomos nao sao implementados.
* [x] Conversa livre entre agentes nao existe no MVP.
* [x] State blackboard e o mecanismo oficial de comunicacao.
* [x] Critic read-only nao e consenso.
* [x] Qualquer implementacao futura exige nova ADR.

---

## Plano de migracao

Esta ADR reforca o estado atual.

Para aplicar:

```text id="yfx69m"
1. Revisar architecture.md.
2. Revisar planning.md.
3. Garantir que MOE e consenso estejam em fase futura.
4. Garantir que rules.md e .cursor/rules/*.mdc bloqueiem implementacao no MVP.
5. Criar testes simples para ausencia de arquivos ou chamadas de MOE/consenso.
6. Registrar em agent.log.md.
```

---

## Plano de rollback

Se MOE ou consenso forem implementados prematuramente:

```text id="4kivmc"
1. Remover componentes dinamicos do fluxo MVP.
2. Restaurar pipeline sequencial.
3. Converter qualquer resultado gerado em backlog futuro.
4. Atualizar planning.md.
5. Registrar correcao em agent.log.md.
```

Se for necessario estudar MOE sem integrar ao MVP:

```text id="e00qqa"
1. Criar branch experimental.
2. Nao integrar ao fluxo principal.
3. Nao marcar no planning do MVP.
4. Documentar como spike ou pesquisa.
```

---

## Riscos

| Risco                                              | Probabilidade | Impacto     | Mitigacao                                               |
| -------------------------------------------------- | ------------- | ----------- | ------------------------------------------------------- |
| LLM no Cursor implementar MOE por excesso de ajuda | Media         | Alto        | ADR, rules.md e .mdc bloqueando                         |
| Consenso ser confundido com Critic                 | Media         | Medio       | Documentar que Critic e read-only                       |
| Projeto parecer menos multi-agente                 | Media         | Baixo/Medio | Explicar diferenca entre visao conceitual e MVP tecnico |
| Fluxo fixo limitar perguntas abertas               | Media         | Medio       | Planejar classificador de intencao futuro               |
| Adicionar dinamismo sem testes                     | Media         | Alto        | Exigir nova ADR e suite especifica                      |

---

## Decisoes relacionadas

```text id="c7ld2z"
ADR-0001 - Pipeline Sequencial no MVP
ADR-0003 - State blackboard sem conversa livre
ADR-0004 - Critic read-only
ADR-0006 - ToolRegistry como fonte unica das tools
ADR-0016 - Bridge fora do MVP
```

---

## Observacoes

MOE e consenso podem ser valiosos em fases futuras.

Esta ADR nao descarta essas capacidades.

Ela apenas impede que sejam implementadas antes de o MVP sequencial estar estavel, testado e auditavel.

Linguagem recomendada:

```text id="sp5nty"
MOE router e consenso multi-agente sao capacidades futuras. O MVP usa pipeline sequencial governado por harness.
```

Evitar:

```text id="i2rb29"
O MVP usa consenso entre agentes autonomos.
```
