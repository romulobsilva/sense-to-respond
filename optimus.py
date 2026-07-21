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
    - capturar_oportunidade: SO acima + plano curto (DOI saudavel, ou dual
      com ruptura quando DOI critico)
    - investigar_desvio_persistente: desvio no mesmo sinal por N meses
    - investigar_desvio_canal: SI e SO divergem no mesmo SKU (futuro)

Detector de falso-positivo (DOI):
  Se um sinal doi_fora_politica tem tendencia "melhorando", a proposicao
  de rebalancear e suprimida. Se tendencia "estavel" e |SO desvio| < limiar,
  tambem e suprimida (overstock historico sem evidencia ativa).

Dual framing (forward):
  Ruptura primaria permanece; se plano subdimensionado, Optimus tambem
  emite capturar_oportunidade (DOI critico + demanda acima do plano).

Enriquecimento de causa-raiz (DOI overstock):
  Quando overstock detectado e SO desacelerando (so_ritmo do sinal de
  tendencia), a descricao destaca a desaceleracao como causa-raiz.

Impacto financeiro: sempre deterministico, nunca calculado por LLM.
"""

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from state_types import Proposicao, Sinal, TIPOS_DECISAO_MVP

if TYPE_CHECKING:
    from config import DomainThresholds


VALOR_UNITARIO_ESTIMADO = 62.0
TOLERANCIA_IMPACTO = 0.01

LIMIAR_DESVIO_PCT = 5.0
LIMIAR_DOI_GAP_DIAS = 7.0


def _peso_prioridade(
    tipo: str,
    thresholds: Optional["DomainThresholds"] = None,
) -> float:
    """
    Multiplicador de prioridade por tipo.

    Fonte de verdade: DomainThresholds (config/.env). Sem thresholds,
    usa defaults do dataclass.
    """
    if thresholds is not None:
        return thresholds.peso_tipo(tipo)
    from config import DomainThresholds

    return DomainThresholds().peso_tipo(tipo)


def _impacto_priorizado(
    impacto: float,
    tipo: str,
    thresholds: Optional["DomainThresholds"] = None,
) -> float:
    """
    Impacto usado na ordenacao: impacto financeiro * peso do tipo.

    Mantem impacto_financeiro/impacto_calculado iguais ao valor bruto
    (invariante ADR-0002); o peso so afeta a chave de sort.
    Usado por Optimus e pela fila Nexus (mesmo criterio).
    """
    return round(impacto * _peso_prioridade(tipo, thresholds), 2)


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

    Prioriza ``sinal.nr_impacto`` quando > 0 (NR real em USD no caminho
    CSV/tool, ou proxy de volume em toneladas no caminho PBI PoC).
    Se nao disponivel (== 0), aplica fallback generico:
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
                if tend is not None and gap_dias > 0:
                    # Overstock: suprimir falso-positivo historico / normalizando
                    if tend.tendencia == "melhorando":
                        continue
                    if (
                        tend.tendencia == "estavel"
                        and abs(tend.desvio_pct) < _limiar_desvio
                    ):
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
                # Caminho PBI PoC: target e DOI atual +/- limiar (nao DOI_Policy).
                if sinal.sinal_id.startswith("SIG-PBI-DOI"):
                    alvo_txt = (
                        f"target PoC {sinal.referencia:.0f}d "
                        f"(DOI atual +/- limiar_doi_gap_media; nao DOI_Policy)"
                    )
                else:
                    alvo_txt = f"target {sinal.referencia:.0f}d"
                descricao = (
                    f"SKU {sinal.sku}{dims}: DOI atual "
                    f"{sinal.valor:.0f}d vs {alvo_txt} "
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
            _doi_rupt = 15.0
            if thresholds is not None:
                _doi_rupt = float(thresholds.doi_ruptura_dias)
            if sinal.valor > 0 and sinal.valor < _doi_rupt:
                descricao = (
                    f"OPORTUNIDADE (dual com ruptura): SKU {sinal.sku}{dims} "
                    f"-- SO acima do plano ({sinal.desvio_pct:+.1f}%), "
                    f"DOI {sinal.valor:.0f}d critico. Plano forward "
                    f"subdimensionado: subir SI/producao para capturar "
                    f"demanda e evitar falta."
                )
            else:
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
            impacto = _estimar_impacto_nr(sinal)
            media_abs = abs(sinal.media_desvio_persistente_pct)
            lim_imp = 100.0
            lim_dev = 5.0
            if thresholds is not None:
                lim_imp = float(thresholds.limiar_persistente_impacto)
                lim_dev = float(thresholds.limiar_persistente_desvio_pct)
            # Ruido: impacto baixo E desvio medio baixo -- nao enfileirar
            if impacto < lim_imp and media_abs < lim_dev:
                continue
            contador += 1
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

    proposicoes.sort(
        key=lambda p: (
            -_impacto_priorizado(p.impacto_financeiro, p.tipo, thresholds),
            p.urgencia_horas,
        )
    )
    for idx, prop in enumerate(proposicoes, start=1):
        prop.proposicao_id = f"P{idx}"

    return proposicoes


def proposicoes_para_state(proposicoes: List[Proposicao]) -> List[Dict[str, Any]]:
    """
    Serializa proposicoes para gravacao no state.
    """
    return [p.para_dict() for p in proposicoes]


# Tipos do quadro executivo estratificado (script do analista). Genericos.
TIPOS_DOI_EXECUTIVO = frozenset({
    "rebalancear_estoque_doi",
})
TIPOS_FORWARD_EXECUTIVO = frozenset({
    "questionar_premissa_plano",
})
TIPOS_OPORTUNIDADE_EXECUTIVO = frozenset({
    "capturar_oportunidade",
})


def _polaridade_doi(proposicao: Proposicao) -> str:
    """
    Classifica DOI como ruptura (estoque baixo) ou overstock.

    Usa texto deterministico gerado pelo Optimus (sem SKU hardcoded).
    """
    desc = proposicao.descricao.upper()
    if "AUMENTAR SELL-IN" in desc or "RUPTURA DE ESTOQUE" in desc:
        return "ruptura"
    return "overstock"


def _polaridade_forward(proposicao: Proposicao) -> str:
    """Classifica forward como ruptura, overstock ou gap de plano."""
    desc = proposicao.descricao.upper()
    if "RUPTURA" in desc:
        return "ruptura"
    if "OVERSTOCK" in desc:
        return "overstock"
    return "gap"


def _repartir_n(total: int) -> Tuple[int, int]:
    """Reparte N em duas cotas (ceil/floor) para diversidade de polaridade."""
    if total < 1:
        return 0, 0
    return (total + 1) // 2, total // 2


def _top_diversificado(
    candidatos: List[Proposicao],
    n_total: int,
    polaridade_fn,
    chave_a: str,
    chave_b: str,
) -> Tuple[List[Proposicao], Dict[str, int]]:
    """
    Seleciona top N garantindo cota para duas polaridades principais.

    Itens residuais (ex.: gap) preenchem sobras.
    """
    n_a, n_b = _repartir_n(n_total)
    grupo_a = [p for p in candidatos if polaridade_fn(p) == chave_a]
    grupo_b = [p for p in candidatos if polaridade_fn(p) == chave_b]
    outros = [
        p for p in candidatos
        if polaridade_fn(p) not in (chave_a, chave_b)
    ]
    escolhidos: List[Proposicao] = []
    escolhidos.extend(grupo_a[:n_a])
    escolhidos.extend(grupo_b[:n_b])
    if len(escolhidos) < n_total:
        resto = [
            p for p in (grupo_a[n_a:] + grupo_b[n_b:] + outros)
            if p not in escolhidos
        ]
        escolhidos.extend(resto[: n_total - len(escolhidos)])
    selecionados = escolhidos[:n_total]
    # n_* = contagem real no top; cota_* = alvo de diversidade (pode nao
    # ser atingida se faltar candidatos de uma polaridade).
    meta = {
        f"cota_{chave_a}": n_a,
        f"cota_{chave_b}": n_b,
        f"n_{chave_a}": sum(
            1 for p in selecionados if polaridade_fn(p) == chave_a
        ),
        f"n_{chave_b}": sum(
            1 for p in selecionados if polaridade_fn(p) == chave_b
        ),
        f"candidatos_{chave_a}": len(grupo_a),
        f"candidatos_{chave_b}": len(grupo_b),
    }
    return selecionados, meta


def montar_resumo_executivo(
    proposicoes: List[Proposicao],
    thresholds: Optional["DomainThresholds"] = None,
) -> Dict[str, Any]:
    """
    Monta top N por topico (DOI, forward, oportunidades) por I_prio.

    Deterministico e estratificado: NR alto de DOI nao remove forward.
    Dentro de DOI/forward, reparte N entre ruptura e overstock.
    """
    n_doi = 5
    n_fwd = 5
    n_opps = 5
    if thresholds is not None:
        n_doi = int(thresholds.top_n_doi)
        n_fwd = int(thresholds.top_n_forward)
        n_opps = int(thresholds.top_n_oportunidades)

    def _key(p: Proposicao) -> Tuple[float, int]:
        return (
            -_impacto_priorizado(p.impacto_financeiro, p.tipo, thresholds),
            p.urgencia_horas,
        )

    doi = sorted(
        [p for p in proposicoes if p.tipo in TIPOS_DOI_EXECUTIVO],
        key=_key,
    )
    forward = sorted(
        [p for p in proposicoes if p.tipo in TIPOS_FORWARD_EXECUTIVO],
        key=_key,
    )
    opps = sorted(
        [p for p in proposicoes if p.tipo in TIPOS_OPORTUNIDADE_EXECUTIVO],
        key=_key,
    )

    doi_sel, doi_meta = _top_diversificado(
        doi, n_doi, _polaridade_doi, "ruptura", "overstock"
    )
    fwd_sel, fwd_meta = _top_diversificado(
        forward, n_fwd, _polaridade_forward, "ruptura", "overstock"
    )

    def _item(p: Proposicao) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "proposicao_id": p.proposicao_id,
            "tipo": p.tipo,
            "titulo": p.titulo,
            "skus": list(p.skus),
            "impacto_financeiro": p.impacto_financeiro,
            "impacto_priorizado": _impacto_priorizado(
                p.impacto_financeiro, p.tipo, thresholds
            ),
            "urgencia_horas": p.urgencia_horas,
            "descricao": p.descricao,
        }
        if p.tipo in TIPOS_DOI_EXECUTIVO:
            item["polaridade"] = _polaridade_doi(p)
        elif p.tipo in TIPOS_FORWARD_EXECUTIVO:
            item["polaridade"] = _polaridade_forward(p)
        return item

    return {
        "top_doi": [_item(p) for p in doi_sel],
        "top_forward": [_item(p) for p in fwd_sel],
        "top_oportunidades": [_item(p) for p in opps[:n_opps]],
        "n_doi": n_doi,
        "n_forward": n_fwd,
        "n_oportunidades": n_opps,
        "total_candidatos_doi": len(doi),
        "total_candidatos_forward": len(forward),
        "total_candidatos_oportunidade": len(opps),
        "diversidade_doi": doi_meta,
        "diversidade_forward": fwd_meta,
    }


def formatar_resumo_executivo_texto(resumo: Dict[str, Any]) -> str:
    """Formata resumo executivo estratificado para terminal / contexto LLM."""
    linhas: List[str] = [
        (
            f"=== RESUMO EXECUTIVO (top {resumo.get('n_doi', 0)} DOI / "
            f"top {resumo.get('n_forward', 0)} forward / "
            f"top {resumo.get('n_oportunidades', 0)} oportunidades) ==="
        ),
        (
            f"Candidatos: doi={resumo.get('total_candidatos_doi', 0)}, "
            f"forward={resumo.get('total_candidatos_forward', 0)}, "
            f"oportunidades={resumo.get('total_candidatos_oportunidade', 0)}"
        ),
    ]
    div_d = resumo.get("diversidade_doi") or {}
    div_f = resumo.get("diversidade_forward") or {}
    if isinstance(div_d, dict) and div_d:
        linhas.append(
            f"Diversidade DOI: no top ruptura={div_d.get('n_ruptura', 0)} "
            f"overstock={div_d.get('n_overstock', 0)} "
            f"(cota {div_d.get('cota_ruptura', div_d.get('n_ruptura', 0))}/"
            f"{div_d.get('cota_overstock', div_d.get('n_overstock', 0))}; "
            f"cand {div_d.get('candidatos_ruptura', 0)}/"
            f"{div_d.get('candidatos_overstock', 0)})"
        )
    if isinstance(div_f, dict) and div_f:
        linhas.append(
            f"Diversidade forward: no top ruptura={div_f.get('n_ruptura', 0)} "
            f"overstock={div_f.get('n_overstock', 0)} "
            f"(cota {div_f.get('cota_ruptura', div_f.get('n_ruptura', 0))}/"
            f"{div_f.get('cota_overstock', div_f.get('n_overstock', 0))}; "
            f"cand {div_f.get('candidatos_ruptura', 0)}/"
            f"{div_f.get('candidatos_overstock', 0)})"
        )

    def _secao(titulo: str, chave: str) -> None:
        linhas.append("")
        linhas.append(titulo)
        itens = resumo.get(chave, [])
        if not isinstance(itens, list) or not itens:
            linhas.append("(nenhum)")
            return
        for i, item in enumerate(itens, start=1):
            if not isinstance(item, dict):
                continue
            pol = item.get("polaridade")
            pol_txt = f" [{pol}]" if pol else ""
            linhas.append(
                f"{i}. [{item.get('proposicao_id', '')}] {item.get('tipo', '')}{pol_txt} | "
                f"{item.get('titulo', '')} | impacto "
                f"{float(item.get('impacto_financeiro', 0)):.2f} "
                f"(I_prio={float(item.get('impacto_priorizado', 0)):.2f})"
            )

    _secao("-- DOI / ESTOQUE --", "top_doi")
    _secao("-- FORWARD / PLANO --", "top_forward")
    _secao("-- OPORTUNIDADES --", "top_oportunidades")
    return "\n".join(linhas)
