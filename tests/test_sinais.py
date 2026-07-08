"""
Testes para sinais.py - extracao de sinais estruturados.

Cobertura:
  - Sinais legados (desvio_demanda, desvio_custo) -- regressao.
  - Sinais Mondelez (desvio_sellout, desvio_sellin, doi_fora_politica).
  - Classificacao de severidade (SO/SI e DOI).
  - Sinais mistos (legado + Mondelez no mesmo dict de resultados).
  - Resultado vazio / tipos invalidos.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from sinais import (
    _classificar_severidade,
    _classificar_severidade_doi,
    extrair_sinais_de_resultados,
    LIMIAR_SEVERIDADE_ALTA,
    LIMIAR_SEVERIDADE_MEDIA,
    LIMIAR_DOI_SEVERIDADE_ALTA,
    LIMIAR_DOI_SEVERIDADE_MEDIA,
)
from state_types import Sinal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resultado_sellout(desvios: list) -> dict:
    """Monta dict no formato retornado por analisar_sellout."""
    return {
        "analise_sellout": {
            "desvios": desvios,
            "resumo": {},
        }
    }


def _resultado_sellin(desvios: list) -> dict:
    """Monta dict no formato retornado por analisar_sellin."""
    return {
        "analise_sellin": {
            "desvios": desvios,
            "resumo": {},
        }
    }


def _resultado_doi(desvios: list) -> dict:
    """Monta dict no formato retornado por analisar_doi."""
    return {
        "analise_doi": {
            "desvios": desvios,
            "resumo": {},
        }
    }


def _desvio_so(
    sku: str = "LAC-TAB-90G",
    desvio_pct: float = 18.4,
    actual_ton: float = 2.51,
    plan_ton: float = 2.12,
    pais: str = "Brazil",
    canal: str = "Traditional Trade",
    categoria: str = "Chocolates",
    marca: str = "Lacta",
) -> dict:
    """Cria um desvio de sell-out no formato da tool."""
    return {
        "sku": sku,
        "pais": pais,
        "canal": canal,
        "categoria": categoria,
        "marca": marca,
        "plan_ton": plan_ton,
        "actual_ton": actual_ton,
        "desvio_pct": desvio_pct,
        "nr_actual": 6275.12,
        "nr_impacto": 1154.62,
    }


def _desvio_si(
    sku: str = "LAC-TAB-90G",
    desvio_pct: float = 26.32,
    actual_ton: float = 2.88,
    plan_ton: float = 2.28,
) -> dict:
    """Cria um desvio de sell-in no formato da tool."""
    return {
        "sku": sku,
        "pais": "Brazil",
        "canal": "Traditional Trade",
        "categoria": "Chocolates",
        "marca": "Lacta",
        "plan_ton": plan_ton,
        "actual_ton": actual_ton,
        "desvio_pct": desvio_pct,
        "nr_actual": 7198.63,
        "nr_impacto": 1894.68,
    }


def _desvio_doi(
    sku: str = "TRI-GUM-14G",
    doi_plan: float = 30.0,
    doi_actual: float = 48.0,
    gap_dias: float = 18.0,
) -> dict:
    """Cria um desvio de DOI no formato da tool."""
    return {
        "sku": sku,
        "pais": "Colombia",
        "canal": "Modern Trade",
        "categoria": "Gum",
        "marca": "Trident",
        "doi_plan": doi_plan,
        "doi_actual": doi_actual,
        "gap_dias": gap_dias,
        "nr_impacto": 2800.00,
    }


# ---------------------------------------------------------------------------
# Testes de classificacao de severidade
# ---------------------------------------------------------------------------

class TestClassificarSeveridade:
    """Testes para _classificar_severidade (SO/SI)."""

    def test_alta(self) -> None:
        assert _classificar_severidade(10.0) == "alta"
        assert _classificar_severidade(-15.0) == "alta"

    def test_media(self) -> None:
        assert _classificar_severidade(5.0) == "media"
        assert _classificar_severidade(-7.5) == "media"

    def test_baixa(self) -> None:
        assert _classificar_severidade(3.0) == "baixa"
        assert _classificar_severidade(-2.0) == "baixa"

    def test_limites_exatos(self) -> None:
        assert _classificar_severidade(LIMIAR_SEVERIDADE_ALTA) == "alta"
        assert _classificar_severidade(LIMIAR_SEVERIDADE_MEDIA) == "media"
        assert _classificar_severidade(LIMIAR_SEVERIDADE_MEDIA - 0.01) == "baixa"


class TestClassificarSeveridadeDoi:
    """Testes para _classificar_severidade_doi."""

    def test_alta(self) -> None:
        assert _classificar_severidade_doi(15.0) == "alta"
        assert _classificar_severidade_doi(-20.0) == "alta"

    def test_media(self) -> None:
        assert _classificar_severidade_doi(7.0) == "media"
        assert _classificar_severidade_doi(-10.0) == "media"

    def test_baixa(self) -> None:
        assert _classificar_severidade_doi(3.0) == "baixa"
        assert _classificar_severidade_doi(-5.0) == "baixa"

    def test_limites_exatos(self) -> None:
        assert _classificar_severidade_doi(LIMIAR_DOI_SEVERIDADE_ALTA) == "alta"
        assert _classificar_severidade_doi(LIMIAR_DOI_SEVERIDADE_MEDIA) == "media"
        assert _classificar_severidade_doi(
            LIMIAR_DOI_SEVERIDADE_MEDIA - 0.01
        ) == "baixa"


# ---------------------------------------------------------------------------
# Testes de extracao de sinais legados (regressao)
# ---------------------------------------------------------------------------

class TestSinaisLegados:
    """Regressao: sinais de comparacao_demanda e comparacao_custos."""

    def test_comparacao_demanda(self) -> None:
        df = pd.DataFrame({
            "sku": ["SKU001", "SKU002"],
            "demanda_real": [1000.0, 500.0],
            "demanda_modelada": [1100.0, 480.0],
            "delta_demanda_pct": [10.0, -4.0],
        })
        resultados = {"comparacao_demanda": df}
        sinais = extrair_sinais_de_resultados(resultados)
        assert len(sinais) == 2
        assert sinais[0].tipo == "desvio_demanda"
        assert sinais[0].sku == "SKU001"
        assert sinais[0].desvio_pct == 10.0

    def test_comparacao_custos(self) -> None:
        resultados = {
            "comparacao_custos": {
                "custo_modelado_total": 115000.0,
                "custo_dre": 100000.0,
                "delta_pct": 15.0,
            }
        }
        sinais = extrair_sinais_de_resultados(resultados)
        assert len(sinais) == 1
        assert sinais[0].tipo == "desvio_custo"
        assert sinais[0].sku == "TOTAL"

    def test_resultado_vazio(self) -> None:
        sinais = extrair_sinais_de_resultados({})
        assert len(sinais) == 0


# ---------------------------------------------------------------------------
# Testes de sinais Mondelez: sell-out
# ---------------------------------------------------------------------------

class TestSinaisSellOut:
    """Sinais de sell-out (ADR-0019)."""

    def test_desvio_sellout_basico(self) -> None:
        res = _resultado_sellout([_desvio_so()])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 1
        s = sinais[0]
        assert s.tipo == "desvio_sellout"
        assert s.sku == "LAC-TAB-90G"
        assert s.metrica == "sellout_ton"
        assert s.desvio_pct == 18.4
        assert s.severidade == "alta"

    def test_dimensoes_preenchidas(self) -> None:
        res = _resultado_sellout([_desvio_so()])
        sinais = extrair_sinais_de_resultados(res)
        s = sinais[0]
        assert s.pais == "Brazil"
        assert s.canal == "Traditional Trade"
        assert s.marca == "Lacta"

    def test_id_sequencial(self) -> None:
        res = _resultado_sellout([
            _desvio_so(sku="A", desvio_pct=10.0),
            _desvio_so(sku="B", desvio_pct=20.0),
        ])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 2
        assert sinais[0].sinal_id == "SIG-SO-001"
        assert sinais[1].sinal_id == "SIG-SO-002"

    def test_desvio_negativo(self) -> None:
        """Sell-out abaixo do plan -> desvio negativo."""
        res = _resultado_sellout([_desvio_so(desvio_pct=-12.5)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].desvio_pct == -12.5
        assert sinais[0].severidade == "alta"

    def test_lista_vazia(self) -> None:
        res = _resultado_sellout([])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 0

    def test_item_invalido_ignorado(self) -> None:
        """Items que nao sao dict devem ser ignorados."""
        res = _resultado_sellout(["nao_um_dict", 42])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 0


# ---------------------------------------------------------------------------
# Testes de sinais Mondelez: sell-in
# ---------------------------------------------------------------------------

class TestSinaisSellIn:
    """Sinais de sell-in (ADR-0019)."""

    def test_desvio_sellin_basico(self) -> None:
        res = _resultado_sellin([_desvio_si()])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 1
        s = sinais[0]
        assert s.tipo == "desvio_sellin"
        assert s.metrica == "sellin_ton"
        assert s.desvio_pct == 26.32

    def test_severidade_media(self) -> None:
        res = _resultado_sellin([_desvio_si(desvio_pct=7.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].severidade == "media"

    def test_severidade_baixa(self) -> None:
        res = _resultado_sellin([_desvio_si(desvio_pct=2.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].severidade == "baixa"


# ---------------------------------------------------------------------------
# Testes de sinais Mondelez: DOI
# ---------------------------------------------------------------------------

class TestSinaisDoi:
    """Sinais de DOI fora da politica (ADR-0019)."""

    def test_doi_basico(self) -> None:
        res = _resultado_doi([_desvio_doi()])
        sinais = extrair_sinais_de_resultados(res)
        assert len(sinais) == 1
        s = sinais[0]
        assert s.tipo == "doi_fora_politica"
        assert s.metrica == "doi_dias"
        assert s.valor == 48.0
        assert s.referencia == 30.0

    def test_doi_desvio_pct_calculado(self) -> None:
        """desvio_pct = (gap_dias / doi_plan) * 100."""
        res = _resultado_doi([_desvio_doi(doi_plan=30.0, doi_actual=48.0, gap_dias=18.0)])
        sinais = extrair_sinais_de_resultados(res)
        s = sinais[0]
        expected_desvio = round((18.0 / 30.0) * 100.0, 2)
        assert s.desvio_pct == expected_desvio

    def test_doi_plan_zero_desvio_zero(self) -> None:
        """Se doi_plan == 0, desvio_pct deve ser 0."""
        res = _resultado_doi([_desvio_doi(doi_plan=0.0, doi_actual=5.0, gap_dias=5.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].desvio_pct == 0.0

    def test_doi_severidade_alta(self) -> None:
        """Gap >= 15 dias -> severidade alta."""
        res = _resultado_doi([_desvio_doi(gap_dias=18.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].severidade == "alta"

    def test_doi_severidade_media(self) -> None:
        """Gap >= 7 e < 15 dias -> severidade media."""
        res = _resultado_doi([_desvio_doi(gap_dias=10.0, doi_actual=40.0, doi_plan=30.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].severidade == "media"

    def test_doi_severidade_baixa(self) -> None:
        """Gap < 7 dias -> severidade baixa."""
        res = _resultado_doi([_desvio_doi(gap_dias=3.0, doi_actual=33.0, doi_plan=30.0)])
        sinais = extrair_sinais_de_resultados(res)
        assert sinais[0].severidade == "baixa"

    def test_doi_negativo(self) -> None:
        """DOI abaixo do target (risco de ruptura)."""
        res = _resultado_doi([_desvio_doi(gap_dias=-10.0, doi_actual=20.0, doi_plan=30.0)])
        sinais = extrair_sinais_de_resultados(res)
        s = sinais[0]
        assert s.valor == 20.0
        assert s.referencia == 30.0
        assert s.severidade == "media"


# ---------------------------------------------------------------------------
# Testes de sinais mistos
# ---------------------------------------------------------------------------

class TestSinaisMistos:
    """Testa extracao com multiplos tipos de resultado simultaneos."""

    def test_legado_e_mondelez_juntos(self) -> None:
        """Deve extrair sinais de todos os tipos presentes."""
        resultados = {
            "comparacao_demanda": pd.DataFrame({
                "sku": ["SKU001"],
                "demanda_real": [1000.0],
                "demanda_modelada": [1100.0],
                "delta_demanda_pct": [10.0],
            }),
            "analise_sellout": {
                "desvios": [_desvio_so()],
                "resumo": {},
            },
            "analise_doi": {
                "desvios": [_desvio_doi()],
                "resumo": {},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados)
        tipos = {s.tipo for s in sinais}
        assert "desvio_demanda" in tipos
        assert "desvio_sellout" in tipos
        assert "doi_fora_politica" in tipos
        assert len(sinais) == 3

    def test_ids_unicos_entre_tipos(self) -> None:
        """IDs devem ser unicos mesmo com multiplos tipos."""
        resultados = {
            "analise_sellout": {
                "desvios": [_desvio_so()],
                "resumo": {},
            },
            "analise_sellin": {
                "desvios": [_desvio_si()],
                "resumo": {},
            },
            "analise_doi": {
                "desvios": [_desvio_doi()],
                "resumo": {},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados)
        ids = [s.sinal_id for s in sinais]
        assert len(ids) == len(set(ids)), f"IDs duplicados: {ids}"

    def test_analise_none_ignorada(self) -> None:
        """Se o valor da chave nao for dict, ignorar."""
        resultados = {"analise_sellout": None}
        sinais = extrair_sinais_de_resultados(resultados)
        assert len(sinais) == 0

    def test_desvios_nao_lista_ignorado(self) -> None:
        """Se desvios nao for lista, ignorar."""
        resultados = {
            "analise_sellout": {
                "desvios": "nao_uma_lista",
                "resumo": {},
            }
        }
        sinais = extrair_sinais_de_resultados(resultados)
        assert len(sinais) == 0
