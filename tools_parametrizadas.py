"""
Tools parametrizadas para analise de dados Mondelez S&OE.

Todas as funcoes recebem (df, mapa) e retornam dict com resultados
deterministicos. Nenhuma usa LLM. Os calculos seguem as regras
do S&OE Analyst Questions Script:

  - SO/SI gap: actual vs plan (absoluto e %)
  - DOI: actual vs policy, gap em dias
  - Alertas cruzados: SO + DOI combinados
  - Impacto: abs(desvio_pct) * NR actual (deterministico)

Agregacao (ADR-0019):
  - Nivel 1 (desvios): SKU x Pais x Canal -- gera sinais/proposicoes
  - Nivel 3 (resumo_categorias): Categoria x Pais x Canal -- para Critic/LLM

Ref: ADR-0019, docs/S&OE - Analyst Questions Script.xlsx
"""

from typing import Any, Dict, List, Optional, Set

import numpy as np
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

DIMS_NIVEL_1 = ["SKU_Code", "Country", "Channel", "Category", "Brand"]
DIMS_NIVEL_3 = ["Category", "Country", "Channel"]


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


def _resolver_dims(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    nomes_canonicos: List[str],
) -> List[str]:
    """Resolve lista de nomes canonicos de dimensao para nomes no DataFrame."""
    resultado: List[str] = []
    for nome in nomes_canonicos:
        col_name = _col(df, mapa, nome)
        if col_name is not None:
            resultado.append(col_name)
    return resultado


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


def _agg_plan_actual(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    col_plan_canon: str,
    col_actual_canon: str,
    col_nr_canon: str,
    dims_canonicos: List[str],
) -> pd.DataFrame:
    """
    Agrega plan/actual/NR por dimensoes usando groupby vetorizado.

    Filtra nulos antes do groupby. Soma tons e NR por grupo.
    Calcula desvio_pct e nr_impacto sobre os totais agregados.

    Returns:
        DataFrame com colunas: dims + plan_ton, actual_ton, desvio_pct,
        nr_actual, nr_impacto.
    """
    col_plan = _col(df, mapa, col_plan_canon)
    col_actual = _col(df, mapa, col_actual_canon)
    col_nr = _col(df, mapa, col_nr_canon)

    if col_plan is None or col_actual is None:
        return pd.DataFrame()

    dim_cols = _resolver_dims(df, mapa, dims_canonicos)
    if not dim_cols:
        return pd.DataFrame()

    cols_needed = dim_cols + [col_plan, col_actual]
    if col_nr is not None:
        cols_needed.append(col_nr)

    work = df[cols_needed].copy()
    work = work.dropna(subset=[col_plan, col_actual])
    if work.empty:
        return pd.DataFrame()

    agg_dict: Dict[str, Any] = {
        col_plan: "sum",
        col_actual: "sum",
    }
    if col_nr is not None:
        agg_dict[col_nr] = "sum"

    grouped = work.groupby(dim_cols, as_index=False).agg(agg_dict)

    grouped["plan_ton"] = grouped[col_plan].round(4)
    grouped["actual_ton"] = grouped[col_actual].round(4)

    grouped["desvio_pct"] = np.where(
        grouped["plan_ton"] != 0.0,
        (((grouped["actual_ton"] - grouped["plan_ton"]) / grouped["plan_ton"]) * 100.0).round(2),
        0.0,
    )

    if col_nr is not None:
        grouped["nr_actual"] = grouped[col_nr].round(2)
    else:
        grouped["nr_actual"] = 0.0

    grouped["nr_impacto"] = (
        (grouped["desvio_pct"].abs() / 100.0) * grouped["nr_actual"]
    ).round(2)

    return grouped


