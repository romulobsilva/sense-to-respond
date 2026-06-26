"""
Testes de invariantes para state_types.py.

Invariantes testadas:
- State inicial tem todos os campos obrigatorios.
- Serializacao de sinais e proposicoes produz string nao vazia.
- Conversao dict -> Sinal e dict -> Proposicao funciona.
- Handoff registra corretamente no state.
- TIPOS_DECISAO_MVP e frozenset imutavel.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state_types import (
    TIPOS_DECISAO_MVP,
    Proposicao,
    Sinal,
    criar_state_inicial,
    proposicoes_do_state,
    registrar_handoff,
    serializar_proposicoes_para_llm,
    serializar_sinais_para_llm,
    sinais_do_state,
)


def _sinal_dict() -> dict:
    """Dicionario com campos de sinal validos."""
    return {
        "sinal_id": "SIG-DEM-001",
        "tipo": "desvio_demanda",
        "sku": "SKU001",
        "canal": "varejo",
        "metrica": "volume_unidades",
        "valor": 1200.0,
        "referencia": 1000.0,
        "desvio_pct": 20.0,
        "severidade": "alta",
    }


def _proposicao_dict() -> dict:
    """Dicionario com campos de proposicao validos."""
    return {
        "proposicao_id": "P1",
        "tipo": "ajustar_demanda",
        "titulo": "Teste",
        "descricao": "Descricao teste",
        "impacto_financeiro": 5000.0,
        "impacto_calculado": 5000.0,
        "urgencia_horas": 48,
        "skus": ["SKU001"],
        "evidencias": ["SIG-DEM-001"],
    }


class TestStateInicial:
    """Testes para criar_state_inicial."""

    def test_campos_obrigatorios_presentes(self) -> None:
        state = criar_state_inicial("Pergunta teste")
        campos = [
            "pergunta", "dados", "resultados", "acoes_executadas",
            "sinais", "proposicoes", "validacao", "critica",
            "fila_nexus", "optimus_tentativas", "handoffs",
        ]
        for campo in campos:
            assert campo in state, f"Campo '{campo}' ausente no state."

    def test_pergunta_armazenada(self) -> None:
        state = criar_state_inicial("Minha pergunta")
        assert state["pergunta"] == "Minha pergunta"

    def test_listas_iniciam_vazias(self) -> None:
        state = criar_state_inicial("teste")
        assert state["sinais"] == []
        assert state["proposicoes"] == []
        assert state["handoffs"] == []


class TestConversaoState:
    """Testes para sinais_do_state e proposicoes_do_state."""

    def test_sinais_de_dict(self) -> None:
        state = criar_state_inicial("teste")
        state["sinais"] = [_sinal_dict()]
        sinais = sinais_do_state(state)
        assert len(sinais) == 1
        assert isinstance(sinais[0], Sinal)
        assert sinais[0].sku == "SKU001"

    def test_sinais_de_objeto(self) -> None:
        state = criar_state_inicial("teste")
        sinal = Sinal(**_sinal_dict())
        state["sinais"] = [sinal]
        sinais = sinais_do_state(state)
        assert len(sinais) == 1
        assert sinais[0] is sinal

    def test_proposicoes_de_dict(self) -> None:
        state = criar_state_inicial("teste")
        state["proposicoes"] = [_proposicao_dict()]
        props = proposicoes_do_state(state)
        assert len(props) == 1
        assert isinstance(props[0], Proposicao)

    def test_sinais_invalido_retorna_vazio(self) -> None:
        state = criar_state_inicial("teste")
        state["sinais"] = "nao_e_lista"
        sinais = sinais_do_state(state)
        assert sinais == []


class TestSerializacao:
    """Testes para serializar_sinais_para_llm e serializar_proposicoes_para_llm."""

    def test_sinais_vazio(self) -> None:
        resultado = serializar_sinais_para_llm([])
        assert "Nenhum" in resultado

    def test_sinais_formatados(self) -> None:
        sinal = Sinal(**_sinal_dict())
        resultado = serializar_sinais_para_llm([sinal])
        assert "SIG-DEM-001" in resultado
        assert "SKU001" in resultado

    def test_proposicoes_vazio(self) -> None:
        resultado = serializar_proposicoes_para_llm([])
        assert "Nenhuma" in resultado

    def test_proposicoes_formatadas(self) -> None:
        prop = Proposicao(**_proposicao_dict())
        resultado = serializar_proposicoes_para_llm([prop])
        assert "P1" in resultado
        assert "R$" in resultado


class TestHandoff:
    """Testes para registrar_handoff."""

    def test_handoff_registrado(self) -> None:
        state = criar_state_inicial("teste")
        registrar_handoff(state, "dominion", "optimus", ["sinais"])
        assert len(state["handoffs"]) == 1
        assert state["handoffs"][0]["origem"] == "dominion"
        assert state["handoffs"][0]["destino"] == "optimus"

    def test_multiplos_handoffs(self) -> None:
        state = criar_state_inicial("teste")
        registrar_handoff(state, "dominion", "optimus", ["sinais"])
        registrar_handoff(state, "optimus", "validator", ["proposicoes"])
        assert len(state["handoffs"]) == 2


class TestTiposDecisaoMVP:
    """Testes para TIPOS_DECISAO_MVP."""

    def test_e_frozenset(self) -> None:
        assert isinstance(TIPOS_DECISAO_MVP, frozenset)

    def test_contem_tipos_esperados(self) -> None:
        esperados = [
            "rebalancear_estoque", "priorizar_skus", "ajustar_cobertura",
            "proteger_promocao", "gerenciar_falta_excesso",
            "ajustar_custo", "ajustar_demanda",
        ]
        for tipo in esperados:
            assert tipo in TIPOS_DECISAO_MVP
