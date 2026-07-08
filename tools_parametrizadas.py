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

DIRECAO_MELHORANDO = "melhorando"
DIRECAO_PIORANDO = "piorando"
DIRECAO_ESTAVEL = "estavel"

RISCO_RUPTURA = "ruptura"
RISCO_OVERSTOCK = "overstock"
RISCO_GAP_PLANO = "gap_plano"

LIMIAR_TENDENCIA_ESTAVEL_PCT = 3.0
LIMIAR_PREMISSA_FURADA_PCT = 15.0
DOI_RUPTURA_DIAS = 15.0
DOI_OVERSTOCK_DIAS = 40.0

RISCO_OPORTUNIDADE = "oportunidade"

LIMIAR_ACELERACAO_PCT = 5.0
LIMIAR_DESVIO_PERSISTENTE_MESES = 3


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


def _data_corte_efetiva(
    df: pd.DataFrame,
    col_date: str,
    col_actual: str,
    data_corte: Optional[str],
) -> pd.Timestamp:
    """
    Determina a data de corte entre dados realizados e forward.

    Se data_corte nao for fornecida, usa a ultima data onde actual nao e NaN.
    """
    if data_corte is not None:
        return pd.Timestamp(data_corte)
    real = df[df[col_actual].notna()]
    if real.empty:
        return pd.Timestamp(df[col_date].max())
    return pd.Timestamp(real[col_date].max())


def _classificar_direcao_doi(doi_recente: float, doi_anterior: float) -> str:
    """
    Classifica direcao da tendencia de DOI.

    DOI caindo = melhorando (estoque drenando).
    DOI subindo = piorando (estoque acumulando).
    """
    if doi_anterior <= 0:
        return DIRECAO_ESTAVEL
    delta_pct = ((doi_recente - doi_anterior) / doi_anterior) * 100.0
    if delta_pct < -LIMIAR_TENDENCIA_ESTAVEL_PCT:
        return DIRECAO_MELHORANDO
    if delta_pct > LIMIAR_TENDENCIA_ESTAVEL_PCT:
        return DIRECAO_PIORANDO
    return DIRECAO_ESTAVEL


def _contar_semanas_consecutivas(
    serie_semanal: pd.Series,
    col_desvio: str,
) -> int:
    """
    Conta semanas consecutivas (do fim para o inicio) com desvio no mesmo sinal.

    Retorna o numero de semanas consecutivas onde o desvio manteve o mesmo
    sinal (positivo ou negativo) a partir da semana mais recente.
    """
    if serie_semanal.empty:
        return 0
    valores = serie_semanal.values
    if len(valores) == 0:
        return 0
    ultimo = valores[-1]
    if ultimo == 0:
        return 0
    sinal_ultimo = ultimo > 0
    contagem = 0
    for v in reversed(valores):
        if (v > 0) == sinal_ultimo and v != 0:
            contagem += 1
        else:
            break
    return contagem


