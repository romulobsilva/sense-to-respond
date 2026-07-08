"""
Testes para hitl.py: protocolo HITL, PedidoAprovacao, DecisaoHumana.
"""

import json
import threading
import time
from pathlib import Path
from typing import Generator

import pytest

from hitl import (
    DecisaoHumana,
    HITLArquivo,
    HITLAutoApprove,
    HITLTerminal,
    InterfaceHITL,
    PedidoAprovacao,
    TIPOS_PEDIDO_VALIDOS,
)


# ---------------------------------------------------------------------------
# PedidoAprovacao
# ---------------------------------------------------------------------------


class TestPedidoAprovacao:
    """Testes para criacao e serializacao de PedidoAprovacao."""

    def test_criar_pedido_valido(self) -> None:
        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="Confirme o mapeamento",
            detalhes={"col_a": "sellout_actual"},
        )
        assert pedido.tipo == "mapeamento_semantico"
        assert pedido.decisao is None

    def test_criar_pedido_tipo_invalido(self) -> None:
        with pytest.raises(ValueError, match="Tipo de pedido invalido"):
            PedidoAprovacao(
                tipo="tipo_inventado",
                resumo="teste",
                detalhes={},
            )

    def test_todos_tipos_validos_aceitos(self) -> None:
        for tipo in TIPOS_PEDIDO_VALIDOS:
            pedido = PedidoAprovacao(tipo=tipo, resumo="ok", detalhes={})
            assert pedido.tipo == tipo

    def test_para_dict_sem_decisao(self) -> None:
        pedido = PedidoAprovacao(
            tipo="fila_nexus",
            resumo="Revise a fila",
            detalhes={"total": 5},
        )
        d = pedido.para_dict()
        assert d["tipo"] == "fila_nexus"
        assert d["decisao"] is None
        assert d["detalhes"] == {"total": 5}

    def test_para_dict_com_decisao(self) -> None:
        pedido = PedidoAprovacao(
            tipo="fila_nexus",
            resumo="Revise",
            detalhes={},
            decisao=DecisaoHumana.APROVADO,
            comentario="OK",
            decidido_por="analista",
            decidido_em="2026-07-08T14:00:00",
        )
        d = pedido.para_dict()
        assert d["decisao"] == "aprovado"
        assert d["decidido_por"] == "analista"

    def test_from_dict_roundtrip(self) -> None:
        original = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="teste roundtrip",
            detalhes={"a": 1},
            decisao=DecisaoHumana.REJEITADO,
            comentario="nao concordo",
            decidido_por="user",
            decidido_em="2026-07-08T15:00:00",
        )
        d = original.para_dict()
        reconstruido = PedidoAprovacao.from_dict(d)
        assert reconstruido.tipo == original.tipo
        assert reconstruido.decisao == original.decisao
        assert reconstruido.comentario == original.comentario

    def test_from_dict_sem_decisao(self) -> None:
        d = {"tipo": "script_etl", "resumo": "rev", "detalhes": {}}
        pedido = PedidoAprovacao.from_dict(d)
        assert pedido.decisao is None
        assert pedido.tipo == "script_etl"


# ---------------------------------------------------------------------------
# DecisaoHumana
# ---------------------------------------------------------------------------


class TestDecisaoHumana:
    """Testes para o enum DecisaoHumana."""

    def test_valores(self) -> None:
        assert DecisaoHumana.APROVADO.value == "aprovado"
        assert DecisaoHumana.REJEITADO.value == "rejeitado"
        assert DecisaoHumana.EDITADO.value == "editado"
        assert DecisaoHumana.POSTERGADO.value == "postergado"

    def test_from_string(self) -> None:
        assert DecisaoHumana("aprovado") == DecisaoHumana.APROVADO
        assert DecisaoHumana("rejeitado") == DecisaoHumana.REJEITADO

    def test_string_invalida(self) -> None:
        with pytest.raises(ValueError):
            DecisaoHumana("invalido")


# ---------------------------------------------------------------------------
# HITLAutoApprove
# ---------------------------------------------------------------------------


class TestHITLAutoApprove:
    """Testes para HITLAutoApprove."""

    def test_aprova_automaticamente(self) -> None:
        hitl = HITLAutoApprove()
        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="Confirme",
            detalhes={"col": "val"},
        )
        resultado = hitl.solicitar_aprovacao(pedido)
        assert resultado.decisao == DecisaoHumana.APROVADO
        assert resultado.decidido_por == "HITLAutoApprove"
        assert resultado.decidido_em is not None

    def test_registra_historico(self) -> None:
        hitl = HITLAutoApprove()
        for tipo in ["mapeamento_semantico", "fila_nexus"]:
            pedido = PedidoAprovacao(tipo=tipo, resumo="t", detalhes={})
            hitl.solicitar_aprovacao(pedido)
        assert len(hitl.historico) == 2
        assert hitl.historico[0].tipo == "mapeamento_semantico"
        assert hitl.historico[1].tipo == "fila_nexus"

    def test_implementa_interface(self) -> None:
        hitl = HITLAutoApprove()
        assert isinstance(hitl, InterfaceHITL)


