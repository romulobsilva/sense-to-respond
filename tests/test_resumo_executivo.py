"""
Testes do resumo executivo estratificado (DOI / forward / opps)
e filtro de ruido persistente.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd

from config import DomainThresholds, aplicar_overrides_thresholds
from optimus import gerar_proposicoes, montar_resumo_executivo
from sinais import extrair_sinais_de_resultados
from state_types import Sinal
from tools_parametrizadas import analisar_forward, analisar_tendencia


FIXTURE_TEMPORAL = Path(__file__).parent / "fixtures" / "mondelez_temporal.csv"


def _sinal_persistente(
    sku: str,
    media_desvio: float,
    nr_impacto: float,
    meses: int = 3,
) -> Sinal:
    """Cria sinal de desvio persistente para teste."""
    return Sinal(
        sinal_id=f"SIG-PERS-{sku}",
        tipo="desvio_persistente",
        sku=sku,
        canal="MT",
        metrica="sellout_desvio_mensal",
        valor=media_desvio,
        referencia=0.0,
        desvio_pct=media_desvio,
        severidade="media",
        meses_desvio_persistente=meses,
        media_desvio_persistente_pct=media_desvio,
        nr_impacto=nr_impacto,
    )


class TestFiltroPersistente:
    """Desvio persistente fraco nao gera proposicao."""

    def test_ruido_baixo_nao_entra(self) -> None:
        th = DomainThresholds(
            limiar_persistente_impacto=100.0,
            limiar_persistente_desvio_pct=5.0,
        )
        sinal = _sinal_persistente("SKU-NOISE", media_desvio=1.5, nr_impacto=0.02)
        props = gerar_proposicoes([sinal], thresholds=th)
        assert props == []

    def test_desvio_alto_entra_mesmo_com_impacto_baixo(self) -> None:
        th = DomainThresholds(
            limiar_persistente_impacto=100.0,
            limiar_persistente_desvio_pct=5.0,
        )
        sinal = _sinal_persistente("SKU-STRUCT", media_desvio=-17.0, nr_impacto=50.0)
        props = gerar_proposicoes([sinal], thresholds=th)
        assert len(props) == 1
        assert props[0].tipo == "investigar_desvio_persistente"

    def test_impacto_alto_entra_mesmo_com_desvio_baixo(self) -> None:
        th = DomainThresholds(
            limiar_persistente_impacto=100.0,
            limiar_persistente_desvio_pct=5.0,
        )
        sinal = _sinal_persistente("SKU-NR", media_desvio=2.0, nr_impacto=500.0)
        props = gerar_proposicoes([sinal], thresholds=th)
        assert len(props) == 1


class TestResumoEstratificado:
    """Top N por topico: DOI, forward e oportunidades separados."""

    def _props_mistas(self) -> List:
        sinais = [
            Sinal(
                sinal_id="SIG-DOI-1",
                tipo="doi_fora_politica",
                sku="SKU-DOI-A",
                canal="MT",
                metrica="doi",
                valor=8.0,
                referencia=30.0,
                desvio_pct=-73.0,
                severidade="alta",
                nr_impacto=50000.0,
            ),
            Sinal(
                sinal_id="SIG-DOI-2",
                tipo="doi_fora_politica",
                sku="SKU-DOI-B",
                canal="MT",
                metrica="doi",
                valor=50.0,
                referencia=30.0,
                desvio_pct=66.0,
                severidade="alta",
                nr_impacto=40000.0,
            ),
            Sinal(
                sinal_id="SIG-FWD-1",
                tipo="premissa_forward_furada",
                sku="SKU-FWD",
                canal="MT",
                metrica="forward",
                valor=8.0,
                referencia=30.0,
                desvio_pct=-40.0,
                severidade="alta",
                risco_forward="ruptura",
                nr_impacto=3000.0,
            ),
            Sinal(
                sinal_id="SIG-OPP-1",
                tipo="forward_oportunidade",
                sku="SKU-OPP",
                canal="MT",
                metrica="forward",
                valor=20.0,
                referencia=30.0,
                desvio_pct=12.0,
                severidade="media",
                risco_forward="oportunidade",
                nr_impacto=2000.0,
            ),
        ]
        return gerar_proposicoes(sinais)

    def test_forward_aparece_mesmo_com_doi_maior_nr(self) -> None:
        """Estratificacao: DOI 50k nao elimina forward 3k do quadro."""
        props = self._props_mistas()
        th = DomainThresholds(top_n_doi=2, top_n_forward=2, top_n_oportunidades=2)
        resumo = montar_resumo_executivo(props, th)
        assert len(resumo["top_doi"]) == 2
        assert len(resumo["top_forward"]) == 1
        assert resumo["top_forward"][0]["tipo"] == "questionar_premissa_plano"
        assert resumo["top_forward"][0]["skus"] == ["SKU-FWD"]
        assert resumo["top_oportunidades"][0]["tipo"] == "capturar_oportunidade"
        assert all(x["tipo"] == "rebalancear_estoque_doi" for x in resumo["top_doi"])

    def test_n_por_topico_independente(self) -> None:
        props = self._props_mistas()
        th = DomainThresholds(top_n_doi=1, top_n_forward=1, top_n_oportunidades=1)
        resumo = montar_resumo_executivo(props, th)
        assert len(resumo["top_doi"]) == 1
        assert len(resumo["top_forward"]) == 1
        assert len(resumo["top_oportunidades"]) == 1
        assert resumo["n_doi"] == 1
        assert resumo["n_forward"] == 1

    def test_override_cli_helper(self) -> None:
        base = DomainThresholds(top_n_doi=5, top_n_forward=5)
        over = aplicar_overrides_thresholds(
            base, top_n_doi=2, top_n_forward=8, top_n_oportunidades=3
        )
        assert over.top_n_doi == 2
        assert over.top_n_forward == 8
        assert over.top_n_oportunidades == 3
        assert base.top_n_doi == 5

    def test_legado_top_riscos_aplica_doi_e_forward(self) -> None:
        base = DomainThresholds(top_n_doi=5, top_n_forward=5)
        over = aplicar_overrides_thresholds(base, top_n_riscos=7)
        assert over.top_n_doi == 7
        assert over.top_n_forward == 7

    def test_diversidade_forward_inclui_overstock(self) -> None:
        """Cota de polaridade: overstock entra mesmo com rupturas de maior NR."""
        sinais = [
            Sinal(
                sinal_id="SIG-R1",
                tipo="premissa_forward_furada",
                sku="SKU-R1",
                canal="MT",
                metrica="forward",
                valor=8.0,
                referencia=30.0,
                desvio_pct=-40.0,
                severidade="alta",
                risco_forward="ruptura",
                nr_impacto=90000.0,
            ),
            Sinal(
                sinal_id="SIG-R2",
                tipo="premissa_forward_furada",
                sku="SKU-R2",
                canal="MT",
                metrica="forward",
                valor=9.0,
                referencia=30.0,
                desvio_pct=-35.0,
                severidade="alta",
                risco_forward="ruptura",
                nr_impacto=80000.0,
            ),
            Sinal(
                sinal_id="SIG-R3",
                tipo="premissa_forward_furada",
                sku="SKU-R3",
                canal="MT",
                metrica="forward",
                valor=10.0,
                referencia=30.0,
                desvio_pct=-30.0,
                severidade="alta",
                risco_forward="ruptura",
                nr_impacto=70000.0,
            ),
            Sinal(
                sinal_id="SIG-O1",
                tipo="premissa_forward_furada",
                sku="SKU-OV1",
                canal="WS",
                metrica="forward",
                valor=58.0,
                referencia=36.0,
                desvio_pct=20.0,
                severidade="alta",
                risco_forward="overstock",
                nr_impacto=5000.0,
            ),
        ]
        props = gerar_proposicoes(sinais)
        th = DomainThresholds(top_n_forward=3, top_n_doi=1, top_n_oportunidades=1)
        resumo = montar_resumo_executivo(props, th)
        pols = [x.get("polaridade") for x in resumo["top_forward"]]
        assert "ruptura" in pols
        assert "overstock" in pols
        skus = []
        for item in resumo["top_forward"]:
            skus.extend(item.get("skus") or [])
        assert "SKU-OV1" in skus

    def test_dual_framing_gera_oportunidade_com_ruptura(self) -> None:
        """Sinal forward_oportunidade com DOI critico vira capturar dual."""
        sinal = Sinal(
            sinal_id="SIG-DUAL",
            tipo="forward_oportunidade",
            sku="SKU-DUAL",
            canal="MT",
            metrica="forward",
            valor=8.0,
            referencia=28.0,
            desvio_pct=-25.0,
            severidade="media",
            risco_forward="oportunidade",
            nr_impacto=4000.0,
        )
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "capturar_oportunidade"
        assert "dual" in props[0].descricao.lower()


class TestResumoFixtureTemporal:
    """Fixture temporal: Belvita no DOI e/ou forward estratificado."""

    def test_belvita_no_forward_ou_doi(self) -> None:
        df = pd.read_csv(str(FIXTURE_TEMPORAL))
        mapa: Dict[str, str] = {str(c): str(c) for c in df.columns}
        th = DomainThresholds(top_n_doi=10, top_n_forward=10, top_n_oportunidades=5)
        resultados = {
            "analise_tendencia": analisar_tendencia(
                df, mapa, janela_recente_dias=30, thresholds=th
            ),
            "analise_forward": analisar_forward(
                df, mapa, janela_recente_dias=30, thresholds=th
            ),
            "analise_doi": {
                "desvios": [
                    {
                        "sku": "BEL-TEST-75G",
                        "pais": "Brazil",
                        "canal": "Modern Trade",
                        "categoria": "Biscuits",
                        "marca": "Belvita",
                        "doi_plan": 30.0,
                        "doi_actual": 8.0,
                        "gap_dias": -22.0,
                        "nr_impacto": 5000.0,
                    }
                ],
                "resumo": {},
            },
        }
        sinais = extrair_sinais_de_resultados(resultados, thresholds=th)
        props = gerar_proposicoes(sinais, thresholds=th)
        resumo = montar_resumo_executivo(props, th)

        skus_doi: List[str] = []
        for item in resumo["top_doi"]:
            skus_doi.extend(item.get("skus") or [])
        skus_fwd: List[str] = []
        for item in resumo["top_forward"]:
            skus_fwd.extend(item.get("skus") or [])

        assert "BEL-TEST-75G" in skus_doi or "BEL-TEST-75G" in skus_fwd
        bel_fwd = [
            p for p in props
            if p.tipo == "questionar_premissa_plano" and "BEL-TEST-75G" in p.skus
        ]
        assert len(bel_fwd) >= 1
        assert "RUPTURA" in bel_fwd[0].descricao.upper()
        assert any(
            item["tipo"] == "questionar_premissa_plano"
            for item in resumo["top_forward"]
        )
