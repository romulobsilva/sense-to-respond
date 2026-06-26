"""
Trilha de auditoria estruturada para sessoes do harness/agente.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
import uuid


def gerar_sessao_id() -> str:
    """
    Gera identificador unico para uma execucao do harness.
    """
    agora = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    sufixo = uuid.uuid4().hex[:8]
    return f"{agora}-{sufixo}"


@dataclass
class EventoAuditoria:
    """Um fato auditavel da execucao."""

    tipo: str
    dados: Dict[str, Any]
    iteracao: Optional[int] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class AuditTrail:
    """Trilha completa de uma sessao."""

    sessao_id: str
    eventos: List[EventoAuditoria] = field(default_factory=list)

    def registrar(
        self,
        tipo: str,
        dados: Dict[str, Any],
        iteracao: Optional[int] = None,
    ) -> None:
        """
        Adiciona um evento a trilha.
        """
        self.eventos.append(
            EventoAuditoria(tipo=tipo, dados=dados, iteracao=iteracao)
        )

    def para_dict(self) -> Dict[str, Any]:
        """
        Serializa a trilha para dict JSON-compativel.
        """
        return {
            "sessao_id": self.sessao_id,
            "eventos": [asdict(evento) for evento in self.eventos],
        }

    def salvar_json(self, caminho: str) -> None:
        """
        Persiste a trilha em arquivo JSON.
        """
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(self.para_dict(), arquivo, indent=2, ensure_ascii=True)