# ---------------------------------------------------------------------------
# HITLTerminal
# ---------------------------------------------------------------------------


class TestHITLTerminal:
    """Testes para HITLTerminal com mock de input."""

    def test_aprovacao_via_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["S"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        hitl = HITLTerminal()
        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="Confirme",
            detalhes={},
        )
        resultado = hitl.solicitar_aprovacao(pedido)
        assert resultado.decisao == DecisaoHumana.APROVADO

    def test_rejeicao_via_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["N", "nao gostei"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        hitl = HITLTerminal()
        pedido = PedidoAprovacao(
            tipo="fila_nexus",
            resumo="Revise",
            detalhes={},
        )
        resultado = hitl.solicitar_aprovacao(pedido)
        assert resultado.decisao == DecisaoHumana.REJEITADO
        assert resultado.comentario == "nao gostei"

    def test_edicao_via_terminal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        inputs = iter(["E", "trocar col_a por col_b"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        hitl = HITLTerminal()
        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="Confirme",
            detalhes={},
        )
        resultado = hitl.solicitar_aprovacao(pedido)
        assert resultado.decisao == DecisaoHumana.EDITADO
        assert resultado.comentario == "trocar col_a por col_b"

    def test_implementa_interface(self) -> None:
        hitl = HITLTerminal()
        assert isinstance(hitl, InterfaceHITL)


# ---------------------------------------------------------------------------
# HITLArquivo
# ---------------------------------------------------------------------------


class TestHITLArquivo:
    """Testes para HITLArquivo com arquivos JSON."""

    def test_gera_json_pendente(self, tmp_path: Path) -> None:
        hitl = HITLArquivo(
            approvals_dir=tmp_path,
            polling_interval=0.1,
            polling_timeout=0.5,
        )
        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo="Confirme",
            detalhes={"col": "val"},
        )
        # vai dar timeout, mas o JSON deve ser gerado
        resultado = hitl.solicitar_aprovacao(pedido)
        assert resultado.decisao == DecisaoHumana.POSTERGADO
        assert "timeout" in (resultado.comentario or "")

        arquivos = list(tmp_path.glob("*.json"))
        assert len(arquivos) == 1

        conteudo = json.loads(arquivos[0].read_text(encoding="utf-8"))
        assert conteudo["tipo"] == "mapeamento_semantico"
        assert conteudo["status"] == "timeout"

    def test_detecta_decisao_externa(self, tmp_path: Path) -> None:
        hitl = HITLArquivo(
            approvals_dir=tmp_path,
            polling_interval=0.1,
            polling_timeout=5.0,
        )
        pedido = PedidoAprovacao(
            tipo="fila_nexus",
            resumo="Revise",
            detalhes={"total": 3},
        )

        def simular_decisao_externa() -> None:
            """Simula um usuario editando o JSON apos 0.3s."""
            time.sleep(0.3)
            arquivos = list(tmp_path.glob("*.json"))
            if not arquivos:
                return
            conteudo = json.loads(arquivos[0].read_text(encoding="utf-8"))
            conteudo["decisao"] = "aprovado"
            conteudo["comentario"] = "ok pelo teste"
            conteudo["decidido_por"] = "test_user"
            conteudo["decidido_em"] = "2026-07-08T14:30:00"
            arquivos[0].write_text(
                json.dumps(conteudo, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )

        thread = threading.Thread(target=simular_decisao_externa, daemon=True)
        thread.start()

        resultado = hitl.solicitar_aprovacao(pedido)
        thread.join(timeout=2)

        assert resultado.decisao == DecisaoHumana.APROVADO
        assert resultado.comentario == "ok pelo teste"
        assert resultado.decidido_por == "test_user"

    def test_cria_diretorio_automaticamente(self, tmp_path: Path) -> None:
        subdir = tmp_path / "sub" / "approvals"
        hitl = HITLArquivo(
            approvals_dir=subdir,
            polling_interval=0.1,
            polling_timeout=0.3,
        )
        pedido = PedidoAprovacao(
            tipo="script_etl",
            resumo="Revise script",
            detalhes={},
        )
        hitl.solicitar_aprovacao(pedido)
        assert subdir.exists()

    def test_implementa_interface(self) -> None:
        hitl = HITLArquivo()
        assert isinstance(hitl, InterfaceHITL)
