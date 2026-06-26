# ADR-0018 - DataShield Lite Nao Substitui Governanca de Dados

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

O DataShield Lite foi definido como uma etapa do MVP para permitir que o Sense to Respond aceite arquivos tabulares reais, como `csv` e `xlsx`.

Sua funcao no MVP e:

```text id="r0esf7"
ler arquivos
gerar perfil de colunas
criar amostra limitada
inferir mapa semantico com LLM
validar o mapa semantico
aplicar confidence gate
exigir confirmacao humana quando necessario
normalizar dataset para schema canonico
registrar handoff para Dominion
```

Essa camada melhora a entrada de dados do MVP, mas nao cobre todos os requisitos de uma governanca de dados corporativa completa.

Uma camada completa de governanca de dados poderia envolver:

```text id="f6ke8s"
catalogo de dados
linhagem ponta a ponta
qualidade de dados historica
reconciliacao entre fontes
controle de versoes de datasets
politicas de retencao
RBAC completo
mascaramento avancado
data contracts formais
freshness monitorado
SLA de atualizacao
conectores com sistemas corporativos
pipelines produtivos
observabilidade de dados
aprovacao formal de datasets
```

Portanto, DataShield Lite deve ser entendido como uma camada de preparacao e interpretacao controlada de arquivos para o MVP, nao como substituto da governanca corporativa.

---

## Decisao

DataShield Lite nao substitui governanca de dados corporativa.

No MVP, DataShield Lite pode:

```text id="mc6i5d"
ler arquivos tabulares simples
gerar perfil basico
identificar colunas semanticamente
validar schema inferido
normalizar nomes de colunas
preservar valores numericos
bloquear schema incerto
registrar handoff auditavel
```

DataShield Lite nao deve prometer:

```text id="4oz26f"
governanca completa de dados
qualidade de dados empresarial
linhagem corporativa ponta a ponta
reconciliacao completa entre fontes
RBAC corporativo completo
data catalog
master data management
pipeline produtivo de dados
certificacao automatica de dados
```

A documentacao, os prompts, a UI e a proposta tecnica devem deixar claro que DataShield Lite e uma etapa de MVP.

---

## Fronteira do DataShield Lite

### Dentro do escopo

```text id="qbr7t5"
csv
xlsx
perfil basico de colunas
amostra limitada
inferencia semantica de schema
validacao deterministica do mapa
confidence gate
confirmacao humana
normalizacao para schema canonico
handoff para Dominion
auditoria segura
```

### Fora do escopo

```text id="mxvz9u"
conectores produtivos com ERP/WMS/TMS
catalogo de dados corporativo
data lineage completo
reconciliacao multi-fonte
qualidade de dados historica
monitoramento continuo de freshness
politicas corporativas de retencao
RBAC completo
MDM
data mesh
pipelines produtivos Kedro ou equivalentes
DataOps completo
```

---

## Alternativas consideradas

### Alternativa A - Tratar DataShield Lite como governanca completa

Descricao:

```text id="durw9v"
Apresentar o DataShield Lite como se ele resolvesse governanca de dados de ponta a ponta.
```

Vantagens:

* narrativa comercial mais forte;
* parece uma solucao mais completa;
* reduz necessidade de explicar fases futuras.

Desvantagens:

* cria overclaiming;
* gera expectativa incorreta;
* aumenta risco em avaliacao tecnica;
* pode conflitar com TI e governanca corporativa;
* mascara limitacoes reais do MVP;
* dificulta planejamento de fase futura.

---

### Alternativa B - Nao implementar DataShield Lite

Descricao:

```text id="0rmqmg"
Exigir dados ja totalmente tratados e no schema canonico.
```

Vantagens:

* escopo tecnico menor;
* menos risco de mapeamento incorreto;
* menos dependencias;
* menos chamadas LLM.

Desvantagens:

* MVP fica menos utilizavel;
* exige preparo manual dos dados;
* reduz valor demonstravel;
* nao atende bem ao uso com arquivos reais;
* transfere complexidade para o usuario.

---

### Alternativa C - DataShield Lite como camada limitada de preparacao de dados

