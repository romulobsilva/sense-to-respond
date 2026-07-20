# Testing Guide - Sense to Respond

> Guia oficial de testes do projeto.
> Toda mudanca de comportamento deve ter teste correspondente.
> Nenhum item deve ser marcado como concluido em `docs/planning.md` sem passar pelos testes minimos aplicaveis.

---

## 1. Principio central

O objetivo dos testes e garantir que o projeto preserve seus invariantes arquiteturais:

```text
IA = LLM + Harness
```

Isso significa testar que:

* o LLM nao calcula numeros;
* tools deterministicas calculam metricas e impactos;
* o harness controla execucao;
* guardrails continuam ativos;
* auditoria continua funcionando;
* proposicoes possuem evidencias;
* Critic permanece read-only;
* human-in-the-loop permanece obrigatorio;
* o pipeline principal continua executando.

---

## 2. Comandos minimos globais

Antes de considerar qualquer tarefa concluida, rodar:

```bash
python -m py_compile *.py
python main.py --modo nexus
```

Se a mudanca afetar modo legado, rodar tambem:

```bash
python main.py --modo legado
```

Se houver diretório de testes automatizados:

```bash
pytest
```

Se `pytest` ainda nao estiver configurado, testar os componentes diretamente via Python ou scripts temporarios, sem commitar scripts descartaveis.

---

## 3. Testes obrigatorios por tipo de mudanca

| Tipo de mudanca | Testes obrigatorios                                    |
| --------------- | ------------------------------------------------------ |
| `fix`           | Teste do bug corrigido + `python main.py --modo nexus` |
| `refactor`      | Testes dos componentes afetados + E2E nexus            |
| `feature`       | Teste unitario + teste de integracao + E2E             |
| `architecture`  | E2E + verificacao de spec + agent.log                  |
| `prompt`        | JSON valido + JSON invalido + retry + fallback         |
| `security`      | Caso permitido + caso bloqueado + auditoria            |
| `tool`          | Entrada valida + entrada invalida + output + auditoria |
| `state`         | Criacao, serializacao, conversao e compatibilidade     |
| `docs`          | Verificar consistencia com architecture/planning/rules |
| `test`          | Rodar suite completa disponivel                        |

---

## 4. Testes de invariantes

### 4.1 LLM nao calcula numeros

Objetivo:

```text
Garantir que valores numericos usados em decisoes venham de tools deterministicas.
```

Testar:

* impactos financeiros sao calculados em Python;
* desvios percentuais sao calculados em Python;
* DOI e tendencias, quando existirem, sao calculados por tools;
* prompts nao pedem ao LLM para calcular;
* explicacao final apenas cita numeros presentes no contexto.

Falha se:

```text
O LLM gerar numero novo usado como evidencia ou impacto.
```

---

### 4.2 Critic read-only

Objetivo:

```text
Garantir que o Critic apenas audite.
```

Testar:

* Critic recebe sinais e proposicoes;
* Critic retorna apenas `aprovado`, `confianca` e `problemas`;
* Critic nao cria proposicoes;
* Critic nao altera sinais;
* Critic nao altera impacto financeiro;
* falha do Critic nao executa acao operacional.

Falha se:

```text
A saida do Critic modificar proposicoes ou criar recomendacoes novas.
```

---

### 4.3 Human-in-the-loop

Objetivo:

```text
Garantir que nenhuma acao operacional seja executada automaticamente no MVP.
```

Testar:

* fila Nexus e gerada;
* itens com baixa confianca exigem revisao;
* output final contem disclaimer;
* nenhuma chamada Bridge/ERP/WMS/TMS existe no fluxo MVP;
* texto final usa linguagem de proposicao, nao de execucao.

Falha se:

```text
O sistema disser ou registrar que executou uma acao operacional.
```

---

### 4.4 Evidencias obrigatorias

Objetivo:

```text
Garantir que proposicoes sejam rastreaveis ate sinais.
```

Testar:

* toda proposicao possui lista `evidencias`;
* cada evidencia existe em `sinais`;
* validator falha se evidencia nao existir;
* output final inclui citacoes/evidencias;
* auditoria registra handoff entre sinais e proposicoes.

Falha se:

```text
Uma proposicao for aprovada sem evidencia existente.
```

---

### 4.5 Guardrails ativos

Objetivo:

```text
Garantir que input, harness e output guardrails continuam funcionando.
```

Testar:

* input curto demais e bloqueado;
* prompt injection simples e bloqueado;
* tool fora da whitelist nao executa;
* tool repetida e bloqueada quando proibida;
* output final tem disclaimer;
* baixa confianca gera revisao obrigatoria.

Falha se:

```text
Entrada maliciosa ou tool nao autorizada passar sem bloqueio.
```

---

## 5. Testes de guardrails

### 5.1 Input guardrail

Casos minimos:

```text
Pergunta valida
Pergunta muito curta
Pergunta muito longa
Prompt injection com "ignore previous instructions"
Prompt injection com "system prompt"
String vazia
```

Resultado esperado:

* perguntas validas passam;
* entradas suspeitas sao bloqueadas antes de qualquer LLM;
* bloqueio fica registrado nos logs.

---

### 5.2 Harness guardrail

Casos minimos:

```text
Tool valida
Tool inexistente
Tool repetida
Acao invalida retornada pelo LLM
Loop atinge max_iteracoes
Dados vazios e LLM tenta validar antes de carregar
```

Resultado esperado:

* tool valida executa;
* tool inexistente nao executa;
* tool repetida e bloqueada;
* acao invalida recebe fallback seguro;
* limite de iteracoes encerra loop;
* se dados estao vazios, harness corrige para `carregar_dados`.

---

### 5.3 Output guardrail

Casos minimos:

```text
Critic confianca abaixo do limiar
Critic confianca acima do limiar
Validacao deterministica falha
Proposicao de alto impacto
Sem proposicoes
```

Resultado esperado:

* disclaimer obrigatorio sempre presente;
* baixa confianca gera `[REVISAO OBRIGATORIA]`;
* validacao falha gera revisao obrigatoria;
* proposicoes aparecem com evidencias;
* sem proposicoes nao quebra resposta final.

---

## 6. Testes de prompts

### 6.1 Prompt `dominion.proximo_passo`

Testar com mock ou resposta simulada do LLM:

```text
JSON valido com acao permitida
JSON invalido
JSON com acao desconhecida
JSON sem justificativa
JSON com acao nao string
JSON com justificativa nao string
Resposta vazia
Acao `fim` correta
```

Resultado esperado:

* JSON valido e aceito;
* JSON invalido dispara retry;
* acao desconhecida nao executa tool arbitraria;
* fallback seguro e aplicado depois dos retries;
* evento e registrado na auditoria.

---

### 6.2 Prompt `critic.auditar`

Testar:

```text
aprovado=true, confianca valida
aprovado=false, confianca valida
aprovado como string
confianca como string
confianca menor que 0
confianca maior que 1
problemas nao lista
JSON invalido
Chaves faltando
```

Resultado esperado:

* `aprovado` deve ser booleano real;
* `confianca` deve estar entre 0.0 e 1.0;
* `problemas` deve ser `list[str]`;
* JSON invalido dispara retry;
* falha apos retries retorna aprovado=False e confianca=0.0.

---

### 6.3 Prompt `final.gerar_explicacao`

Testar:

```text
Resultados com divergencia acima de 10%
Critic com baixa confianca
Validacao com erro
Sem proposicoes
Proposicoes com evidencias
```

Resultado esperado:

* texto cita apenas numeros fornecidos;
* texto nao inventa valores;
* texto nao afirma execucao;
* texto menciona cautela quando necessario;
* output guardrail adiciona disclaimer e evidencias.

---

### 6.4 Prompt `datashield.inferir_mapa_semantico` (implementado)

Testar com mock (`tests/test_datashield_llm.py`):