def analisar_sellout(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de sell-out agregada por SKU x Pais x Canal (Nivel 1).

    Baseado no S&OE Script:
      - "How much have we sold vs. plan? SO"
      - Gap absoluto e % por SKU/pais/canal (acumulado do periodo)
      - Impacto = abs(desvio_pct/100) * NR actual (deterministico)

    Args:
        df: DataFrame com dados (pode ser canonico ou original).
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista agregada por SKU/Pais/Canal) e "resumo".
    """
    col_plan_ton = _col(df, mapa, "SellOut_Plan_Ton")
    col_actual_ton = _col(df, mapa, "SellOut_Actual_Ton")

    if col_plan_ton is None or col_actual_ton is None:
        return {"desvios": [], "resumo": {"erro": "colunas sellout ausentes"}}

    grouped = _agg_plan_actual(
        df, mapa,
        "SellOut_Plan_Ton", "SellOut_Actual_Ton", "SellOut_Actual_NR_USD",
        DIMS_NIVEL_1,
    )

    if grouped.empty:
        return {"desvios": [], "resumo": {"total_registros": 0}}

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    desvios: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        d: Dict[str, Any] = {
            "plan_ton": row["plan_ton"],
            "actual_ton": row["actual_ton"],
            "desvio_pct": row["desvio_pct"],
            "nr_actual": row["nr_actual"],
            "nr_impacto": row["nr_impacto"],
        }
        for col_df, col_canon in dim_map.items():
            val = row.get(col_df)
            key = col_canon.lower() if col_canon != "SKU_Code" else "sku"
            if col_canon == "SKU_Code":
                key = "sku"
            elif col_canon == "Country":
                key = "pais"
            elif col_canon == "Channel":
                key = "canal"
            elif col_canon == "Category":
                key = "categoria"
            elif col_canon == "Brand":
                key = "marca"
            else:
                key = col_canon.lower()
            d[key] = str(val) if val is not None and not pd.isna(val) else ""
        desvios.append(d)

    total_plan = grouped["plan_ton"].sum()
    total_actual = grouped["actual_ton"].sum()
    total_nr_impacto = grouped["nr_impacto"].sum()

    if total_plan > 0:
        desvio_total_pct = round(
            ((total_actual - total_plan) / total_plan) * 100.0, 2
        )
    else:
        desvio_total_pct = 0.0

    acima_plan = int((grouped["desvio_pct"] > 0).sum())
    abaixo_plan = int((grouped["desvio_pct"] < 0).sum())

    resumo: Dict[str, Any] = {
        "total_registros": len(desvios),
        "total_plan_ton": round(float(total_plan), 4),
        "total_actual_ton": round(float(total_actual), 4),
        "desvio_total_pct": desvio_total_pct,
        "total_nr_impacto": round(float(total_nr_impacto), 2),
        "acima_plan": acima_plan,
        "abaixo_plan": abaixo_plan,
    }

    return {"desvios": desvios, "resumo": resumo}


def analisar_sellin(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de sell-in agregada por SKU x Pais x Canal (Nivel 1).

    Baseado no S&OE Script:
      - "How is order entry pace? SI"
      - SI > SO sem aumento de DOI planejado -> trade overstock
      - SI puxado para frente (pipeline fill) ou atrasado

    Args:
        df: DataFrame com dados.
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista agregada por SKU/Pais/Canal) e "resumo".
    """
    col_plan_ton = _col(df, mapa, "SellIn_Plan_Ton")
    col_actual_ton = _col(df, mapa, "SellIn_Actual_Ton")

    if col_plan_ton is None or col_actual_ton is None:
        return {"desvios": [], "resumo": {"erro": "colunas sellin ausentes"}}

    grouped = _agg_plan_actual(
        df, mapa,
        "SellIn_Plan_Ton", "SellIn_Actual_Ton", "SellIn_Actual_NR_USD",
        DIMS_NIVEL_1,
    )

    if grouped.empty:
        return {"desvios": [], "resumo": {"total_registros": 0}}

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    desvios: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        d: Dict[str, Any] = {
            "plan_ton": row["plan_ton"],
            "actual_ton": row["actual_ton"],
            "desvio_pct": row["desvio_pct"],
            "nr_actual": row["nr_actual"],
            "nr_impacto": row["nr_impacto"],
        }
        for col_df, col_canon in dim_map.items():
            val = row.get(col_df)
            if col_canon == "SKU_Code":
                key = "sku"
            elif col_canon == "Country":
                key = "pais"
            elif col_canon == "Channel":
                key = "canal"
            elif col_canon == "Category":
                key = "categoria"
            elif col_canon == "Brand":
                key = "marca"
            else:
                key = col_canon.lower()
            d[key] = str(val) if val is not None and not pd.isna(val) else ""
        desvios.append(d)

    total_plan = grouped["plan_ton"].sum()
    total_actual = grouped["actual_ton"].sum()
    total_nr_impacto = grouped["nr_impacto"].sum()

    if total_plan > 0:
        desvio_total_pct = round(
            ((total_actual - total_plan) / total_plan) * 100.0, 2
        )
    else:
        desvio_total_pct = 0.0

    acima_plan = int((grouped["desvio_pct"] > 0).sum())
    abaixo_plan = int((grouped["desvio_pct"] < 0).sum())

    resumo: Dict[str, Any] = {
        "total_registros": len(desvios),
        "total_plan_ton": round(float(total_plan), 4),
        "total_actual_ton": round(float(total_actual), 4),
        "desvio_total_pct": desvio_total_pct,
        "total_nr_impacto": round(float(total_nr_impacto), 2),
        "acima_plan": acima_plan,
        "abaixo_plan": abaixo_plan,
    }

    return {"desvios": desvios, "resumo": resumo}


