"""
Extracao de sinais estruturados a partir dos resultados do Dominion.

Tipos de sinal suportados:
  - desvio_demanda: sell-out/sell-in vs plan (dados simulados legado)
  - desvio_custo: custo modelado vs DRE (dados simulados legado)
  - desvio_sellout: SO actual vs plan (dados Mondelez, ADR-0019)
  - desvio_sellin: SI actual vs plan (dados Mondelez, ADR-0019)
  - doi_fora_politica: DOI actual vs target (dados Mondelez, ADR-0019)
  - tendencia_temporal: direcao DOI + SO recente vs anterior
  - premissa_forward_furada: plano futuro diverge da tendencia recente

Severidade segue thresholds do S&OE Analyst Questions Script:
  - SO/SI: >10% alta, >5% media, resto baixa
  - DOI: gap >15 dias alta, >7 dias media, resto baixa
"""

from typing import Any, Dict, List

import pandas as pd

from state_types import Sinal


LIMIAR_SEVERIDADE_ALTA = 10.0
LIMIAR_SEVERIDADE_MEDIA = 5.0

LIMIAR_DOI_SEVERIDADE_ALTA = 15.0
LIMIAR_DOI_SEVERIDADE_MEDIA = 7.0


def _classificar_severidade(desvio_pct: float) -> str:
    """
    Classifica severidade com base no desvio percentual absoluto.

    Thresholds: >= 10% alta, >= 5% media, < 5% baixa.
    """
    abs_desvio = abs(desvio_pct)
    if abs_desvio >= LIMIAR_SEVERIDADE_ALTA:
        return "alta"
    if abs_desvio >= LIMIAR_SEVERIDADE_MEDIA:
        return "media"
    return "baixa"


def _classificar_severidade_doi(gap_dias: float) -> str:
    """
    Classifica severidade de DOI com base no gap em dias absoluto.

    Thresholds: >= 15 dias alta, >= 7 dias media, < 7 dias baixa.
    """
    abs_gap = abs(gap_dias)
    if abs_gap >= LIMIAR_DOI_SEVERIDADE_ALTA:
        return "alta"
    if abs_gap >= LIMIAR_DOI_SEVERIDADE_MEDIA:
        return "media"
    return "baixa"


