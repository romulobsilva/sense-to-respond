"""
Human-in-the-Loop: protocolo abstrato e implementacoes plugaveis.

Cada momento de decisao humana no pipeline usa InterfaceHITL.
O Nexus recebe a implementacao como dependencia injetada.

Implementacoes disponiveis:
  - HITLTerminal: input() no terminal (desenvolvimento)
  - HITLAutoApprove: aprova tudo (testes automatizados)
  - HITLStreamlit: JSON em approvals/ (demo EY, ADR-0023)

Refs: ADR-0022, ADR-0023
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class DecisaoHumana(Enum):
    """Decisoes possiveis do humano."""

    APROVADO = "aprovado"
    REJEITADO = "rejeitado"
    EDITADO = "editado"
    POSTERGADO = "postergado"


TIPOS_PEDIDO_VALIDOS = frozenset({
    "mapeamento_semantico",
    "script_etl",
    "fila_nexus",
    "incompatibilidade_dados",
})


@dataclass
class PedidoAprovacao:
    """
    Pedido de aprovacao enviado ao humano.

    Atributos:
        tipo: tipo do pedido (deve estar em TIPOS_PEDIDO_VALIDOS)
        resumo: descricao curta legivel do que precisa ser decidido
        detalhes: payload com dados especificos do pedido
        decisao: preenchido pelo humano apos decidir
        comentario: justificativa opcional do humano
        decidido_por: identificacao do humano (opcional)
        decidido_em: timestamp ISO da decisao (opcional)
    """

    tipo: str
    resumo: str
    detalhes: Dict[str, object]
    decisao: Optional[DecisaoHumana] = None
    comentario: Optional[str] = None
    decidido_por: Optional[str] = None
    decidido_em: Optional[str] = None

    def __post_init__(self) -> None:
        """Valida tipo do pedido."""
        if self.tipo not in TIPOS_PEDIDO_VALIDOS:
            raise ValueError(
                f"Tipo de pedido invalido: {self.tipo}. "
                f"Validos: {', '.join(sorted(TIPOS_PEDIDO_VALIDOS))}"
            )

    def para_dict(self) -> Dict[str, object]:
        """Serializa para JSON auditavel."""
        return {
            "tipo": self.tipo,
            "resumo": self.resumo,
            "detalhes": self.detalhes,
            "decisao": self.decisao.value if self.decisao else None,
            "comentario": self.comentario,
            "decidido_por": self.decidido_por,
            "decidido_em": self.decidido_em,
        }

    @staticmethod
    def from_dict(dados: Dict[str, object]) -> "PedidoAprovacao":
        """Reconstroi a partir de dicionario."""
        decisao_raw = dados.get("decisao")
        decisao: Optional[DecisaoHumana] = None
        if isinstance(decisao_raw, str) and decisao_raw:
            decisao = DecisaoHumana(decisao_raw)

        tipo = dados.get("tipo", "")
        if not isinstance(tipo, str):
            tipo = str(tipo)

        resumo = dados.get("resumo", "")
        if not isinstance(resumo, str):
            resumo = str(resumo)

        detalhes = dados.get("detalhes", {})
        if not isinstance(detalhes, dict):
            detalhes = {}

        comentario = dados.get("comentario")
        if comentario is not None and not isinstance(comentario, str):
            comentario = str(comentario)

        decidido_por = dados.get("decidido_por")
        if decidido_por is not None and not isinstance(decidido_por, str):
            decidido_por = str(decidido_por)

        decidido_em = dados.get("decidido_em")
        if decidido_em is not None and not isinstance(decidido_em, str):
            decidido_em = str(decidido_em)

        return PedidoAprovacao(
            tipo=tipo,
            resumo=resumo,
            detalhes=detalhes,
            decisao=decisao,
            comentario=comentario,
            decidido_por=decidido_por,
            decidido_em=decidido_em,
        )


class InterfaceHITL(ABC):
    """
    Protocolo abstrato para Human-in-the-Loop.

    Toda implementacao deve fornecer solicitar_aprovacao().
    O Nexus chama esse metodo quando precisa de uma decisao humana.
    """

    @abstractmethod
    def solicitar_aprovacao(self, pedido: PedidoAprovacao) -> PedidoAprovacao:
        """
        Envia pedido ao humano e retorna com decisao preenchida.

        Args:
            pedido: PedidoAprovacao com tipo, resumo e detalhes.

        Returns:
            O mesmo PedidoAprovacao com decisao, comentario e timestamp.
        """


class HITLTerminal(InterfaceHITL):
    """
    HITL via terminal (input). Para desenvolvimento local.

    Exibe o pedido formatado e aguarda input do usuario.
    """

    def solicitar_aprovacao(self, pedido: PedidoAprovacao) -> PedidoAprovacao:
        """Solicita aprovacao via terminal."""
        print(f"\n{'=' * 60}")
        print(f"  APROVACAO NECESSARIA: {pedido.tipo}")
        print(f"{'=' * 60}")
        print(f"  {pedido.resumo}\n")

        if isinstance(pedido.detalhes, dict):
            for chave, valor in pedido.detalhes.items():
                valor_str = str(valor)
                if len(valor_str) > 200:
                    valor_str = f"{valor_str[:200]}..."
                print(f"  {chave}: {valor_str}")

        print(f"\n  [S] Aprovar  [N] Rejeitar  [E] Editar  [P] Postergar")
        escolha = input("  Sua escolha: ").strip().upper()

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

        if escolha == "S":
            pedido.decisao = DecisaoHumana.APROVADO
        elif escolha == "E":
            pedido.decisao = DecisaoHumana.EDITADO
            pedido.comentario = input("  Comentario/correcao: ").strip()
        elif escolha == "P":
            pedido.decisao = DecisaoHumana.POSTERGADO
            pedido.comentario = input("  Motivo (opcional): ").strip() or None
        else:
            pedido.decisao = DecisaoHumana.REJEITADO
            pedido.comentario = input("  Motivo: ").strip() or None

        pedido.decidido_por = "terminal_user"
        pedido.decidido_em = timestamp

        return pedido


class HITLAutoApprove(InterfaceHITL):
    """
    HITL que aprova tudo automaticamente. Para testes pytest.

    Registra as aprovacoes em uma lista interna para verificacao.
    """

    def __init__(self) -> None:
        self.historico: List[PedidoAprovacao] = []

    def solicitar_aprovacao(self, pedido: PedidoAprovacao) -> PedidoAprovacao:
        """Aprova automaticamente e registra no historico."""
        pedido.decisao = DecisaoHumana.APROVADO
        pedido.comentario = "auto-aprovado (teste)"
        pedido.decidido_por = "HITLAutoApprove"
        pedido.decidido_em = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.historico.append(pedido)
        return pedido


APPROVALS_DIR_DEFAULT = Path("approvals")
POLLING_INTERVAL_DEFAULT = 1.0
POLLING_TIMEOUT_DEFAULT = 300.0


class HITLArquivo(InterfaceHITL):
    """
    HITL via arquivo JSON. O pipeline gera um JSON pendente,
    faz polling ate o campo 'decisao' ser preenchido.

    Usado como base para HITLStreamlit (ADR-0023).
    """

    def __init__(
        self,
        approvals_dir: Path = APPROVALS_DIR_DEFAULT,
        polling_interval: float = POLLING_INTERVAL_DEFAULT,
        polling_timeout: float = POLLING_TIMEOUT_DEFAULT,
    ) -> None:
        self.approvals_dir = approvals_dir
        self.polling_interval = polling_interval
        self.polling_timeout = polling_timeout

    def solicitar_aprovacao(self, pedido: PedidoAprovacao) -> PedidoAprovacao:
        """Gera JSON pendente e aguarda decisao via polling."""
        self.approvals_dir.mkdir(parents=True, exist_ok=True)

        timestamp_id = int(time.time())
        arquivo = self.approvals_dir / f"{pedido.tipo}_{timestamp_id}.json"

        payload = {
            "id": f"hitl_{pedido.tipo}_{timestamp_id}",
            "tipo": pedido.tipo,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "status": "pendente",
            "resumo": pedido.resumo,
            "dados": pedido.detalhes,
            "decisao": None,
            "comentario": None,
            "decidido_por": None,
            "decidido_em": None,
        }

        arquivo.write_text(
            json.dumps(payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

        inicio = time.time()
        while True:
            elapsed = time.time() - inicio
            if elapsed >= self.polling_timeout:
                pedido.decisao = DecisaoHumana.POSTERGADO
                pedido.comentario = "timeout atingido"
                pedido.decidido_em = time.strftime("%Y-%m-%dT%H:%M:%S")
                payload["status"] = "timeout"
                payload["decisao"] = pedido.decisao.value
                payload["comentario"] = pedido.comentario
                payload["decidido_em"] = pedido.decidido_em
                arquivo.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=True),
                    encoding="utf-8",
                )
                return pedido

            conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
            decisao_raw = conteudo.get("decisao")

            if decisao_raw is not None and isinstance(decisao_raw, str):
                try:
                    pedido.decisao = DecisaoHumana(decisao_raw)
                except ValueError:
                    pedido.decisao = DecisaoHumana.REJEITADO

                comentario = conteudo.get("comentario")
                pedido.comentario = str(comentario) if comentario else None

                decidido_por = conteudo.get("decidido_por")
                pedido.decidido_por = str(decidido_por) if decidido_por else None

                decidido_em = conteudo.get("decidido_em")
                pedido.decidido_em = str(decidido_em) if decidido_em else None

                return pedido

            time.sleep(self.polling_interval)
