# Tool Contract - Sense to Respond

> Contrato oficial das ferramentas deterministicas do projeto.
> Toda tool deve seguir este contrato.
> Qualquer mudanca neste contrato exige atualizar `docs/architecture.md`, `docs/planning.md` e `docs/agent.log.md`.

---

## 1. Principio central

Tools calculam. LLM nao calcula.

O LLM pode decidir qual ferramenta chamar, mas a execucao, os calculos e a validacao numerica devem ser feitos por codigo deterministico.

```text id="c6d4r9"
LLM -> escolhe proxima acao
Harness -> valida se a tool e permitida
Tool -> executa calculo deterministico
State -> recebe resultado
Auditoria -> registra execucao
```

---

## 2. O que e uma tool

Uma tool e uma funcao controlada pelo harness, registrada em whitelist, com entrada e saida definidas.

Exemplos atuais:

```text id="54uy7t"
carregar_dados
validar_demanda
validar_custos
```

Exemplos planejados:

```text id="ofk7tx"
ler_arquivo
gerar_perfil_dataframe
inferir_mapa_semantico
normalizar_dataset
detectar_capacidades
analisar_sellout
analisar_sellin
analisar_doi
analisar_desvio_plano
analisar_desequilibrio_canal
analisar_ruptura_doi
analisar_tendencia
gerar_script_etl
executar_script_etl_aprovado
```

---

## 3. Invariantes das tools

Toda tool deve respeitar:

1. Ser deterministica sempre que possivel.
2. Nao chamar LLM, salvo tools explicitamente classificadas como `llm_tool`.
3. Nao calcular nada dentro de prompt.
4. Nao alterar state silenciosamente.
5. Nao acessar dados ou arquivos fora do escopo autorizado.
6. Nao registrar dados sensiveis em logs.
7. Validar entradas antes de calcular.
8. Retornar saida estruturada.
9. Ser auditavel.
10. Ter teste minimo.

---

## 4. Tipos de tools

### 4.1 `deterministic_tool`

Tool puramente Python/pandas.

Exemplos:

```text id="diuhlb"
validar_demanda
validar_custos
gerar_perfil_dataframe
normalizar_dataset
analisar_desvio_plano
plotar_resumo_executivo
gerar_relatorio_analista
```

Regras:

* Pode calcular numeros.
* Nao pode chamar LLM.
* Deve ser testavel sem API externa.
* Deve ter resultado reproduzivel para mesma entrada.
* `gerar_relatorio_analista` monta HTML/PDF a partir de dados ja
  calculados; pode embutir texto LLM ja gerado, mas nao chama LLM
  nem recalcula impactos/ranking.

---

### 4.2 `llm_tool`

Tool que chama LLM para tarefa nao numerica.

Exemplos planejados:

```text id="8vfj8h"
inferir_mapa_semantico
classificar_intencao
gerar_script_etl
```

Regras:

* Nao pode calcular metricas ou impacto financeiro.
* Deve retornar JSON validado.
* Deve ter retry limitado.
* Deve ter fallback seguro.
* Deve registrar prompt version, modelo e schema.
* Deve enviar apenas contexto minimo necessario.
* Deve evitar dados sensiveis e datasets completos.
* Para `gerar_script_etl`: script gerado deve conter apenas operacoes ETL (ADR-0021).
* Scripts gerados devem passar por revisao humana antes de execucao.

---

### 4.3 `io_tool`

Tool que le ou grava arquivos.

Exemplos:

```text id="357o2j"
ler_arquivo_csv
ler_arquivo_xlsx
salvar_template_mapeamento
carregar_template_mapeamento
salvar_auditoria_json
plotar_resumo_executivo
gerar_relatorio_analista
```

Regras:

* Validar caminho.
* Validar extensao permitida.
* Nao sobrescrever arquivo sem autorizacao.
* Nao gravar segredo.
* Nao gravar dados reais completos em diretorios de exemplo ou docs.
* Registrar operacao em auditoria quando fizer parte do pipeline.
* `plotar_resumo_executivo` e deterministic_tool + io_tool: le apenas
  `resumo_executivo`, grava PNG em `output/`, nao chama LLM, nao
  recalcula impactos nem ordem do ranking.
