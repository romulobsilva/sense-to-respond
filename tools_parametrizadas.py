"""
Tools parametrizadas para analise de dados Mondelez S&OE.

Todas as funcoes recebem (df, mapa) e retornam dict com resultados
deterministicos. Nenhuma usa LLM. Os calculos seguem as regras
do S&OE Analyst Questions Script:

  - SO/SI gap: actual vs plan (absoluto e %)
  - DOI: actual vs policy, gap em dias
  - Alertas cruzados: SO + DOI combinados
  - Impacto: abs(desvio_pct) * NR actual (deterministico)

Ref: ADR-0019, docs/S&OE - Analyst Questions Script.xlsx
"""

from typing import Any, Dict, List, Optional, Set

import pandas as pd


CAPACIDADE_SELLOUT = "sellout"
CAPACIDADE_SELLIN = "sellin"
CAPACIDADE_DOI = "doi"

COLUNAS_SELLOUT = frozenset({
    "SellOut_Plan_Ton", "SellOut_Actual_Ton",
    "SellOut_Plan_NR_USD", "SellOut_Actual_NR_USD",
})

COLUNAS_SELLIN = frozenset({
    "SellIn_Plan_Ton", "SellIn_Actual_Ton",
    "SellIn_Plan_NR_USD", "SellIn_Actual_NR_USD",
})

COLUNAS_DOI = frozenset({
    "DOI_Plan_Days", "DOI_Actual_Days",
})

COLUNAS_DIMENSOES = frozenset({
    "Country", "Channel", "Category", "Brand",
    "SKU_Code", "SKU_Description",
})


def _resolver_coluna(mapa: Dict[str, str], nome_canonico: str) -> Optional[str]:
    """
    Dado um mapa {col_original: col_canonica}, retorna a col_original
    que mapeia para nome_canonico. Se o mapa for identidade (col ja
    canonicada), retorna o proprio nome.
    """
    for col_orig, col_canon in mapa.items():
        if col_canon == nome_canonico:
            return col_orig
    return None


def _col(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    nome_canonico: str,
) -> Optional[str]:
    """
    Retorna o nome da coluna no DataFrame que corresponde ao nome canonico.

    Prioriza a coluna mapeada; se nao existir no mapa, tenta o
    proprio nome canonico direto no DataFrame.
    """
    via_mapa = _resolver_coluna(mapa, nome_canonico)
    if via_mapa is not None and via_mapa in df.columns:
        return via_mapa
    if nome_canonico in df.columns:
        return nome_canonico
    return None


def detectar_capacidades(mapa: Dict[str, str]) -> List[str]:
    """
    Detecta quais analises sao possiveis com base no mapa semantico.

    Verifica se as colunas necessarias para cada tipo de analise
    estao presentes no mapeamento.

    Args:
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Lista de capacidades: ["sellout", "sellin", "doi"] ou subconjunto.
    """
    valores_mapeados: Set[str] = set(mapa.values())

    capacidades: List[str] = []

    if COLUNAS_SELLOUT.issubset(valores_mapeados):
        capacidades.append(CAPACIDADE_SELLOUT)

    if COLUNAS_SELLIN.issubset(valores_mapeados):
        capacidades.append(CAPACIDADE_SELLIN)

    if COLUNAS_DOI.issubset(valores_mapeados):
        capacidades.append(CAPACIDADE_DOI)

    return capacidades


def _extrair_dimensoes(
    row: pd.Series,
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, str]:
    """Extrai valores das dimensoes de uma linha."""
    dims: Dict[str, str] = {}
    for dim_canon in ["Country", "Channel", "Category", "Brand",
                      "SKU_Code", "SKU_Description"]:
        col_name = _col(df, mapa, dim_canon)
        if col_name is not None:
            val = row.get(col_name)
            if val is not None and not pd.isna(val):
                dims[dim_canon] = str(val)
            else:
                dims[dim_canon] = ""
        else:
            dims[dim_canon] = ""
    return dims


