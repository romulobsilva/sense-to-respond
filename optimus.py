"""
Optimus: gera proposicoes priorizadas a partir dos sinais do Dominion.

Tipos de proposicao suportados:
  Legado (dados simulados):
    - ajustar_demanda: desvio de demanda >= 5%
    - ajustar_custo: desvio de custo >= 5%

  Mondelez (ADR-0019):
    - ajustar_plano_sellout: desvio sell-out >= 5%
    - ajustar_plano_sellin: desvio sell-in >= 5%
    - rebalancear_estoque_doi: DOI fora da politica (gap >= 7 dias)
    - questionar_premissa_plano: plano forward diverge da tendencia recente
    - capturar_oportunidade: SO acima do plano + DOI baixo (oportunidade, nao risco)
    - investigar_desvio_persistente: desvio no mesmo sinal por N meses
    - investigar_desvio_canal: SI e SO divergem no mesmo SKU (futuro)

Detector de falso-positivo (DOI):
  Se um sinal doi_fora_politica tem tendencia "melhorando" (campo via
  analise_tendencia), a proposicao de rebalancear e suprimida para evitar
  alertas sobre DOI que ja esta normalizando.

Enriquecimento de causa-raiz (DOI overstock):
  Quando overstock detectado e SO desacelerando (so_ritmo do sinal de
  tendencia), a descricao destaca a desaceleracao como causa-raiz.

Impacto financeiro: sempre deterministico, nunca calculado por LLM.
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING

from state_types import Proposicao, Sinal, TIPOS_DECISAO_MVP

if TYPE_CHECKING:
    from config import DomainThresholds


VALOR_UNITARIO_ESTIMADO = 62.0
TOLERANCIA_IMPACTO = 0.01

LIMIAR_DESVIO_PCT = 5.0
LIMIAR_DOI_GAP_DIAS = 7.0


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


def _estimar_impacto_nr(sinal: Sinal) -> float:
    """
    Estima impacto financeiro usando NR real propagado pela tool.

    Prioriza ``sinal.nr_impacto`` (NR real em USD, calculado pela tool
    parametrizada). Se nao disponivel (== 0), aplica fallback generico:
    abs(desvio_pct/100) * abs(valor_ton).

    ADR-0024: propagar NR real elimina distorcao de priorizacao onde
    SKU barato com alto volume aparecia antes de caro com pouco volume.
    """
    if sinal.nr_impacto > 0:
        return round(sinal.nr_impacto, 2)
    return round(abs(sinal.desvio_pct / 100.0) * abs(sinal.valor), 2)


def _urgencia_de_severidade(severidade: str) -> int:
    """
    Converte severidade em urgencia em horas.
    """
    mapa = {"alta": 48, "media": 120, "baixa": 336}
    return mapa.get(severidade, 168)


def _dim_label(sinal: Sinal) -> str:
    """Gera label com dimensoes do sinal para a descricao."""
    partes: List[str] = []
    if sinal.pais:
        partes.append(sinal.pais)
    if sinal.canal:
        partes.append(sinal.canal)
    if sinal.marca:
        partes.append(sinal.marca)
    if partes:
        return f" ({', '.join(partes)})"
    return ""


def _build_tendencia_index(
    sinais: List[Sinal],
) -> Dict[str, Sinal]:
    """
    Constroi indice de sinais de tendencia por chave (sku, pais, canal).

    Permite consulta rapida ao avaliar se um sinal DOI deve ser suprimido
    como falso-positivo.
    """
    idx: Dict[str, Sinal] = {}
    for s in sinais:
        if s.tipo == "tendencia_temporal":
            chave = f"{s.sku}|{s.pais}|{s.canal}"
            idx[chave] = s
    return idx


def gerar_proposicoes(
    sinais: List[Sinal],
    feedback_validacao: Optional[List[str]] = None,
    feedback_critic: Optional[List[str]] = None,
    thresholds: Optional["DomainThresholds"] = None,
) -> List[Proposicao]:
    """
    Gera proposicoes deterministicas a partir dos sinais.

    Feedback de validador/critic e registrado na descricao para retry.
    ``thresholds`` permite configurar limiares por dominio (ADR-0024).
    """
    proposicoes: List[Proposicao] = []
    contador = 0
    tendencia_idx = _build_tendencia_index(sinais)

    _limiar_desvio = LIMIAR_DESVIO_PCT
    _limiar_doi_gap = LIMIAR_DOI_GAP_DIAS
    if thresholds is not None:
        _limiar_desvio = thresholds.limiar_desvio_pct
        _limiar_doi_gap = thresholds.limiar_doi_gap_media

    for sinal in sinais:

        if sinal.tipo == "desvio_demanda" and abs(sinal.desvio_pct) >= _limiar_desvio:
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

        if sinal.tipo == "desvio_custo" and abs(sinal.desvio_pct) >= _limiar_desvio:
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

        if sinal.tipo == "desvio_sellout" and abs(sinal.desvio_pct) >= _limiar_desvio:
            contador += 1
            impacto = _estimar_impacto_nr(sinal)
            tipo = "ajustar_plano_sellout"
            dims = _dim_label(sinal)
            descricao = (
                f"SKU {sinal.sku}{dims}: sell-out actual "
                f"{sinal.valor:.2f} ton vs plan {sinal.referencia:.2f} ton "
                f"(desvio {sinal.desvio_pct:.1f}%). "
                f"Revisar plano de sell-out."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Ajustar plano sell-out - {sinal.sku}{dims}",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

        if sinal.tipo == "desvio_sellin" and abs(sinal.desvio_pct) >= _limiar_desvio:
            contador += 1
            impacto = _estimar_impacto_nr(sinal)
            tipo = "ajustar_plano_sellin"
            dims = _dim_label(sinal)
            descricao = (
                f"SKU {sinal.sku}{dims}: sell-in actual "
                f"{sinal.valor:.2f} ton vs plan {sinal.referencia:.2f} ton "
                f"(desvio {sinal.desvio_pct:.1f}%). "
                f"Revisar plano de sell-in."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Ajustar plano sell-in - {sinal.sku}{dims}",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

        if sinal.tipo == "doi_fora_politica":
            gap_dias = sinal.valor - sinal.referencia
            if abs(gap_dias) >= _limiar_doi_gap:
                chave_tend = f"{sinal.sku}|{sinal.pais}|{sinal.canal}"
                tend = tendencia_idx.get(chave_tend)
                if tend is not None and tend.tendencia == "melhorando" and gap_dias > 0:
                    continue
                contador += 1
                impacto = _estimar_impacto_nr(sinal)
                tipo = "rebalancear_estoque_doi"
                dims = _dim_label(sinal)
                if gap_dias > 0:
                    if tend is not None and tend.so_ritmo == "desacelerando":
                        acao = (
                            f"CAUSA-RAIZ: SO desacelerando "
                            f"({tend.so_aceleracao_pct:+.1f}pp entre semanas recentes vs anteriores). "
                            f"Segurar sell-in e investigar queda de sell-out."
                        )
                    elif tend is not None and tend.tendencia == "piorando":
                        acao = "SEGURAR sell-in imediatamente; DOI piorando."
                    else:
                        acao = "Reduzir sell-in ou acelerar sell-out para drenar estoque."
                else:
                    acao = "AUMENTAR sell-in para evitar ruptura de estoque."
                descricao = (
                    f"SKU {sinal.sku}{dims}: DOI actual "
                    f"{sinal.valor:.0f}d vs target {sinal.referencia:.0f}d "
                    f"(gap {gap_dias:+.0f}d). {acao}"
                )
                proposicoes.append(Proposicao(
                    proposicao_id=f"P{contador}",
                    tipo=tipo,
                    titulo=f"Rebalancear estoque (DOI) - {sinal.sku}{dims}",
                    descricao=descricao,
                    impacto_financeiro=impacto,
                    impacto_calculado=impacto,
                    urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                    skus=[sinal.sku],
                    evidencias=[sinal.sinal_id],
                ))

        if sinal.tipo == "premissa_forward_furada":
            contador += 1
            impacto = _estimar_impacto_nr(sinal)
            tipo = "questionar_premissa_plano"
            dims = _dim_label(sinal)
            risco = sinal.risco_forward
            if risco == "ruptura":
                acao = (
                    "RISCO DE RUPTURA: DOI baixo e SO acima do plano, "
                    "mas plano forward nao aumenta SI. Subir SI/producao."
                )
            elif risco == "overstock":
                acao = (
                    "RISCO DE OVERSTOCK: DOI alto e plano forward "
                    "ainda preve SI elevado. Segurar sell-in."
                )
            else:
                acao = (
                    "PREMISSA FURADA: plano forward diverge da tendencia "
                    f"recente em {sinal.desvio_pct:+.1f}%. Revisar premissas."
                )
            descricao = (
                f"SKU {sinal.sku}{dims}: DOI atual "
                f"{sinal.valor:.0f}d (plan forward {sinal.referencia:.0f}d). "
                f"{acao}"
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Questionar premissa plano - {sinal.sku}{dims}",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

        if sinal.tipo == "forward_oportunidade":
            contador += 1
            impacto = _estimar_impacto_nr(sinal)
            tipo = "capturar_oportunidade"
            dims = _dim_label(sinal)
            descricao = (
                f"OPORTUNIDADE: SKU {sinal.sku}{dims} -- SO acima do plano "
                f"({sinal.desvio_pct:+.1f}%), DOI {sinal.valor:.0f}d "
                f"(saudavel). Plano forward subdimensionado: aumentar "
                f"sell-in e realocar estoque para capturar demanda."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Capturar oportunidade - {sinal.sku}{dims}",
                descricao=descricao,
                impacto_financeiro=impacto,
                impacto_calculado=impacto,
                urgencia_horas=_urgencia_de_severidade(sinal.severidade),
                skus=[sinal.sku],
                evidencias=[sinal.sinal_id],
            ))

        if sinal.tipo == "desvio_persistente":
            contador += 1
            impacto = _estimar_impacto_nr(sinal)
            tipo = "investigar_desvio_persistente"
            dims = _dim_label(sinal)
            direcao_txt = "acima" if sinal.media_desvio_persistente_pct > 0 else "abaixo"
            descricao = (
                f"DESVIO PERSISTENTE: SKU {sinal.sku}{dims} -- SO "
                f"{direcao_txt} do plano por {sinal.meses_desvio_persistente} "
                f"meses consecutivos (media {sinal.media_desvio_persistente_pct:+.1f}%). "
                f"Indica problema estrutural no plano, nao pontual. "
                f"Revisar premissas de baseline."
            )
            proposicoes.append(Proposicao(
                proposicao_id=f"P{contador}",
                tipo=tipo,
                titulo=f"Investigar desvio persistente - {sinal.sku}{dims}",
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
