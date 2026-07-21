# ADR-0013 - Dominion Executa Apenas Analises Compativeis com os Dados

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

O Dominion e a fase responsavel por detectar sinais operacionais e comerciais a partir dos dados disponiveis.

Com a entrada do DataShield Lite, o sistema podera receber arquivos reais com diferentes schemas.

Nem todo arquivo tera todas as colunas necessarias para todas as analises.

Exemplos:

```text
Um arquivo pode ter volume_real, mas nao volume_plano.
Um arquivo pode ter sku e canal, mas nao estoque_atual.
Um arquivo pode ter receita_real, mas nao receita_plano.
Um arquivo pode ter periodo mensal, mas nao semanal.
Um arquivo pode ter estoque, mas nao DOI minimo.
```

Se o Dominion tentar executar todas as analises indiscriminadamente, podem ocorrer erros ou, pior, sinais frageis produzidos sobre dados incompletos.

Por isso, o Dominion deve primeiro identificar quais analises sao possiveis com o dataset canonico disponivel.

---

## Decisao

O Dominion deve executar apenas analises compativeis com as colunas e a granularidade dos dados disponiveis.

Antes de rodar analises, o sistema deve inferir as capacidades do dataset.

Exemplo de capacidades:

```text
desvio_vs_plano
desequilibrio_canal
risco_ruptura_doi
tendencia_temporal
aceleracao_canal
analise_receita
analise_volume
```

Cada capacidade deve depender de colunas minimas.

Analises sem colunas necessarias devem ser puladas com registro auditavel.

O sistema nao deve inventar colunas, imputar valores ou pedir ao LLM para completar informacoes ausentes.

---

## Regra operacional

Fluxo recomendado:

```text
1. DataShield produz dataset canonico.
2. Nexus verifica schema_confirmado.
3. Dominion recebe dataset canonico.
4. Dominion infere capacidades disponiveis.
5. Dominion executa apenas analises compativeis.
6. Analises puladas sao registradas em auditoria.
7. Sinais sao gerados apenas a partir de resultados calculados.
8. Usuario recebe limitacoes na resposta final.
```

---

## Capacidades minimas

### `desvio_vs_plano`

Requer:

```text
sku
periodo
volume_real ou receita_real
volume_plano ou receita_plano
```

Pode produzir:

```text
sinal de excesso
sinal de falta
sinal de desvio relevante
```

Nao executar se nao houver baseline/plano/forecast.

---

### `desequilibrio_canal`

Requer:

```text
sku
canal
periodo
volume_real ou receita_real
```

Pode produzir:

```text
sinal de queda em canal
sinal de crescimento em canal
sinal de possivel rebalanceamento entre canais
```

Requer mais de um canal para o mesmo SKU.

---

### `risco_ruptura_doi`

Requer:

```text
sku
estoque_atual
doi_atual ou campos suficientes para calcular DOI
doi_minimo ou parametro configurado
```

Pode produzir:

```text
sinal de risco de ruptura
sinal de cobertura insuficiente
```

Nao executar se nao houver estoque ou parametro minimo de cobertura.

---

### `tendencia_temporal`

Requer:

```text
sku
periodo
volume_real ou receita_real
```

Pode produzir:

```text
sinal de tendencia de queda
sinal de tendencia de alta
sinal de aceleracao ou desaceleracao
```

Requer pelo menos dois periodos comparaveis.

Para tendencia consecutiva, requer pelo menos tres periodos ou parametro configurado.

---

### `analise_receita`

Requer:

```text
sku
receita_real
```

Opcional:

```text
receita_plano
canal
periodo
```

Pode produzir sinais de variacao de receita se houver comparativo temporal ou plano.

---

### `analise_volume`

Requer:

```text
sku
volume_real
```

Opcional:

```text
volume_plano
canal
periodo
```

Pode produzir sinais de variacao de volume se houver comparativo temporal ou plano.

---

## Alternativas consideradas

### Alternativa A - Rodar todas as analises sempre

Descricao:

```text
Dominion tenta executar todas as analises, mesmo quando algumas colunas estao ausentes.
```

Vantagens:

* implementacao simples;
* maior cobertura aparente;
* menos logica de capacidades.

Desvantagens:

* erros frequentes;
* sinais frageis;
* risco de inferir demais;
* maior dependencia de excecoes;
* pior experiencia com arquivos reais;
* risco de proposicoes sem evidencia suficiente.

---

### Alternativa B - Exigir schema completo para qualquer analise

Descricao:

```text
Dominion so roda se o arquivo tiver todas as colunas previstas no schema completo.
```

Vantagens:

* simples de validar;
* reduz ambiguidade;
* evita analises parciais.

Desvantagens:

* muito restritivo;
* bloqueia muitos arquivos reais uteis;
* reduz valor do MVP;
* exige do usuario uma estrutura ideal de dados;
* nao aproveita dados parcialmente bons.

---

### Alternativa C - Executar analises compativeis com as capacidades disponiveis

Descricao:

```text
Dominion identifica capacidades a partir das colunas disponiveis e executa apenas o que for suportado.
```

Vantagens:

* robusto para arquivos reais;
* evita sinais sem base;
* melhora transparencia;
* permite valor mesmo com dados parciais;
* preserva governanca;
* facilita explicar limitacoes;
* melhora testabilidade.

Desvantagens:

* exige camada de inferencia de capacidades;
* exige testes por capacidade;
* exige mensagens claras ao usuario;
* aumenta um pouco a complexidade.

---

## Justificativa

A alternativa escolhida foi:

```text
Executar analises compativeis com as capacidades disponiveis.
```

Essa decisao permite que o MVP trabalhe com arquivos reais sem exigir schema perfeito.

Ao mesmo tempo, evita que o Dominion gere sinais quando os dados nao suportam determinada analise.

Essa abordagem preserva os principios:

```text
LLM nao calcula numeros
Tools deterministicas calculam metricas
State blackboard
Auditoria obrigatoria
Human-in-the-loop
```

---

## Consequencias positivas

* O sistema fica mais robusto para dados reais.
* Analises incompletas nao geram sinais falsos.
* O usuario entende quais analises foram executadas e quais foram puladas.
* O Dominion fica menos propenso a erro.
* O DataShield pode aceitar schemas parciais.
* O output final pode explicar limitacoes.
* O Validator recebe proposicoes mais bem fundamentadas.
* A auditoria registra lacunas de dados.
* O MVP fica mais demonstravel.

---

## Consequencias negativas ou trade-offs

* Exige funcao para inferir capacidades.
* Exige documentar precondicoes de cada analise.
* Pode gerar menos sinais quando dados forem pobres.
* Exige mensagens de limitacao ao usuario.
* Exige testes por combinacao de colunas.
* Pode demandar parametros configuraveis para algumas analises.

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
Nenhum invariante foi violado. A decisao reforca que sinais so devem nascer de dados e calculos deterministicos disponiveis.
```

---

## Impacto em arquitetura

Arquivos de spec afetados:

* [x] `docs/architecture.md`
* [x] `docs/planning.md`
* [x] `docs/contracts/state_contract.md`
* [x] `docs/contracts/tool_contract.md`
* [x] `docs/testing.md`
* [x] `docs/agent.log.md`
* [ ] `docs/prompts.md`
* [ ] `rules.md`
* [ ] `.cursor/rules/spec-driven-dev.mdc`

Impacto:

```text
A arquitetura deve declarar que Dominion executa analises condicionadas as capacidades do dataset canonico.
```

---

## Impacto em codigo

Arquivos afetados ou previstos:

* [x] `sinais.py`
* [x] `tools.py`
* [x] `nexus.py`
* [x] `state_types.py`
* [ ] `harness.py`
* [ ] `optimus.py`
* [ ] `validator.py`
* [ ] `guardrails.py`

Novo arquivo recomendado:

```text
dominion_capabilities.py
```

Responsabilidade do novo arquivo:

```text
inferir_capacidades_do_dataset
listar_analises_executaveis
listar_analises_puladas
explicar_colunas_faltantes
```

---

## Estrutura proposta

Criar uma estrutura como:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityResult:
    name: str
    enabled: bool
    required_columns: tuple[str, ...]
    available_columns: tuple[str, ...]
    missing_columns: tuple[str, ...]
    reason: str
```

Funcoes recomendadas:

```python
def inferir_capacidades(colunas: set[str]) -> list[CapabilityResult]:
    ...


def analise_disponivel(capacidades: list[CapabilityResult], nome: str) -> bool:
    ...


def explicar_capacidades(capacidades: list[CapabilityResult]) -> str:
    ...
```

---

## Impacto em state

Campos recomendados para o state:

```text
capacidades_dominion
analises_executadas
analises_puladas
limitacoes_dados
```

Regras:

* `capacidades_dominion` deve ser produzido antes das analises.
* `analises_puladas` deve explicar colunas faltantes.
* `limitacoes_dados` deve ser usado no output final.
* Nenhum desses campos deve conter dataset completo.

---

## Impacto em tools

Cada tool analitica do Dominion deve declarar precondicoes.

Exemplo:

```text
analisar_desvio_plano:
  requer: sku, periodo, volume_real, volume_plano
```

Se precondicoes nao forem satisfeitas:

```text
nao executar a tool
registrar analise pulada
nao gerar sinal
explicar limitacao
```

Tools atuais com dados simulados podem continuar funcionando.

Ao adaptar para dataset canonico, preservar compatibilidade com:

```bash
python main.py --modo nexus
```

---

## Impacto em prompts

O LLM nao deve decidir sozinho se uma analise e possivel.

Essa decisao deve vir de regra deterministica de capacidades.

O prompt final pode explicar:

```text
A analise de ruptura nao foi executada porque o arquivo nao possui campos de estoque ou DOI.
```

O prompt nao pode dizer:

```text
Mesmo sem estoque, inferi risco de ruptura a partir da queda de volume.
```

---

## Impacto em auditoria

A auditoria deve registrar:

```text
capacidades_dominion_inferidas
analise_executada
analise_pulada
colunas_faltantes
sinais_gerados
```

Exemplo seguro:

```json
{
  "event_type": "analise_pulada",
  "phase": "dominion",
  "analysis": "risco_ruptura_doi",
  "metadata_safe": {
    "missing_columns": ["estoque_atual", "doi_atual"],
    "reason": "Dataset canonico nao contem colunas minimas para ruptura."
  }
}
```

---

## Impacto em testes

Testes exigidos:

* [x] dataset com colunas completas;
* [x] dataset sem plano;
* [x] dataset sem canal;
* [x] dataset sem periodo;
* [x] dataset sem estoque;
* [x] dataset com apenas volume_real;
* [x] analise compativel executa;
* [x] analise incompativel e pulada;
* [x] analise pulada nao gera sinal;
* [x] auditoria registra colunas faltantes;
* [x] output menciona limitacoes.

Comandos minimos:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

---

## Criterios de aceite

* [ ] Existe mecanismo deterministico para inferir capacidades.
* [ ] Dominion executa apenas analises suportadas.
* [ ] Analises puladas sao registradas.
* [ ] Analises puladas nao geram sinais.
* [ ] Output final menciona limitacoes relevantes.
* [ ] Testes cobrem schemas incompletos.
* [ ] Pipeline atual continua funcionando com dados simulados.
* [ ] Nenhum LLM decide capacidade analitica sozinho.
* [ ] Nenhuma coluna ausente e inventada.

---

## Plano de migracao

Implementar em etapas:

```text
1. Documentar capacidades minimas no planning.
2. Criar `dominion_capabilities.py`.
3. Criar testes de capacidades.
4. Integrar capacidades ao Dominion.
5. Fazer tools analiticas consultarem capacidades.
6. Registrar analises puladas em auditoria.
7. Atualizar output final para mencionar limitacoes.
8. Rodar E2E nexus.
9. Registrar em agent.log.md.
```

---

## Plano de rollback

Se a inferencia de capacidades quebrar o fluxo atual:

```text
1. Manter fluxo atual com dados simulados.
2. Desabilitar capacidades apenas para dataset simulado.
3. Registrar implementacao parcial.
4. Corrigir testes com fixtures pequenas.
```

Rollback proibido:

```text
rodar analises com colunas ausentes
inventar dados para completar schema
pedir ao LLM para preencher lacunas numericas
gerar sinais sem resultado deterministico
```

---

## Riscos

| Risco                                 | Probabilidade | Impacto | Mitigacao                                          |
| ------------------------------------- | ------------- | ------- | -------------------------------------------------- |
| Capacidade ser detectada erroneamente | Media         | Alto    | Testes por schema e validacao de colunas           |
| Analises demais serem puladas         | Media         | Medio   | Mensagens claras e melhoria incremental            |
| Usuario achar que sistema falhou      | Media         | Medio   | Explicar limitacoes dos dados                      |
| Tool executar sem precondicao         | Media         | Alto    | Harness/ToolRegistry validando required_state_keys |
| LLM inferir sinal onde dados faltam   | Media         | Alto    | Prompt e testes proibindo isso                     |

---

## Decisoes relacionadas

```text
ADR-0002 - LLM nao calcula numeros
ADR-0005 - DataShield Lite antes do Dominion
ADR-0009 - DataShield nao envia dataset completo ao LLM
ADR-0012 - Auditoria sem dados sensiveis
```

---

## Observacoes

Essa ADR torna o Dominion mais confiavel para arquivos reais.

Ela tambem ajuda a explicar ao usuario que ausencia de sinal nem sempre significa ausencia de problema; pode significar ausencia de dados suficientes.

Linguagem recomendada:

```text
O Dominion executa apenas analises suportadas pelas colunas disponiveis no dataset canonico.
```

Evitar:

```text
O Dominion sempre executa todas as analises independentemente dos dados.
```

### Addendum 2026-07-21 (ADR-0025)

No caminho PBI, as "capacidades" equivalem as **queries do catalogo DAX**
disponiveis e com `ok` em `catalog_execucao`, nao apenas colunas do CSV.
Catalogo Mondelez S&OE no PBI = backlog pos-PoC.