def analisar_sellout(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de sell-out: actual vs plan com gap absoluto e percentual.

    Baseado no S&OE Script:
      - "How much have we sold vs. plan? SO"
      - Gap absoluto e % por SKU/pais/canal
      - Impacto = abs(desvio_pct/100) * NR actual (deterministico)

    Alertas derivados:
      - SO abaixo do plan + DOI alto -> future slowdown risk
      - SO abaixo do plan + DOI baixo -> imminent stock-out risk

    Args:
        df: DataFrame com dados (pode ser canonico ou original).
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista) e "resumo" (agregado).
    """
    col_plan_ton = _col(df, mapa, "SellOut_Plan_Ton")
    col_actual_ton = _col(df, mapa, "SellOut_Actual_Ton")
    col_plan_nr = _col(df, mapa, "SellOut_Plan_NR_USD")
    col_actual_nr = _col(df, mapa, "SellOut_Actual_NR_USD")

    colunas_necessarias = [col_plan_ton, col_actual_ton]
    if any(c is None for c in colunas_necessarias):
        return {"desvios": [], "resumo": {"erro": "colunas sellout ausentes"}}

    desvios: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        plan_val = row.get(col_plan_ton)
        actual_val = row.get(col_actual_ton)

        if plan_val is None or actual_val is None:
            continue
        if pd.isna(plan_val) or pd.isna(actual_val):
            continue

        plan_f = float(plan_val)
        actual_f = float(actual_val)

        if plan_f == 0.0:
            desvio_pct = 0.0
        else:
            desvio_pct = round(((actual_f - plan_f) / plan_f) * 100.0, 2)

        nr_actual = 0.0
        if col_actual_nr is not None:
            nr_raw = row.get(col_actual_nr)
            if nr_raw is not None and not pd.isna(nr_raw):
                nr_actual = float(nr_raw)

        nr_impacto = round(abs(desvio_pct / 100.0) * nr_actual, 2)

        dims = _extrair_dimensoes(row, df, mapa)

        desvios.append({
            "sku": dims.get("SKU_Code", ""),
            "pais": dims.get("Country", ""),
            "canal": dims.get("Channel", ""),
            "categoria": dims.get("Category", ""),
            "marca": dims.get("Brand", ""),
            "plan_ton": round(plan_f, 4),
            "actual_ton": round(actual_f, 4),
            "desvio_pct": desvio_pct,
            "nr_actual": round(nr_actual, 2),
            "nr_impacto": nr_impacto,
        })

    total_plan = sum(d["plan_ton"] for d in desvios)
    total_actual = sum(d["actual_ton"] for d in desvios)
    total_nr_impacto = sum(d["nr_impacto"] for d in desvios)

    if total_plan > 0:
        desvio_total_pct = round(
            ((total_actual - total_plan) / total_plan) * 100.0, 2
        )
    else:
        desvio_total_pct = 0.0

    acima_plan = sum(1 for d in desvios if d["desvio_pct"] > 0)
    abaixo_plan = sum(1 for d in desvios if d["desvio_pct"] < 0)

    resumo: Dict[str, Any] = {
        "total_registros": len(desvios),
        "total_plan_ton": round(total_plan, 4),
        "total_actual_ton": round(total_actual, 4),
        "desvio_total_pct": desvio_total_pct,
        "total_nr_impacto": round(total_nr_impacto, 2),
        "acima_plan": acima_plan,
        "abaixo_plan": abaixo_plan,
    }

    return {"desvios": desvios, "resumo": resumo}


def analisar_sellin(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de sell-in: actual vs plan com gap absoluto e percentual.

    Baseado no S&OE Script:
      - "How is order entry pace? SI"
      - SI > SO sem aumento de DOI planejado -> trade overstock
      - SI puxado para frente (pipeline fill) ou atrasado

    Args:
        df: DataFrame com dados.
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista) e "resumo" (agregado).
    """
    col_plan_ton = _col(df, mapa, "SellIn_Plan_Ton")
    col_actual_ton = _col(df, mapa, "SellIn_Actual_Ton")
    col_plan_nr = _col(df, mapa, "SellIn_Plan_NR_USD")
    col_actual_nr = _col(df, mapa, "SellIn_Actual_NR_USD")

    colunas_necessarias = [col_plan_ton, col_actual_ton]
    if any(c is None for c in colunas_necessarias):
        return {"desvios": [], "resumo": {"erro": "colunas sellin ausentes"}}

    desvios: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        plan_val = row.get(col_plan_ton)
        actual_val = row.get(col_actual_ton)

        if plan_val is None or actual_val is None:
            continue
        if pd.isna(plan_val) or pd.isna(actual_val):
            continue

        plan_f = float(plan_val)
        actual_f = float(actual_val)

        if plan_f == 0.0:
            desvio_pct = 0.0
        else:
            desvio_pct = round(((actual_f - plan_f) / plan_f) * 100.0, 2)

        nr_actual = 0.0
        if col_actual_nr is not None:
            nr_raw = row.get(col_actual_nr)
            if nr_raw is not None and not pd.isna(nr_raw):
                nr_actual = float(nr_raw)

        nr_impacto = round(abs(desvio_pct / 100.0) * nr_actual, 2)

        dims = _extrair_dimensoes(row, df, mapa)

        desvios.append({
            "sku": dims.get("SKU_Code", ""),
            "pais": dims.get("Country", ""),
            "canal": dims.get("Channel", ""),
            "categoria": dims.get("Category", ""),
            "marca": dims.get("Brand", ""),
            "plan_ton": round(plan_f, 4),
            "actual_ton": round(actual_f, 4),
            "desvio_pct": desvio_pct,
            "nr_actual": round(nr_actual, 2),
            "nr_impacto": nr_impacto,
        })

    total_plan = sum(d["plan_ton"] for d in desvios)
    total_actual = sum(d["actual_ton"] for d in desvios)
    total_nr_impacto = sum(d["nr_impacto"] for d in desvios)

    if total_plan > 0:
        desvio_total_pct = round(
            ((total_actual - total_plan) / total_plan) * 100.0, 2
        )
    else:
        desvio_total_pct = 0.0

    acima_plan = sum(1 for d in desvios if d["desvio_pct"] > 0)
    abaixo_plan = sum(1 for d in desvios if d["desvio_pct"] < 0)

    resumo: Dict[str, Any] = {
        "total_registros": len(desvios),
        "total_plan_ton": round(total_plan, 4),
        "total_actual_ton": round(total_actual, 4),
        "desvio_total_pct": desvio_total_pct,
        "total_nr_impacto": round(total_nr_impacto, 2),
        "acima_plan": acima_plan,
        "abaixo_plan": abaixo_plan,
    }

    return {"desvios": desvios, "resumo": resumo}