* `gerar_relatorio_analista` grava HTML+PDF em `output/`; PDF via
  WeasyPrint; se PDF falhar, HTML deve permanecer.

---

### 4.4 `audit_tool`

Tool ou funcao auxiliar ligada a auditoria.

Exemplos:

```text id="w797sy"
registrar_evento
salvar_json
resumir_eventos
```

Regras:

* Nao deve conter segredo.
* Deve registrar timestamp.
* Deve evitar payloads grandes.
* Deve preferir resumo, contagens e hashes a dumps completos.

---

## 5. ToolSpec obrigatorio

Toda tool registrada deve ter uma especificacao.

Estrutura recomendada:

```python id="vyk9dr"
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

Campos:

| Campo                         | Descricao                                                   |
| ----------------------------- | ----------------------------------------------------------- |
| `name`                        | Nome unico usado pelo LLM/harness                           |
| `description`                 | Descricao curta para humanos e prompts                      |
| `phase`                       | Fase autorizada: DataShield, Dominion, Optimus, Nexus etc.  |
| `kind`                        | `deterministic_tool`, `llm_tool`, `io_tool` ou `audit_tool` |
| `function_name`               | Nome da funcao Python                                       |
| `required_state_keys`         | Campos exigidos do state                                    |
| `produced_state_keys`         | Campos adicionados ou atualizados                           |
| `repeatable`                  | Se pode executar mais de uma vez na mesma sessao            |
| `risk_level`                  | `low`, `medium` ou `high`                                   |
| `requires_human_confirmation` | Se precisa confirmacao humana                               |
| `audit_required`              | Se deve registrar evento de auditoria                       |

---

## 6. Fases permitidas

As fases reconhecidas no MVP sao:

```text id="cdwtck"
datashield
dominion
optimus
validator
critic
nexus
output
```

### 6.1 DataShield

Tools permitidas:

```text id="1gc0zg"
ler_arquivo
gerar_perfil_dataframe
amostrar_dataframe
inferir_mapa_semantico
validar_mapa_semantico
normalizar_dataset
salvar_template_mapeamento
carregar_template_mapeamento
gerar_script_etl
executar_script_etl_aprovado
```

Responsabilidade:

```text id="geka4h"
ler dados
inferir schema
confirmar mapeamento
normalizar dataset
```

Nao deve:

```text id="6ttcea"
gerar proposicoes
calcular decisoes
executar acoes operacionais
gerar scripts com calculos de metricas (ADR-0021)
```

### 6.1b DataShield - Niveis de adaptacao (ADR-0020)

```text
Nivel 1: mapeamento puro
  Tools: inferir_mapa_semantico, validar_mapa_semantico, normalizar_dataset
  LLM: retorna JSON de mapeamento
  Humano: confirma mapeamento

Nivel 2: ETL gerado
  Tools: gerar_script_etl, executar_script_etl_aprovado
  LLM: gera script Python (apenas operacoes ETL)
  Humano: revisa e aprova script
  Sandbox: executa script aprovado
  Whitelist pandas: rename, groupby, merge, fillna, drop, astype, pivot_table

Nivel 3: diagnostico
  Tools: inferir_mapa_semantico (retorna diagnostico)
  LLM: identifica incompatibilidade
  Humano: decide se prossegue
```

---

### 6.2 Dominion

Tools permitidas atuais:

```text id="v0hxf1"
carregar_dados
validar_demanda
validar_custos
```

Tools planejadas (ADR-0019):

```text id="nl67cy"
detectar_capacidades
analisar_sellout
analisar_sellin
analisar_doi
analisar_desvio_plano
analisar_desequilibrio_canal
analisar_ruptura_doi
analisar_tendencia
analisar_aceleracao_canal
```

Assinatura parametrizada (ADR-0019, ADR-0024):

```python
def analisar_sellout(
    df: pd.DataFrame,
    mapa: dict,
    thresholds: DomainThresholds | None = None,
) -> dict:
    ...

def detectar_capacidades(mapa: dict) -> list[str]:
    ...
