# Sense to Respond - MVP Nexus

Sistema multi-agente para deteccao de sinais e geracao de proposicoes de acao
na cadeia comercial (S&OE), com harness controlado e human-in-the-loop.

Principio central: **IA = LLM + Harness**. Numeros sao sempre calculados por
tools deterministicas (Python/pandas). O LLM decide passos e gera narrativa.

## Pre-requisitos

- Python 3.10+
- Chave da API OpenAI

## Instalacao

```bash
git clone https://github.com/romulobsilva/sense-to-respond.git
cd sense-to-respond

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edite .env e defina OPENAI_API_KEY
```

## Configuracao (.env)

| Variavel | Padrao | Descricao |
|---|---|---|
| `OPENAI_API_KEY` | - | Chave da API OpenAI (obrigatoria) |
| `OPENAI_MODEL` | `gpt-4o-mini` | Modelo LLM |
| `LIMIAR_CONFIANCA_CRITIC` | `0.7` | Abaixo disso: revisao obrigatoria |
| `MAX_OPTIMUS_RETRIES` | `1` | Retries do Optimus (0 a 3) |

## Execucao

Modo MVP completo (Nexus + Validador + Critic + fila):

```bash
python main.py --modo nexus
```

Modo legado (apenas Dominion + explicacao):

```bash
python main.py --modo legado
```

Chat analitico Power BI (ADR-0026; paralelo ao batch; nao gera PDF):

```bash
# one-shot (requer PBI_ACCESS_TOKEN + PBI_ARTIFACT_ID; modelo default gpt-5.4)
python main.py --modo chat --pergunta "Tem estoque suficiente no curto prazo?"

# REPL sequencial (historico em RAM ate "sair"; estilo Cursor/ChatGPT)
python main.py --modo chat
```

Salvar auditoria em arquivo customizado:

```bash
python main.py --modo nexus --audit-out auditoria/minha_sessao.json
```

## Testes

```bash
python -m pytest tests/ -v --override-ini="addopts="
```

## Arquitetura (MVP)

Componentes principais:

| Componente | Arquivo | Usa LLM? | Papel |
|---|---|---|---|
| **Nexus** | `nexus.py` | Nao | Orquestra a sequencia e governa o fluxo |
| **Dominion** | `harness.py` | Sim | LLM escolhe a ordem das tools; Python calcula |
| **Optimus** | `optimus.py` | Nao | Transforma sinais em propostas (deterministico) |
| **Validador** | `validator.py` | Nao | Checa regras formais (sim/nao) |
| **Critic** | `critic.py` | Sim | Julga coerencia (LLM leitura-only) |
| **Chat PBI** | `chat_pbi.py` | Sim | Q&A analitico MCP (ADR-0026; paralelo ao batch) |
| **Guardrails** | `guardrails.py` | Nao | Input/output guardrails |
| **State** | `state_types.py` | Nao | Blackboard compartilhado entre agentes |

### Fluxo de eventos e handoffs (MVP implementado)

O diagrama abaixo mostra o pipeline implementado no MVP. Cada seta e uma
chamada real no codigo. Os blocos `Note` marcam handoffs (transicoes de fase
registradas na auditoria). Os blocos `alt` representam retries controlados
pelo Nexus quando o Validador ou o Critic encontram problemas.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant N as Nexus
    participant DOM as Dominion
    participant OPTI as Optimus
    participant VAL as Validador
    participant C as Critic

    U->>N: pergunta
    N->>N: input guardrail
    N->>DOM: executar loop tools
    DOM->>N: state.resultados
    Note over N: handoff dominion para sinais

    N->>OPTI: ler sinais
    OPTI->>N: state.proposicoes
    Note over N: handoff sinais para optimus

    N->>VAL: validar proposicoes vs sinais
    VAL->>N: state.validacao
    Note over N: handoff optimus para validador

    alt validador falhou e retry disponivel
        N->>OPTI: retry com erros no contexto
        OPTI->>N: state.proposicoes revisadas
        N->>VAL: revalidar
        VAL->>N: state.validacao atualizada
    end

    N->>C: auditar proposicoes vs sinais
    C->>N: state.critica
    Note over N: handoff validador para critic

    alt critic falhou e retry disponivel
        N->>OPTI: retry com feedback critic
        OPTI->>N: state.proposicoes revisadas
        N->>VAL: revalidar
        VAL->>N: state.validacao atualizada
        N->>C: reauditar
        C->>N: state.critica atualizada
    end

    N->>N: montar fila_nexus
    N->>N: output guardrail
    N->>U: resposta + fila para decisao