```text
Schema claro
Schema ambiguo
JSON invalido
source_column inexistente
canonical_name invalido
confidence fora da faixa
mapeamentos vazios
warnings nao lista
colunas extras nao mapeadas
payload sem dataset completo
hibrido deterministico + LLM
```

Resultado esperado:

* schema claro passa;
* schema ambiguo pede confirmacao humana / gate;
* JSON invalido dispara retry;
* colunas inexistentes bloqueiam normalizacao;
* confidence baixo bloqueia avanco automatico (`HITL_MODE=auto`);
* colunas extras sao listadas em warnings;
* fixture Mondelez nao chama LLM (match deterministico suficiente).

### 6.5 Prompt futuro `datashield.gerar_script_etl` (ADR-0021)

Testar com mock:

```text
Script com apenas operacoes ETL permitidas
Script com calculo de desvio percentual (proibido)
Script com calculo de DOI (proibido)
Script com import de modulo nao permitido
Script vazio
JSON invalido
```

Resultado esperado:

* scripts com operacoes ETL permitidas passam;
* scripts com calculos de metricas sao rejeitados;
* scripts com imports proibidos sao rejeitados;
* JSON invalido dispara retry;
* script vazio retorna fallback seguro.

---

## 7. Testes de tools

### 7.1 Tool deterministica

Toda tool deterministica deve testar:

```text
entrada valida
entrada invalida
valores nulos
colunas ausentes
valores limite
saida esperada
sem chamada LLM
sem mutacao silenciosa do state
```

Exemplos atuais:

```text
validar_demanda
validar_custos
```

---

### 7.1b Tools parametrizadas (ADR-0019)

Toda tool parametrizada deve testar:

```text
entrada valida com mapa completo
entrada valida com mapa parcial (campos faltando)
DataFrame vazio
DataFrame com colunas erradas
mapa com campo inexistente no DataFrame
resultado deterministico reproduzivel
sem chamada LLM
```

Exemplos planejados:

```text
analisar_sellout(df, mapa)
analisar_sellin(df, mapa)
analisar_doi(df, mapa)
detectar_capacidades(mapa)
```

### 7.2 Tool de IO

Toda tool de IO deve testar:

```text
arquivo valido
arquivo inexistente
arquivo vazio
extensao nao suportada
permissao negada
saida estruturada
ausencia de segredo em logs
```

Exemplos planejados:

```text
ler_arquivo_csv
ler_arquivo_xlsx
salvar_template_mapeamento
carregar_template_mapeamento
```

---

### 7.3 Tool com LLM

Toda tool com LLM deve testar com mock:

```text
JSON valido
JSON invalido
chaves faltando
tipos errados
faixas invalidas
retry
fallback
payload minimo enviado ao LLM
```

Exemplo planejado:

```text
inferir_mapa_semantico
```

---

## 8. Testes de state

Quando `state_types.py` ou o contrato do state mudar, testar:

```text
criar_state_inicial
registrar_handoff
sinais_do_state
proposicoes_do_state
serializar_sinais_para_llm
serializar_proposicoes_para_llm
ItemFilaNexus.para_dict
ResultadoCritica.para_dict
ResultadoValidacao.para_dict
```

Resultado esperado:

* state inicial contem todos os campos obrigatorios;
* handoff e append-only;
* conversoes aceitam objetos e dicts validos;
* serializacao nao inclui dados sensiveis;
* pipeline nexus continua funcionando.

---

## 9. Testes de Optimus

Testar:

```text
sem sinais
sinal de demanda abaixo do threshold
sinal de demanda acima do threshold
sinal de custo abaixo do threshold
sinal de custo acima do threshold
feedback do validador
feedback do critic
ordenacao por impacto e urgencia
```

Resultado esperado:

* sem sinais nao deve gerar proposicoes validas;
* sinais abaixo do threshold nao geram proposicoes;
* proposicoes possuem evidencias;
* impactos sao deterministicos;
* ordenacao e estavel;
* feedback aparece sem alterar calculo numerico.

---

## 10. Testes do Validador

Testar proposicoes com:

```text
tipo fora da whitelist
evidencia inexistente
SKU inexistente
impacto_financeiro diferente de impacto_calculado
urgencia_horas <= 0
descricao vazia
lista vazia de proposicoes
```

Resultado esperado:

* validator retorna `ok=False`;
* erros sao claros e estruturados;
* validator nao chama LLM;
* validator nao corrige proposicao silenciosamente.

---

## 11. Testes de Nexus

### 11.1 E2E atual com dados simulados

Comando:

```bash
python main.py --modo nexus
```

Validar:

```text
input guardrail OK
Dominion executa
sinais extraidos
Optimus gera proposicoes
Validador roda
Critic roda
Fila Nexus e montada
Output guardrail aplicado
Auditoria gerada
```

---

### 11.2 E2E legado

Comando:

```bash
python main.py --modo legado
```

Validar:

```text
Dominion executa
explicacao final gerada
auditoria gerada
sem Optimus/Critic/Nexus completo
```

---

### 11.3 E2E futuro com CSV Mondelez (ADR-0019)

Comando planejado:

```bash
python main.py --modo nexus --input data/mondelez_s2r_base_diaria.csv
```

Validar:

```text
DataShield le arquivo CSV
perfil de dados e gerado
mapa semantico inferido (confianca > 0.90 para Mondelez)
schema confirmado via HITL
dataset canonico criado
capacidades detectadas (sellout, sellin, doi)
Dominion roda tools parametrizadas sobre dataset canonico
sinais de tipo desvio_sellout, desvio_sellin, doi_fora_politica
Optimus gera proposicoes com novos tipos
handoff DataShield -> Dominion registrado
```

### 11.4 E2E futuro com Streamlit (ADR-0022)

Comando planejado:

```bash
HITL_MODE=auto python main.py --modo nexus --input data/mondelez_s2r_base_diaria.csv
```

Validar com HITLAutoApprove:

```text
Pipeline roda sem intervencao humana
Arquivos JSON de aprovacao gerados em approvals/
Decisoes registradas na auditoria
Fila Nexus montada normalmente
```

---

## 12. Testes de auditoria

Testar:

```text
sessao_id gerado
timestamp presente
eventos append-only
eventos serializaveis em JSON
tool_inicio/tool_fim presentes
handoffs presentes
critic_auditoria presente
fila_nexus presente
output_guardrail presente
sessao_fim presente
```

Validar que auditoria nao contem:

```text
OPENAI_API_KEY
conteudo completo de .env
dataset completo
dados sensiveis desnecessarios
payload gigante
```

---

## 13. Testes de DataShield Lite

Quando DataShield Lite for implementado, testar:

### 13.1 Leitura

```text
csv com virgula
csv com ponto e virgula
xlsx valido
arquivo inexistente
arquivo vazio
extensao nao suportada
```

### 13.2 Perfil

```text
tipos inferidos
nulos por coluna
percentual de completeness
valores unicos
amostra limitada
```

### 13.3 Inferencia semantica

```text
coluna temporal clara
coluna SKU clara
metricas claras
colunas ambiguas
confidence baixa
source_column inexistente
```

### 13.4 Confirmacao humana (ADR-0022)

```text
usuario confirma via HITLTerminal
usuario rejeita via HITLTerminal
HITLAutoApprove aprova automaticamente (testes)
HITLStreamlit gera e consome JSON (integracao)
modo no-interactive com confidence alta
modo no-interactive com confidence baixa
```

### 13.6 Niveis de adaptacao (ADR-0020)

```text
Nivel 1: CSV com colunas claras (Mondelez) -> mapeamento puro
Nivel 2: CSV com nomes diferentes -> ETL gerado e aprovado
Nivel 3: CSV incompativel -> diagnostico retornado, pipeline parcial
```

### 13.7 Script ETL gerado (ADR-0021)

```text
script com operacoes ETL permitidas -> aprovado
script com calculo de metrica -> rejeitado pela validacao estatica
script aprovado executado em sandbox -> output valido
script aprovado executado em sandbox -> schema checker passa
```

### 13.5 Normalizacao