def analisar_doi(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Analise de DOI agregada por SKU x Pais x Canal (Nivel 1).

    DOI usa media (nao soma) porque dias de inventario nao sao aditivos.

    Baseado no S&OE Script:
      - "Are trade inventories on track vs. policies? DOI"
      - Actual DOI vs target por Country/Channel/Brand
      - gap_dias = DOI_Actual_media - DOI_Plan_media

    Args:
        df: DataFrame com dados.
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "desvios" (lista agregada por SKU/Pais/Canal) e "resumo".
    """
    col_plan = _col(df, mapa, "DOI_Plan_Days")
    col_actual = _col(df, mapa, "DOI_Actual_Days")

    if col_plan is None or col_actual is None:
        return {"desvios": [], "resumo": {"erro": "colunas DOI ausentes"}}

    col_so_actual_nr = _col(df, mapa, "SellOut_Actual_NR_USD")

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    if not dim_cols:
        return {"desvios": [], "resumo": {"erro": "dimensoes ausentes"}}

    cols_needed = dim_cols + [col_plan, col_actual]
    if col_so_actual_nr is not None:
        cols_needed.append(col_so_actual_nr)

    work = df[cols_needed].copy()
    work = work.dropna(subset=[col_plan, col_actual])
    if work.empty:
        return {"desvios": [], "resumo": {"total_registros": 0}}

    agg_dict: Dict[str, Any] = {
        col_plan: "mean",
        col_actual: "mean",
    }
    if col_so_actual_nr is not None:
        agg_dict[col_so_actual_nr] = "sum"

    grouped = work.groupby(dim_cols, as_index=False).agg(agg_dict)

    grouped["doi_plan"] = grouped[col_plan].round(2)
    grouped["doi_actual"] = grouped[col_actual].round(2)
    grouped["gap_dias"] = (grouped["doi_actual"] - grouped["doi_plan"]).round(2)

    if col_so_actual_nr is not None:
        grouped["nr_base"] = grouped[col_so_actual_nr]
        grouped["nr_impacto"] = np.where(
            grouped["doi_plan"] > 0,
            ((grouped["gap_dias"].abs() / grouped["doi_plan"]) * grouped["nr_base"]).round(2),
            0.0,
        )
    else:
        grouped["nr_impacto"] = 0.0

    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    desvios: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        d: Dict[str, Any] = {
            "doi_plan": float(row["doi_plan"]),
            "doi_actual": float(row["doi_actual"]),
            "gap_dias": float(row["gap_dias"]),
            "nr_impacto": float(row["nr_impacto"]),
        }
        for col_df, col_canon in dim_map.items():
            val = row.get(col_df)
            if col_canon == "SKU_Code":
                key = "sku"
            elif col_canon == "Country":
                key = "pais"
            elif col_canon == "Channel":
                key = "canal"
            elif col_canon == "Category":
                key = "categoria"
            elif col_canon == "Brand":
                key = "marca"
            else:
                key = col_canon.lower()
            d[key] = str(val) if val is not None and not pd.isna(val) else ""
        desvios.append(d)

    acima_target = int((grouped["gap_dias"] > 0).sum())
    abaixo_target = int((grouped["gap_dias"] < 0).sum())
    total_nr_impacto = float(grouped["nr_impacto"].sum())

    if not grouped.empty:
        media_gap = round(float(grouped["gap_dias"].mean()), 2)
        max_gap = float(grouped["gap_dias"].max())
        min_gap = float(grouped["gap_dias"].min())
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


def resumir_por_categoria(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> Dict[str, Any]:
    """
    Resumo Nivel 3: Categoria x Pais x Canal.

    Gera visao compacta para o Critic e LLM avaliarem, agregando
    SO, SI e DOI por categoria. Resulta em ~140 linhas max.

    Args:
        df: DataFrame com dados (canonico ou original).
        mapa: dicionario {col_original: col_canonica}.

    Returns:
        Dict com "resumo_categorias" (lista) e "totais".
    """
    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_3)
    if not dim_cols:
        return {"resumo_categorias": [], "totais": {}}

    col_so_plan = _col(df, mapa, "SellOut_Plan_Ton")
    col_so_actual = _col(df, mapa, "SellOut_Actual_Ton")
    col_si_plan = _col(df, mapa, "SellIn_Plan_Ton")
    col_si_actual = _col(df, mapa, "SellIn_Actual_Ton")
    col_doi_plan = _col(df, mapa, "DOI_Plan_Days")
    col_doi_actual = _col(df, mapa, "DOI_Actual_Days")
    col_so_nr = _col(df, mapa, "SellOut_Actual_NR_USD")

    agg_dict: Dict[str, Any] = {}
    cols_needed = list(dim_cols)

    metricas_sum = [
        (col_so_plan, "so_plan"),
        (col_so_actual, "so_actual"),
        (col_si_plan, "si_plan"),
        (col_si_actual, "si_actual"),
        (col_so_nr, "so_nr"),
    ]
    metricas_mean = [
        (col_doi_plan, "doi_plan"),
        (col_doi_actual, "doi_actual"),
    ]

    rename_map: Dict[str, str] = {}
    for col, alias in metricas_sum:
        if col is not None and col in df.columns:
            agg_dict[col] = "sum"
            cols_needed.append(col)
            rename_map[col] = alias
    for col, alias in metricas_mean:
        if col is not None and col in df.columns:
            agg_dict[col] = "mean"
            cols_needed.append(col)
            rename_map[col] = alias

    if not agg_dict:
        return {"resumo_categorias": [], "totais": {}}

    work = df[cols_needed].copy()
    grouped = work.groupby(dim_cols, as_index=False).agg(agg_dict)
    grouped = grouped.rename(columns=rename_map)

    dim_canon_map = dict(zip(dim_cols, DIMS_NIVEL_3))

    resumos: List[Dict[str, Any]] = []
    for _, row in grouped.iterrows():
        r: Dict[str, Any] = {}
        for col_df, col_canon in dim_canon_map.items():
            val = row.get(col_df)
            if col_canon == "Category":
                key = "categoria"
            elif col_canon == "Country":
                key = "pais"
            elif col_canon == "Channel":
                key = "canal"
            else:
                key = col_canon.lower()
            r[key] = str(val) if val is not None and not pd.isna(val) else ""

        if "so_plan" in grouped.columns and "so_actual" in grouped.columns:
            so_plan = float(row.get("so_plan", 0) or 0)
            so_actual = float(row.get("so_actual", 0) or 0)
            r["so_plan_ton"] = round(so_plan, 2)
            r["so_actual_ton"] = round(so_actual, 2)
            r["so_desvio_pct"] = round(
                ((so_actual - so_plan) / so_plan * 100.0) if so_plan else 0.0,
                2,
            )

        if "si_plan" in grouped.columns and "si_actual" in grouped.columns:
            si_plan = float(row.get("si_plan", 0) or 0)
            si_actual = float(row.get("si_actual", 0) or 0)
            r["si_plan_ton"] = round(si_plan, 2)
            r["si_actual_ton"] = round(si_actual, 2)
            r["si_desvio_pct"] = round(
                ((si_actual - si_plan) / si_plan * 100.0) if si_plan else 0.0,
                2,
            )

        if "doi_plan" in grouped.columns and "doi_actual" in grouped.columns:
            doi_plan = float(row.get("doi_plan", 0) or 0)
            doi_actual = float(row.get("doi_actual", 0) or 0)
            r["doi_plan_dias"] = round(doi_plan, 1)
            r["doi_actual_dias"] = round(doi_actual, 1)
            r["doi_gap_dias"] = round(doi_actual - doi_plan, 1)

        if "so_nr" in grouped.columns:
            r["nr_total"] = round(float(row.get("so_nr", 0) or 0), 2)

        resumos.append(r)

    totais: Dict[str, Any] = {"total_categorias": len(resumos)}
    if "so_plan" in grouped.columns:
        totais["so_plan_total"] = round(float(grouped["so_plan"].sum()), 2)
        totais["so_actual_total"] = round(float(grouped["so_actual"].sum()), 2)
    if "si_plan" in grouped.columns:
        totais["si_plan_total"] = round(float(grouped["si_plan"].sum()), 2)
        totais["si_actual_total"] = round(float(grouped["si_actual"].sum()), 2)

    return {"resumo_categorias": resumos, "totais": totais}
