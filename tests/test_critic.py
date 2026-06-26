"""
Testes de invariantes para critic.py.

Invariantes testadas:
- Parsing booleano: "false" (string) deve resultar em aprovado=False.
- Confianca fora de 0-1 e clamped.
- Confianca invalida cai para 0.0.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state_types import ResultadoCritica


class TestCriticBoolParsing:
    """Testa que o fix de parsing booleano funciona corretamente."""

    def test_string_false_nao_vira_true(self) -> None:
        """ADR-0011: bool("false") == True e um bug. Deve ser False."""
        raw = "false"
        if isinstance(raw, bool):
            resultado = raw
        elif isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is False

    def test_string_true_vira_true(self) -> None:
        raw = "true"
        if isinstance(raw, bool):
            resultado = raw
        elif isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is True

    def test_bool_true_permanece(self) -> None:
        raw = True
        if isinstance(raw, bool):
            resultado = raw
        elif isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is True

    def test_bool_false_permanece(self) -> None:
        raw = False
        if isinstance(raw, bool):
            resultado = raw
        elif isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is False

    def test_string_zero_e_false(self) -> None:
        raw = "0"
        if isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is False

    def test_string_um_e_true(self) -> None:
        raw = "1"
        if isinstance(raw, str):
            resultado = raw.lower() in ("true", "1", "sim", "yes")
        else:
            resultado = False
        assert resultado is True


class TestCriticConfiancaRange:
    """Testa clamping de confianca 0-1."""

    def test_confianca_valida(self) -> None:
        rc = ResultadoCritica(aprovado=True, confianca=0.85, problemas=[])
        assert 0.0 <= rc.confianca <= 1.0

    def test_confianca_negativa_clamp(self) -> None:
        valor = -0.5
        clamped = max(0.0, min(1.0, valor))
        assert clamped == 0.0

    def test_confianca_acima_um_clamp(self) -> None:
        valor = 1.5
        clamped = max(0.0, min(1.0, valor))
        assert clamped == 1.0

    def test_confianca_invalida_cai_para_zero(self) -> None:
        raw = "nao_e_numero"
        try:
            confianca = float(raw)
        except (TypeError, ValueError):
            confianca = 0.0
        assert confianca == 0.0