```text
renomeia colunas corretamente
preserva colunas auxiliares
bloqueia coluna inexistente
bloqueia mapa semantico invalido
```

---

## 13b. Testes de HITL (ADR-0022, ADR-0023)

### 13b.1 Protocolo abstrato

```text
HITLAutoApprove: pipeline roda sem intervencao
HITLTerminal com mock de input(): decisoes corretas
InterfaceHITL: qualquer implementacao funciona com Nexus
```

### 13b.2 Arquivos JSON de aprovacao

```text
JSON gerado com todos os campos obrigatorios
JSON com decisao preenchida e lida pelo pipeline
JSON com decisao rejeitada e pipeline para
Timeout de polling (limite maximo de espera)
Cleanup de arquivos antigos
Sem dados sensiveis nos JSONs
```

### 13b.3 Streamlit (integracao)

```text
Streamlit le pedidos pendentes de approvals/
Streamlit grava decisao no JSON
Pipeline detecta decisao e continua
Multiplos pedidos em sequencia
```

Arquivos de teste sugeridos:

```text
test_hitl.py
test_hitl_json.py
test_hitl_streamlit.py (integracao)
```

---

## 13c. Testes de portabilidade (ADR-0024)

### 13c.1 DomainThresholds

```text
Defaults Mondelez preservam comportamento existente
Thresholds alterados mudam classificacao de severidade
DOI_RUPTURA_DIAS=5 classifica DOI 10 como overstock (pereciveis)
```

### 13c.2 NR impacto real

```text
Sinal com nr_impacto > 0 priorizado por NR, nao toneladas
Sinal com nr_impacto == 0 usa fallback de toneladas
Priorizacao muda com NR real vs toneladas
```

### 13c.3 Forward marker

```text
FORWARD_MARKER=nan detecta NaN como forward (default)
FORWARD_MARKER=zero detecta zeros como forward
Dados actuais nao sao classificados como forward
```

### 13c.3b Fronteira oportunidade vs ruptura + priorizacao

```text
DOI < DOI_RUPTURA + SO acima do plano -> ruptura (risco primario)
Ruptura + plano subdimensionado -> dual framing (ruptura E capturar_oportunidade)
Oportunidade pura: DOI saudavel [RUPTURA, OVERSTOCK] + SO acima + plano curto
Peso questionar_premissa_plano sobe na fila vs snapshot com mesmo NR
impacto_financeiro bruto == impacto_calculado (peso so no sort)
Snapshot SO/SI/DOI com janela recente exclui series antigas
Alertas forward carregam nr_impacto do periodo recente
Fila Nexus ordena com o mesmo I_prio do Optimus (nao so R$ bruto)
PESO_* via DomainThresholds/.env altera a ordem sem mudar R$
DOI overstock + tendencia estavel + |SO desvio| < limiar -> sem rebalancear
```

### 13c.3c Resumo executivo estratificado + filtro persistente

```text
TOP_N_DOI / TOP_N_FORWARD / TOP_N_OPORTUNIDADES (ou --top-doi/--top-forward/--top-opps)
Blocos separados: top_doi, top_forward, top_oportunidades (sem ranking misturado)
Dentro de DOI/forward: cota ruptura vs overstock (diversidade de polaridade)
DOI com NR alto nao remove forward do quadro executivo
Ordenacao por topico via I_prio; impacto_financeiro bruto inalterado
--top-riscos legado aplica o mesmo N a DOI e FORWARD
Persistente com |impacto|<100 e |desvio%|<5 nao gera proposicao
state.resumo_executivo gravado na auditoria (inclui diversidade_*)
Fixture temporal: Belvita em top_doi e/ou top_forward; dual framing testado
```

### 13c.3d Export PNG do resumo executivo

```text
plotar_resumo_executivo(resumo) -> output/recomendacoes_<sessao_id>.png
Barras / secoes refletem len(top_doi|top_forward|top_oportunidades)
N=3 vs N=5 muda quantidade de itens no grafico (mesmo contrato de campos)
Sem SKU/marca hardcoded no codigo de plotagem
Evento auditoria visualizacao_png com caminho e contagens
state.artefatos_visuais contem o path do PNG
LLM nao e chamado na geracao do PNG
```

