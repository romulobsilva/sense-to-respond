# Contrato: Catalogo DAX Power BI (MCP)

> Fonte de verdade das queries batch do caminho **PBI unificado**
> (ADR-0025). ASCII only no YAML de catalogo versionado no repo.

---

## 1. Escopo

### PoC (agora)

* Um arquivo de catalogo por semantic model de teste (ex.: Agua).
* Campos obrigatorios abaixo.
* Consumido por `dominion_pbi` (a implementar; planning 1.7a).

### Pos-PoC / backlog (sinalizado)

* Catalogo Mondelez S&OE: `catalogs/mondelez_s2r_v1.yaml` (modelo publicado;
  batch ainda depende de `dominion_pbi` em planning 1.7a.2).
* Versionamento semantico de catalogo (semver) e CI contra modelo live.
* Popa / registro enterprise do catalogo (fora do MVP harness).

Nao implementar o restante do backlog na primeira entrega da PoC.

---

## 2. Identidade do catalogo

| Campo | Tipo | Obrigatorio | Descricao |
| --- | --- | --- | --- |
| `catalog_id` | str | sim | Id estavel (ex.: `agua_io_v1`) |
| `display_name` | str | sim | Nome legivel |
| `artifact_id_env` | str | sim | Nome da env var do GUID (ex.: `PBI_ARTIFACT_ID`) |
| `artifact_id_default` | str ou null | nao | So para fixtures locais; preferir env |
| `domain` | str | sim | Ex.: `agua_io` ou `mondelez_s2r` |
| `notes` | str | nao | ASCII; UOM e avisos |

Troca Mondelez futura: novo arquivo YAML + novo `artifact_id` na env.
O harness nao deve hardcodar nomes de tabela do modelo Agua.

---

## 3. Query do catalogo

Cada item em `queries[]`:

| Campo | Tipo | Obrigatorio | Descricao |
| --- | --- | --- | --- |
| `query_id` | str | sim | Ex.: `Q1_kpis` |
| `description` | str | sim | Intencao de negocio (ASCII) |
| `dax` | str | sim | Um statement `EVALUATE ...` |
| `max_rows` | int | nao | Default 250 |
| `expected_columns` | list[str] | sim | Colunas do resultado |
| `grain` | str | nao | Ex.: `model`, `sku_x_unidade`, `uf` |
| `uom` | dict | recomendado | Mapa coluna -> unidade/escopo |
| `maps_to_signal_types` | list[str] | nao | Tipos `Sinal` alvo (nomes reais: `doi_fora_politica`, `desvio_sellout`, `premissa_forward_furada`, `forward_oportunidade`) |

Mondelez 1.7a.3 (paridade parcial):

* `Q4_forward_risco` -> `premissa_forward_furada` (`risco_forward` ruptura/overstock)
* `Q5_forward_oportunidade` -> `forward_oportunidade`
* Aproximacao: measures snapshot + `Policy DOI Ideal` / SI Gap %;
  nao substitui serie temporal CSV com `forward_marker`.

Regras:

* Batch so executa `query_id` listados no catalogo.
* Proibido `GenerateQuery` no caminho de relatorio.
* Falha de uma query: registrar auditoria; nao inventar numeros no LLM.
* Fallback Python so se a regra estiver **documentada** no catalogo
  (nao na PoC inicial).

---

## 4. UOM / escopo (mitigacao de escala)

Exemplo:

```yaml
uom:
  Vnd Real: { unit: "un", scope: "gdpa" }
  Estoque Centro: { unit: "un", scope: "centro" }
  Gap %: { unit: "pct", scope: "vs_plan_ajustado" }
```

Medidas do modelo com escala distinta da coluna devem ser anotadas
(ex.: fator 1000). Misturar escopos sem anotacao e erro de contrato.

---

## 5. State produzido

Apos execucao do catalogo (ADR-0025 / state_contract):

```text
fonte_dados = "pbi"
pbi_catalog_id
pbi_artifact_id
resultados_pbi[query_id] = { columns, rows, meta }
catalog_execucao = { query_id, ok, erro?, n_rows }
```

Nao serializar `resultados_pbi` completo em auditoria se volume alto
(ADR-0012): preferir meta + amostra.

---

## 6. Exemplo

Ver `docs/contracts/examples/agua_io_catalog.example.yaml`.

---

## 7. Checklist de aceicao (PoC)

* [x] YAML valida contra este contrato
* [x] Tres ou mais queries MCP-safe testadas manualmente (Q1-Q5)
* [x] Env configuravel para artifact_id
* [x] Fixture JSON para testes offline
* [x] Mondelez YAML: `catalogs/mondelez_s2r_v1.yaml` + env `PBI_ARTIFACT_ID`
* [x] Q4/Q5 mapeados a tipos Optimus de forward/oportunidade (1.7a.3)