def analisar_tendencia(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    janela_recente_dias: int = 30,
    data_corte: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analise de tendencia temporal: compara periodo recente vs anterior.

    Separa dados realizados em duas janelas (recente e anterior) e
    calcula direcao de SO e DOI por SKU x Pais x Canal.

    Args:
        df: DataFrame com dados (canonico ou original).
        mapa: dicionario {col_original: col_canonica}.
        janela_recente_dias: tamanho da janela recente em dias.
        data_corte: data de corte opcional (ISO format). Se None,
            usa ultima data com actuals.

    Returns:
        Dict com "tendencias" (lista por SKU/Pais/Canal) e "resumo".
    """
    col_date = _col(df, mapa, "Date")
    col_so_actual = _col(df, mapa, "SellOut_Actual_Ton")
    col_so_plan = _col(df, mapa, "SellOut_Plan_Ton")
    col_doi_actual = _col(df, mapa, "DOI_Actual_Days")

    if col_date is None or col_so_actual is None:
        return {"tendencias": [], "resumo": {"erro": "colunas temporais ausentes"}}

    work = df.copy()
    work[col_date] = pd.to_datetime(work[col_date], errors="coerce")
    work = work.dropna(subset=[col_date])

    corte = _data_corte_efetiva(work, col_date, col_so_actual, data_corte)

    realizados = work[work[col_so_actual].notna()].copy()
    if realizados.empty:
        return {"tendencias": [], "resumo": {"total_skus": 0}}

    corte_recente = corte - pd.Timedelta(days=janela_recente_dias)
    corte_anterior = corte_recente - pd.Timedelta(days=janela_recente_dias)

    recentes = realizados[realizados[col_date] > corte_recente]
    anteriores = realizados[
        (realizados[col_date] > corte_anterior)
        & (realizados[col_date] <= corte_recente)
    ]

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    if not dim_cols:
        return {"tendencias": [], "resumo": {"erro": "dimensoes ausentes"}}

    def _agg_janela(sub: pd.DataFrame) -> pd.DataFrame:
        if sub.empty:
            return pd.DataFrame()
        agg: Dict[str, Any] = {}
        if col_so_plan is not None and col_so_plan in sub.columns:
            agg[col_so_plan] = "sum"
        agg[col_so_actual] = "sum"
        if col_doi_actual is not None and col_doi_actual in sub.columns:
            agg[col_doi_actual] = "mean"
        return sub.groupby(dim_cols, as_index=False).agg(agg)

    df_recente = _agg_janela(recentes)
    df_anterior = _agg_janela(anteriores)

    if df_recente.empty:
        return {"tendencias": [], "resumo": {"total_skus": 0}}

    realizados["_semana"] = realizados[col_date].dt.isocalendar().week.astype(int)
    semana_cols = dim_cols + ["_semana"]
    if col_so_plan is not None and col_so_plan in realizados.columns:
        sem_agg = {col_so_plan: "sum", col_so_actual: "sum"}
    else:
        sem_agg = {col_so_actual: "sum"}
    semanal = realizados.groupby(semana_cols, as_index=False).agg(sem_agg)
    if col_so_plan is not None and col_so_plan in semanal.columns:
        semanal["_desvio_sem"] = semanal[col_so_actual] - semanal[col_so_plan]
        semanal["_desvio_sem_pct"] = np.where(
            semanal[col_so_plan] != 0,
            ((semanal[col_so_actual] - semanal[col_so_plan]) / semanal[col_so_plan] * 100.0),
            0.0,
        )
    else:
        semanal["_desvio_sem"] = 0.0
        semanal["_desvio_sem_pct"] = 0.0

    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    tendencias: List[Dict[str, Any]] = []
    for _, row_r in df_recente.iterrows():
        chave_vals = tuple(row_r[c] for c in dim_cols)

        so_recente = float(row_r[col_so_actual])
        so_plan_recente = float(row_r.get(col_so_plan, 0) or 0) if col_so_plan else 0.0
        doi_recente = float(row_r.get(col_doi_actual, 0) or 0) if col_doi_actual else 0.0

        so_anterior = 0.0
        doi_anterior = 0.0
        if not df_anterior.empty:
            filtro_ant = df_anterior
            for col_d, val in zip(dim_cols, chave_vals):
                if col_d in filtro_ant.columns:
                    filtro_ant = filtro_ant[filtro_ant[col_d] == val]
            if not filtro_ant.empty:
                so_anterior = float(filtro_ant[col_so_actual].iloc[0])
                if col_doi_actual and col_doi_actual in filtro_ant.columns:
                    doi_anterior = float(filtro_ant[col_doi_actual].iloc[0])

        if so_plan_recente != 0:
            so_desvio_recente = round(
                ((so_recente - so_plan_recente) / so_plan_recente) * 100.0, 2
            )
        else:
            so_desvio_recente = 0.0

        direcao_doi = _classificar_direcao_doi(doi_recente, doi_anterior)

        if so_anterior > 0:
            so_variacao = round(
                ((so_recente - so_anterior) / so_anterior) * 100.0, 2
            )
        else:
            so_variacao = 0.0

        filtro_sem = semanal.copy()
        for col_d, val in zip(dim_cols, chave_vals):
            filtro_sem = filtro_sem[filtro_sem[col_d] == val]
        filtro_sem = filtro_sem.sort_values("_semana")
        sem_consec = _contar_semanas_consecutivas(
            filtro_sem["_desvio_sem"], "_desvio_sem"
        )

        # Ritmo de variacao SO: comparar desvio% das ultimas 3 semanas
        # vs 3 semanas anteriores para detectar aceleracao/desaceleracao
        desvios_sem = filtro_sem["_desvio_sem_pct"].values
        so_aceleracao = 0.0
        so_ritmo = "estavel"
        if len(desvios_sem) >= 4:
            metade = len(desvios_sem) // 2
            media_recente_sem = float(np.mean(desvios_sem[metade:]))
            media_anterior_sem = float(np.mean(desvios_sem[:metade]))
            so_aceleracao = round(media_recente_sem - media_anterior_sem, 2)
            if so_aceleracao > LIMIAR_ACELERACAO_PCT:
                so_ritmo = "acelerando"
            elif so_aceleracao < -LIMIAR_ACELERACAO_PCT:
                so_ritmo = "desacelerando"

        t: Dict[str, Any] = {
            "so_recente_ton": round(so_recente, 2),
            "so_anterior_ton": round(so_anterior, 2),
            "so_desvio_recente_pct": so_desvio_recente,
            "so_variacao_pct": so_variacao,
            "so_aceleracao_pct": so_aceleracao,
            "so_ritmo": so_ritmo,
            "doi_recente": round(doi_recente, 1),
            "doi_anterior": round(doi_anterior, 1),
            "direcao_doi": direcao_doi,
            "semanas_consecutivas": sem_consec,
        }
        for col_df, col_canon in dim_map.items():
            val = row_r.get(col_df)
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
            t[key] = str(val) if val is not None and not pd.isna(val) else ""
        tendencias.append(t)

    piorando = sum(1 for t in tendencias if t["direcao_doi"] == DIRECAO_PIORANDO)
    melhorando = sum(1 for t in tendencias if t["direcao_doi"] == DIRECAO_MELHORANDO)
    acelerando = sum(1 for t in tendencias if t["so_ritmo"] == "acelerando")
    desacelerando = sum(1 for t in tendencias if t["so_ritmo"] == "desacelerando")

    resumo: Dict[str, Any] = {
        "total_skus": len(tendencias),
        "janela_dias": janela_recente_dias,
        "data_corte": str(corte.date()),
        "doi_piorando": piorando,
        "doi_melhorando": melhorando,
        "doi_estavel": len(tendencias) - piorando - melhorando,
        "so_acelerando": acelerando,
        "so_desacelerando": desacelerando,
    }

    return {"tendencias": tendencias, "resumo": resumo}


def analisar_forward(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    janela_recente_dias: int = 30,
    data_corte: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analise forward: cruza tendencia recente com plano futuro.

    Detecta premissas furadas no plano (plan-only diverge da tendencia
    recente) e projeta riscos de ruptura/overstock.

    Args:
        df: DataFrame com dados (canonico ou original).
        mapa: dicionario {col_original: col_canonica}.
        janela_recente_dias: tamanho da janela recente em dias.
        data_corte: data de corte opcional (ISO format).

    Returns:
        Dict com "alertas_forward" (lista por SKU/Pais/Canal) e "resumo".
    """
    col_date = _col(df, mapa, "Date")
    col_so_actual = _col(df, mapa, "SellOut_Actual_Ton")
    col_so_plan = _col(df, mapa, "SellOut_Plan_Ton")
    col_si_plan = _col(df, mapa, "SellIn_Plan_Ton")
    col_si_actual = _col(df, mapa, "SellIn_Actual_Ton")
    col_doi_actual = _col(df, mapa, "DOI_Actual_Days")
    col_doi_plan = _col(df, mapa, "DOI_Plan_Days")

    if col_date is None or col_so_plan is None:
        return {"alertas_forward": [], "resumo": {"erro": "colunas ausentes"}}

    work = df.copy()
    work[col_date] = pd.to_datetime(work[col_date], errors="coerce")
    work = work.dropna(subset=[col_date])

    corte = _data_corte_efetiva(
        work, col_date,
        col_so_actual if col_so_actual is not None else col_so_plan,
        data_corte,
    )
    corte_recente_inicio = corte - pd.Timedelta(days=janela_recente_dias)

    # Dados realizados recentes (janela)
    if col_so_actual is not None:
        realizados = work[
            (work[col_so_actual].notna())
            & (work[col_date] > corte_recente_inicio)
            & (work[col_date] <= corte)
        ]
    else:
        realizados = pd.DataFrame()

    # Dados forward (plan-only, apos a data de corte)
    if col_so_actual is not None:
        forward = work[work[col_so_actual].isna() & (work[col_date] > corte)]
    else:
        forward = work[work[col_date] > corte]

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    if not dim_cols:
        return {"alertas_forward": [], "resumo": {"erro": "dimensoes ausentes"}}

    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    # Agregar realizados recentes
    agg_real: Dict[str, Any] = {}
    if col_so_plan is not None and col_so_plan in realizados.columns:
        agg_real[col_so_plan] = "sum"
    if col_so_actual is not None and col_so_actual in realizados.columns:
        agg_real[col_so_actual] = "sum"
    if col_si_plan is not None and col_si_plan in realizados.columns:
        agg_real[col_si_plan] = "sum"
    if col_si_actual is not None and col_si_actual in realizados.columns:
        agg_real[col_si_actual] = "sum"
    if col_doi_actual is not None and col_doi_actual in realizados.columns:
        agg_real[col_doi_actual] = "mean"

    if not realizados.empty and agg_real:
        real_agg = realizados.groupby(dim_cols, as_index=False).agg(agg_real)
    else:
        real_agg = pd.DataFrame()

    # Agregar forward
    agg_fwd: Dict[str, Any] = {}
    if col_so_plan is not None and col_so_plan in forward.columns:
        agg_fwd[col_so_plan] = "sum"
    if col_si_plan is not None and col_si_plan in forward.columns:
        agg_fwd[col_si_plan] = "sum"
    if col_doi_plan is not None and col_doi_plan in forward.columns:
        agg_fwd[col_doi_plan] = "mean"

    if not forward.empty and agg_fwd:
        fwd_agg = forward.groupby(dim_cols, as_index=False).agg(agg_fwd)
    else:
        fwd_agg = pd.DataFrame()

    if real_agg.empty or fwd_agg.empty:
        return {"alertas_forward": [], "resumo": {"total_alertas": 0}}

    # Obter ultimo DOI realizado por grupo (snapshot mais recente)
    doi_snapshot: Dict[tuple, float] = {}
    if col_doi_actual is not None and col_doi_actual in work.columns:
        real_all = work[work[col_doi_actual].notna()]
        if not real_all.empty:
            idx_max = real_all.groupby(dim_cols)[col_date].idxmax()
            for idx_val in idx_max:
                row_snap = real_all.loc[idx_val]
                chave = tuple(row_snap[c] for c in dim_cols)
                doi_snapshot[chave] = float(row_snap[col_doi_actual])

    alertas: List[Dict[str, Any]] = []
    for _, row_fwd in fwd_agg.iterrows():
        chave_vals = tuple(row_fwd[c] for c in dim_cols)

        # Encontrar dados recentes correspondentes
        filtro_real = real_agg.copy()
        for col_d, val in zip(dim_cols, chave_vals):
            filtro_real = filtro_real[filtro_real[col_d] == val]
        if filtro_real.empty:
            continue

        row_real = filtro_real.iloc[0]

        # SO: tendencia recente (actual vs plan) vs plano forward
        so_plan_recente = float(row_real.get(col_so_plan, 0) or 0) if col_so_plan else 0.0
        so_actual_recente = float(row_real.get(col_so_actual, 0) or 0) if col_so_actual else 0.0
        so_plan_forward = float(row_fwd.get(col_so_plan, 0) or 0) if col_so_plan else 0.0

        if so_plan_recente > 0:
            so_tendencia_pct = round(
                ((so_actual_recente - so_plan_recente) / so_plan_recente) * 100.0, 2
            )
        else:
            so_tendencia_pct = 0.0

        # Plano forward assume que SO tera qual variacao vs actual recente?
        dias_forward = max(1, (forward[col_date].max() - corte).days)
        dias_recente = max(1, janela_recente_dias)
        so_diario_real = so_actual_recente / dias_recente
        so_diario_plan_fwd = so_plan_forward / dias_forward

        if so_diario_real > 0:
            divergencia_forward_pct = round(
                ((so_diario_plan_fwd - so_diario_real) / so_diario_real) * 100.0, 2
            )
        else:
            divergencia_forward_pct = 0.0

        premissa_coerente = abs(divergencia_forward_pct) <= LIMIAR_PREMISSA_FURADA_PCT

        # DOI: snapshot atual vs plano forward
        doi_atual = doi_snapshot.get(chave_vals, 0.0)
        doi_plan_fwd = float(row_fwd.get(col_doi_plan, 0) or 0) if col_doi_plan else 0.0

        # SI forward
        si_plan_fwd = float(row_fwd.get(col_si_plan, 0) or 0) if col_si_plan else 0.0
        si_actual_recente = float(row_real.get(col_si_actual, 0) or 0) if col_si_actual else 0.0

        # Classificar risco projetado
        # SO acima do plano + DOI baixo + plano subdimensionado = OPORTUNIDADE
        # SO acima do plano + DOI baixo + plano nao cobre = RUPTURA se plano nao sobe
        risco = ""
        so_acima_plano = so_tendencia_pct > 5.0
        plano_subdimensionado = divergencia_forward_pct < -LIMIAR_PREMISSA_FURADA_PCT

        if doi_atual > 0 and doi_atual < DOI_RUPTURA_DIAS and so_acima_plano:
            if plano_subdimensionado:
                risco = RISCO_OPORTUNIDADE
            else:
                risco = RISCO_RUPTURA
        elif doi_atual > DOI_OVERSTOCK_DIAS:
            risco = RISCO_OVERSTOCK
        if not premissa_coerente and not risco:
            risco = RISCO_GAP_PLANO

        if not risco and premissa_coerente:
            continue

        alerta: Dict[str, Any] = {
            "so_tendencia_recente_pct": so_tendencia_pct,
            "so_diario_real": round(so_diario_real, 4),
            "so_diario_plan_fwd": round(so_diario_plan_fwd, 4),
            "divergencia_forward_pct": divergencia_forward_pct,
            "premissa_coerente": premissa_coerente,
            "doi_atual": round(doi_atual, 1),
            "doi_plan_forward": round(doi_plan_fwd, 1),
            "si_plan_forward_ton": round(si_plan_fwd, 2),
            "si_actual_recente_ton": round(si_actual_recente, 2),
            "risco_projetado": risco,
        }
        for col_df, col_canon in dim_map.items():
            val = row_fwd.get(col_df)
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
            alerta[key] = str(val) if val is not None and not pd.isna(val) else ""
        alertas.append(alerta)

    rupturas = sum(1 for a in alertas if a["risco_projetado"] == RISCO_RUPTURA)
    overstocks = sum(1 for a in alertas if a["risco_projetado"] == RISCO_OVERSTOCK)
    gaps = sum(1 for a in alertas if a["risco_projetado"] == RISCO_GAP_PLANO)
    oportunidades = sum(1 for a in alertas if a["risco_projetado"] == RISCO_OPORTUNIDADE)

    resumo: Dict[str, Any] = {
        "total_alertas": len(alertas),
        "rupturas_projetadas": rupturas,
        "overstocks_projetados": overstocks,
        "gaps_plano": gaps,
        "oportunidades": oportunidades,
        "data_corte": str(corte.date()),
    }

    return {"alertas_forward": alertas, "resumo": resumo}


def analisar_desvio_persistente(
    df: pd.DataFrame,
    mapa: Dict[str, str],
    min_meses: int = LIMIAR_DESVIO_PERSISTENTE_MESES,
) -> Dict[str, Any]:
    """
    Detecta SKUs com desvio de SO no mesmo sinal por N meses consecutivos.

    Agrupa dados realizados por mes-calendario e calcula desvio% mensal.
    Se o desvio mantem o mesmo sinal (positivo ou negativo) por pelo menos
    ``min_meses`` meses consecutivos (contando do mais recente para tras),
    o SKU e marcado como desvio persistente.

    Args:
        df: DataFrame com dados (canonico ou original).
        mapa: dicionario {col_original: col_canonica}.
        min_meses: minimo de meses consecutivos para considerar
            desvio como persistente.

    Returns:
        Dict com "persistentes" (lista por SKU/Pais/Canal) e "resumo".
    """
    col_date = _col(df, mapa, "Date")
    col_so_actual = _col(df, mapa, "SellOut_Actual_Ton")
    col_so_plan = _col(df, mapa, "SellOut_Plan_Ton")

    if col_date is None or col_so_actual is None or col_so_plan is None:
        return {"persistentes": [], "resumo": {"erro": "colunas ausentes"}}

    work = df.copy()
    work[col_date] = pd.to_datetime(work[col_date], errors="coerce")
    work = work.dropna(subset=[col_date, col_so_actual, col_so_plan])

    if work.empty:
        return {"persistentes": [], "resumo": {"total": 0}}

    work["_ano_mes"] = work[col_date].dt.to_period("M")

    dim_cols = _resolver_dims(df, mapa, DIMS_NIVEL_1)
    if not dim_cols:
        return {"persistentes": [], "resumo": {"erro": "dimensoes ausentes"}}

    group_cols = dim_cols + ["_ano_mes"]
    mensal = work.groupby(group_cols, as_index=False).agg(
        {col_so_actual: "sum", col_so_plan: "sum"}
    )
    mensal["_desvio_pct"] = np.where(
        mensal[col_so_plan] != 0,
        ((mensal[col_so_actual] - mensal[col_so_plan]) / mensal[col_so_plan] * 100.0),
        0.0,
    )

    dim_map = dict(zip(dim_cols, DIMS_NIVEL_1))

    persistentes: List[Dict[str, Any]] = []
    for chave, grupo in mensal.groupby(dim_cols, sort=False):
        if not isinstance(chave, tuple):
            chave = (chave,)
        grupo_ord = grupo.sort_values("_ano_mes")
        desvios = grupo_ord["_desvio_pct"].values
        if len(desvios) < min_meses:
            continue

        meses_consec = _contar_meses_consecutivos_mesmo_sinal(desvios)
        if meses_consec < min_meses:
            continue

        media_desvio = round(float(np.mean(desvios[-meses_consec:])), 2)
        direcao = "acima" if media_desvio > 0 else "abaixo"

        item: Dict[str, Any] = {
            "meses_consecutivos": meses_consec,
            "media_desvio_pct": media_desvio,
            "direcao": direcao,
            "total_meses_dados": len(desvios),
        }
        for col_df, col_canon in dim_map.items():
            val = grupo_ord[col_df].iloc[0]
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
            item[key] = str(val) if val is not None and not pd.isna(val) else ""
        persistentes.append(item)

    persistentes.sort(key=lambda p: abs(p["media_desvio_pct"]), reverse=True)

    resumo: Dict[str, Any] = {
        "total": len(persistentes),
        "acima": sum(1 for p in persistentes if p["direcao"] == "acima"),
        "abaixo": sum(1 for p in persistentes if p["direcao"] == "abaixo"),
        "min_meses": min_meses,
    }
    return {"persistentes": persistentes, "resumo": resumo}


def _contar_meses_consecutivos_mesmo_sinal(valores: "np.ndarray") -> int:
    """
    Conta meses consecutivos com desvio no mesmo sinal, do fim para o inicio.

    Ignora valores exatamente zero.
    """
    if len(valores) == 0:
        return 0
    ultimo = valores[-1]
    if ultimo == 0:
        return 0
    sinal_ultimo = ultimo > 0
    contagem = 0
    for v in reversed(valores):
        if v == 0:
            break
        if (v > 0) == sinal_ultimo:
            contagem += 1
        else:
            break
    return contagem