### 13c.3e Relatorio analista HTML -> PDF

```text
gerar_relatorio_analista(...) -> output/relatorio_<sessao_id>.html|.pdf
HTML contem secoes: cabecalho, tabelas top N, grafico, leitura por bloco,
  analise narrativa, HITL/disclaimer
Numeros das tabelas == resumo_executivo do mesmo input
PDF gerado quando WeasyPrint disponivel; senao html_ok e pdf ok=False
Evento auditoria relatorio_pdf com caminhos
LLM nao reordena top N; narrativa e citacao da explicacao pos-guardrail
```

### 13c.4 Schema configuravel

```text
Schema padrao Mondelez funciona sem SCHEMA_PATH
Schema alternativo carregado de JSON funciona
Schema com campos faltantes gera diagnostico
```

---

## 14. Testes de seguranca

Testar:

```text
prompt injection no input
tentativa de exibir system prompt
tentativa de executar tool inexistente
tentativa de ativar Bridge
tentativa de remover human-in-the-loop
arquivo com extensao nao suportada
log sem segredo
auditoria sem chave de API
```

Resultado esperado:

* bloqueio seguro;
* log claro;
* nenhuma chamada LLM antes do input guardrail;
* nenhuma execucao operacional.

---

## 15. Testes de regressao

Antes de concluir refatoracoes grandes, comparar:

```text
acoes_executadas
numero de sinais
numero de proposicoes
validacao.ok
quantidade de itens na fila
presenca de disclaimer
presenca de auditoria
```

Se mudar comportamento esperado, registrar em:

```text
docs/architecture.md
docs/planning.md
docs/agent.log.md
```

---

## 16. Estrutura recomendada de testes

Diretorio sugerido:

```text
tests/
```

Arquivos sugeridos:

```text
test_guardrails.py
test_agent_decision.py
test_critic.py
test_tools.py
test_tools_parametrizadas.py
test_state_types.py
test_sinais.py
test_optimus.py
test_validator.py
test_nexus_pipeline.py
test_datashield_tools.py
test_datashield_schema.py
test_datashield_etl.py
test_hitl.py
test_hitl_json.py
```

---

## 17. Dados de teste

Regras:

* usar apenas dados ficticios;
* nao incluir dados reais de cliente;
* nao incluir informacoes pessoais;
* nao incluir arquivos grandes;
* manter exemplos pequenos e legiveis.

Diretorio sugerido:

```text
tests/fixtures/
```

Exemplos:

```text
sellout_simples.csv
sellout_schema_ambiguo.csv
demanda_custos_basico.csv
arquivo_vazio.csv
mondelez_ficticio.csv (mesmas colunas do real, dados fake)
nielsen_incompativel.csv (para testar Nivel 3)
espanhol_nomes_diferentes.csv (para testar Nivel 2)
```

---

## 18. Como registrar testes no agent.log.md

Ao final da sessao, registrar:

```text
### Testes realizados

- `python -m py_compile *.py`: passou/falhou
- `python main.py --modo nexus`: passou/falhou
- `python main.py --modo legado`: passou/falhou/nao aplicavel
- `pytest`: passou/falhou/nao configurado
- Testes manuais: listar
- Limitacoes: listar
```

Se algum teste nao foi rodado, explicar o motivo.

---

## 19. Regra para falhas

Se teste obrigatorio falhar:

* nao marcar item como `[x]`;
* nao dizer que a tarefa esta concluida;
* registrar falha em `docs/agent.log.md`;
* propor correcao ou rollback;
* garantir que o usuario saiba o estado real.

---

## 20. Regra final

Se uma mudanca nao pode ser testada, ela nao deve ser considerada concluida.

Se um teste contradiz a arquitetura, a arquitetura deve ser revisada antes do codigo.

Se a arquitetura e o teste estiverem certos, o codigo deve ser corrigido.
