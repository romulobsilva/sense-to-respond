"""
Guardrails de entrada e saida do Nexus (MVP).
"""

import re
from dataclasses import dataclass
from typing import List, Optional

from state_types import ItemFilaNexus, Proposicao, serializar_proposicoes_para_llm

DISCLAIMER_OBRIGATORIO = (
    "AVISO: Proposicoes geradas por IA com base em analises deterministicas. "
    "Revisao humana obrigatoria antes de qualquer acao operacional."
)

PADRAO_INJECAO = re.compile(
    r"(ignore\s+(all\s+)?previous|system\s+prompt|jailbreak|"
    r"<\s*script|drop\s+table)",
    re.IGNORECASE,
)

PERGUNTA_MIN_CHARS = 10
PERGUNTA_MAX_CHARS = 2000


@dataclass
class ResultadoGuardrail:
    """Resultado de uma verificacao de guardrail."""

    ok: bool
    detalhe: str


def verificar_input(pergunta: str) -> ResultadoGuardrail:
    """
    Input guardrail: valida pergunta antes de qualquer chamada LLM.
    """
    texto = (pergunta or "").strip()
    if len(texto) < PERGUNTA_MIN_CHARS:
        return ResultadoGuardrail(
            ok=False,
            detalhe=f"Pergunta muito curta (minimo {PERGUNTA_MIN_CHARS} caracteres).",
        )
    if len(texto) > PERGUNTA_MAX_CHARS:
        return ResultadoGuardrail(
            ok=False,
            detalhe=f"Pergunta muito longa (maximo {PERGUNTA_MAX_CHARS} caracteres).",
        )
    if PADRAO_INJECAO.search(texto):
        return ResultadoGuardrail(
            ok=False,
            detalhe="Bloqueado: possivel injecao de prompt.",
        )
    return ResultadoGuardrail(ok=True, detalhe="permitido")


def aplicar_output_guardrail(
    texto: str,
    proposicoes: List[Proposicao],
    confianca_critic: Optional[float],
    limiar_confianca: float,
) -> str:
    """
    Output guardrail: garante disclaimer, citacoes e flag de confianca.
    """
    partes: List[str] = []

    if confianca_critic is not None and confianca_critic < limiar_confianca:
        partes.append(
            f"[REVISAO OBRIGATORIA] Confianca do auditor: "
            f"{confianca_critic:.2f} (limiar: {limiar_confianca:.2f})"
        )

    partes.append(DISCLAIMER_OBRIGATORIO)
    partes.append("")
    partes.append(texto)

    if proposicoes:
        partes.append("")
        partes.append("=== Citacoes (evidencias deterministicas) ===")
        partes.append(serializar_proposicoes_para_llm(proposicoes))

    return "\n".join(partes)


def montar_fila_com_flags(
    proposicoes: List[Proposicao],
    confianca_critic: Optional[float],
    limiar_confianca: float,
    validacao_ok: bool,
) -> List[ItemFilaNexus]:
    """
    Monta fila Nexus com flag de revisao obrigatoria quando necessario.
    """
    fila: List[ItemFilaNexus] = []
    ordenadas = sorted(
        proposicoes,
        key=lambda p: (-p.impacto_financeiro, p.urgencia_horas),
    )
    for idx, prop in enumerate(ordenadas, start=1):
        motivos: List[str] = []
        revisao = False

        if not validacao_ok:
            revisao = True
            motivos.append("validador deterministico reportou erros")

        if confianca_critic is not None and confianca_critic < limiar_confianca:
            revisao = True
            motivos.append(
                f"confianca do critic abaixo do limiar ({confianca_critic:.2f})"
            )

        if prop.impacto_financeiro > 10000:
            revisao = True
            motivos.append("impacto financeiro alto")

        fila.append(ItemFilaNexus(
            proposicao=prop,
            prioridade=idx,
            revisao_obrigatoria=revisao,
            motivo_revisao="; ".join(motivos) if motivos else "",
        ))
    return fila