```

**Principios do fluxo:**

- **Nenhum componente se autoaprova.** Optimus propoe, Validador contesta regras formais, Critic contesta coerencia, Nexus arbitra, humano decide.
- **Handoff** = passagem formal de artefato via state, registrada na auditoria para rastreabilidade.
- **Retry controlado:** se Validador ou Critic falhar, Nexus envia os erros como feedback ao Optimus, que regenera propostas. Limite configuravel via `MAX_OPTIMUS_RETRIES`.
- **LLM nunca calcula numeros.** Todos os impactos financeiros e desvios sao calculados por Python/pandas.

### Visao macro com DataShield (MVP + fase futura)

O diagrama abaixo inclui o DataShield Lite (fase 1.5, planejado) que fara
inferencia semantica de arquivos xlsx/csv antes do Dominion. O restante do
pipeline e o mesmo do MVP.

```mermaid
sequenceDiagram
    participant U as Usuario
    participant N as Nexus
    participant DS as DataShieldLite
    participant DOM as Dominion
    participant SIG as Sinais
    participant OPTI as Optimus
    participant VAL as Validador
    participant C as Critic
    participant SB as State

    U->>N: pergunta + arquivo opcional
    N->>N: input guardrail

    rect rgb(240, 248, 255)
        Note over N,DS: arquivo presente
        N->>DS: processar arquivo
        DS->>SB: perfil_dados, mapa_semantico, dataset_canonico
        DS->>N: status_schema
    end

    alt schema invalido
        N->>U: solicitar confirmacao ou correcao humana
    else schema ok ou sem arquivo
        N->>DOM: executar analise
        DOM->>SB: ler dados disponiveis
        DOM->>SB: resultados, capacidades, analises_puladas

        N->>SIG: estruturar sinais
        SIG->>SB: sinais

        N->>OPTI: gerar proposicoes
        OPTI->>SB: proposicoes

        N->>VAL: validar proposicoes contra sinais
        VAL->>SB: validacao

        alt validacao falhou
            N->>OPTI: retry controlado com erros
            OPTI->>SB: proposicoes revisadas
            N->>VAL: revalidar
            VAL->>SB: validacao atualizada
        else validacao ok
            N->>C: auditar proposicoes
            C->>SB: critica
        end

        alt critic reprovou ou baixa confianca
            N->>OPTI: retry controlado com feedback
            OPTI->>SB: proposicoes revisadas
            N->>VAL: revalidar
            VAL->>SB: validacao atualizada
            N->>C: reauditar
            C->>SB: critica atualizada
        else critic ok
            N->>SB: montar fila_nexus
        end

        N->>N: output guardrail
        N->>U: resposta final e fila para revisao humana
    end
```

### Pipeline detalhado (flowchart)

Visao por camadas: entrada, DataShield, state blackboard, Dominion, Sinais,
Optimus, validacao/auditoria e saida com human-in-the-loop.

```mermaid
flowchart TB
    START[Usuario<br/>pergunta + arquivo opcional]

    subgraph ENTRADA["Camada de entrada"]
        IG[Input Guardrail<br/>validacao inicial]
    end

    subgraph DATASHIELD["DataShield Lite"]
        DS1[Perfil de dados]
        DS2[Inferencia semantica controlada]
        DS3[Validacao do mapa semantico]
        DS4[Dataset canonico + schema_confirmado]
        DSG{Schema confirmado?}
    end

    subgraph STATE["State Blackboard"]
        SB[(State compartilhado)]
    end

    subgraph DOMINION["Fase Dominion"]
        DOM1[Inferir capacidades do dataset]
        DOM2[Executar apenas analises compativeis]
        DOM3[Resultados analiticos]
    end

    subgraph SINAIS["Fase Sinais"]
        SIG[Extrair sinais estruturados]
    end

    subgraph OPTIMUS["Fase Optimus"]
        OPT[Gerar proposicoes candidatas]
    end

    subgraph VALIDACAO["Camada de validacao e auditoria"]
        VAL[Validador deterministico]
        CRIT[Critic read-only]
        RETRY{Retry controlado permitido?}
    end

    subgraph SAIDA["Camada de saida"]
        FILA[Fila Nexus ranqueada]
        REV[Flag de revisao obrigatoria]
        OG[Output Guardrail<br/>disclaimer + evidencias + limitacoes]
        HITL[Human-in-the-loop<br/>usuario decide]
    end

    START --> IG
    IG -->|bloqueado| REJ[Encerrar com resposta segura]
    IG -->|ok| DS1

    DS1 --> DS2 --> DS3 --> DS4 --> DSG
    DSG -->|nao| HUM[Solicitar confirmacao humana]
    DSG -->|sim| SB

    SB --> DOM1 --> DOM2 --> DOM3 --> SB
    SB --> SIG --> SB
    SB --> OPT --> SB
    SB --> VAL --> SB

    VAL -->|falhou| RETRY
    VAL -->|ok| CRIT
    CRIT --> SB

    CRIT -->|baixa confianca ou reprovado| RETRY
    CRIT -->|ok| FILA

    RETRY -->|sim| OPT
    RETRY -->|nao| FILA

    FILA --> REV --> OG --> HITL
```

**Guardrails (3 camadas):**

| Camada | Quando roda | O que faz |
|---|---|---|
| **Input** | Antes de qualquer LLM/tool | Bloqueia pergunta curta, longa ou com injection |
| **Harness** | Durante execucao | Whitelist de tools, max iteracoes, JSON validado com retry |
| **Output** | Antes de devolver ao usuario | Disclaimer obrigatorio, citacoes, flag de revisao |

## Documentacao

- `docs/architecture.md` - especificacao da solucao
- `docs/planning.md` - checklist de implementacao
- `docs/testing.md` - guia de testes
- `docs/adr/` - decisoes arquiteturais (ADRs)
- `rules.md` - regras de desenvolvimento

Documentos de contexto EY/7D (PDF, PPTX) **nao estao versionados** neste
repositorio por serem material interno.

## Licenca

A definir.