Descricao:

```text id="svz6nq"
Implementar uma camada simples, controlada e auditavel para interpretar arquivos e gerar dataset canonico, sem prometer governanca completa.
```

Vantagens:

* melhora usabilidade do MVP;
* mantem escopo realista;
* reduz overclaiming;
* preserva governanca;
* prepara evolucao futura;
* facilita demonstracao com arquivos reais;
* deixa claro o que ainda falta.

Desvantagens:

* exige explicar limites;
* nao resolve todos os problemas de dados;
* pode bloquear arquivos complexos;
* pode exigir fase futura de DataShield completo.

---

## Justificativa

A alternativa escolhida foi:

```text id="v2rdd6"
DataShield Lite como camada limitada de preparacao de dados.
```

Essa decisao preserva a honestidade tecnica do projeto.

O MVP deve entregar valor real, mas sem afirmar que ja possui uma plataforma completa de governanca de dados.

DataShield Lite resolve um problema especifico:

```text id="o1r5nl"
Como transformar um arquivo tabular heterogeneo em um dataset canonico minimamente confiavel para o Dominion?
```

Ele nao resolve integralmente:

```text id="suw4bq"
Como governar todos os dados corporativos de forma produtiva e continua?
```

---

## Consequencias positivas

* Reduz overclaiming.
* Mantem escopo do MVP realista.
* Facilita avaliacao tecnica honesta.
* Evita conflito com areas de dados corporativas.
* Permite demonstracao com arquivos reais.
* Separa MVP de fase produtiva.
* Prepara evolucao para DataShield completo.
* Mantem DataShield Lite testavel.
* Ajuda a comunicar limitacoes ao usuario.
* Preserva confianca do projeto.

---

## Consequencias negativas ou trade-offs

* Requer explicar que DataShield Lite e limitado.
* Pode parecer menos completo comercialmente.
* Algumas demandas corporativas ficarao para fase futura.
* Arquivos complexos podem exigir preparo manual.
* Governanca produtiva ainda precisara ser desenhada.
* O MVP nao cobre todos os requisitos de dados da empresa.

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

