"""
Testes de invariantes para optimus.py.

Invariantes testadas:
- Sem sinais -> sem proposicoes.
- Desvio < 5% nao gera proposicao.
- Desvio >= 5% gera proposicao com tipo na whitelist.
- Impacto financeiro == impacto calculado (invariante).
- Proposicoes ordenadas por impacto decrescente.

Novos testes Mondelez (ADR-0019):
- desvio_sellout -> ajustar_plano_sellout
- desvio_sellin -> ajustar_plano_sellin
- doi_fora_politica -> rebalancear_estoque_doi
- Dimensoes (pais, canal, marca) no titulo/descricao
- Acao DOI: drenar estoque vs evitar ruptura
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from optimus import (
    gerar_proposicoes,
    LIMIAR_DESVIO_PCT,
    LIMIAR_DOI_GAP_DIAS,
)
from state_types import TIPOS_DECISAO_MVP, Sinal


# ---------------------------------------------------------------------------
# Helpers legados
# ---------------------------------------------------------------------------

def _sinal_demanda(
    sku: str = "SKU001",
    valor: float = 1200.0,
    referencia: float = 1000.0,
    desvio_pct: float = 20.0,
    severidade: str = "alta",
) -> Sinal:
    """Cria sinal de demanda para teste."""
    return Sinal(
        sinal_id=f"SIG-DEM-{sku}",
        tipo="desvio_demanda",
        sku=sku,
        canal="varejo",
        metrica="volume_unidades",
        valor=valor,
        referencia=referencia,
        desvio_pct=desvio_pct,
        severidade=severidade,
    )


def _sinal_custo(
    desvio_pct: float = 15.0,
    valor: float = 115000.0,
    referencia: float = 100000.0,
) -> Sinal:
    """Cria sinal de custo para teste."""
    return Sinal(
        sinal_id="SIG-CUS-001",
        tipo="desvio_custo",
        sku="TOTAL",
        canal="consolidado",
        metrica="custo_total",
        valor=valor,
        referencia=referencia,
        desvio_pct=desvio_pct,
        severidade="alta",
    )


# ---------------------------------------------------------------------------
# Helpers Mondelez
# ---------------------------------------------------------------------------

def _sinal_sellout(
    sku: str = "LAC-TAB-90G",
    desvio_pct: float = 18.4,
    valor: float = 2.51,
    referencia: float = 2.12,
    severidade: str = "alta",
    pais: str = "Brazil",
    canal: str = "Traditional Trade",
    marca: str = "Lacta",
) -> Sinal:
    """Cria sinal de sell-out para teste."""
    return Sinal(
        sinal_id=f"SIG-SO-{sku}",
        tipo="desvio_sellout",
        sku=sku,
        canal=canal,
        metrica="sellout_ton",
        valor=valor,
        referencia=referencia,
        desvio_pct=desvio_pct,
        severidade=severidade,
        pais=pais,
        categoria="Chocolates",
        marca=marca,
    )


def _sinal_sellin(
    sku: str = "LAC-TAB-90G",
    desvio_pct: float = 26.32,
    valor: float = 2.88,
    referencia: float = 2.28,
    severidade: str = "alta",
) -> Sinal:
    """Cria sinal de sell-in para teste."""
    return Sinal(
        sinal_id=f"SIG-SI-{sku}",
        tipo="desvio_sellin",
        sku=sku,
        canal="Traditional Trade",
        metrica="sellin_ton",
        valor=valor,
        referencia=referencia,
        desvio_pct=desvio_pct,
        severidade=severidade,
        pais="Brazil",
        categoria="Chocolates",
        marca="Lacta",
    )


def _sinal_doi(
    sku: str = "TRI-GUM-14G",
    valor: float = 48.0,
    referencia: float = 30.0,
    desvio_pct: float = 60.0,
    severidade: str = "alta",
    canal: str = "Modern Trade",
    pais: str = "Colombia",
    marca: str = "Trident",
) -> Sinal:
    """Cria sinal de DOI fora da politica para teste."""
    return Sinal(
        sinal_id=f"SIG-DOI-{sku}",
        tipo="doi_fora_politica",
        sku=sku,
        canal=canal,
        metrica="doi_dias",
        valor=valor,
        referencia=referencia,
        desvio_pct=desvio_pct,
        severidade=severidade,
        pais=pais,
        categoria="Gum",
        marca=marca,
    )


# ---------------------------------------------------------------------------
# Testes legados (regressao)
# ---------------------------------------------------------------------------

class TestOptimusGeracaoProposicoes:
    """Testes para gerar_proposicoes (legado)."""

    def test_sem_sinais_retorna_vazio(self) -> None:
        props = gerar_proposicoes([])
        assert len(props) == 0

    def test_desvio_abaixo_limiar_sem_proposicao(self) -> None:
        sinal = _sinal_demanda(desvio_pct=3.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 0

    def test_desvio_acima_limiar_gera_proposicao(self) -> None:
        sinal = _sinal_demanda(desvio_pct=10.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1

    def test_tipo_na_whitelist(self) -> None:
        sinal = _sinal_demanda()
        props = gerar_proposicoes([sinal])
        for prop in props:
            assert prop.tipo in TIPOS_DECISAO_MVP

    def test_invariante_impacto_igual_calculado(self) -> None:
        """ADR-0002: impacto_financeiro == impacto_calculado."""
        sinal = _sinal_demanda()
        props = gerar_proposicoes([sinal])
        for prop in props:
            assert prop.impacto_financeiro == prop.impacto_calculado

    def test_ordenacao_por_impacto_decrescente(self) -> None:
        s1 = _sinal_demanda("SKU001", valor=1100, referencia=1000, desvio_pct=10.0)
        s2 = _sinal_demanda("SKU002", valor=2000, referencia=1000, desvio_pct=100.0)
        props = gerar_proposicoes([s1, s2])
        assert len(props) == 2
        assert props[0].impacto_financeiro >= props[1].impacto_financeiro

    def test_custo_gera_proposicao(self) -> None:
        sinal = _sinal_custo()
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "ajustar_custo"

    def test_ids_reindexados(self) -> None:
        s1 = _sinal_demanda("SKU001", desvio_pct=10.0)
        s2 = _sinal_demanda("SKU002", desvio_pct=20.0)
        props = gerar_proposicoes([s1, s2])
        ids = [p.proposicao_id for p in props]
        assert ids == ["P1", "P2"]


# ---------------------------------------------------------------------------
# Testes de proposicoes sell-out (ADR-0019)
# ---------------------------------------------------------------------------

class TestOptimusSellOut:
    """Proposicoes de ajuste de sell-out."""

    def test_sellout_gera_proposicao(self) -> None:
        sinal = _sinal_sellout(desvio_pct=18.4)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "ajustar_plano_sellout"
        assert props[0].tipo in TIPOS_DECISAO_MVP

    def test_sellout_abaixo_limiar(self) -> None:
        """Desvio < 5% nao gera proposicao."""
        sinal = _sinal_sellout(desvio_pct=3.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 0

    def test_sellout_negativo_gera_proposicao(self) -> None:
        """Desvio negativo (abaixo do plan) >= 5% gera proposicao."""
        sinal = _sinal_sellout(desvio_pct=-8.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1

    def test_sellout_dimensoes_no_titulo(self) -> None:
        """Titulo deve conter dimensoes do sinal."""
        sinal = _sinal_sellout(pais="Brazil", canal="Modern Trade", marca="Lacta")
        props = gerar_proposicoes([sinal])
        titulo = props[0].titulo
        assert "Brazil" in titulo
        assert "Lacta" in titulo

    def test_sellout_impacto_invariante(self) -> None:
        """ADR-0002: impacto_financeiro == impacto_calculado."""
        sinal = _sinal_sellout()
        props = gerar_proposicoes([sinal])
        for prop in props:
            assert prop.impacto_financeiro == prop.impacto_calculado

    def test_sellout_evidencia_vinculada(self) -> None:
        sinal = _sinal_sellout()
        props = gerar_proposicoes([sinal])
        assert sinal.sinal_id in props[0].evidencias

    def test_sellout_skus_preenchido(self) -> None:
        sinal = _sinal_sellout(sku="BEL-BIS-45G")
        props = gerar_proposicoes([sinal])
        assert "BEL-BIS-45G" in props[0].skus


# ---------------------------------------------------------------------------
# Testes de proposicoes sell-in (ADR-0019)
# ---------------------------------------------------------------------------

class TestOptimusSellIn:
    """Proposicoes de ajuste de sell-in."""

    def test_sellin_gera_proposicao(self) -> None:
        sinal = _sinal_sellin(desvio_pct=26.32)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "ajustar_plano_sellin"
        assert props[0].tipo in TIPOS_DECISAO_MVP

    def test_sellin_abaixo_limiar(self) -> None:
        sinal = _sinal_sellin(desvio_pct=4.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 0

    def test_sellin_impacto_invariante(self) -> None:
        sinal = _sinal_sellin()
        props = gerar_proposicoes([sinal])
        for prop in props:
            assert prop.impacto_financeiro == prop.impacto_calculado


# ---------------------------------------------------------------------------
# Testes de proposicoes DOI (ADR-0019)
# ---------------------------------------------------------------------------

class TestOptimusDoi:
    """Proposicoes de rebalanceamento de estoque (DOI)."""

    def test_doi_acima_target_gera_drenar(self) -> None:
        """DOI actual > target: drenar estoque."""
        sinal = _sinal_doi(valor=48.0, referencia=30.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert props[0].tipo == "rebalancear_estoque_doi"
        assert props[0].tipo in TIPOS_DECISAO_MVP
        assert "drenar" in props[0].descricao.lower() or "Reduzir" in props[0].descricao

    def test_doi_abaixo_target_gera_evitar_ruptura(self) -> None:
        """DOI actual < target: evitar ruptura."""
        sinal = _sinal_doi(valor=20.0, referencia=30.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1
        assert "ruptura" in props[0].descricao.lower() or "Aumentar" in props[0].descricao

    def test_doi_gap_pequeno_sem_proposicao(self) -> None:
        """Gap < 7 dias nao gera proposicao."""
        sinal = _sinal_doi(valor=33.0, referencia=30.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 0

    def test_doi_gap_exato_limiar(self) -> None:
        """Gap == 7 dias gera proposicao."""
        sinal = _sinal_doi(valor=37.0, referencia=30.0)
        props = gerar_proposicoes([sinal])
        assert len(props) == 1

    def test_doi_impacto_invariante(self) -> None:
        sinal = _sinal_doi()
        props = gerar_proposicoes([sinal])
        for prop in props:
            assert prop.impacto_financeiro == prop.impacto_calculado

    def test_doi_urgencia_alta(self) -> None:
        """DOI alta severidade -> 48h urgencia."""
        sinal = _sinal_doi(severidade="alta")
        props = gerar_proposicoes([sinal])
        assert props[0].urgencia_horas == 48


# ---------------------------------------------------------------------------
# Testes de proposicoes mistas
# ---------------------------------------------------------------------------

class TestOptimusMisto:
    """Testa geracao com sinais de tipos diversos."""

    def test_misto_legado_e_mondelez(self) -> None:
        """Sinais legados e Mondelez geram proposicoes de tipos diferentes."""
        sinais = [
            _sinal_demanda(desvio_pct=10.0),
            _sinal_sellout(desvio_pct=15.0),
            _sinal_doi(valor=45.0, referencia=30.0),
        ]
        props = gerar_proposicoes(sinais)
        tipos = {p.tipo for p in props}
        assert "ajustar_demanda" in tipos
        assert "ajustar_plano_sellout" in tipos
        assert "rebalancear_estoque_doi" in tipos

    def test_misto_todos_na_whitelist(self) -> None:
        sinais = [
            _sinal_demanda(desvio_pct=10.0),
            _sinal_custo(desvio_pct=15.0),
            _sinal_sellout(desvio_pct=15.0),
            _sinal_sellin(desvio_pct=10.0),
            _sinal_doi(valor=45.0, referencia=30.0),
        ]
        props = gerar_proposicoes(sinais)
        for prop in props:
            assert prop.tipo in TIPOS_DECISAO_MVP, (
                f"Tipo '{prop.tipo}' fora da whitelist"
            )

    def test_misto_ordenacao_global(self) -> None:
        """Proposicoes de todos os tipos ordenadas por impacto."""
        sinais = [
            _sinal_demanda(desvio_pct=10.0, valor=1100, referencia=1000),
            _sinal_sellout(desvio_pct=50.0, valor=100.0, referencia=50.0),
            _sinal_doi(valor=60.0, referencia=30.0, desvio_pct=100.0),
        ]
        props = gerar_proposicoes(sinais)
        impactos = [p.impacto_financeiro for p in props]
        assert impactos == sorted(impactos, reverse=True)

    def test_misto_ids_sequenciais(self) -> None:
        sinais = [
            _sinal_demanda(desvio_pct=10.0),
            _sinal_sellout(desvio_pct=15.0),
            _sinal_sellin(desvio_pct=10.0),
        ]
        props = gerar_proposicoes(sinais)
        ids = [p.proposicao_id for p in props]
        expected = [f"P{i}" for i in range(1, len(props) + 1)]
        assert ids == expected

    def test_feedback_validacao_aplicado(self) -> None:
        sinais = [_sinal_sellout(desvio_pct=15.0)]
        feedback = ["Erro de validacao X"]
        props = gerar_proposicoes(sinais, feedback_validacao=feedback)
        assert "retry validador" in props[0].descricao

    def test_feedback_critic_aplicado(self) -> None:
        sinais = [_sinal_doi(valor=45.0, referencia=30.0)]
        feedback = ["Problema Y"]
        props = gerar_proposicoes(sinais, feedback_critic=feedback)
        assert "retry critic" in props[0].descricao