def extrair_sinais_de_resultados(resultados: Dict[str, Any]) -> List[Sinal]:
    """
    Converte resultados deterministicos do Dominion em sinais estruturados.

    Suporta tanto resultados legados (comparacao_demanda, comparacao_custos)
    quanto resultados das tools parametrizadas Mondelez (analise_sellout,
    analise_sellin, analise_doi).
    """
    sinais: List[Sinal] = []
    contador = 0

    if "comparacao_demanda" in resultados:
        df = resultados["comparacao_demanda"]
        if isinstance(df, pd.DataFrame):
            for _, linha in df.iterrows():
                sku_val = linha.get("sku", "")
                sku = str(sku_val) if sku_val is not None else ""
                demanda_real = float(linha.get("demanda_real", 0) or 0)
                demanda_modelada = float(linha.get("demanda_modelada", 0) or 0)
                desvio_pct = float(linha.get("delta_demanda_pct", 0) or 0)
                contador += 1
                sinais.append(Sinal(
                    sinal_id=f"SIG-DEM-{contador:03d}",
                    tipo="desvio_demanda",
                    sku=sku,
                    canal="geral",
                    metrica="demanda",
                    valor=demanda_modelada,
                    referencia=demanda_real,
                    desvio_pct=desvio_pct,
                    severidade=_classificar_severidade(desvio_pct),
                ))

    if "comparacao_custos" in resultados:
        custos = resultados["comparacao_custos"]
        if isinstance(custos, dict):
            custo_modelado = float(custos.get("custo_modelado_total", 0) or 0)
            custo_dre = float(custos.get("custo_dre", 0) or 0)
            desvio_pct = float(custos.get("delta_pct", 0) or 0)
            contador += 1
            sinais.append(Sinal(
                sinal_id=f"SIG-CUS-{contador:03d}",
                tipo="desvio_custo",
                sku="TOTAL",
                canal="geral",
                metrica="custo_frete",
                valor=custo_modelado,
                referencia=custo_dre,
                desvio_pct=desvio_pct,
                severidade=_classificar_severidade(desvio_pct),
            ))

    if "analise_sellout" in resultados:
        analise = resultados["analise_sellout"]
        if isinstance(analise, dict):
            desvios = analise.get("desvios", [])
            if isinstance(desvios, list):
                for d in desvios:
                    if not isinstance(d, dict):
                        continue
                    desvio_pct = float(d.get("desvio_pct", 0))
                    contador += 1
                    sinais.append(Sinal(
                        sinal_id=f"SIG-SO-{contador:03d}",
                        tipo="desvio_sellout",
                        sku=str(d.get("sku", "")),
                        canal=str(d.get("canal", "")),
                        metrica="sellout_ton",
                        valor=float(d.get("actual_ton", 0)),
                        referencia=float(d.get("plan_ton", 0)),
                        desvio_pct=desvio_pct,
                        severidade=_classificar_severidade(desvio_pct),
                        pais=str(d.get("pais", "")),
                        categoria=str(d.get("categoria", "")),
                        marca=str(d.get("marca", "")),
                    ))

    if "analise_sellin" in resultados:
        analise = resultados["analise_sellin"]
        if isinstance(analise, dict):
            desvios = analise.get("desvios", [])
            if isinstance(desvios, list):
                for d in desvios:
                    if not isinstance(d, dict):
                        continue
                    desvio_pct = float(d.get("desvio_pct", 0))
                    contador += 1
                    sinais.append(Sinal(
                        sinal_id=f"SIG-SI-{contador:03d}",
                        tipo="desvio_sellin",
                        sku=str(d.get("sku", "")),
                        canal=str(d.get("canal", "")),
                        metrica="sellin_ton",
                        valor=float(d.get("actual_ton", 0)),
                        referencia=float(d.get("plan_ton", 0)),
                        desvio_pct=desvio_pct,
                        severidade=_classificar_severidade(desvio_pct),
                        pais=str(d.get("pais", "")),
                        categoria=str(d.get("categoria", "")),
                        marca=str(d.get("marca", "")),
                    ))

    if "analise_doi" in resultados:
        analise = resultados["analise_doi"]
        if isinstance(analise, dict):
            desvios = analise.get("desvios", [])
            if isinstance(desvios, list):
                for d in desvios:
                    if not isinstance(d, dict):
                        continue
                    gap_dias = float(d.get("gap_dias", 0))
                    doi_plan = float(d.get("doi_plan", 0))
                    doi_actual = float(d.get("doi_actual", 0))
                    desvio_pct = 0.0
                    if doi_plan > 0:
                        desvio_pct = round(
                            (gap_dias / doi_plan) * 100.0, 2
                        )
                    contador += 1
                    sinais.append(Sinal(
                        sinal_id=f"SIG-DOI-{contador:03d}",
                        tipo="doi_fora_politica",
                        sku=str(d.get("sku", "")),
                        canal=str(d.get("canal", "")),
                        metrica="doi_dias",
                        valor=doi_actual,
                        referencia=doi_plan,
                        desvio_pct=desvio_pct,
                        severidade=_classificar_severidade_doi(gap_dias),
                        pais=str(d.get("pais", "")),
                        categoria=str(d.get("categoria", "")),
                        marca=str(d.get("marca", "")),
                    ))

    if "analise_tendencia" in resultados:
        analise = resultados["analise_tendencia"]
        if isinstance(analise, dict):
            tendencias = analise.get("tendencias", [])
            if isinstance(tendencias, list):
                for t in tendencias:
                    if not isinstance(t, dict):
                        continue
                    direcao = str(t.get("direcao_doi", ""))
                    doi_rec = float(t.get("doi_recente", 0))
                    doi_ant = float(t.get("doi_anterior", 0))
                    so_var = float(t.get("so_variacao_pct", 0))
                    sem_consec = int(t.get("semanas_consecutivas", 0))
                    desvio_pct = float(t.get("so_desvio_recente_pct", 0))
                    contador += 1
                    sinais.append(Sinal(
                        sinal_id=f"SIG-TEND-{contador:03d}",
                        tipo="tendencia_temporal",
                        sku=str(t.get("sku", "")),
                        canal=str(t.get("canal", "")),
                        metrica="tendencia_doi_so",
                        valor=doi_rec,
                        referencia=doi_ant,
                        desvio_pct=desvio_pct,
                        severidade=_classificar_severidade(so_var),
                        pais=str(t.get("pais", "")),
                        categoria=str(t.get("categoria", "")),
                        marca=str(t.get("marca", "")),
                        tendencia=direcao,
                        semanas_consecutivas=sem_consec,
                    ))

    if "analise_forward" in resultados:
        analise = resultados["analise_forward"]
        if isinstance(analise, dict):
            alertas = analise.get("alertas_forward", [])
            if isinstance(alertas, list):
                for a in alertas:
                    if not isinstance(a, dict):
                        continue
                    risco = str(a.get("risco_projetado", ""))
                    div_pct = float(a.get("divergencia_forward_pct", 0))
                    doi_atual = float(a.get("doi_atual", 0))
                    doi_plan_fwd = float(a.get("doi_plan_forward", 0))
                    if risco == "ruptura":
                        sev = "alta"
                    elif risco == "overstock":
                        sev = "alta"
                    else:
                        sev = "media"
                    contador += 1
                    sinais.append(Sinal(
                        sinal_id=f"SIG-FWD-{contador:03d}",
                        tipo="premissa_forward_furada",
                        sku=str(a.get("sku", "")),
                        canal=str(a.get("canal", "")),
                        metrica="forward_divergencia",
                        valor=doi_atual,
                        referencia=doi_plan_fwd,
                        desvio_pct=div_pct,
                        severidade=sev,
                        pais=str(a.get("pais", "")),
                        categoria=str(a.get("categoria", "")),
                        marca=str(a.get("marca", "")),
                        risco_forward=risco,
                    ))

    return sinais
