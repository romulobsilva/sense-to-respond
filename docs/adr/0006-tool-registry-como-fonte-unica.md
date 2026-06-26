# ADR-0006 - ToolRegistry como Fonte Unica das Tools

---

## Status

Proposto

---

## Data

2026-06-25

---

## Responsavel

7D Analytics / Agente IA de desenvolvimento

---

## Contexto

O MVP atual do Sense to Respond usa tools deterministicas para executar calculos e validacoes.

No desenho arquitetural do projeto, o LLM pode escolher a proxima acao, mas apenas dentro de uma lista controlada pelo harness.

Esse padrao preserva o principio:

```text
IA = LLM + Harness
```

Entretanto, existe risco de duplicacao e divergencia se a lista de tools autorizadas aparecer em mais de um lugar, por exemplo:

```text
agent.py
tools.py
harness.py
prompts
documentacao
testes
```

Quando a whitelist de tools fica duplicada, podem surgir problemas:

* o prompt oferece uma tool que o harness nao executa;
* o harness aceita uma tool que nao aparece no prompt;
* uma tool nova e criada, mas nao e documentada;
* uma tool antiga e removida do codigo, mas continua no prompt;
* uma tool repetivel nao e marcada corretamente;
* uma tool de risco alto pode ser chamada sem controle;
* testes ficam inconsistentes com a arquitetura.

Para evitar drift entre codigo, prompt e documentacao, o projeto deve evoluir para uma fonte unica de verdade das tools.

---

## Decisao

Criar um arquivo dedicado:

```text
tool_registry.py
```

Esse arquivo deve conter o registro oficial das tools disponiveis no projeto.

O ToolRegistry deve ser usado por:

```text
agent.py
harness.py
tools.py
datashield.py
nexus.py
testes
prompts dinamicos ou validadores de prompt
```

O ToolRegistry deve responder perguntas como:

```text
quais tools existem?
qual fase pode usar cada tool?
qual funcao Python executa a tool?
quais campos do state a tool requer?
quais campos do state a tool produz?
a tool pode repetir?
qual o nivel de risco?
a tool exige confirmacao humana?
a tool exige auditoria?
```

O LLM nunca deve conseguir chamar uma tool que nao esteja registrada.

---

## Alternativas consideradas

### Alternativa A - Manter listas duplicadas

Descricao:

```text
Cada arquivo mantem sua propria lista de tools validas.
```

Vantagens:

* implementacao imediata;
* menos refatoracao inicial;
* facil para MVP muito pequeno.

Desvantagens:

* alto risco de divergencia;
* dificil auditar permissoes;
* prompt pode ficar desalinhado do harness;
* dificulta adicionar DataShield Lite;
* dificulta testes;
* aumenta chance de chamada indevida.

---

### Alternativa B - Whitelist apenas no harness

Descricao:

```text
O harness possui a lista oficial de tools permitidas. Outros arquivos consultam ou duplicam essa lista.
```

Vantagens:

* centraliza execucao;
* reduz risco em relacao a listas totalmente soltas;
* mantem controle no componente correto.

Desvantagens:

* harness fica com responsabilidade demais;
* prompt ainda pode ficar desalinhado;
* metadados da tool ficam espalhados;
* dificulta documentar fase, risco e contratos.

---

### Alternativa C - ToolRegistry como fonte unica

Descricao:

```text
Um registry central declara todas as tools, suas fases, riscos, entradas, saidas e permissoes. Harness e prompts consultam esse registry.
```

Vantagens:

* fonte unica de verdade;
* reduz drift;
* facilita testes;
* facilita auditoria;
* facilita evolucao para DataShield;
* facilita bloqueio de tools por fase;
* melhora explicabilidade do harness;
* facilita gerar descricoes para prompts;
* prepara arquitetura para features futuras.

Desvantagens:

* exige refatoracao;
* exige criar contrato formal;
* exige migrar listas existentes;
* pode parecer excesso para MVP pequeno.

---

## Justificativa

A alternativa escolhida foi:

```text
ToolRegistry como fonte unica.
```

Essa decisao melhora governanca sem transformar o MVP em uma arquitetura complexa.

O ToolRegistry nao torna o sistema mais autonomo. Ele torna o sistema mais controlado.

A ideia central e:

```text
LLM escolhe acao
Harness valida permissao
ToolRegistry define o que existe e o que e permitido
Tool executa calculo deterministico
Auditoria registra
```

Isso preserva os invariantes:

```text
LLM nao calcula numeros
harness controla ferramentas
tools sao deterministicas
execucao e auditavel
human-in-the-loop permanece obrigatorio
```