```text id="hspgcn"
Nenhum invariante foi violado. Esta ADR apenas delimita o escopo real do DataShield Lite.
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

```text id="d7mlem"
A arquitetura deve diferenciar DataShield Lite, no MVP, de DataShield completo, em fase futura.
```

---

## Impacto em codigo

Arquivos previstos ou afetados:

* [x] `datashield.py`
* [x] `datashield_tools.py`
* [x] `datashield_schema.py`
* [x] `nexus.py`
* [x] `state_types.py`
* [x] `audit.py`
* [x] `guardrails.py`
* [ ] `tools.py`
* [ ] `harness.py`
* [ ] `main.py`

Impacto:

```text id="mmq7pz"
O codigo do DataShield Lite deve focar em arquivos tabulares, profiling, inferencia semantica, validacao e normalizacao. Nao deve tentar implementar conectores produtivos, catalogo de dados ou governanca corporativa completa.
```

---

## Impacto em prompts

Prompt afetado:

```text id="u62sd4"
datashield.inferir_mapa_semantico
```

O prompt pode dizer:

```text id="5y4dtn"
"Mapeie semanticamente as colunas fornecidas para o schema canonico permitido."
```

O prompt nao pode dizer:

```text id="r61ae9"
"Certifique a qualidade corporativa completa deste dataset."
```

O LLM nao deve prometer:

```text id="k7kv1x"
linhagem completa
qualidade certificada
reconciliacao multi-fonte
governanca produtiva
```

---

## Impacto em output

Quando relevante, a resposta final pode mencionar:

```text id="xazxl2"
O arquivo foi normalizado pelo DataShield Lite com base no schema inferido e confirmado.
```

Evitar:

```text id="ko0riv"
Os dados foram certificados por uma governanca corporativa completa.
```

Se houver limitacao de dados, o output deve informar:

```text id="4kwm9w"
A analise depende da qualidade e completude do arquivo fornecido.
```

---

## Impacto em planejamento

DataShield deve continuar separado em duas fases:

```text id="9x7qr8"
DataShield Lite - MVP
DataShield completo - fase futura
```

DataShield Lite inclui:

```text id="ro9ndh"
upload/leitura simples
perfil de colunas
inferencia semantica
confirmacao
normalizacao
handoff
```

DataShield completo pode incluir futuramente:

```text id="0t1zsg"
fontes multiplas
reconciliacao
freshness
lineage
data contracts
qualidade avancada
conectores produtivos
governanca corporativa
```

---

## Impacto em testes

Testes para DataShield Lite:

```text id="jtxz7y"
leitura csv
leitura xlsx
perfil de colunas
amostra limitada
payload LLM reduzido
validacao de mapa semantico
confidence gate
normalizacao de colunas
bloqueio de schema incerto
auditoria segura
```

Testes que nao pertencem ao DataShield Lite MVP:

```text id="rv5j4o"
conector ERP produtivo
lineage corporativo completo
reconciliacao entre sistemas
RBAC corporativo completo
data catalog
monitoramento continuo de freshness
```

Comandos minimos:

```bash id="41dnju"
python -m py_compile *.py
python main.py --modo nexus
```

---

## Criterios de aceite

* [x] DataShield Lite delimitado como MVP.
* [x] DataShield completo mantido como fase futura.
* [x] Documentacao nao promete governanca completa no MVP.
* [x] Prompts nao prometem certificacao de dados.
* [x] Output nao afirma governanca corporativa completa.
* [x] Planning separa DataShield Lite de DataShield completo.
* [x] Testes focam no escopo real do Lite.
* [x] Arquitetura mantem limites claros.

---

## Plano de migracao

Para aplicar esta ADR:

```text id="ey8k2f"
1. Revisar architecture.md.
2. Garantir distincao entre DataShield Lite e DataShield completo.
3. Revisar planning.md.
4. Garantir que itens de governanca completa estejam em fase futura.
5. Revisar prompts do DataShield.
6. Revisar linguagem de output.
7. Registrar em agent.log.md.
```

---

## Plano de rollback

Se algum texto ou codigo tratar DataShield Lite como governanca completa:

```text id="i9s0wh"
1. Corrigir a documentacao.
2. Ajustar prompts.
3. Ajustar output.
4. Mover funcionalidades completas para backlog/fase futura.
5. Registrar correcao em agent.log.md.
```

Rollback proibido:

```text id="598kux"
prometer certificacao completa de dados
afirmar lineage corporativo completo sem implementacao
afirmar reconciliacao multi-fonte sem conectores
```

---

## Riscos

| Risco                                                | Probabilidade | Impacto    | Mitigacao                                    |
| ---------------------------------------------------- | ------------- | ---------- | -------------------------------------------- |
| Overclaiming comercial                               | Media         | Alto       | ADR e linguagem clara                        |
| TI entender DataShield Lite como governanca completa | Media         | Alto       | Separar Lite vs completo                     |
| LLM prometer certificacao dos dados                  | Media         | Medio/Alto | Prompt e output guardrail                    |
| Escopo crescer demais                                | Media         | Alto       | Planning por fases                           |
| MVP depender de governanca nao implementada          | Media         | Alto       | Manter entrada por arquivo e schema canonico |

---

## Decisoes relacionadas

```text id="pr8p8f"
ADR-0005 - DataShield Lite antes do Dominion
ADR-0009 - DataShield nao envia dataset completo ao LLM
ADR-0012 - Auditoria sem dados sensiveis
ADR-0013 - Dominion executa apenas analises compativeis com os dados
```

---

## Observacoes

DataShield Lite e uma ponte pragmatica entre arquivos reais e analise agentic.

Ele deve ser util, controlado e honesto quanto ao seu escopo.

Linguagem recomendada:

```text id="srx6m2"
DataShield Lite prepara arquivos tabulares para o MVP, mas nao substitui uma governanca de dados corporativa completa.
```

Evitar:

```text id="91kc1g"
DataShield Lite resolve toda a governanca de dados da empresa.
```
