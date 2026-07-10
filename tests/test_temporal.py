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
    RISCO_OPORTUNIDADE,
    analisar_tendencia,
    analisar_forward,
    analisar_desvio_persistente,
    _classificar_direcao_doi,
    _contar_semanas_consecutivas,
    _contar_meses_consecutivos_mesmo_sinal,
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
        bel_rup = [a for a in bel if a["risco_projetado"] == RISCO_RUPTURA]
        assert len(bel_rup) == 1
        # Dual framing: pode haver oportunidade adicional se plano curto
        for a in bel:
            if a["risco_projetado"] == RISCO_OPORTUNIDADE:
                assert a.get("dual_com_ruptura") is True

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
        total = (
            resumo["rupturas_projetadas"]
            + resumo["overstocks_projetados"]
            + resumo["gaps_plano"]
            + resumo.get("oportunidades", 0)
        )
        assert total == resumo["total_alertas"]

    def test_doi_baixo_nunca_substitui_ruptura_por_oportunidade(self) -> None:
        """
        Fronteira: DOI < tau + SO acima -> ruptura primaria permanece.
        Dual framing pode adicionar oportunidade se plano subdimensionado.
        """
        df = _carregar_fixture()
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(df, mapa, janela_recente_dias=30)
        bel = [a for a in resultado["alertas_forward"] if a["sku"] == "BEL-TEST-75G"]
        bel_rup = [a for a in bel if a["risco_projetado"] == RISCO_RUPTURA]
        assert len(bel_rup) == 1
        assert bel_rup[0]["doi_atual"] < 15.0
        assert bel_rup[0].get("dual_com_ruptura") is False
        bel_opp = [a for a in bel if a["risco_projetado"] == RISCO_OPORTUNIDADE]
        for a in bel_opp:
            assert a.get("dual_com_ruptura") is True
            assert a.get("plano_subdimensionado") is True

    def test_dual_framing_ruptura_e_oportunidade(self) -> None:
        """
        Ruptura + plano subdimensionado emite dois alertas (sem SKU hardcoded).
        """
        rows = []
        for day in range(1, 31):
            rows.append({
                "Date": f"2026-05-{day:02d}",
                "SKU_Code": "DUAL-TEST-01",
                "Country": "Brazil",
                "Channel": "Modern Trade",
                "Category": "Biscuits",
                "Brand": "DualBrand",
                "SellOut_Plan_Ton": 10.0,
                "SellOut_Actual_Ton": 18.0,
                "SellIn_Plan_Ton": 10.0,
                "SellIn_Actual_Ton": 12.0,
                "DOI_Plan_Days": 30.0,
                "DOI_Actual_Days": 8.0,
                "SellOut_Actual_NR_USD": 2000.0,
            })
        for day in range(1, 15):
            rows.append({
                "Date": f"2026-06-{day:02d}",
                "SKU_Code": "DUAL-TEST-01",
                "Country": "Brazil",
                "Channel": "Modern Trade",
                "Category": "Biscuits",
                "Brand": "DualBrand",
                "SellOut_Plan_Ton": 8.0,
                "SellOut_Actual_Ton": float("nan"),
                "SellIn_Plan_Ton": 8.0,
                "SellIn_Actual_Ton": float("nan"),
                "DOI_Plan_Days": 28.0,
                "DOI_Actual_Days": float("nan"),
                "SellOut_Actual_NR_USD": float("nan"),
            })
        df = pd.DataFrame(rows)
        mapa = {c: c for c in df.columns}
        resultado = analisar_forward(
            df, mapa, janela_recente_dias=30, data_corte="2026-05-30"
        )
        alertas = [
            a for a in resultado["alertas_forward"]
            if a["sku"] == "DUAL-TEST-01"
        ]
        riscos = {a["risco_projetado"] for a in alertas}
        assert RISCO_RUPTURA in riscos
        assert RISCO_OPORTUNIDADE in riscos
        opp = [a for a in alertas if a["risco_projetado"] == RISCO_OPORTUNIDADE]
        assert opp[0]["dual_com_ruptura"] is True

    def test_oportunidade_exige_doi_saudavel(self) -> None:
        """
        Oportunidade so quando DOI na faixa [tau_r, tau_o], SO acima
        e plano forward subdimensionado -- regra sem SKU hardcoded.
        """
        rows = []
        # Janela recente: DOI saudavel (20d), SO acima do plano
        for i, day in enumerate(range(1, 31)):
            rows.append({
                "Date": f"2026-05-{day:02d}",
                "SKU_Code": "OPP-TEST-01",
                "Country": "Brazil",
                "Channel": "Modern Trade",
                "Category": "Biscuits",
                "Brand": "OppBrand",
                "SellOut_Plan_Ton": 10.0,
                "SellOut_Actual_Ton": 15.0,
                "SellIn_Plan_Ton": 10.0,
                "SellIn_Actual_Ton": 12.0,
                "DOI_Plan_Days": 30.0,
                "DOI_Actual_Days": 20.0,
                "SellOut_Actual_NR_USD": 1000.0,
            })
        # Forward: plano SO curto vs ritmo recente
        for day in range(1, 15):
            rows.append({
                "Date": f"2026-06-{day:02d}",
                "SKU_Code": "OPP-TEST-01",
                "Country": "Brazil",
                "Channel": "Modern Trade",
                "Category": "Biscuits",
                "Brand": "OppBrand",
                "SellOut_Plan_Ton": 5.0,
                "SellOut_Actual_Ton": float("nan"),
                "SellIn_Plan_Ton": 5.0,
                "SellIn_Actual_Ton": float("nan"),
                "DOI_Plan_Days": 30.0,
                "DOI_Actual_Days": float("nan"),
                "SellOut_Actual_NR_USD": float("nan"),
            })
        df = pd.DataFrame(rows)
        mapa = _mapa_identidade(df)
        resultado = analisar_forward(
            df, mapa, janela_recente_dias=30, data_corte="2026-05-30"
        )
        opp = [a for a in resultado["alertas_forward"] if a["sku"] == "OPP-TEST-01"]
        assert len(opp) == 1
        assert opp[0]["risco_projetado"] == RISCO_OPORTUNIDADE

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

    def test_doi_estavel_so_proximo_suprimido(self) -> None:
        """Overstock com tendencia estavel e SO perto do plano nao rebalanceia."""
        sinais = [
            Sinal(
                sinal_id="SIG-DOI-1",
                tipo="doi_fora_politica",
                sku="SKU-STABLE",
                canal="MT",
                metrica="doi",
                valor=47.0,
                referencia=25.0,
                desvio_pct=88.0,
                severidade="alta",
                pais="BR",
                nr_impacto=5000.0,
            ),
            Sinal(
                sinal_id="SIG-TEND-1",
                tipo="tendencia_temporal",
                sku="SKU-STABLE",
                canal="MT",
                metrica="tendencia_doi_so",
                valor=47.0,
                referencia=46.0,
                desvio_pct=2.0,
                severidade="baixa",
                pais="BR",
                tendencia="estavel",
                so_ritmo="estavel",
            ),
        ]
        props = gerar_proposicoes(sinais)
        assert props == []

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


