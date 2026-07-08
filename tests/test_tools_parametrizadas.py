"""
Testes para tools_parametrizadas.py: analises S&OE Mondelez.

Valida regras do S&OE Analyst Questions Script:
  - Gap actual vs plan (absoluto e %)
  - DOI actual vs policy
  - Impacto financeiro deterministico
  - Deteccao de capacidades a partir do mapa
"""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from datashield import ler_arquivo, mapear_semantico_deterministico
from tools_parametrizadas import (
    CAPACIDADE_DOI,
    CAPACIDADE_SELLIN,
    CAPACIDADE_SELLOUT,
    analisar_doi,
    analisar_sellin,
    analisar_sellout,
    detectar_capacidades,
)


FIXTURE_CSV = Path(__file__).parent / "fixtures" / "mondelez_ficticio.csv"


def _carregar_fixture() -> pd.DataFrame:
    """Carrega fixture CSV."""
    return ler_arquivo(str(FIXTURE_CSV))


def _mapa_identidade() -> Dict[str, str]:
    """Mapa onde col_original == col_canonica (fixture usa nomes canonicos)."""
    df = _carregar_fixture()
    return {str(c): str(c) for c in df.columns}


# ---------------------------------------------------------------------------
# detectar_capacidades
# ---------------------------------------------------------------------------


class TestDetectarCapacidades:
    """Testes para deteccao de capacidades do dataset."""

    def test_fixture_tem_todas_capacidades(self) -> None:
        mapa = _mapa_identidade()
        caps = detectar_capacidades(mapa)
        assert CAPACIDADE_SELLOUT in caps
        assert CAPACIDADE_SELLIN in caps
        assert CAPACIDADE_DOI in caps

    def test_mapa_sem_sellout(self) -> None:
        mapa = {
            "SellIn_Plan_Ton": "SellIn_Plan_Ton",
            "SellIn_Actual_Ton": "SellIn_Actual_Ton",
            "SellIn_Plan_NR_USD": "SellIn_Plan_NR_USD",
            "SellIn_Actual_NR_USD": "SellIn_Actual_NR_USD",
            "DOI_Plan_Days": "DOI_Plan_Days",
            "DOI_Actual_Days": "DOI_Actual_Days",
        }
        caps = detectar_capacidades(mapa)
        assert CAPACIDADE_SELLOUT not in caps
        assert CAPACIDADE_SELLIN in caps
        assert CAPACIDADE_DOI in caps

    def test_mapa_vazio(self) -> None:
        caps = detectar_capacidades({})
        assert caps == []

    def test_mapa_parcial_sellout(self) -> None:
        mapa = {
            "SellOut_Plan_Ton": "SellOut_Plan_Ton",
            "SellOut_Actual_Ton": "SellOut_Actual_Ton",
        }
        caps = detectar_capacidades(mapa)
        assert CAPACIDADE_SELLOUT not in caps

    def test_mapa_renomeado(self) -> None:
        mapa = {
            "venda_plan": "SellOut_Plan_Ton",
            "venda_real": "SellOut_Actual_Ton",
            "venda_plan_nr": "SellOut_Plan_NR_USD",
            "venda_real_nr": "SellOut_Actual_NR_USD",
        }
        caps = detectar_capacidades(mapa)
        assert CAPACIDADE_SELLOUT in caps


# ---------------------------------------------------------------------------
# analisar_sellout
# ---------------------------------------------------------------------------


