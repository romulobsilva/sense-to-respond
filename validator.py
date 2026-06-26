"""
Validador deterministico pos-Optimus (sem LLM).
"""

from typing import List, Set

from state_types import Proposicao, ResultadoValidacao, Sinal, TIPOS_DECISAO_MVP

TOLERANCIA_IMPACTO = 0.01


def validar_proposicoes(
    proposicoes: List[Proposicao],
    sinais: List[Sinal],
) -> ResultadoValidacao:
    """
    Valida proposicoes contra sinais do Dominion.
    """
    erros: List[str] = []

    if not proposicoes:
        erros.append("Nenhuma proposicao gerada pelo Optimus.")
        return ResultadoValidacao(ok=False, erros=erros)

    sinal_ids: Set[str] = {s.sinal_id for s in sinais}
    skus_sinais: Set[str] = {s.sku for s in sinais if s.sku != "TOTAL"}

    for prop in proposicoes:
        if prop.tipo not in TIPOS_DECISAO_MVP:
            erros.append(
                f"{prop.proposicao_id}: tipo '{prop.tipo}' fora da whitelist MVP."
            )

        diff_impacto = abs(prop.impacto_financeiro - prop.impacto_calculado)
        if diff_impacto > TOLERANCIA_IMPACTO:
            erros.append(
                f"{prop.proposicao_id}: impacto_financeiro ({prop.impacto_financeiro}) "
                f"diverge de impacto_calculado ({prop.impacto_calculado})."
            )

        for evid in prop.evidencias:
            if evid not in sinal_ids:
                erros.append(
                    f"{prop.proposicao_id}: evidencia '{evid}' nao existe nos sinais."
                )

        for sku in prop.skus:
            if sku != "TOTAL" and sku not in skus_sinais:
                erros.append(
                    f"{prop.proposicao_id}: SKU '{sku}' nao encontrado nos sinais."
                )

        if prop.urgencia_horas <= 0:
            erros.append(
                f"{prop.proposicao_id}: urgencia_horas deve ser positiva."
            )

        if not prop.descricao.strip():
            erros.append(
                f"{prop.proposicao_id}: descricao vazia."
            )

    return ResultadoValidacao(ok=len(erros) == 0, erros=erros)