---

## Estrutura proposta

Criar `tool_registry.py` com uma estrutura como:

```python
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    phase: str
    kind: str
    function_name: str
    required_state_keys: tuple[str, ...]
    produced_state_keys: tuple[str, ...]
    repeatable: bool
    risk_level: str
    requires_human_confirmation: bool
    audit_required: bool
```

Campos obrigatorios:

| Campo                         | Descricao                          |
| ----------------------------- | ---------------------------------- |
| `name`                        | Nome usado pelo LLM e pelo harness |
| `description`                 | Descricao curta da tool            |
| `phase`                       | Fase autorizada                    |
| `kind`                        | Tipo da tool                       |
| `function_name`               | Nome da funcao Python              |
| `required_state_keys`         | Campos exigidos do state           |
| `produced_state_keys`         | Campos produzidos                  |
| `repeatable`                  | Se pode repetir na mesma sessao    |
| `risk_level`                  | `low`, `medium` ou `high`          |
| `requires_human_confirmation` | Se precisa confirmacao humana      |
| `audit_required`              | Se execucao precisa auditoria      |

---

## Fases reconhecidas

O registry deve reconhecer inicialmente:

```text
datashield
dominion
optimus
validator
critic
nexus
output
```

No MVP atual, as principais tools estao em `dominion`.

Com DataShield Lite, novas tools devem ser registradas em `datashield`.

---

## Tipos de tools reconhecidos

Tipos permitidos:

```text
deterministic_tool
llm_tool
io_tool
audit_tool
```

### deterministic_tool

Pode calcular metricas e impactos.

Nao pode chamar LLM.

Exemplos:

```text
validar_demanda
validar_custos
analisar_desvio_plano
analisar_tendencia
```

### llm_tool

Pode chamar LLM para tarefas nao numericas.

Nao pode calcular metricas.

Exemplos:

```text
inferir_mapa_semantico
classificar_intencao
```

### io_tool

Pode ler ou gravar arquivos autorizados.

Exemplos:

```text
ler_arquivo
salvar_template_mapeamento
carregar_template_mapeamento
```

### audit_tool

Pode registrar ou processar eventos de auditoria.

Exemplos:

```text
registrar_evento
salvar_auditoria_json
```

---

## API minima do ToolRegistry

O arquivo `tool_registry.py` deve fornecer funcoes como:

```python
def listar_tools() -> list[ToolSpec]:
    ...


def listar_tools_por_fase(phase: str) -> list[ToolSpec]:
    ...


def obter_tool(name: str) -> ToolSpec:
    ...


def tool_existe(name: str) -> bool:
    ...


def validar_tool_na_fase(name: str, phase: str) -> bool:
    ...


def pode_repetir(name: str) -> bool:
    ...


def listar_nomes_por_fase(phase: str) -> list[str]:
    ...


def gerar_descricao_para_prompt(phase: str) -> str:
    ...
```

Essas funcoes permitem que:

* o prompt apresente apenas tools validas;
* o harness valide a acao escolhida;
* testes verifiquem consistencia;
* documentacao seja mantida alinhada;
* novas fases sejam adicionadas com controle.

---

## Tools atuais a registrar

Registrar inicialmente:

```text
carregar_dados
validar_demanda
validar_custos
```

Exemplo conceitual:

```python
ToolSpec(
    name="carregar_dados",
    description="Carrega dados simulados ou pre-estruturados no state.",
    phase="dominion",
    kind="deterministic_tool",
    function_name="carregar_dados",
    required_state_keys=(),
    produced_state_keys=("dados",),
    repeatable=False,
    risk_level="low",
    requires_human_confirmation=False,
    audit_required=True,
)
```

```python
ToolSpec(
    name="validar_demanda",
    description="Compara demanda baseline e modelada de forma deterministica.",
    phase="dominion",
    kind="deterministic_tool",
    function_name="validar_demanda",
    required_state_keys=("dados",),
    produced_state_keys=("resultados",),
    repeatable=False,
    risk_level="low",
    requires_human_confirmation=False,
    audit_required=True,
)
```

```python
ToolSpec(
    name="validar_custos",
    description="Compara custos modelados e DRE de forma deterministica.",
    phase="dominion",
    kind="deterministic_tool",
    function_name="validar_custos",
    required_state_keys=("dados",),
    produced_state_keys=("resultados",),
    repeatable=False,
    risk_level="low",
    requires_human_confirmation=False,
    audit_required=True,
)
```

---

## Tools planejadas para DataShield Lite

Quando DataShield Lite for implementado, registrar:

```text
ler_arquivo
gerar_perfil_dataframe
amostrar_dataframe
inferir_mapa_semantico
validar_mapa_semantico
normalizar_dataset
salvar_template_mapeamento
carregar_template_mapeamento
```

Classificacao sugerida:

| Tool                           | Fase       | Tipo               | Risco  |
| ------------------------------ | ---------- | ------------------ | ------ |
| `ler_arquivo`                  | datashield | io_tool            | medium |
| `gerar_perfil_dataframe`       | datashield | deterministic_tool | low    |
| `amostrar_dataframe`           | datashield | deterministic_tool | low    |
| `inferir_mapa_semantico`       | datashield | llm_tool           | medium |
| `validar_mapa_semantico`       | datashield | deterministic_tool | medium |
| `normalizar_dataset`           | datashield | deterministic_tool | medium |
| `salvar_template_mapeamento`   | datashield | io_tool            | medium |
| `carregar_template_mapeamento` | datashield | io_tool            | medium |

---

## Regras de integracao com `agent.py`

`agent.py` nao deve manter lista manual duplicada de tools.

O prompt de decisao deve receber a lista de tools validas para a fase atual a partir do ToolRegistry.

Exemplo conceitual:

```python
tools_disponiveis = listar_nomes_por_fase("dominion")
descricao_tools = gerar_descricao_para_prompt("dominion")
```

Regra:

```text
Se uma tool nao estiver no ToolRegistry, ela nao deve aparecer no prompt.
```

---

## Regras de integracao com `harness.py`

O harness deve validar toda acao retornada pelo LLM contra o ToolRegistry.

Fluxo:

```text
1. LLM retorna acao.
2. Harness valida JSON.
3. Harness verifica se a tool existe.
4. Harness verifica se a tool pertence a fase atual.
5. Harness verifica se pode repetir.
6. Harness verifica campos requeridos do state.
7. Harness executa funcao correspondente.
8. Harness registra auditoria.
```

Regra:

```text
Se a tool nao existir, nao executar.
Se a tool nao for permitida na fase, nao executar.
Se a tool ja foi executada e repeatable=False, nao executar.
```

---

## Regras de integracao com `tools.py`

`tools.py` deve conter a implementacao das funcoes.

`tool_registry.py` deve conter os metadados.

Evitar:

```text
tools.py define a lista oficial
agent.py define outra lista
harness.py define outra lista
```

Preferir:

```text
tools.py implementa
tool_registry.py registra
harness.py executa apenas o registrado
agent.py usa registry para montar prompt
```

---

## Regras de integracao com testes

Criar testes para garantir que:

```text
toda tool registrada tem funcao implementada
toda tool implementada relevante esta registrada
nao ha nomes duplicados
toda tool tem fase valida
toda tool tem tipo valido
toda tool tem risk_level valido
tools high risk nao estao habilitadas no MVP
prompts usam tools do registry
harness rejeita tool fora do registry
```

Arquivo sugerido:

```text
tests/test_tool_registry.py
```

---

## Consequencias positivas

* Reduz duplicacao.
* Reduz risco de tool fantasma.
* Reduz risco de prompt desalinhado.
* Facilita adicionar DataShield Lite.
* Facilita controlar tools por fase.
* Melhora auditabilidade.
* Melhora testabilidade.
* Ajuda a impedir execucao indevida.
* Facilita documentar risco e permissoes.
* Prepara evolucao para orquestracao mais complexa no futuro.

---

## Consequencias negativas ou trade-offs

