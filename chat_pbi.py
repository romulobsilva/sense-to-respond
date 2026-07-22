"""
Chat PBI analitico (ADR-0026 / planning 1.7b).

Nucleo UI-agnostic: run(pergunta) -> ChatResult.
CLI (main.py) apenas imprime answer_markdown.
Batch S&OE (Nexus/Optimus) permanece intacto.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from audit import AuditTrail, gerar_sessao_id
from config import Settings
from guardrails import verificar_input
from powerbi_mcp import PowerBIQueryClient, PowerBIQueryError, RestPowerBIClient

DEFAULT_PBI_MCP_URL = "https://api.fabric.microsoft.com/v1/mcp/powerbi"
TRANSPORTS_VALIDOS = frozenset({"mcp", "rest", "mock"})
CHAT_AUDIT_DIR = Path("auditoria")

# Playbook geral (qualquer pergunta NL): espelha o caminho eficiente do
# chat Cursor (schema/contexto -> DAX -> ExecuteQuery -> narrativa).
SYSTEM_INSTRUCTIONS = """Voce e um analista S&OE consultando um semantic model Power BI.

OBJETIVO
Responder QUALQUER pergunta de negocio com numeros do modelo, no menor
numero util de tool calls. Nao ha FAQ fixo: descubra o caminho a cada
pergunta.

CAMINHO EFICIENTE (siga nesta ordem; pule o que ja souber)
1) Intencao: o que medir? (KPI agregado, ranking SKU, filtro data/pais,
   tendencia, etc.)
2) Contexto de modelo:
   - Se nao souber tabelas/medidas: GetSemanticModelSchema UMA vez.
   - Se a pergunta citar dia/mes SEM ano: NAO assuma 2023. Resolva a
     data com ExecuteQuery (ex. Last Actual Date / DimDate) ou use o
     ano da data de hoje nas instrucoes + confirme no modelo.
3) Obter DAX (prioridade = estabilidade, nao GenerateQuery-first):
   - PREFERIDO: escrever DAX EVALUATE curto com medidas do schema/hints
     e chamar ExecuteQuery (pode enviar 2 statements no mesmo call:
     agregado + detalhe).
   - FALLBACK: GenerateQuery NO MAXIMO UMA vez, so se a pergunta for
     complexa/nova e voce nao souber montar o DAX.
   - Se GenerateQuery falhar ou estiver indisponivel (rest): DAX manual
     + ExecuteQuery imediatamente.
4) ExecuteQuery. Sem linhas validas, NAO conclua "nao ha dados" sem
   ter tentado um segundo DAX mais simples (agregado ou sem filtro
   duvidoso).
5) Resposta em portugues, Markdown ESTRUTURADO (ver COMPLETUDE).

COMPLETUDE DA RESPOSTA (alvo: igual ou mais detalhado que chat IDE rico)
Nao responda so com KPI agregado quando a pergunta for de cobertura,
estoque, risco, ruptura, "suficiente", curto prazo, alertas ou DOI.
Nesses casos a resposta OBRIGATORIA:
  A) tabela agregada com PELO MENOS:
     # SKUs in Alert, # SKUs Understock, # SKUs Overstock,
     DOI Actual (Days), e Policy DOI Ideal se disponivel;
  B) tabela de detalhe com 5 a 10 SKUs (nao 1 exemplo), colunas:
     Country, Category, Brand, SKU_Code, SKU_Description,
     Alert Type, DOI Status, DOI Actual (Days), Policy DOI Ideal,
     SellOut Actual (Ton) quando existir;
  C) conclusao 2-4 frases: sim / nao / parcial; citar 2+ SKUs/paises
     se houver understock; contrastar agregado vs pressao pontual.
