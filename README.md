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

Salvar auditoria em arquivo customizado:

```bash
python main.py --modo nexus --audit-out auditoria/minha_sessao.json
```

## Testes

```bash
python -m pytest tests/ -v --override-ini="addopts="
```

## Arquitetura (MVP)

```text
Input Guardrail
  -> Dominion (loop LLM + tools deterministicas)
  -> Sinais estruturados
  -> Optimus (proposicoes deterministicas)
  -> Validador deterministico
  -> Critic LLM (auditoria read-only)
  -> Fila Nexus (human-in-the-loop)
  -> Output Guardrail
```

Componentes principais:

| Arquivo | Papel |
|---|---|
| `nexus.py` | Orquestrador do pipeline |
| `harness.py` | Loop Dominion (perceive-decide-act) |
| `optimus.py` | Proposicoes priorizadas |
| `validator.py` | Validacao formal pos-Optimus |
| `critic.py` | Auditoria LLM (leitura only) |
| `guardrails.py` | Input/output guardrails |
| `state_types.py` | Blackboard compartilhado |

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