* Exige refatoracao inicial.
* Exige atualizar chamadas existentes.
* Exige cuidado para evitar import circular.
* Exige testes adicionais.
* Pode parecer burocratico para poucas tools.
* Exige disciplina para manter o registry atualizado.

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
Nenhum invariante foi violado. O ToolRegistry reforca o controle do harness sobre as tools.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/testing.md`
* [x] `rules.md`
* [x] `.cursor/rules/spec-driven-dev.mdc`
* [x] `docs/agent.log.md`
* [ ] `docs/contracts/state_contract.md`
* [ ] `docs/prompts.md`

Impacto:

```text
A arquitetura deve declarar que tools sao registradas em fonte unica e que o harness executa apenas tools registradas e permitidas para a fase.
```

---

## Impacto em codigo

Arquivos afetados:

* [x] novo arquivo `tool_registry.py`
* [x] `agent.py`
* [x] `harness.py`
* [x] `tools.py`
* [x] `main.py`
* [x] `audit.py`
* [ ] `nexus.py`
* [ ] `state_types.py`
* [ ] `critic.py`
* [ ] `optimus.py`
* [ ] `validator.py`

Impacto:

```text
As listas manuais de tools devem ser substituidas ou validadas pelo ToolRegistry. O harness deve consultar o registry antes de executar qualquer tool.
```

---

## Impacto em prompts

O prompt `dominion.proximo_passo` deve ser gerado ou validado a partir das tools disponiveis no registry.

Regra:

```text
O LLM so pode escolher uma acao listada para a fase atual.
```

Se o LLM retornar acao fora do registry:

```text
harness rejeita
registra auditoria
aplica retry ou fallback
```

---

## Impacto em testes

Testes exigidos:

* [x] `python -m py_compile *.py`
* [x] `python main.py --modo nexus`
* [ ] `python main.py --modo legado`
* [x] teste de nomes duplicados
* [x] teste de fase invalida
* [x] teste de tipo invalido
* [x] teste de risk_level invalido
* [x] teste de tool existente
* [x] teste de tool inexistente
* [x] teste de repeatable=False
* [x] teste de prompt gerado com tools do registry
* [x] teste de harness rejeitando tool fora do registry

Detalhar:

```text
A suite deve impedir que uma nova tool seja criada sem registro ou que uma tool removida continue aparecendo no prompt.
```

---

## Criterios de aceite

* [ ] `tool_registry.py` criado.
* [ ] `ToolSpec` definido.
* [ ] Tools atuais registradas.
* [ ] `agent.py` usa registry para listar tools validas.
* [ ] `harness.py` valida acao contra registry.
* [ ] Tools fora do registry sao rejeitadas.
* [ ] Tools repetidas sao bloqueadas quando `repeatable=False`.
* [ ] Testes de registry criados.
* [ ] `python main.py --modo nexus` continua funcionando.
* [ ] `docs/contracts/tool_contract.md` atualizado.
* [ ] `docs/agent.log.md` atualizado.

---

## Plano de migracao

Implementar em passos pequenos:

```text
1. Criar `tool_registry.py` com `ToolSpec`.
2. Registrar tools atuais.
3. Criar funcoes `listar_tools_por_fase`, `obter_tool` e `validar_tool_na_fase`.
4. Atualizar `agent.py` para usar registry na lista de tools do prompt.
5. Atualizar `harness.py` para validar acao contra registry.
6. Remover ou reduzir listas duplicadas.
7. Criar testes de registry.
8. Rodar `python main.py --modo nexus`.
9. Atualizar `docs/agent.log.md`.
```

---

## Plano de rollback

Se a migracao quebrar o pipeline:

```text
1. Restaurar listas manuais temporariamente.
2. Manter `tool_registry.py` sem uso ate corrigir.
3. Registrar falha em `docs/agent.log.md`.
4. Corrigir testes de registry.
5. Reintegrar em passo menor.
```

Fallback aceitavel durante migracao:

```text
ToolRegistry existe, mas harness ainda usa lista manual por uma iteracao.
```

Nesse caso:

```text
nao marcar item como concluido
registrar implementacao parcial
criar subitem no planning
```

---

## Riscos

| Risco                                  | Probabilidade | Impacto    | Mitigacao                                                                |
| -------------------------------------- | ------------- | ---------- | ------------------------------------------------------------------------ |
| Import circular entre registry e tools | Media         | Medio      | Registry guarda function_name, nao importa funcoes diretamente no inicio |
| Prompt continuar usando lista antiga   | Media         | Medio/Alto | Teste de consistencia prompt-registry                                    |
| Harness executar tool fora do registry | Baixa/Media   | Alto       | Validacao obrigatoria no harness                                         |
| Nova tool sem registro                 | Media         | Medio      | Teste que compara tools implementadas e registradas                      |
| Refatoracao quebrar modo nexus         | Media         | Medio      | Migracao incremental e E2E                                               |

---

## Decisoes relacionadas

```text
ADR-0001 - Pipeline Sequencial no MVP
ADR-0002 - LLM nao calcula numeros
ADR-0003 - State blackboard sem conversa livre
ADR-0005 - DataShield Lite antes do Dominion
```

---

## Observacoes

O ToolRegistry nao deve ser confundido com MOE router.

ToolRegistry apenas define quais tools existem e em quais fases podem ser usadas.

Ele nao escolhe dinamicamente agentes nem muda o fluxo do MVP.

Linguagem recomendada:

```text
ToolRegistry e a fonte unica de verdade das tools permitidas pelo harness.
```

Evitar:

```text
ToolRegistry e um roteador inteligente de agentes.
```
