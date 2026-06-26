"""
Testes de invariantes para validator.py.

Invariantes testadas:
- SKU inexistente nos sinais gera erro.
- Evidencia inexistente nos sinais gera erro.
- Tipo fora da whitelist gera erro.
- Impacto divergente gera erro.
- Proposicoes validas passam sem erros.
- Lista vazia de proposicoes gera erro.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state_types import Proposicao, Sinal
from validator import validar_proposicoes


def _sinal_teste() -> Sinal:
    """Cria sinal de teste padrao."""
    return Sinal(
        sinal_id="SIG-DEM-001",
        tipo="desvio_demanda",
        sku="SKU001",
        canal="varejo",
        metrica="volume_unidades",
        valor=1200.0,
        referencia=1000.0,
        desvio_pct=20.0,
        severidade="alta",
    )


def _proposicao_valida() -> Proposicao:
    """Cria proposicao valida compativel com _sinal_teste."""
    return Proposicao(
        proposicao_id="P1",
        tipo="ajustar_demanda",
        titulo="Ajustar demanda SKU001",
        descricao="Desvio de 20% na demanda",
        impacto_financeiro=12400.0,
        impacto_calculado=12400.0,
        urgencia_horas=48,
        skus=["SKU001"],
        evidencias=["SIG-DEM-001"],
    )


class TestValidadorDeterministico:
    """Testes para validar_proposicoes."""

    def test_proposicao_valida_passa(self) -> None:
        sinais = [_sinal_teste()]
        props = [_proposicao_valida()]
        resultado = validar_proposicoes(props, sinais)
        assert resultado.ok is True
        assert len(resultado.erros) == 0

    def test_lista_vazia_gera_erro(self) -> None:
        resultado = validar_proposicoes([], [_sinal_teste()])
        assert resultado.ok is False

    def test_sku_inexistente(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.skus = ["SKU_INEXISTENTE"]
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False
        assert any("SKU" in e for e in resultado.erros)

    def test_evidencia_inexistente(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.evidencias = ["SIG-FAKE-999"]
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False
        assert any("evidencia" in e for e in resultado.erros)

    def test_tipo_fora_whitelist(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.tipo = "tipo_inventado"
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False
        assert any("whitelist" in e for e in resultado.erros)

    def test_impacto_divergente(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.impacto_financeiro = 99999.0
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False
        assert any("impacto" in e.lower() for e in resultado.erros)

    def test_urgencia_zero_gera_erro(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.urgencia_horas = 0
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False

    def test_descricao_vazia_gera_erro(self) -> None:
        sinais = [_sinal_teste()]
        prop = _proposicao_valida()
        prop.descricao = ""
        resultado = validar_proposicoes([prop], sinais)
        assert resultado.ok is False