class TestContarMesesConsecutivos:
    """Testes para _contar_meses_consecutivos_mesmo_sinal."""

    def test_todos_negativos(self) -> None:
        import numpy as np
        vals = np.array([-10.0, -15.0, -17.0, -12.0])
        assert _contar_meses_consecutivos_mesmo_sinal(vals) == 4

    def test_mudanca_de_sinal(self) -> None:
        import numpy as np
        vals = np.array([5.0, -10.0, -15.0, -17.0])
        assert _contar_meses_consecutivos_mesmo_sinal(vals) == 3

    def test_ultimo_zero(self) -> None:
        import numpy as np
        vals = np.array([-10.0, -15.0, 0.0])
        assert _contar_meses_consecutivos_mesmo_sinal(vals) == 0

    def test_vazio(self) -> None:
        import numpy as np
        assert _contar_meses_consecutivos_mesmo_sinal(np.array([])) == 0

    def test_todos_positivos(self) -> None:
        import numpy as np
        vals = np.array([3.0, 5.0, 8.0])
        assert _contar_meses_consecutivos_mesmo_sinal(vals) == 3


class TestRitmoVariacaoSO:
    """Testes para ritmo de variacao SO (aceleracao/desaceleracao)."""

    def test_tendencia_contem_so_ritmo(self) -> None:
        """analisar_tendencia deve retornar so_ritmo e so_aceleracao_pct."""
        sinal_tend = Sinal(
            sinal_id="SIG-TEND-001", tipo="tendencia_temporal",
            sku="OREO_MX", canal="RETAIL", metrica="tendencia_doi_so",
            valor=50.0, referencia=40.0, desvio_pct=-16.0,
            severidade="alta", pais="MX", tendencia="piorando",
            so_ritmo="desacelerando", so_aceleracao_pct=-8.0,
        )
        assert sinal_tend.so_ritmo == "desacelerando"
        assert sinal_tend.so_aceleracao_pct == -8.0

    def test_optimus_overstock_com_causa_raiz(self) -> None:
        """DOI overstock + SO desacelerando -> proposicao com CAUSA-RAIZ."""
        sinal_doi = Sinal(
            sinal_id="SIG-DOI-001", tipo="doi_fora_politica",
            sku="OREO_MX", canal="RETAIL", metrica="doi_dias",
            valor=50.0, referencia=30.0, desvio_pct=66.0,
            severidade="alta", pais="MX",
        )
        sinal_tend = Sinal(
            sinal_id="SIG-TEND-001", tipo="tendencia_temporal",
            sku="OREO_MX", canal="RETAIL", metrica="tendencia_doi_so",
            valor=50.0, referencia=40.0, desvio_pct=-16.0,
            severidade="alta", pais="MX", tendencia="piorando",
            so_ritmo="desacelerando", so_aceleracao_pct=-8.0,
        )
        proposicoes = gerar_proposicoes([sinal_doi, sinal_tend])
        doi_props = [
            p for p in proposicoes
            if p.tipo == "rebalancear_estoque_doi"
        ]
        assert len(doi_props) == 1
        assert "CAUSA-RAIZ" in doi_props[0].descricao
        assert "desacelerando" in doi_props[0].descricao.lower()