class TestAnalisarSellout:
    """Testes para analise de sell-out."""

    def test_retorna_desvios_e_resumo(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade()
        resultado = analisar_sellout(df, mapa)

        assert "desvios" in resultado
        assert "resumo" in resultado
        assert len(resultado["desvios"]) == 20

    def test_desvio_positivo_quando_actual_maior(self) -> None:
        df = pd.DataFrame({
            "SellOut_Plan_Ton": [100.0],
            "SellOut_Actual_Ton": [120.0],
            "SellOut_Plan_NR_USD": [1000.0],
            "SellOut_Actual_NR_USD": [1200.0],
            "SKU_Code": ["TEST-01"],
            "Country": ["BR"],
            "Channel": ["MT"],
            "Category": ["Chocolates"],
            "Brand": ["Lacta"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellout(df, mapa)

        assert len(resultado["desvios"]) == 1
        desvio = resultado["desvios"][0]
        assert desvio["desvio_pct"] == 20.0
        assert desvio["sku"] == "TEST-01"
        assert desvio["pais"] == "BR"

    def test_desvio_negativo_quando_actual_menor(self) -> None:
        df = pd.DataFrame({
            "SellOut_Plan_Ton": [100.0],
            "SellOut_Actual_Ton": [85.0],
            "SellOut_Plan_NR_USD": [1000.0],
            "SellOut_Actual_NR_USD": [850.0],
            "SKU_Code": ["TEST-02"],
            "Country": ["MX"],
            "Channel": ["TT"],
            "Category": ["Biscuits"],
            "Brand": ["Oreo"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellout(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["desvio_pct"] == -15.0

    def test_impacto_nr_calculado_deterministico(self) -> None:
        df = pd.DataFrame({
            "SellOut_Plan_Ton": [100.0],
            "SellOut_Actual_Ton": [110.0],
            "SellOut_Plan_NR_USD": [5000.0],
            "SellOut_Actual_NR_USD": [5500.0],
            "SKU_Code": ["TEST-03"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellout(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["desvio_pct"] == 10.0
        expected_impact = round(abs(10.0 / 100.0) * 5500.0, 2)
        assert desvio["nr_impacto"] == expected_impact

    def test_resumo_contagens(self) -> None:
        df = pd.DataFrame({
            "SellOut_Plan_Ton": [100.0, 100.0, 100.0],
            "SellOut_Actual_Ton": [120.0, 80.0, 100.0],
            "SellOut_Actual_NR_USD": [1200.0, 800.0, 1000.0],
            "SKU_Code": ["A", "B", "C"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellout(df, mapa)

        resumo = resultado["resumo"]
        assert resumo["total_registros"] == 3
        assert resumo["acima_plan"] == 1
        assert resumo["abaixo_plan"] == 1

    def test_colunas_ausentes_retorna_erro(self) -> None:
        df = pd.DataFrame({"col_x": [1]})
        resultado = analisar_sellout(df, {})
        assert resultado["desvios"] == []
        assert "erro" in resultado["resumo"]

    def test_plan_zero_desvio_zero(self) -> None:
        df = pd.DataFrame({
            "SellOut_Plan_Ton": [0.0],
            "SellOut_Actual_Ton": [50.0],
            "SKU_Code": ["ZERO"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellout(df, mapa)
        assert resultado["desvios"][0]["desvio_pct"] == 0.0

    def test_fixture_com_mapa_datashield(self) -> None:
        df = _carregar_fixture()
        mapa_result = mapear_semantico_deterministico(list(df.columns))
        resultado = analisar_sellout(df, mapa_result.mapa)
        assert len(resultado["desvios"]) == 20


# ---------------------------------------------------------------------------
# analisar_sellin
# ---------------------------------------------------------------------------


class TestAnalisarSellin:
    """Testes para analise de sell-in."""

    def test_retorna_desvios_e_resumo(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade()
        resultado = analisar_sellin(df, mapa)

        assert "desvios" in resultado
        assert "resumo" in resultado
        assert len(resultado["desvios"]) == 20

    def test_desvio_sellin_calculado(self) -> None:
        df = pd.DataFrame({
            "SellIn_Plan_Ton": [200.0],
            "SellIn_Actual_Ton": [240.0],
            "SellIn_Plan_NR_USD": [10000.0],
            "SellIn_Actual_NR_USD": [12000.0],
            "SKU_Code": ["SI-01"],
            "Country": ["BR"],
            "Channel": ["MT"],
            "Category": ["Chocolates"],
            "Brand": ["Lacta"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_sellin(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["desvio_pct"] == 20.0
        assert desvio["sku"] == "SI-01"

    def test_colunas_ausentes_retorna_erro(self) -> None:
        df = pd.DataFrame({"irrelevante": [1]})
        resultado = analisar_sellin(df, {})
        assert resultado["desvios"] == []
        assert "erro" in resultado["resumo"]


# ---------------------------------------------------------------------------
# analisar_doi
# ---------------------------------------------------------------------------


class TestAnalisarDoi:
    """Testes para analise de DOI."""

    def test_retorna_desvios_e_resumo(self) -> None:
        df = _carregar_fixture()
        mapa = _mapa_identidade()
        resultado = analisar_doi(df, mapa)

        assert "desvios" in resultado
        assert "resumo" in resultado
        assert len(resultado["desvios"]) == 20

    def test_gap_positivo_quando_acima_target(self) -> None:
        df = pd.DataFrame({
            "DOI_Plan_Days": [30.0],
            "DOI_Actual_Days": [45.0],
            "SellOut_Actual_NR_USD": [5000.0],
            "SKU_Code": ["DOI-01"],
            "Country": ["BR"],
            "Channel": ["MT"],
            "Category": ["Chocolates"],
            "Brand": ["Halls"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["gap_dias"] == 15.0
        assert desvio["doi_actual"] == 45.0
        assert desvio["doi_plan"] == 30.0
        assert desvio["sku"] == "DOI-01"

    def test_gap_negativo_quando_abaixo_target(self) -> None:
        df = pd.DataFrame({
            "DOI_Plan_Days": [30.0],
            "DOI_Actual_Days": [8.0],
            "SellOut_Actual_NR_USD": [6000.0],
            "SKU_Code": ["DOI-02"],
            "Country": ["BR"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["gap_dias"] == -22.0

    def test_nr_impacto_doi(self) -> None:
        df = pd.DataFrame({
            "DOI_Plan_Days": [30.0],
            "DOI_Actual_Days": [60.0],
            "SellOut_Actual_NR_USD": [9000.0],
            "SKU_Code": ["DOI-03"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        desvio = resultado["desvios"][0]
        expected = round(abs(30.0 / 30.0) * 9000.0, 2)
        assert desvio["nr_impacto"] == expected

    def test_resumo_agregado(self) -> None:
        df = pd.DataFrame({
            "DOI_Plan_Days": [20.0, 20.0, 20.0],
            "DOI_Actual_Days": [25.0, 15.0, 20.0],
            "SKU_Code": ["A", "B", "C"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        resumo = resultado["resumo"]
        assert resumo["total_registros"] == 3
        assert resumo["acima_target"] == 1
        assert resumo["abaixo_target"] == 1
        assert resumo["max_gap_dias"] == 5.0
        assert resumo["min_gap_dias"] == -5.0

    def test_colunas_ausentes_retorna_erro(self) -> None:
        df = pd.DataFrame({"x": [1]})
        resultado = analisar_doi(df, {})
        assert resultado["desvios"] == []
        assert "erro" in resultado["resumo"]

    def test_cenario_a3_halls_overstock(self) -> None:
        """
        Cenario A3 do gabarito: DOI ~58d com target 36d.
        O gap deve ser positivo e significativo (overstock).
        """
        df = pd.DataFrame({
            "DOI_Plan_Days": [36.0],
            "DOI_Actual_Days": [58.0],
            "SellOut_Actual_NR_USD": [3000.0],
            "SKU_Code": ["HAL-EXTRAFORTE-28G"],
            "Country": ["Brazil"],
            "Channel": ["Wholesale-C&C"],
            "Category": ["Candy"],
            "Brand": ["Halls"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["gap_dias"] == 22.0
        assert desvio["sku"] == "HAL-EXTRAFORTE-28G"
        assert desvio["nr_impacto"] > 0

    def test_cenario_a1_belvita_ruptura(self) -> None:
        """
        Cenario A1 do gabarito: DOI ~8d com target 31d.
        Gap negativo grande -> risco de ruptura.
        """
        df = pd.DataFrame({
            "DOI_Plan_Days": [31.0],
            "DOI_Actual_Days": [8.0],
            "SellOut_Actual_NR_USD": [6000.0],
            "SKU_Code": ["BEL-LEITE-75G"],
            "Country": ["Brazil"],
            "Channel": ["Modern Trade"],
            "Category": ["Biscuits"],
            "Brand": ["Belvita"],
        })
        mapa = {c: c for c in df.columns}
        resultado = analisar_doi(df, mapa)

        desvio = resultado["desvios"][0]
        assert desvio["gap_dias"] == -23.0
        assert desvio["sku"] == "BEL-LEITE-75G"