def analisar_doi(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de DOI (Days of Inventory): actual vs policy/target.

    Baseado no S&OE Script:
      - "Are trade inventories on track vs. policies? DOI"
      - Actual DOI vs target por Country/Channel/Brand
      - SKUs fora das bandas min/max
      - High DOI + weak SO -> overstock/SI risk
      - Low DOI + strong SO -> service level risk

    O gap_dias = DOI_Actual - DOI_Plan (positivo = acima do target).

    Args:
        df: DataFrame com dados.
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista) e "resumo" (agregado).
    """
    col_plan = _col(df, mapa, "DOI_Plan_Days")
    col_actual = _col(df, mapa, "DOI_Actual_Days")

    if col_plan is None or col_actual is None:
        return {"desvios": [], "resumo": {"erro": "colunas DOI ausentes"}}

    col_so_actual_nr = _col(df, mapa, "SellOut_Actual_NR_USD")

    desvios: List[Dict[str, Any]] = []

    for idx, row in df.iterrows():
        plan_val = row.get(col_plan)
        actual_val = row.get(col_actual)

        if plan_val is None or actual_val is None:
            continue
        if pd.isna(plan_val) or pd.isna(actual_val):
            continue

        plan_f = float(plan_val)
        actual_f = float(actual_val)
        gap_dias = round(actual_f - plan_f, 2)

        nr_impacto = 0.0
        if col_so_actual_nr is not None:
            nr_raw = row.get(col_so_actual_nr)
            if nr_raw is not None and not pd.isna(nr_raw):
                nr_val = float(nr_raw)
                if plan_f > 0:
                    nr_impacto = round(
                        abs(gap_dias / plan_f) * nr_val, 2
                    )

        dims = _extrair_dimensoes(row, df, mapa)

        desvios.append({
            "sku": dims.get("SKU_Code", ""),
            "pais": dims.get("Country", ""),
            "canal": dims.get("Channel", ""),
            "categoria": dims.get("Category", ""),
            "marca": dims.get("Brand", ""),
            "doi_plan": round(plan_f, 2),
            "doi_actual": round(actual_f, 2),
            "gap_dias": gap_dias,
            "nr_impacto": nr_impacto,
        })

    acima_target = sum(1 for d in desvios if d["gap_dias"] > 0)
    abaixo_target = sum(1 for d in desvios if d["gap_dias"] < 0)
    total_nr_impacto = sum(d["nr_impacto"] for d in desvios)

    if desvios:
        media_gap = round(
            sum(d["gap_dias"] for d in desvios) / len(desvios), 2
        )
        max_gap = max(d["gap_dias"] for d in desvios)
        min_gap = min(d["gap_dias"] for d in desvios)
    else:
        media_gap = 0.0
        max_gap = 0.0
        min_gap = 0.0

    resumo: Dict[str, Any] = {
        "total_registros": len(desvios),
        "acima_target": acima_target,
        "abaixo_target": abaixo_target,
        "media_gap_dias": media_gap,
        "max_gap_dias": max_gap,
        "min_gap_dias": min_gap,
        "total_nr_impacto": round(total_nr_impacto, 2),
    }

    return {"desvios": desvios, "resumo": resumo}
