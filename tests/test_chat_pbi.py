"""
Testes do Chat PBI (ADR-0026 / planning 1.7b).

CI usa transport=mock ou agent_runner injetado (sem OAuth / sem OpenAI).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from chat_pbi import (
    ChatResult,
    carregar_hints_catalogo,
    chat_result_to_dict,
    criar_chat_session,
    formatar_saida_cli,
    montar_instrucoes_agente,
    resolver_transport,
    run,
)
from config import DomainThresholds, Settings


def _settings_minimo(**overrides: Any) -> Settings:
    """Settings minimo para testes de chat."""
    base: Dict[str, Any] = {
        "openai_api_key": "sk-test",
        "openai_model": "gpt-4o-mini",
        "limiar_confianca_critic": 0.7,
        "limiar_confianca_datashield": 0.6,
        "max_optimus_retries": 1,
        "hitl_mode": "auto",
        "thresholds": DomainThresholds(),
        "pbi_artifact_id": "11111111-1111-1111-1111-111111111111",
        "chat_pbi_transport": "mock",
    }
    base.update(overrides)
    return Settings(**base)


def test_resolver_transport_invalido() -> None:
    """Transport desconhecido deve falhar cedo."""
    with pytest.raises(ValueError, match="CHAT_PBI_TRANSPORT"):
        resolver_transport("websocket")


def test_playbook_instrucoes_caminho_eficiente() -> None:
    """Instrucoes espelham caminho schema/DAX/ExecuteQuery (geral)."""
    texto = montar_instrucoes_agente(
        artifact_id="aid-1",
        transport="mcp",
        catalog_path="catalogs/mondelez_s2r_v1.yaml",
    )
    assert "CAMINHO EFICIENTE" in texto
    assert "COMPLETUDE" in texto
    assert "understock" in texto.lower()
    assert "5 a 10" in texto or "TOPN" in texto
    assert "PREFERIDO" in texto or "Preferir ExecuteQuery" in texto
    assert "GenerateQuery" in texto
    assert "2023" in texto  # alerta para nao assumir ano errado
    assert "DOI Actual" in texto or "Q1_kpis" in texto


def test_carregar_hints_catalogo_mondelez() -> None:
    """Hints do catalogo expoe query_ids uteis ao agente."""
    hints = carregar_hints_catalogo("catalogs/mondelez_s2r_v1.yaml")
    assert "Q1_kpis" in hints
    assert "Q2_top_alertas" in hints


def test_input_guardrail_bloqueia_pergunta_curta(tmp_path: Path) -> None:
    """Pergunta curta nao chama tools."""
    resultado = run(
        "oi",
        settings=_settings_minimo(),
        transport="mock",
        persistir_auditoria=False,
    )
    assert resultado.bloqueado is True
    assert "curta" in resultado.motivo.lower()


def test_mock_retorna_markdown_estruturado() -> None:
    """Transport mock devolve KPIs + tabela de SKUs."""
    pergunta = "Tem estoque suficiente no curto prazo para a demanda?"
    resultado = run(
        pergunta,
        settings=_settings_minimo(),
        transport="mock",
        persistir_auditoria=False,
    )
    assert resultado.bloqueado is False
    assert "DOI Actual" in resultado.answer_markdown
    assert "BEL-LEITE-75G" in resultado.answer_markdown
    assert "| Metrica |" in resultado.answer_markdown
    assert resultado.meta.get("transport") == "mock"
    assert "ExecuteQuery" in (resultado.meta.get("tools_usadas") or [])


def test_formatar_saida_cli_contem_delimitadores() -> None:
    """CLI wrapper preserva delimitadores e pergunta."""
    resultado = ChatResult(
        answer_markdown="### DOI\n\n| Metrica | Valor |\n|---|---|\n| DOI | 28 |",
        meta={"sessao_id": "s1", "transport": "mock"},
    )
    texto = formatar_saida_cli(resultado, "DOI no dia 7 de julho?")
    assert "=== CHAT PBI ===" in texto
    assert "DOI no dia 7 de julho?" in texto
    assert "=== FIM CHAT ===" in texto
    assert "transport=mock" in texto


def test_agent_runner_injecao() -> None:
    """Injecao de runner bypassa MAF (teste de contrato)."""
    def runner(_pergunta: str) -> str:
        return "## Resposta\n\n| KPI | Valor |\n|---|---|\n| DOI | 10 |"

    resultado = run(
        "Qual o DOI agregado do modelo hoje?",
        settings=_settings_minimo(),
        transport="rest",
        agent_runner=runner,
        persistir_auditoria=False,
    )
    assert resultado.bloqueado is False
    assert "DOI" in resultado.answer_markdown
    assert resultado.meta.get("transport") == "rest"


def test_chat_session_multi_turno_historico() -> None:
    """Follow-up reutiliza mesma sessao e recebe historico."""
    sessao = criar_chat_session()
    visto: list[object] = []

    def runner(pergunta: str, historico: object = None) -> str:
        visto.append({"pergunta": pergunta, "n_hist": len(historico or [])})
        if "proxima" in pergunta.lower() or "camada" in pergunta.lower():
            return (
                "### Follow-up\n\nConcentracao understock: Brazil Cheese "
                "(Philadelphia) e Mexico Chocolates (Toblerone)."
            )
        return (
            "## Estoque\n\n| Metrica | Valor |\n|---|---|\n"
            "| DOI Actual | 28.8 |\n| Understock | 2 |\n\n"
            "Parcial: ha SKUs sob pressao."
        )

    r1 = run(
        "Temos estoque suficiente no curto prazo hoje?",
        settings=_settings_minimo(),
        transport="mock",
        agent_runner=runner,
        chat_session=sessao,
        persistir_auditoria=False,
    )
    assert r1.bloqueado is False
    assert r1.meta.get("turno") == 1
    assert r1.meta.get("multi_turno") is True
    assert r1.meta.get("sessao_id") == sessao.sessao_id
    assert len(sessao.messages) == 2

    r2 = run(
        "Abre a proxima camada por pais e categoria",
        settings=_settings_minimo(),
        transport="mock",
        agent_runner=runner,
        chat_session=sessao,
        persistir_auditoria=False,
    )
    assert r2.bloqueado is False
    assert r2.meta.get("turno") == 2
    assert r2.meta.get("sessao_id") == sessao.sessao_id
    assert "Philadelphia" in r2.answer_markdown or "Follow-up" in r2.answer_markdown
    assert len(sessao.messages) == 4
    assert visto[0]["n_hist"] == 0
    assert visto[1]["n_hist"] == 2


def test_chat_result_to_dict() -> None:
    """Serializacao estavel para API futura."""
    resultado = ChatResult(
        answer_markdown="ok",
        tables=[{"name": "kpis"}],
        citations=[{"tool": "ExecuteQuery"}],
        meta={"sessao_id": "abc"},
    )
    payload = chat_result_to_dict(resultado)
    assert payload["answer_markdown"] == "ok"
    assert payload["tables"][0]["name"] == "kpis"
    assert payload["citations"][0]["tool"] == "ExecuteQuery"


def test_auditoria_chat_persistida(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auditoria de chat vai para arquivo dedicado."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "auditoria").mkdir()
    pergunta = "Qual o status de DOI no modelo Power BI?"
    resultado = run(
        pergunta,
        settings=_settings_minimo(),
        transport="mock",
        persistir_auditoria=True,
    )
    assert resultado.bloqueado is False
    caminho = Path(str(resultado.meta.get("auditoria_path")))
    assert caminho.is_file()
    data = json.loads(caminho.read_text(encoding="utf-8"))
    tipos = [e.get("tipo") for e in data.get("eventos", [])]
    assert "chat_inicio" in tipos
    assert "chat_fim" in tipos
    raw = caminho.read_text(encoding="utf-8")
    assert "sk-" not in raw
    assert "Bearer" not in raw


def test_cli_modo_chat_mock(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """main.py --modo chat --pergunta imprime Markdown."""
    import main as main_mod

    monkeypatch.setattr(
        main_mod,
        "load_settings",
        lambda: _settings_minimo(chat_pbi_transport="mock"),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "main.py",
            "--modo",
            "chat",
            "--chat-transport",
            "mock",
            "--pergunta",
            "Tem estoque suficiente no curto prazo hoje?",
        ],
    )
    main_mod.main()
    out = capsys.readouterr().out
    assert "=== CHAT PBI ===" in out
    assert "DOI Actual" in out
    assert "=== FIM CHAT ===" in out


def test_build_local_tools_execute_query() -> None:
    """Tool local ExecuteQuery delega ao client."""
    from chat_pbi import _build_local_tools
    from powerbi_mcp import QueryResult

    client = MagicMock()
    client.execute_query.return_value = QueryResult(
        columns=["DOI Actual"],
        rows=[[28.7]],
        meta={"source": "rest", "n_rows": 1},
    )
    citations: list[dict[str, Any]] = []
    tools = _build_local_tools(
        client=client,
        default_artifact_id="aid-1",
        citations=citations,
        allow_generate_query=False,
    )
    execute = next(t for t in tools if getattr(t, "name", "") == "ExecuteQuery")
    # Chama a funcao wrapping (evita detalhes async do FunctionTool.invoke)
    raw = execute.func(
        artifactId="aid-1",
        daxQueries=["EVALUATE ROW(\"x\", 1)"],
        maxRows=10,
    )
    texto = raw if isinstance(raw, str) else str(raw)
    assert "28.7" in texto or "DOI Actual" in texto
    assert any(c.get("tool") == "ExecuteQuery" for c in citations)
    client.execute_query.assert_called_once()