```

As tools parametrizadas recebem `df`, `mapa` e opcionalmente `thresholds`
como argumentos. `thresholds` contem limiares de dominio configuraveis
(DOI, desvio, janela temporal, marcador forward) -- ADR-0024.
Se `thresholds` nao for fornecido, usa defaults Mondelez.

Responsabilidade:

```text id="2flfni"
gerar resultados deterministicos e sinais operacionais
```

Nao deve:

```text id="hh7bxt"
priorizar decisoes finais
aprovar proposicoes
executar Bridge
```

---

### 6.3 Optimus

No MVP atual, Optimus pode ser deterministico.

Responsabilidade:

```text id="ghtwbx"
transformar sinais em proposicoes priorizadas
```

Nao deve:

```text id="725tau"
alterar sinais
inventar evidencias
calcular impacto via LLM
aprovar acao operacional
```

---

### 6.4 Validator

Responsabilidade:

```text id="8qx788"
validar proposicoes contra sinais
```

Regras:

```text id="d65pqd"
nao chama LLM
nao cria proposicoes
nao corrige silenciosamente
```

---

### 6.5 Critic

Critic e LLM read-only.

Responsabilidade:

```text id="gumfzk"
auditar coerencia entre sinais e proposicoes
```

Regras:

```text id="p83y20"
nao cria proposicoes
nao altera state numerico
retorna JSON validado
```

---

### 6.6 Nexus

Responsabilidade:

```text id="hcrfn2"
orquestrar pipeline
montar fila
aplicar flags
registrar handoffs
```

Nao deve:

```text id="bkryev"
calcular metricas
executar acoes operacionais
```

---

## 7. Assinatura recomendada

### 7.1 Tools deterministicas atuais

Padrao aceito no MVP atual:

```python id="4g1da0"
def nome_tool(state: dict) -> dict:
    ...
```

### 7.2 Padrao recomendado para novas tools

Para novas APIs publicas, preferir tipos explicitos:

```python id="h21wl3"
def nome_tool(input_data: ToolInput) -> ToolOutput:
    ...
```

ou:

```python id="4zl3bg"
def nome_tool(state: NexusState) -> ToolResult:
    ...
```

Evitar `Any` em novas APIs publicas.

---

## 8. Entrada de tool

Toda tool deve validar:

```text id="tkm6i1"
campos obrigatorios
tipo dos campos
valores nulos
faixas numericas
colunas necessarias em DataFrame
estado minimo exigido
```

Exemplo:

```text id="il2ams"
analisar_desvio_plano requer:
- dataset_canonico
- coluna volume_real
- coluna volume_plano
```

### Tools Dual Ingress PBI (ADR-0025) -- PoC / planejado

Contrato detalhado: `docs/contracts/powerbi_catalog_contract.md`.

```text
carregar_catalogo_dax(path) -> dict
  deterministic_tool / io_tool
  Valida YAML contra contrato; nao chama rede.

executar_catalogo_pbi(catalog, artifact_id, client) -> dict
  io_tool (ExecuteQuery: fixture CI ou REST live)
  So DAX do catalogo; sem GenerateQuery no batch.
  Saida: resultados_pbi + catalog_execucao
  REST: normaliza chaves [Col] / Table[Col] (1.7a.4)

adaptar_resultados_pbi_para_sinais(resultados_pbi, ...) -> list[Sinal]
  deterministic_tool
  Mondelez: doi_fora_politica, desvio_sellout,
  premissa_forward_furada, forward_oportunidade

exportar_resultados_pbi_para_auditoria(...) -> {sessao, ultima}
  io_tool / audit helper
  Grava auditoria/resultados_pbi_*.json (gitignored; ADR-0012)
```

PoC 1.7a.2--1.7a.4: `powerbi_catalog.py`, `powerbi_mcp.py`,
`dominion_pbi.py` + catalogo `catalogs/mondelez_s2r_v1.yaml` (Q1-Q5).

### Tools Chat PBI (ADR-0026 / planning 1.7b)

Somente `--modo chat`. Proibido no batch Optimus/PDF.

```text
chat_pbi.run(pergunta, ...) -> ChatResult
  orchestration_tool (MAF)
  Entrada: pergunta NL (+ sessao opcional)
  Saida: answer_markdown, tables[], citations[], meta
  Numeros so via tools abaixo; CLI so imprime.
  Modelo: CHAT_OPENAI_MODEL (default gpt-5.4)

GetSemanticModelSchema(artifactId) -> schema/meta
  io_tool (MCP primario)

