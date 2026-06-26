"""
Testes de invariantes para optimus.py.

Invariantes testadas:
- Sem sinais -> sem proposicoes.
- Desvio < 5% nao gera proposicao.
- Desvio >= 5% gera proposicao com tipo na whitelist.
- Impacto financeiro == impacto calculado (invariante).
- Proposicoes ordenadas por impacto decrescente.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from optimus import gerar_proposicoes
from state_types import TIPOS_DECISAO_MVP, Sinal


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


class TestOptimusGeracaoProposicoes:
    """Testes para gerar_proposicoes."""

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
