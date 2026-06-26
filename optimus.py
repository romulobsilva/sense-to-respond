"""
Optimus: gera proposicoes priorizadas a partir dos sinais do Dominion.
"""

from typing import Any, Dict, List, Optional

from state_types import Proposicao, Sinal, TIPOS_DECISAO_MVP


VALOR_UNITARIO_ESTIMADO = 62.0
TOLERANCIA_IMPACTO = 0.01


def _estimar_impacto_demanda(sinal: Sinal) -> float:
    """
    Estima impacto financeiro de um desvio de demanda (deterministico).
    """
    delta_unidades = abs(sinal.valor - sinal.referencia)
    return round(delta_unidades * VALOR_UNITARIO_ESTIMADO, 2)


def _estimar_impacto_custo(sinal: Sinal) -> float:
    """
    Estima impacto financeiro de um desvio de custo (deterministico).
    """
    return round(abs(sinal.valor - sinal.referencia), 2)


def _urgencia_de_severidade(severidade: str) -> int:
    """
    Converte severidade em urgencia em horas.
    """
    mapa = {"alta": 48, "media": 120, "baixa": 336}
    return mapa.get(severidade, 168)


def gerar_proposicoes(
    sinais: List[Sinal],
    feedback_validacao: Optional[List[str]] = None,
    feedback_critic: Optional[List[str]] = None,
) -> List[Proposicao]:
    """
    Gera proposicoes deterministicas a partir dos sinais.
    Feedback de validador/critic e registrado na descricao para retry.
    """
    proposicoes: List[Proposicao] = []
    contador = 0

    for sinal in sinais:
        if sinal.tipo == "desvio_demanda" and abs(sinal.desvio_pct) >= 5.0:
            contador += 1
            impacto = _estimar_impacto_demanda(sinal)
            tipo = "ajustar_demanda"
            if tipo not in TIPOS_DECISAO_MVP:
                continue
            descricao = (
                f"SKU {sinal.sku}: demanda modelada {sinal.valor:.0f} vs "
                f"real {sinal.referencia:.0f} (desvio {sinal.desvio_pct:.1f}%). "
                f"Revisar alocacao ou previsao."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Ajustar demanda modelada - {sinal.sku}",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

        if sinal.tipo == "desvio_custo" and abs(sinal.desvio_pct) >= 5.0:
            contador += 1
            impacto = _estimar_impacto_custo(sinal)
            tipo = "ajustar_custo"
            descricao = (
                f"Custo modelado R$ {sinal.valor:.2f} vs DRE R$ "
                f"{sinal.referencia:.2f} (desvio {sinal.desvio_pct:.1f}%). "
                f"Revisar parametros de frete ou modelagem."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo="Ajustar custo modelado vs DRE",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

    if feedback_validacao:
        for prop in proposicoes:
            erros_txt = "; ".join(feedback_validacao)
            prop.descricao = f"{prop.descricao} [retry validador: {erros_txt}]"

    if feedback_critic:
        for prop in proposicoes:
            prob_txt = "; ".join(feedback_critic)
            prop.descricao = f"{prop.descricao} [retry critic: {prob_txt}]"

    proposicoes.sort(key=lambda p: (-p.impacto_financeiro, p.urgencia_horas))
    for idx, prop in enumerate(proposicoes, start=1):
        prop.proposicao_id = f"P{idx}"

    return proposicoes


def proposicoes_para_state(proposicoes: List[Proposicao]) -> List[Dict[str, Any]]:
    """
    Serializa proposicoes para gravacao no state.
    """
    return [p.para_dict() for p in proposicoes]