ExecuteQuery(artifactId, daxQueries[], maxRows?) -> rows
  io_tool (MCP primario; fallback REST RestPowerBIClient)
  Preferido no playbook (DAX manual / hints do catalogo)

GenerateQuery(artifactId, userInput, schemaSelection?, ...) -> DAX
  io_tool (MCP; chat only; FALLBACK max 1x se DAX nao estiver claro)
```

Transport (`CHAT_PBI_TRANSPORT`):

* `mcp` (preferido): MCP Streamable HTTP Fabric
* `rest` (fallback): ExecuteQuery via REST; GenerateQuery indisponivel
* `mock` (CI): fixtures/tools injetadas; sem OAuth

Playbook/completude: ver ADR-0026 D6 (agregado + 5-10 SKUs em
perguntas de cobertura/risco).

Backlog restante:

```text
REPL multi-turno (AgentSession)
connector HTTP Fabric standalone (cron)
alinhar tipos sinal Agua <-> Mondelez
paridade temporal total (forward_marker) no modelo PBI
UI React sobre ChatResult
```

Se entrada for invalida, a tool deve:

```text id="z9l0gk"
retornar erro estruturado
ou levantar excecao especifica
e registrar auditoria quando aplicavel
```

---

## 9. Saida de tool

Toda tool deve retornar saida estruturada.

Exemplo:

```python id="3nopka"
return {
    "comparacao_demanda": df,
    "inconsistencias_demanda": inconsistencias,
}
```

Para novas tools, preferir dataclasses ou TypedDicts.

Regras:

* Saida deve ser previsivel.
* Chaves devem ser documentadas.
* Chaves novas devem ser adicionadas ao state contract se forem persistidas.
* Saida numerica deve ser calculada por codigo.
* Saida textual deve ser explicativa, nao decisoria.

---

## 10. Mutacao do state

Padrao recomendado:

```text id="5mokd6"
Tool retorna output.
Harness aplica output ao state.
```

Evitar:

```text id="6cir63"
Tool altera state diretamente de forma profunda e silenciosa.
```

Se uma tool precisar alterar state diretamente, isso deve estar documentado no ToolSpec.

---

## 11. Auditoria obrigatoria

Toda tool relevante deve gerar eventos:

```text id="15jb8c"
tool_inicio
tool_fim
```

O evento `tool_inicio` deve conter:

```text id="76d5q8"
nome da tool
fase
resumo do estado antes
timestamp
iteracao, se houver
```

O evento `tool_fim` deve conter:

```text id="m8zfh0"
nome da tool
duracao_ms
resumo do efeito
estado depois resumido
timestamp
iteracao, se houver
```

Em caso de erro:

```text id="g9h22u"
tool_erro
nome da tool
tipo do erro
mensagem segura
estado resumido
```

Nao registrar:

```text id="jeb16r"
OPENAI_API_KEY
.env
dataset completo
dados sensiveis
payloads gigantes
```

---

## 12. Ferramentas repetiveis

Por padrao, tools nao devem repetir na mesma fase.

Excecoes possiveis:

```text id="trzyal"
inferir_mapa_semantico, durante retry
validar_mapa_semantico
gerar_perfil_dataframe, se arquivo mudar
```

Toda repeticao deve ser autorizada por `repeatable=True` no ToolSpec ou por regra explicita do harness.

---

## 13. Niveis de risco

### 13.1 Low

Exemplos:

```text id="d716hb"
gerar_perfil_dataframe
validar_demanda
validar_custos
```

Caracteristicas:

```text id="2rzroi"
sem LLM
sem escrita externa
sem acao operacional
```

---

### 13.2 Medium

Exemplos:

```text id="a1256m"
inferir_mapa_semantico
normalizar_dataset
salvar_template_mapeamento
```

Caracteristicas:

```text id="yhk52h"
pode alterar estrutura de dados
pode depender de LLM
pode afetar analises seguintes
```

Requer:

```text id="hv8uov"
validacao
auditoria
possivel confirmacao humana
```

---

### 13.3 High

Exemplos futuros:

```text id="diwvyl"
executar_acao_erp
criar_pedido
alterar_estoque
enviar_comando_wms
```

No MVP:

```text id="fvqer4"
tools high risk sao proibidas
Bridge nao esta habilitado
acao operacional automatica nao e permitida
```

---

## 14. Tools com LLM

Tools com LLM devem seguir contrato adicional.

Toda llm_tool deve definir:

```text id="hncjqr"
prompt_name
prompt_version
modelo
schema_json
max_retries
fallback
campos proibidos
dados enviados ao LLM
```

Regras:

* Nao enviar dataset completo.
* Usar amostras limitadas.
* Usar estatisticas agregadas.
* Validar JSON de resposta.
* Validar tipos e faixas.
* Registrar modelo e tamanho aproximado do contexto.
* Nao registrar prompt com dados sensiveis completos.

---

## 15. ToolRegistry

O projeto deve evoluir para uma unica fonte de verdade das tools.

Arquivo recomendado:

```text id="av9vpm"
tool_registry.py
```

Responsabilidades:

```text id="ff6p7o"
registrar tools
listar tools por fase
validar existencia
validar permissao por fase
informar se tool pode repetir
fornecer descricoes ao prompt do LLM
```

Regra:

* Nomes de tools nao devem ser duplicados manualmente em varios arquivos.
* Prompt do LLM deve ser gerado ou validado a partir do registry.
* Harness deve executar apenas tools registradas.

---

## 16. Checklist para criar nova tool

Antes de implementar nova tool, responder:

```text id="xp7dls"
1. Esta tool esta prevista no planning?
2. Qual fase pode usa-la?
3. Ela e deterministica, LLM, IO ou auditoria?
4. Quais campos do state ela precisa?
5. Quais campos do state ela produz?
6. Pode repetir?
7. Qual o nivel de risco?
8. Precisa confirmacao humana?
9. Precisa auditoria?
10. Quais testes serao criados?
```

Se qualquer resposta for incerta, parar e atualizar spec antes do codigo.

---

## 17. Checklist de aceite de nova tool

Uma nova tool so esta pronta quando:

```text id="zkb4i4"
- esta registrada no ToolRegistry ou mecanismo equivalente;
- tem docstring;
- tem typing;
- valida entradas;
- retorna saida estruturada;
- nao chama LLM se for deterministic_tool;
- nao calcula em prompt;
- gera auditoria quando aplicavel;
- tem teste minimo;
- foi documentada no planning ou contrato;
- pipeline principal continua funcionando.
```

---

## 18. Testes minimos por tipo de tool

### 18.1 Deterministic tool

Testar:

```text id="qjyvds"
entrada valida
entrada invalida
valores limite
saida esperada
sem mutacao inesperada do state
```

---

### 18.2 LLM tool

Testar com mock:

```text id="a3pvgs"
JSON valido
JSON invalido
chaves faltando
tipo errado
confidence fora de faixa
retry
fallback
```

---

### 18.3 IO tool

Testar:

```text id="m0jcqq"
arquivo valido
arquivo inexistente
extensao nao suportada
arquivo vazio
permissao de escrita
```

---

### 18.4 Audit tool

Testar:

```text id="766kae"
evento registrado
timestamp presente
payload serializavel
ausencia de segredo
```

---

## 19. Proibicoes explicitas

Nao criar tool que:

```text id="ra17a3"
execute acao em ERP/WMS/TMS no MVP
envie email automatico
aprove proposicao automaticamente
calcule valores via LLM
altere resultado sem auditoria
grave dados sensiveis em log
acesse segredo desnecessariamente
ignore human-in-the-loop
```

---

## 20. Compatibilidade

Mudancas em tools devem preservar:

```bash id="ins5y7"
python main.py --modo nexus
```

Se alterou modo legado:

```bash id="y5wsi3"
python main.py --modo legado
```

Se a compatibilidade for quebrada intencionalmente, registrar:

```text id="na8zp9"
motivo
impacto
arquivos afetados
plano de migracao
testes alternativos
```

em:

```text id="fu1scl"
docs/architecture.md
docs/planning.md
docs/agent.log.md
```

---

## 21. Regra final

Se houver conflito entre flexibilidade do LLM e controle do harness, o harness vence.

Se houver conflito entre uma nova tool e este contrato, o contrato vence.

Se o contrato estiver incompleto, atualizar o contrato antes de implementar.
