# ADR-0024 - Portabilidade Multi-Dominio

## Status

```text
Aceito
```

## Data

```text
2026-07-08
```

## Responsavel

```text
Agente Cursor + usuario
```

## Contexto

O pipeline S&OE esta funcional para dados Mondelez, mas contem acoplamentos
ao dominio que impedem reutilizacao com outros clientes/setores:

1. Thresholds de DOI (15d ruptura, 40d overstock) hardcoded para politica
   Mondelez. Em pereciveis (DOI alvo 5d) ou commodities (DOI alvo 90d),
   classificariam tudo errado.
2. Impacto financeiro no Optimus usa toneladas (campo `valor` do Sinal)
   em vez de NR real, distorcendo priorizacao.
3. Schema canonico `SCHEMA_CANONICO_MONDELEZ` hardcoded em datashield.py.
   Datasets com colunas em portugues ou layout diferente nao sao mapeados.
4. Deteccao de dados forward usa `actual.isna()`. Datasets que marcam
   forward com zero ou flag explicita nao sao detectados.

## Decisao

Implementar 4 mudancas de portabilidade:

### B2: Propagar nr_impacto real ate o Optimus

- Adicionar campo `nr_impacto: float` ao `Sinal`.
- `sinais.py` preenche com valor calculado pela tool (`d["nr_impacto"]`).
- `optimus.py` usa `sinal.nr_impacto` quando > 0, fallback para formula.

### B1: Externalizar thresholds para DomainThresholds

- Criar `DomainThresholds` dataclass em `config.py`.
- Ler de variaveis `.env` opcionais com defaults Mondelez.
- Propagar de `Settings` para tools e Optimus via parametro.

### B4: Generalizar deteccao de forward

- Adicionar `forward_marker` a `DomainThresholds` ("nan", "zero", "flag").
- Criar `_is_forward` em `tools_parametrizadas.py`.
- Substituir `.isna()` hardcoded por chamada generica.

### B3: Schema canonico configuravel

- Adicionar `schema_path: Optional[str]` a `Settings`.
- `datashield.py` aceita schema externo como parametro.
- Sem `--schema`, usa default Mondelez.

## Alternativas consideradas

### A: Manter hardcoded e documentar limitacao

Vantagens: zero esforco.
Desvantagens: inviavel para multi-cliente.

### B: Arquivo YAML/JSON de configuracao por cliente (escolhida)

Vantagens: zero mudanca de codigo para novo cliente.
Desvantagens: mais complexidade no config.

## Justificativa

O custo de portabilidade e baixo (~120 linhas de mudanca) e o ganho
e alto: qualquer novo cliente pode ser atendido com um `.env` diferente
e um JSON de schema, sem tocar no codigo.

## Consequencias positivas

- Pipeline reutilizavel para outros clientes EY.
- Priorizacao financeira correta (NR real).
- Suporte a datasets com diferentes marcadores de forward.
- Schema configuravel sem mudanca de codigo.

## Consequencias negativas ou trade-offs

- `DomainThresholds` adiciona ~10 parametros ao `.env`.
- Testes existentes precisam propagar thresholds.
- Compatibilidade retroativa: defaults Mondelez preservam comportamento.

## Invariantes preservados

- [x] Spec antes do codigo
- [x] IA = LLM + Harness
- [x] LLM nao calcula numeros
- [x] Tools deterministicas calculam metricas
- [x] State blackboard
- [x] Sem conversa livre entre agentes no MVP
- [x] Human-in-the-loop obrigatorio
- [x] Critic read-only
- [x] Auditoria obrigatoria

## Impacto em arquitetura

- [x] `docs/architecture.md` -- secao 7 (config), secao 6.2 (tipos), secao 12 (schema)
- [x] `docs/planning.md` -- nova Fase 1.9
- [x] `docs/contracts/state_contract.md` -- campo nr_impacto no Sinal
- [x] `docs/contracts/tool_contract.md` -- tools recebem thresholds
- [ ] `docs/prompts.md` -- sem impacto
- [x] `docs/testing.md` -- novos testes de portabilidade

## Impacto em codigo

- [x] `config.py` -- DomainThresholds + schema_path
- [x] `state_types.py` -- campo nr_impacto no Sinal
- [x] `sinais.py` -- propagar nr_impacto
- [x] `optimus.py` -- usar nr_impacto real + receber thresholds
- [x] `tools_parametrizadas.py` -- receber thresholds + forward_marker
- [x] `datashield.py` -- schema parametrizavel
- [x] `nexus.py` -- propagar thresholds e schema
- [x] `.env` -- novas variaveis opcionais

## Criterios de aceite

- [ ] ADR-0024 escrito
- [ ] architecture.md atualizado
- [ ] planning.md atualizado
- [ ] state_contract.md atualizado
- [ ] tool_contract.md atualizado
- [ ] Codigo implementado (B2, B1, B4, B3)
- [ ] Testes passando
- [ ] Pipeline com dados reais funciona
- [ ] Defaults Mondelez preservam comportamento
