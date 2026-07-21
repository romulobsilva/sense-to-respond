"""
Tests for Dual Ingress / Dominion PBI (ADR-0025 PoC).

No network/OAuth: uses fixture JSON + local catalog YAML.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import DomainThresholds, Settings
from dominion_pbi import (
    adaptar_resultados_pbi_para_sinais,
    executar_catalogo_pbi,
    rodar_dominion_pbi,
)
from hitl import HITLAutoApprove
from nexus import Nexus
from powerbi_catalog import (
    CatalogValidationError,
    carregar_catalogo_dax,
    resolver_artifact_id,
)
from powerbi_mcp import FixturePowerBIClient, criar_cliente_pbi


ROOT = Path(__file__).resolve().parent.parent
CATALOG_MONDELEZ = ROOT / "catalogs" / "mondelez_s2r_v1.yaml"
CATALOG_AGUA = (
    ROOT / "docs" / "contracts" / "examples" / "agua_io_catalog.example.yaml"
)
FIXTURE_PBI = (
    Path(__file__).parent / "fixtures" / "pbi_mondelez_catalog_responses.json"
)


def _settings_pbi() -> Settings:
    """Settings pointed at local catalog + fixture."""
    return Settings(
        openai_api_key="sk-test-fake-key-for-pbi",
        openai_model="gpt-4o-mini",
        limiar_confianca_critic=0.6,
        limiar_confianca_datashield=0.6,
        max_optimus_retries=1,
        hitl_mode="auto",
        thresholds=DomainThresholds(),
        pbi_artifact_id="8d81650c-ea21-4fc4-8303-d067226f9442",
        pbi_catalog_path=str(CATALOG_MONDELEZ),
        pbi_fixture_path=str(FIXTURE_PBI),
    )


class TestCatalogoDax:
    """carregar_catalogo_dax validation."""

    def test_carrega_mondelez(self) -> None:
        catalog = carregar_catalogo_dax(CATALOG_MONDELEZ)
        assert catalog["catalog_id"] == "mondelez_s2r_v1"
        assert len(catalog["queries"]) >= 5
        ids = {q["query_id"] for q in catalog["queries"]}
        assert "Q1_kpis" in ids
        assert "Q2_top_alertas" in ids
        assert "Q3_sta_por_categoria" in ids
        assert "Q4_forward_risco" in ids
        assert "Q5_forward_oportunidade" in ids

    def test_carrega_agua_exemplo(self) -> None:
        catalog = carregar_catalogo_dax(CATALOG_AGUA)
        assert catalog["domain"] == "agua_io"
        assert catalog["queries"]

    def test_rejeita_sem_evaluate(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            "\n".join(
                [
                    "catalog_id: x",
                    "display_name: x",
                    "artifact_id_env: PBI_ARTIFACT_ID",
                    "domain: x",
                    "queries:",
                    "  - query_id: Q1",
                    "    description: bad",
                    "    expected_columns: [A]",
                    "    dax: |",
                    "      ROW(1)",
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(CatalogValidationError):
            carregar_catalogo_dax(bad)

    def test_resolver_artifact_id_env_preferido(self) -> None:
        catalog = carregar_catalogo_dax(CATALOG_MONDELEZ)
        resolved = resolver_artifact_id(catalog, env_value="aaa-bbb")
        assert resolved == "aaa-bbb"


class TestExecutarCatalogoFixture:
    """executar_catalogo_pbi offline."""

    def test_fixture_executa_todas_queries(self) -> None:
        catalog = carregar_catalogo_dax(CATALOG_MONDELEZ)
        client = FixturePowerBIClient(FIXTURE_PBI)
        out = executar_catalogo_pbi(
            catalog,
            artifact_id="8d81650c-ea21-4fc4-8303-d067226f9442",
            client=client,
        )
        assert all(item["ok"] for item in out["catalog_execucao"])
        assert len(out["catalog_execucao"]) >= 5
        assert "Q1_kpis" in out["resultados_pbi"]
        assert "Q4_forward_risco" in out["resultados_pbi"]
        assert "Q5_forward_oportunidade" in out["resultados_pbi"]
        assert out["resultados_pbi"]["Q1_kpis"]["rows"]


class TestAdaptadorSinais:
    """adaptar_resultados_pbi_para_sinais."""

    def test_gera_doi_sellout_forward_e_oportunidade(self) -> None:
        client = FixturePowerBIClient(FIXTURE_PBI)
        catalog = carregar_catalogo_dax(CATALOG_MONDELEZ)
        out = executar_catalogo_pbi(
            catalog,
            "8d81650c-ea21-4fc4-8303-d067226f9442",
            client,
        )
        from optimus import gerar_proposicoes, montar_resumo_executivo

        sinais = adaptar_resultados_pbi_para_sinais(
            out["resultados_pbi"],
            thresholds=DomainThresholds(),
        )
        tipos = {s.tipo for s in sinais}
        assert "doi_fora_politica" in tipos
        assert "desvio_sellout" in tipos
        assert "premissa_forward_furada" in tipos
        assert "forward_oportunidade" in tipos
        assert any(s.sku == "PHI-LIGHT-150G" for s in sinais)
        doi_sinais = [s for s in sinais if s.tipo == "doi_fora_politica"]
        assert all(s.metrica == "doi_dias_policy" for s in doi_sinais)
        fwd = [s for s in sinais if s.tipo == "premissa_forward_furada"]
        riscos = {s.risco_forward for s in fwd}
        assert "ruptura" in riscos
        assert "overstock" in riscos

        props = gerar_proposicoes(sinais)
        doi_props = [
            p for p in props if p.tipo == "rebalancear_estoque_doi"
        ]
        assert doi_props
        assert any("Policy DOI Ideal" in p.descricao for p in doi_props)
        assert any(
            p.tipo == "questionar_premissa_plano" for p in props
        )
        assert any(p.tipo == "capturar_oportunidade" for p in props)

        resumo = montar_resumo_executivo(props, DomainThresholds())
        assert len(resumo["top_forward"]) >= 1
        assert len(resumo["top_oportunidades"]) >= 1
        assert resumo["diversidade_forward"]["n_ruptura"] >= 1
        assert resumo["diversidade_forward"]["n_overstock"] >= 1


class TestRodarDominionPbi:
    """rodar_dominion_pbi integration helper."""

    def test_state_shape(self) -> None:
        client = criar_cliente_pbi(fixture_path=str(FIXTURE_PBI))
        out = rodar_dominion_pbi(
            catalog_path=str(CATALOG_MONDELEZ),
            artifact_id_env="8d81650c-ea21-4fc4-8303-d067226f9442",
            client=client,
            thresholds=DomainThresholds(),
        )
        assert out["fonte_dados"] == "pbi"
        assert out["pbi_catalog_id"] == "mondelez_s2r_v1"
        assert isinstance(out["sinais"], list)
        assert out["sinais"]
        assert out["resultados_pbi"] is not None


class TestNexusFontePbi:
    """Nexus --fonte pbi path with mocked LLM."""

    @patch("agent.AgenteOpenAI.gerar_explicacao")
    @patch("critic.CriticAgent.auditar")
    def test_nexus_pbi_sem_dataset_canonico(
        self,
        mock_auditar: MagicMock,
        mock_explicacao: MagicMock,
    ) -> None:
        from state_types import ResultadoCritica

        mock_auditar.return_value = ResultadoCritica(
            aprovado=True,
            confianca=0.85,
            problemas=[],
        )
        mock_explicacao.return_value = (
            "Analise PBI concluida com sinais de DOI e sell-out."
        )

        from agent import AgenteOpenAI

        settings = _settings_pbi()
        agente = AgenteOpenAI(settings)
        client = FixturePowerBIClient(FIXTURE_PBI)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            fonte_dados="pbi",
            pbi_client=client,
        )
        state = nexus.executar(
            "Analise os indicadores do modelo Power BI e gere proposicoes."
        )
        assert not state.get("bloqueado")
        assert state.get("fonte_dados") == "pbi"
        assert state.get("dataset_canonico") is None
        assert state.get("resultados_pbi") is not None
        assert isinstance(state.get("catalog_execucao"), list)
        assert state.get("sinais")
        assert state.get("proposicoes")
        assert state.get("fila_nexus")
        meta_rel = None
        for art in state.get("artefatos_visuais", []):
            if isinstance(art, dict) and art.get("tipo") == "relatorio_analista_pdf":
                meta_rel = art
        assert meta_rel is not None
        assert meta_rel.get("fonte_dados") == "pbi"

        auditoria = state.get("auditoria")
        assert isinstance(auditoria, dict)
        tipos = {e.get("tipo") for e in auditoria.get("eventos", [])}
        assert "catalog_execucao" in tipos
        # No full resultados_pbi dump in catalog_execucao event
        for evento in auditoria.get("eventos", []):
            if evento.get("tipo") == "catalog_execucao":
                dados = evento.get("dados", {})
                assert "resultados_pbi" not in dados
                assert "execucao" in dados

    def test_nexus_pbi_e_input_bloqueia(self) -> None:
        from agent import AgenteOpenAI

        settings = _settings_pbi()
        nexus = Nexus(
            agente=AgenteOpenAI(settings),
            settings=settings,
            hitl=HITLAutoApprove(),
            fonte_dados="pbi",
            arquivo_entrada="data/x.csv",
            pbi_client=FixturePowerBIClient(FIXTURE_PBI),
        )
        state = nexus.executar(
            "Analise os indicadores do modelo Power BI e gere proposicoes."
        )
        assert state.get("bloqueado") is True
