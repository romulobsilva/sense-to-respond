"""
Testes para analise temporal e projecao forward.

Valida:
  - analisar_tendencia: janela recente vs anterior, direcao DOI, semanas consecutivas
  - analisar_forward: deteccao de premissa furada, risco ruptura/overstock/gap_plano

Fixture: tests/fixtures/mondelez_temporal.csv com 3 cenarios plantados:
  - BEL-TEST-75G: SO subindo + DOI caindo -> ruptura
  - HAL-TEST-28G: DOI subindo + SI alto -> overstock
  - MLK-TEST-100G: DOI era alto mas normalizou -> falso-positivo
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from tools_parametrizadas import (
    DIRECAO_MELHORANDO,
    DIRECAO_PIORANDO,
    DIRECAO_ESTAVEL,
    RISCO_RUPTURA,
    RISCO_OVERSTOCK,
    RISCO_GAP_PLANO,
    analisar_tendencia,
    analisar_forward,
    _classificar_direcao_doi,
    _contar_semanas_consecutivas,
)
from sinais import extrair_sinais_de_resultados
from optimus import gerar_proposicoes
from state_types import Sinal


FIXTURE_TEMPORAL = Path(__file__).parent / "fixtures" / "mondelez_temporal.csv"


def _carregar_fixture() -> pd.DataFrame:
    """Carrega fixture temporal."""
    return pd.read_csv(str(FIXTURE_TEMPORAL))


def _mapa_identidade(df: pd.DataFrame) -> Dict[str, str]:
    """Mapa identidade onde col_original == col_canonica."""
    return {str(c): str(c) for c in df.columns}


# ---------------------------------------------------------------------------
# _classificar_direcao_doi
# ---------------------------------------------------------------------------


class TestClassificarDirecaoDoi:
    """Testes para classificacao de direcao de DOI."""

    def test_doi_caindo_e_melhorando(self) -> None:
        assert _classificar_direcao_doi(20.0, 30.0) == DIRECAO_MELHORANDO

    def test_doi_subindo_e_piorando(self) -> None:
        assert _classificar_direcao_doi(40.0, 30.0) == DIRECAO_PIORANDO

    def test_doi_estavel(self) -> None:
        assert _classificar_direcao_doi(30.5, 30.0) == DIRECAO_ESTAVEL

    def test_doi_anterior_zero(self) -> None:
        assert _classificar_direcao_doi(10.0, 0.0) == DIRECAO_ESTAVEL


# ---------------------------------------------------------------------------
# _contar_semanas_consecutivas
# ---------------------------------------------------------------------------


class TestContarSemanasConsecutivas:
    """Testes para contagem de semanas consecutivas."""

    def test_todas_positivas(self) -> None:
        s = pd.Series([1.0, 2.0, 3.0])
        assert _contar_semanas_consecutivas(s, "_desvio") == 3

    def test_mudanca_de_sinal(self) -> None:
        s = pd.Series([-1.0, 2.0, 3.0])
        assert _contar_semanas_consecutivas(s, "_desvio") == 2

    def test_serie_vazia(self) -> None:
        s = pd.Series([], dtype=float)
        assert _contar_semanas_consecutivas(s, "_desvio") == 0

    def test_ultimo_zero(self) -> None:
        s = pd.Series([1.0, 2.0, 0.0])
        assert _contar_semanas_consecutivas(s, "_desvio") == 0

    def test_todas_negativas(self) -> None:
        s = pd.Series([-5.0, -3.0, -1.0])
        assert _contar_semanas_consecutivas(s, "_desvio") == 3


# ---------------------------------------------------------------------------
# analisar_tendencia
# ---------------------------------------------------------------------------


class TestAnalisarTendencia:
    """Testes para analise de tendencia temporal."""

    def test_retorna_tendencias(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa)
        assert "tendencias" in resultado
        assert "resumo" in resultado
        assert len(resultado["tendencias"]) > 0

    def test_belvita_doi_melhorando(self) -> None:
        """BEL-TEST-75G: DOI cai de 20 a 5 -> direcao melhorando."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa, janela_recente_dias=30)
        bel = [t for t in resultado["tendencias"] if t["sku"] == "BEL-TEST-75G"]
        assert len(bel) == 1
        assert bel[0]["direcao_doi"] == DIRECAO_MELHORANDO
        assert bel[0]["doi_recente"] < bel[0]["doi_anterior"]

    def test_halls_doi_piorando(self) -> None:
        """HAL-TEST-28G: DOI sobe de 40 a 60 -> direcao piorando."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa, janela_recente_dias=30)
        hal = [t for t in resultado["tendencias"] if t["sku"] == "HAL-TEST-28G"]
        assert len(hal) == 1
        assert hal[0]["direcao_doi"] == DIRECAO_PIORANDO
        assert hal[0]["doi_recente"] > hal[0]["doi_anterior"]

    def test_milka_doi_melhorando(self) -> None:
        """MLK-TEST-100G: DOI cai de 68 a 25 -> direcao melhorando."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa, janela_recente_dias=30)
        mlk = [t for t in resultado["tendencias"] if t["sku"] == "MLK-TEST-100G"]
        assert len(mlk) == 1
        assert mlk[0]["direcao_doi"] == DIRECAO_MELHORANDO

    def test_resumo_contagens(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa)
        resumo = resultado["resumo"]
        total = resumo["doi_piorando"] + resumo["doi_melhorando"] + resumo["doi_estavel"]
        assert total == resumo["total_skus"]

    def test_data_corte_explicita(self) -> None:
        """Passando data_corte explicita funciona sem erro."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(
            df, mapa, data_corte="2026-05-01"
        )
        assert len(resultado["tendencias"]) > 0

    def test_semanas_consecutivas_positivas(self) -> None:
        """BEL-TEST-75G: SO consistentemente acima do plano -> semanas > 0."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa, janela_recente_dias=60)
        bel = [t for t in resultado["tendencias"] if t["sku"] == "BEL-TEST-75G"]
        assert len(bel) == 1
        assert bel[0]["semanas_consecutivas"] > 0

    def test_colunas_ausentes_retorna_erro(self) -> None:
        """Se colunas temporais ausentes, retorna dict com erro."""
        df = pd.DataFrame({"x": [1]})
        resultado = analisar_tendencia(df, {})
        assert resultado["tendencias"] == []

    def test_dimensoes_presentes(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_tendencia(df, mapa)
        for t in resultado["tendencias"]:
            assert "sku" in t
            assert "pais" in t
            assert "canal" in t


# ---------------------------------------------------------------------------
# analisar_forward
# ---------------------------------------------------------------------------


class TestAnalisarForward:
    """Testes para analise forward e deteccao de premissa furada."""

    def test_retorna_alertas(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa)
        assert "alertas_forward" in resultado
        assert "resumo" in resultado

    def test_belvita_risco_ruptura(self) -> None:
        """BEL-TEST-75G: DOI baixo + SO subindo + plano nao cobre -> ruptura."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa, janela_recente_dias=30)
        bel = [a for a in resultado["alertas_forward"]
               if a["sku"] == "BEL-TEST-75G"]
        assert len(bel) == 1
        assert bel[0]["risco_projetado"] == RISCO_RUPTURA

    def test_halls_risco_overstock(self) -> None:
        """HAL-TEST-28G: DOI > 40 + SI alto -> overstock."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa, janela_recente_dias=30)
        hal = [a for a in resultado["alertas_forward"]
               if a["sku"] == "HAL-TEST-28G"]
        assert len(hal) == 1
        assert hal[0]["risco_projetado"] == RISCO_OVERSTOCK

    def test_milka_sem_alerta_ou_gap(self) -> None:
        """MLK-TEST-100G: DOI normalizou -> nao deve ser ruptura nem overstock."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa, janela_recente_dias=30)
        mlk = [a for a in resultado["alertas_forward"]
               if a["sku"] == "MLK-TEST-100G"]
        for alerta in mlk:
            assert alerta["risco_projetado"] != RISCO_RUPTURA
            assert alerta["risco_projetado"] != RISCO_OVERSTOCK

    def test_premissa_coerente_booleano(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa)
        for alerta in resultado["alertas_forward"]:
            assert isinstance(alerta["premissa_coerente"], bool)

    def test_resumo_contagens(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa)
        resumo = resultado["resumo"]
        total = (resumo["rupturas_projetadas"]
                 + resumo["overstocks_projetados"]
                 + resumo["gaps_plano"])
        assert total == resumo["total_alertas"]

    def test_data_corte_explicita(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(
            df, mapa, data_corte="2026-05-20"
        )
        assert "alertas_forward" in resultado

    def test_colunas_ausentes_retorna_erro(self) -> None:
        df = pd.DataFrame({"x": [1]})
        resultado = analisar_forward(df, {})
        assert resultado["alertas_forward"] == []

    def test_dimensoes_presentes(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa)
        for alerta in resultado["alertas_forward"]:
            assert "sku" in alerta
            assert "pais" in alerta
            assert "canal" in alerta

    def test_doi_atual_e_snapshot(self) -> None:
        """doi_atual deve ser o ultimo valor realizado, nao a media."""
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa)
        for alerta in resultado["alertas_forward"]:
            assert alerta["doi_atual"] >= 0


# ---------------------------------------------------------------------------
# Sinais enriquecidos
# ---------------------------------------------------------------------------


class TestSinaisEnriquecidos:
    """Testes para extracao de sinais de tendencia e forward."""

    def _resultados_completos(self) -> Dict[str, Any]:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        return {
            "analise_tendencia": analisar_tendencia(df, mapa),
            "analise_forward": analisar_forward(df, mapa),
        }

    def test_sinais_tendencia_temporal(self) -> None:
        resultados = self._resultados_completos()
        sinais = extrair_sinais_de_resultados(resultados)
        tend = [s for s in sinais if s.tipo == "tendencia_temporal"]
        assert len(tend) > 0
        for s in tend:
            assert s.sinal_id.startswith("SIG-TEND-")
            assert s.tendencia in ("melhorando", "piorando", "estavel")

    def test_sinais_forward(self) -> None:
        resultados = self._resultados_completos()
        sinais = extrair_sinais_de_resultados(resultados)
        fwd = [s for s in sinais if s.tipo == "premissa_forward_furada"]
        assert len(fwd) > 0
        for s in fwd:
            assert s.sinal_id.startswith("SIG-FWD-")
            assert s.risco_forward in ("ruptura", "overstock", "gap_plano")

    def test_sinal_tendencia_tem_semanas_consecutivas(self) -> None:
        resultados = self._resultados_completos()
        sinais = extrair_sinais_de_resultados(resultados)
        tend = [s for s in sinais if s.tipo == "tendencia_temporal"]
        assert any(s.semanas_consecutivas > 0 for s in tend)

    def test_sinal_para_dict_inclui_novos_campos(self) -> None:
        s = Sinal(
            sinal_id="SIG-TEND-001", tipo="tendencia_temporal",
            sku="TEST", canal="MT", metrica="tendencia_doi_so",
            valor=10.0, referencia=20.0, desvio_pct=-5.0,
            severidade="media", tendencia="melhorando",
            semanas_consecutivas=3, risco_forward="",
        )
        d = s.para_dict()
        assert d["tendencia"] == "melhorando"
        assert d["semanas_consecutivas"] == 3
        assert d["risco_forward"] == ""


# ---------------------------------------------------------------------------
# Proposicoes enriquecidas
# ---------------------------------------------------------------------------


class TestProposicoesEnriquecidas:
    """Testes para proposicoes com regras de tendencia/forward."""

    def _sinais_completos(self) -> List[Sinal]:
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultados = {
            "analise_tendencia": analisar_tendencia(df, mapa),
            "analise_forward": analisar_forward(df, mapa),
            "analise_doi": {
                "desvios": [
                    {
                        "sku": "HAL-TEST-28G", "pais": "Brazil",
                        "canal": "Wholesale/C&C", "categoria": "Candy",
                        "marca": "Halls", "doi_plan": 36.0,
                        "doi_actual": 58.0, "gap_dias": 22.0,
                        "nr_impacto": 100.0,
                    },
                    {
                        "sku": "MLK-TEST-100G", "pais": "Brazil",
                        "canal": "E-commerce", "categoria": "Chocolates",
                        "marca": "Milka", "doi_plan": 23.0,
                        "doi_actual": 42.0, "gap_dias": 19.0,
                        "nr_impacto": 50.0,
                    },
                ],
                "resumo": {},
            },
        }
        return extrair_sinais_de_resultados(resultados)

    def test_questionar_premissa_plano(self) -> None:
        """Alertas forward geram proposicoes questionar_premissa_plano."""
        sinais = self._sinais_completos()
        proposicoes = gerar_proposicoes(sinais)
        quest = [p for p in proposicoes if p.tipo == "questionar_premissa_plano"]
        assert len(quest) > 0

    def test_milka_falso_positivo_suprimido(self) -> None:
        """Milka: DOI alto mas tendencia melhorando -> nao gera rebalancear."""
        sinais = self._sinais_completos()
        proposicoes = gerar_proposicoes(sinais)
        milka_doi = [
            p for p in proposicoes
            if p.tipo == "rebalancear_estoque_doi"
            and "MLK-TEST-100G" in p.skus
        ]
        assert len(milka_doi) == 0, (
            "Milka com DOI normalizando nao deveria gerar rebalancear_estoque_doi"
        )

    def test_halls_nao_suprimido(self) -> None:
        """Halls: DOI alto e piorando -> gera rebalancear com SEGURAR."""
        sinais = self._sinais_completos()
        proposicoes = gerar_proposicoes(sinais)
        halls_doi = [
            p for p in proposicoes
            if p.tipo == "rebalancear_estoque_doi"
            and "HAL-TEST-28G" in p.skus
        ]
        assert len(halls_doi) == 1
        assert "SEGURAR" in halls_doi[0].descricao

    def test_belvita_ruptura_forward(self) -> None:
        """Belvita: DOI baixo + SO subindo -> questionar premissa ruptura."""
        sinais = self._sinais_completos()
        proposicoes = gerar_proposicoes(sinais)
        bel_fwd = [
            p for p in proposicoes
            if p.tipo == "questionar_premissa_plano"
            and "BEL-TEST-75G" in p.skus
        ]
        assert len(bel_fwd) == 1
        assert "RUPTURA" in bel_fwd[0].descricao.upper()

    def test_halls_overstock_forward(self) -> None:
        """Halls: DOI alto -> questionar premissa overstock."""
        sinais = self._sinais_completos()
        proposicoes = gerar_proposicoes(sinais)
        hal_fwd = [
            p for p in proposicoes
            if p.tipo == "questionar_premissa_plano"
            and "HAL-TEST-28G" in p.skus
        ]
        assert len(hal_fwd) == 1
        assert "OVERSTOCK" in hal_fwd[0].descricao.upper()