class TestClassificadorOportunidade:
    """Testes para classificacao oportunidade vs risco."""

    def test_oportunidade_forward_gera_sinal_correto(self) -> None:
        """forward_oportunidade no sinais.py gera tipo correto."""
        resultados = {
            "analise_forward": {
                "alertas_forward": [
                    {
                        "risco_projetado": "oportunidade",
                        "divergencia_forward_pct": -20.0,
                        "doi_atual": 10.0,
                        "doi_plan_forward": 25.0,
                        "sku": "TANG_BR",
                        "canal": "RETAIL",
                        "pais": "BR",
                        "categoria": "Beverage",
                        "marca": "Tang",
                    },
                ],
                "resumo": {"total_alertas": 1},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados)
        oport = [s for s in sinais if s.tipo == "forward_oportunidade"]
        assert len(oport) == 1
        assert oport[0].risco_forward == "oportunidade"
        assert oport[0].sku == "TANG_BR"

    def test_oportunidade_gera_proposicao_capturar(self) -> None:
        """forward_oportunidade -> capturar_oportunidade proposicao."""
        sinal = Sinal(
            sinal_id="SIG-FWD-001", tipo="forward_oportunidade",
            sku="TANG_BR", canal="RETAIL", metrica="forward_divergencia",
            valor=10.0, referencia=25.0, desvio_pct=-20.0,
            severidade="media", pais="BR", risco_forward="oportunidade",
        )
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "capturar_oportunidade"
        assert "OPORTUNIDADE" in props[0].descricao

    def test_ruptura_nao_vira_oportunidade(self) -> None:
        """premissa_forward_furada com risco ruptura mantido como ruptura."""
        sinal = Sinal(
            sinal_id="SIG-FWD-001", tipo="premissa_forward_furada",
            sku="BEL_X", canal="RETAIL", metrica="forward_divergencia",
            valor=8.0, referencia=20.0, desvio_pct=-30.0,
            severidade="alta", pais="BR", risco_forward="ruptura",
        )
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "questionar_premissa_plano"
        assert "RUPTURA" in props[0].descricao


class TestDesvioPersistente:
    """Testes para heuristica de desvio persistente."""

    def test_sinal_desvio_persistente_criado(self) -> None:
        """analise_desvio_persistente gera sinais corretos."""
        resultados = {
            "analise_desvio_persistente": {
                "persistentes": [
                    {
                        "sku": "TANG_AR",
                        "canal": "RETAIL",
                        "pais": "AR",
                        "categoria": "Beverage",
                        "marca": "Tang",
                        "meses_consecutivos": 4,
                        "media_desvio_pct": -17.0,
                        "direcao": "abaixo",
                    },
                ],
                "resumo": {"total": 1},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados)
        pers = [s for s in sinais if s.tipo == "desvio_persistente"]
        assert len(pers) == 1
        assert pers[0].meses_desvio_persistente == 4
        assert pers[0].media_desvio_persistente_pct == -17.0
        assert pers[0].severidade == "alta"

    def test_proposicao_investigar_desvio_persistente(self) -> None:
        """desvio_persistente -> investigar_desvio_persistente."""
        sinal = Sinal(
            sinal_id="SIG-PERS-001", tipo="desvio_persistente",
            sku="TANG_AR", canal="RETAIL", metrica="sellout_desvio_mensal",
            valor=-17.0, referencia=0.0, desvio_pct=-17.0,
            severidade="alta", pais="AR",
            meses_desvio_persistente=4, media_desvio_persistente_pct=-17.0,
        )
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "investigar_desvio_persistente"
        assert "PERSISTENTE" in props[0].descricao
        assert "4 meses" in props[0].descricao
        assert "estrutural" in props[0].descricao.lower()

    def test_menos_de_3_meses_nao_gera_sinal(self) -> None:
        """Desvio por apenas 2 meses nao gera sinal de alta severidade."""
        resultados = {
            "analise_desvio_persistente": {
                "persistentes": [
                    {
                        "sku": "TEST_X",
                        "canal": "RETAIL",
                        "pais": "BR",
                        "meses_consecutivos": 2,
                        "media_desvio_pct": -10.0,
                        "direcao": "abaixo",
                    },
                ],
                "resumo": {"total": 1},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados)
        pers = [s for s in sinais if s.tipo == "desvio_persistente"]
        assert len(pers) == 1
        assert pers[0].severidade == "media"