Padrao eficiente (1 ExecuteQuery, 2 DAX) - use este shape quando couber:
  DAX1:
    EVALUATE ROW(
      "SKUsInAlert", [# SKUs in Alert],
      "SKUsUnderstock", [# SKUs Understock],
      "SKUsOverstock", [# SKUs Overstock],
      "DOIActualDays", [DOI Actual (Days)],
      "DOIIdealDays", [Policy DOI Ideal],
      "SellOutActualTon", [SellOut Actual (Ton)]
    )
  DAX2:
    EVALUATE TOPN(
      10,
      SUMMARIZECOLUMNS(
        'Fact_S2R'[Country], 'Fact_S2R'[Category], 'Fact_S2R'[Brand],
        'Fact_S2R'[SKU_Code], 'Fact_S2R'[SKU_Description],
        "AlertType", [Alert Type],
        "DOIStatus", [DOI Status],
        "DOIActualDays", [DOI Actual (Days)],
        "DOIIdealDays", [Policy DOI Ideal],
        "SellOutActualTon", [SellOut Actual (Ton)],
        "AlertSeverity", [Alert Severity]
      ),
      [AlertSeverity], DESC
    )
Proibido: tabela de detalhe com 1 linha quando understock/alertas > 1;
proibido coluna agregada (# SKUs Understock) no grain de SKU.
Se o primeiro detalhe vier pobre, REEXECUTE com o DAX2 acima antes
de concluir. Nunca diga "estoque suficiente" ignorando understock.

Para perguntas pontuais (um SKU, um pais, uma data unica) o detalhe
pode ser so essa fatia; ainda assim mostre numero + status + ideal.

REGRAS DURAS
- Numeros so das tools. Nunca invente DOI, contagens ou status.
- Nao fique em loop em GenerateQuery (max 1 tentativa).
- Nao ranqueie proposicoes S&OE nem sugira ERP/WMS/Bridge.
- Se tool falhar, diga o limite e continue com ExecuteQuery.
- Use sempre o artifactId default informado nas instrucoes, salvo o
  usuario pedir outro.
"""


def _extrair_medidas_do_dax(dax: str) -> List[str]:
    """
    Extrai nomes de medidas [Nome] de um statement DAX (heuristica).
    """
    achados = re.findall(r"\[([^\]]+)\]", dax or "")
    unicos: List[str] = []
    vistos = set()
    for nome in achados:
        chave = nome.strip()
        if not chave or chave in vistos:
            continue
        # ignora aliases de coluna tipicos em ROW("Alias", ...)
        if chave.startswith("Fact_") or chave.startswith("Dim"):
            continue
        vistos.add(chave)
        unicos.append(chave)
    return unicos


def carregar_hints_catalogo(catalog_path: Optional[str]) -> str:
    """
    Le o YAML de catalogo e monta dicas de medidas/queries para o agente.

    Nao executa DAX; so acelera o caminho (como memoria de trabalho).
    """
    if not catalog_path or not str(catalog_path).strip():
        return ""
    caminho = Path(catalog_path)
    if not caminho.is_file():
        return ""
    try:
        import yaml
    except ImportError:
        return ""
    try:
        with caminho.open("r", encoding="utf-8") as handle:
            doc = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return ""
    if not isinstance(doc, dict):
        return ""
    queries = doc.get("queries")
    if not isinstance(queries, list):
        return ""
    linhas = [
        "HINTS DO CATALOGO BATCH (atalho; chat pode gerar DAX ad hoc):",
        f"catalog_id={doc.get('catalog_id', '')}",
    ]
    medidas: List[str] = []
    for item in queries:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("query_id", ""))
        desc = str(item.get("description", ""))
        dax = str(item.get("dax", ""))
        linhas.append(f"- {qid}: {desc}")
        for m in _extrair_medidas_do_dax(dax):
            if m not in medidas:
                medidas.append(m)
    if medidas:
        linhas.append("Medidas vistas no catalogo:")
        linhas.append(", ".join(medidas[:40]))
    return "\n".join(linhas)


def montar_instrucoes_agente(
    *,
    artifact_id: str,
    transport: str,
    catalog_path: Optional[str] = None,
    hoje: Optional[date] = None,
) -> str:
    """
    Instrucoes de sistema + contexto de sessao (data, transport, hints).
    """
    dia = hoje or date.today()
    hints = carregar_hints_catalogo(catalog_path)
    partes = [
        SYSTEM_INSTRUCTIONS,
        "",
        "CONTEXTO DA SESSAO",
        f"- Data de hoje (calendario local): {dia.isoformat()} "
        f"(ano de referencia {dia.year})",
        f"- Default artifactId: {artifact_id}",
        f"- Transport: {transport}",
    ]
    if transport == "rest":
        partes.append(
            "- GenerateQuery INDISPONIVEL: ExecuteQuery com DAX manual "
            "(agregado + detalhe no mesmo call quando a pergunta pedir "
            "cobertura/risco)."
        )
    elif transport == "mcp":
        partes.append(
            "- Preferir ExecuteQuery com DAX manual; GenerateQuery so como "
            "fallback (max 1x). Completude: agregado + SKUs sob pressao."
        )
    if hints:
        partes.extend(["", hints])
    return "\n".join(partes)


@dataclass
class ChatResult:
    """
    Resultado estavel do nucleo de chat (CLI ou UI futura).
    """

    answer_markdown: str
    tables: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    bloqueado: bool = False
    motivo: str = ""


AgentRunner = Callable[[str], str]


def resolver_transport(valor: Optional[str] = None) -> str:
    """
    Resolve CHAT_PBI_TRANSPORT (mcp|rest|mock).
    """
    raw = (valor or os.getenv("CHAT_PBI_TRANSPORT", "mcp") or "mcp").strip().lower()
    if raw not in TRANSPORTS_VALIDOS:
        raise ValueError(
            f"CHAT_PBI_TRANSPORT '{raw}' invalido. "
            f"Validos: {', '.join(sorted(TRANSPORTS_VALIDOS))}"
        )
    return raw


def formatar_saida_cli(resultado: ChatResult, pergunta: str) -> str:
    """
    Formata ChatResult para stdout do terminal.
    """
    linhas = [
        "=== CHAT PBI ===",
        f"Pergunta: {pergunta.strip()}",
        "",
    ]
    if resultado.bloqueado:
        linhas.append(f"BLOQUEADO: {resultado.motivo}")
    else:
        linhas.append(resultado.answer_markdown.strip())
    meta = resultado.meta or {}
    transport = meta.get("transport", "")
    sessao = meta.get("sessao_id", "")
    modelo = meta.get("openai_model", "")
    if transport or sessao or modelo:
        linhas.extend(
            [
                "",
                f"(sessao={sessao} transport={transport} model={modelo})",
            ]
        )
    linhas.append("=== FIM CHAT ===")
    return "\n".join(linhas)


def _truncar(texto: str, max_chars: int = 400) -> str:
    """Trunca texto para auditoria sem vazar dumps grandes."""
    limpo = (texto or "").strip()
    if len(limpo) <= max_chars:
        return limpo
    return f"{limpo[:max_chars]}..."


def _build_local_tools(
    *,
    client: Optional[PowerBIQueryClient],
    default_artifact_id: str,
    citations: List[Dict[str, Any]],
    allow_generate_query: bool,
    mock_schema: Optional[Dict[str, Any]] = None,
    mock_generate: Optional[str] = None,
) -> List[Any]:
    """
    Constroi FunctionTools locais (transport rest/mock).
    """
    from agent_framework import tool

    @tool(name="GetSemanticModelSchema")
    def get_semantic_model_schema(artifactId: str) -> str:
        """
        Retrieve semantic model schema metadata for the given artifactId.
        """
        aid = (artifactId or default_artifact_id).strip()
        citations.append(
            {
                "tool": "GetSemanticModelSchema",
                "artifact_id": aid,
            }
        )
        if mock_schema is not None:
            return json.dumps(mock_schema, ensure_ascii=True)
        return json.dumps(
            {
                "artifact_id": aid,
                "note": (
                    "Schema completo requer transport=mcp. "
                    "Use medidas conhecidas do catalogo Mondelez S2R "
                    "(DOI Actual, DOI Plan, Policy DOI Ideal, DOI Status, "
                    "SKU, Country, Date)."
                ),
            },
            ensure_ascii=True,
        )

    @tool(name="GenerateQuery")
    def generate_query(artifactId: str, userInput: str) -> str:
        """
        Generate a DAX query for the user question (MCP-parity tool).
        """
        aid = (artifactId or default_artifact_id).strip()
        citations.append(
            {
                "tool": "GenerateQuery",
                "artifact_id": aid,
                "user_input": _truncar(userInput, 200),
            }
        )
        if not allow_generate_query:
            return (
                "GenerateQuery indisponivel neste transport "
                "(use CHAT_PBI_TRANSPORT=mcp). "
                "Escreva DAX EVALUATE simples e chame ExecuteQuery."
            )
        if mock_generate is not None:
            return mock_generate
        return "GenerateQuery mock sem DAX configurado."

    @tool(name="ExecuteQuery")
    def execute_query(
        artifactId: str,
        daxQueries: List[str],
        maxRows: Optional[int] = None,
    ) -> str:
        """
        Execute one or more DAX EVALUATE statements and return rows.
        """
        aid = (artifactId or default_artifact_id).strip()
        limit = 250 if maxRows is None else int(maxRows)
        if client is None:
            citations.append(
                {
                    "tool": "ExecuteQuery",
                    "artifact_id": aid,
                    "erro": "client_ausente",
                }
            )
            return json.dumps({"erro": "cliente PBI ausente"}, ensure_ascii=True)
        saidas: List[Dict[str, Any]] = []
        for dax in daxQueries:
            citations.append(
                {
                    "tool": "ExecuteQuery",
                    "artifact_id": aid,
                    "dax": _truncar(dax, 240),
                }
            )
            try:
                result = client.execute_query(
                    aid,
                    dax,
                    max_rows=limit,
                    query_id=None,
                )
                saidas.append(
                    {
                        "columns": result.columns,
                        "rows": result.rows[:limit],
                        "n_rows": len(result.rows),
                        "meta": {
                            k: v
                            for k, v in result.meta.items()
                            if k != "token"
                        },
                    }
                )
            except PowerBIQueryError as exc:
                saidas.append({"erro": str(exc)})
        return json.dumps(saidas, ensure_ascii=True, default=str)

    return [get_semantic_model_schema, generate_query, execute_query]


def _criar_cliente_rest_ou_none(settings: Settings) -> Optional[PowerBIQueryClient]:
    """Cria RestPowerBIClient se houver token."""
    token = (settings.pbi_access_token or "").strip()
    if not token:
        return None
    return RestPowerBIClient(token)


async def _run_maf_async(
    pergunta: str,
    *,
    settings: Settings,
    transport: str,
    artifact_id: str,
    citations: List[Dict[str, Any]],
    tools_override: Optional[Sequence[Any]] = None,
) -> str:
    """
    Executa agente MAF com MCP remoto ou tools locais.
    """
    from agent_framework import Agent, MCPStreamableHTTPTool
    from agent_framework.openai import OpenAIChatClient

    # Chat pode usar modelo mais forte via CHAT_OPENAI_MODEL (batch intacto).
    model_chat = (
        (settings.chat_openai_model or "").strip()
        or settings.openai_model
    )
    client = OpenAIChatClient(
        model=model_chat,
        api_key=settings.openai_api_key,
    )
    instructions = montar_instrucoes_agente(
        artifact_id=artifact_id,
        transport=transport,
        catalog_path=settings.pbi_catalog_path,
    )
    instructions = (
        f"{instructions}\n- Modelo LLM desta sessao: {model_chat}\n"
    )

    if tools_override is not None:
        async with Agent(
            client=client,
            name="ChatPBI",
            instructions=instructions,
            tools=list(tools_override),
        ) as agent:
            response = await agent.run(pergunta)
            return (response.text or "").strip()

    if transport == "mcp":
        token = (settings.pbi_access_token or "").strip()
        if not token:
            raise PowerBIQueryError(
                "CHAT_PBI_TRANSPORT=mcp exige PBI_ACCESS_TOKEN."
            )
        mcp_url = (
            (settings.pbi_mcp_url or "").strip()
            or os.getenv("PBI_MCP_URL", DEFAULT_PBI_MCP_URL).strip()
            or DEFAULT_PBI_MCP_URL
        )
        # Auth no http_client: o handshake MCP (initialize) ocorre no
        # __aenter__ do Agent, ANTES de function_invocation_kwargs.
        # header_provider so cobre call_tool; sem header na conexao a
        # sessao e cancelada ("MCP server failed to initialize").
        import httpx

        http_client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(60.0, connect=30.0),
        )
        mcp_tool = MCPStreamableHTTPTool(
            name="powerbi",
            description="Power BI Fabric MCP tools",
            url=mcp_url,
            allowed_tools={
                "GetSemanticModelSchema",
                "GenerateQuery",
                "ExecuteQuery",
                "GetReportMetadata",
            },
            http_client=http_client,
            header_provider=lambda kwargs: {
                "Authorization": f"Bearer {kwargs.get('pbi_access_token', token)}"
            },
        )
        try:
            async with Agent(
                client=client,
                name="ChatPBI",
                instructions=instructions,
                tools=mcp_tool,
            ) as agent:
                response = await agent.run(
                    pergunta,
                    function_invocation_kwargs={"pbi_access_token": token},
                )
                citations.append(
                    {
                        "tool": "mcp_session",
                        "artifact_id": artifact_id,
                        "url": mcp_url,
                    }
                )
                return (response.text or "").strip()
        finally:
            await http_client.aclose()

    # rest / mock com tools locais
    pbi_client = _criar_cliente_rest_ou_none(settings)
    if transport == "rest" and pbi_client is None:
        raise PowerBIQueryError(
            "CHAT_PBI_TRANSPORT=rest exige PBI_ACCESS_TOKEN."
        )
    local_tools = _build_local_tools(
        client=pbi_client,
        default_artifact_id=artifact_id,
        citations=citations,
        allow_generate_query=False,
    )
    async with Agent(
        client=client,
        name="ChatPBI",
        instructions=instructions,
        tools=local_tools,
    ) as agent:
        response = await agent.run(pergunta)
        return (response.text or "").strip()


def _run_mock_deterministic(
    pergunta: str,
    *,
    artifact_id: str,
    citations: List[Dict[str, Any]],
    mock_payload: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Resposta deterministica para CI (sem OpenAI / sem rede).
    """
    payload = mock_payload or {
        "doi_actual": 28.7,
        "doi_plan": 28.3,
        "policy_ideal": 26.1,
        "doi_status": "Within Policy",
        "skus_understock": 3,
        "skus": [
            {
                "sku": "BEL-LEITE-75G",
                "pais": "Brazil",
                "doi": 8.5,
                "status": "Understock",
            },
            {
                "sku": "TAN-LARANJA-25G",
                "pais": "Brazil",
                "doi": 12.0,
                "status": "Understock",
            },
        ],
    }
    citations.append(
        {
            "tool": "ExecuteQuery",
            "artifact_id": artifact_id,
            "source": "mock",
        }
    )
    skus = payload.get("skus") or []
    linhas_sku = [
        "| SKU | Pais | DOI (d) | Status |",
        "|---|---|---|---|",
    ]
    for item in skus:
        if not isinstance(item, dict):
            continue
        linhas_sku.append(
            "| {sku} | {pais} | {doi} | {status} |".format(
                sku=item.get("sku", ""),
                pais=item.get("pais", ""),
                doi=item.get("doi", ""),
                status=item.get("status", ""),
            )
        )
    return "\n".join(
        [
            f"Pergunta recebida (mock): {_truncar(pergunta, 160)}",
            "",
            "### DOI agregado (visao modelo / mock)",
            "",
            "| Metrica | Valor |",
            "|---|---|",
            f"| DOI Actual | ~{payload.get('doi_actual')} dias |",
            f"| DOI Plan | ~{payload.get('doi_plan')} dias |",
            f"| Policy DOI Ideal | ~{payload.get('policy_ideal')} dias |",
            f"| DOI Status | {payload.get('doi_status')} |",
            f"| SKUs Understock | {payload.get('skus_understock')} |",
            "",
            "### Menores DOI (exemplos)",
            "",
            *linhas_sku,
            "",
            (
                "**Resposta:** no agregado o DOI fica dentro da politica; "
                "ainda ha pressao pontual em SKUs understock. "
                f"(artifact_id={artifact_id})"
            ),
        ]
    )


def _salvar_auditoria_chat(trail: AuditTrail) -> Path:
    """
    Persiste trilha de chat sem misturar com dump batch.
    """
    CHAT_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    caminho = CHAT_AUDIT_DIR / f"chat_{trail.sessao_id}.json"
    with caminho.open("w", encoding="utf-8") as handle:
        json.dump(trail.para_dict(), handle, indent=2, ensure_ascii=True)
    ultima = CHAT_AUDIT_DIR / "chat_ultima.json"
    with ultima.open("w", encoding="utf-8") as handle:
        json.dump(trail.para_dict(), handle, indent=2, ensure_ascii=True)
    return caminho


def run(
    pergunta: str,
    *,
    settings: Optional[Settings] = None,
    transport: Optional[str] = None,
    artifact_id: Optional[str] = None,
    agent_runner: Optional[AgentRunner] = None,
    tools_override: Optional[Sequence[Any]] = None,
    mock_payload: Optional[Dict[str, Any]] = None,
    persistir_auditoria: bool = True,
) -> ChatResult:
    """
    Executa um turno de chat PBI e devolve ChatResult.

    Args:
        pergunta: pergunta do usuario em linguagem natural.
        settings: configuracao (obrigatoria fora de transport=mock puro).
        transport: mcp | rest | mock.
        artifact_id: GUID do semantic model.
        agent_runner: injecao para testes (bypass MAF).
        tools_override: tools MAF injetadas (testes).
        mock_payload: payload deterministico do transport mock.
        persistir_auditoria: grava JSON em auditoria/.
    """
    sessao_id = gerar_sessao_id()
    trail = AuditTrail(sessao_id=sessao_id)
    transport_default = None
    if transport is None and settings is not None:
        transport_default = settings.chat_pbi_transport
    transport_resolvido = resolver_transport(transport or transport_default)
    aid = (
        artifact_id
        or (settings.pbi_artifact_id if settings else None)
        or os.getenv("PBI_ARTIFACT_ID", "")
    ).strip()

    guard = verificar_input(pergunta)
    trail.registrar(
        "chat_input_guardrail",
        {"ok": guard.ok, "detalhe": guard.detalhe},
    )
    if not guard.ok:
        resultado = ChatResult(
            answer_markdown="",
            meta={
                "sessao_id": sessao_id,
                "transport": transport_resolvido,
                "artifact_id": aid,
            },
            bloqueado=True,
            motivo=guard.detalhe,
        )
        if persistir_auditoria:
            _salvar_auditoria_chat(trail)
        return resultado

    if not aid:
        resultado = ChatResult(
            answer_markdown="",
            meta={
                "sessao_id": sessao_id,
                "transport": transport_resolvido,
            },
            bloqueado=True,
            motivo="PBI_ARTIFACT_ID nao configurado.",
        )
        trail.registrar("chat_erro", {"motivo": resultado.motivo})
        if persistir_auditoria:
            _salvar_auditoria_chat(trail)
        return resultado

    citations: List[Dict[str, Any]] = []
    trail.registrar(
        "chat_inicio",
        {
            "pergunta": _truncar(pergunta, 300),
            "transport": transport_resolvido,
            "artifact_id": aid,
        },
    )

    try:
        if agent_runner is not None:
            answer = agent_runner(pergunta)
        elif transport_resolvido == "mock" and tools_override is None:
            answer = _run_mock_deterministic(
                pergunta,
                artifact_id=aid,
                citations=citations,
                mock_payload=mock_payload,
            )
        else:
            if settings is None:
                raise ValueError(
                    "settings e obrigatorio para transport mcp/rest."
                )
            answer = asyncio.run(
                _run_maf_async(
                    pergunta,
                    settings=settings,
                    transport=transport_resolvido,
                    artifact_id=aid,
                    citations=citations,
                    tools_override=tools_override,
                )
            )
    except Exception as exc:  # noqa: BLE001 - fronteira CLI
        trail.registrar(
            "chat_erro",
            {"tipo": type(exc).__name__, "mensagem": _truncar(str(exc), 400)},
        )
        if persistir_auditoria:
            _salvar_auditoria_chat(trail)
        return ChatResult(
            answer_markdown="",
            citations=citations,
            meta={
                "sessao_id": sessao_id,
                "transport": transport_resolvido,
                "artifact_id": aid,
            },
            bloqueado=True,
            motivo=f"Falha no chat PBI: {exc}",
        )

    trail.registrar(
        "chat_fim",
        {
            "n_citations": len(citations),
            "resposta_chars": len(answer),
            "tools": [c.get("tool") for c in citations if isinstance(c, dict)],
        },
    )
    audit_path: Optional[str] = None
    if persistir_auditoria:
        audit_path = str(_salvar_auditoria_chat(trail))

    model_usado = ""
    if settings is not None:
        model_usado = (
            (settings.chat_openai_model or "").strip()
            or settings.openai_model
        )
    return ChatResult(
        answer_markdown=answer,
        tables=[],
        citations=citations,
        meta={
            "sessao_id": sessao_id,
            "transport": transport_resolvido,
            "artifact_id": aid,
            "auditoria_path": audit_path,
            "openai_model": model_usado,
            "tools_usadas": [
                c.get("tool") for c in citations if isinstance(c, dict)
            ],
        },
    )


def run_repl(
    *,
    settings: Settings,
    transport: Optional[str] = None,
    artifact_id: Optional[str] = None,
) -> None:
    """
    Loop interativo no terminal ate 'sair' / 'exit' / 'quit'.
    """
    print("Chat PBI (ADR-0026). Digite 'sair' para encerrar.")
    while True:
        try:
            pergunta = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not pergunta:
            continue
        if pergunta.lower() in {"sair", "exit", "quit"}:
            break
        resultado = run(
            pergunta,
            settings=settings,
            transport=transport,
            artifact_id=artifact_id,
        )
        print(formatar_saida_cli(resultado, pergunta))
        print()


def chat_result_to_dict(resultado: ChatResult) -> Dict[str, Any]:
    """Serializa ChatResult para JSON/API futura."""
    return asdict(resultado)
