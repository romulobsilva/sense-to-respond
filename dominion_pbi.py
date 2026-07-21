"""
Dominion PBI: execute DAX catalog via MCP/REST client and adapt to Sinal.

ADR-0025 PoC. Numbers come from the semantic model; adapter only maps
rows into existing signal types consumed by Optimus.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from config import DomainThresholds
from powerbi_catalog import (
    CatalogDocument,
    CatalogQuery,
    carregar_catalogo_dax,
    resolver_artifact_id,
)
from powerbi_mcp import PowerBIQueryClient, PowerBIQueryError
from state_types import Sinal


def executar_catalogo_pbi(
    catalog: CatalogDocument,
    artifact_id: str,
    client: PowerBIQueryClient,
) -> Dict[str, Any]:
    """
    Execute every catalog query via ExecuteQuery-equivalent client.

    Returns:
        {
          "resultados_pbi": {query_id: {columns, rows, meta}},
          "catalog_execucao": [{query_id, ok, erro?, n_rows}],
        }
    """
    resultados: Dict[str, Any] = {}
    execucao: List[Dict[str, Any]] = []

    queries: Sequence[CatalogQuery] = catalog.get("queries", [])
    for query in queries:
        query_id = query["query_id"]
        max_rows = int(query.get("max_rows", 250))
        try:
            result = client.execute_query(
                artifact_id=artifact_id,
                dax=query["dax"],
                max_rows=max_rows,
                query_id=query_id,
            )
            resultados[query_id] = {
                "columns": list(result.columns),
                "rows": [list(r) for r in result.rows],
                "meta": dict(result.meta),
            }
            execucao.append(
                {
                    "query_id": query_id,
                    "ok": True,
                    "n_rows": len(result.rows),
                }
            )
        except (PowerBIQueryError, OSError, ValueError) as exc:
            resultados[query_id] = {
                "columns": [],
                "rows": [],
                "meta": {"error": str(exc)},
            }
            execucao.append(
                {
                    "query_id": query_id,
                    "ok": False,
                    "erro": str(exc),
                    "n_rows": 0,
                }
            )

    return {
        "resultados_pbi": resultados,
        "catalog_execucao": execucao,
    }


def _row_as_dict(columns: Sequence[str], row: Sequence[Any]) -> Dict[str, Any]:
    """Zip columns with row values."""
    out: Dict[str, Any] = {}
    for index, col in enumerate(columns):
        out[col] = row[index] if index < len(row) else None
    return out


def _get_cell(row: Mapping[str, Any], *keys: str) -> Any:
    """Return first present key value (exact then suffix match)."""
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    # Power BI often prefixes with table name: "Fact_S2R Country"
    for key in keys:
        for col, value in row.items():
            if col.endswith(f" {key}") or col.endswith(key):
                if value is not None:
                    return value
    return None


def _to_float(value: Any, default: float = 0.0) -> float:
    """Safe float conversion."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def adaptar_resultados_pbi_para_sinais(
    resultados_pbi: Mapping[str, Any],
    thresholds: Optional[DomainThresholds] = None,
) -> List[Sinal]:
    """
    Map catalog result tables into Sinal objects for Optimus.

    PoC mapping (Mondelez / generic alert catalog):
    - Q2_top_alertas Understock/Overstock -> doi_fora_politica
    - Q3_sta_por_categoria STA gap -> desvio_sellout (category grain)
    """
    th = thresholds if thresholds is not None else DomainThresholds()
    sinais: List[Sinal] = []
    contador = 0

    alertas = resultados_pbi.get("Q2_top_alertas")
    if isinstance(alertas, Mapping):
        columns = alertas.get("columns")
        rows = alertas.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            for row_raw in rows:
                if not isinstance(row_raw, list):
                    continue
                row = _row_as_dict([str(c) for c in columns], row_raw)
                status = str(
                    _get_cell(row, "DOIStatus", "DOI Status") or ""
                ).strip()
                status_l = status.lower()
                if status_l not in ("understock", "overstock"):
                    continue

                doi_actual = _to_float(
                    _get_cell(row, "DOIActualDays", "DOI Actual (Days)")
                )
                sellout = _to_float(
                    _get_cell(row, "SellOutActualTon", "SellOut Actual (Ton)")
                )
                sku = str(
                    _get_cell(row, "SKU_Code", "Fact_S2R SKU_Code") or ""
                )
                if not sku:
                    continue

                # Understock: actual below target -> gap negativo
                # Overstock: actual above target -> gap positivo
                if status_l == "understock":
                    referencia = doi_actual + th.limiar_doi_gap_media
                else:
                    referencia = max(doi_actual - th.limiar_doi_gap_media, 0.0)

                gap = doi_actual - referencia
                desvio_pct = 0.0
                if referencia > 0:
                    desvio_pct = round((gap / referencia) * 100.0, 2)

                abs_gap = abs(gap)
                if abs_gap >= th.limiar_doi_gap_alta:
                    severidade = "alta"
                elif abs_gap >= th.limiar_doi_gap_media:
                    severidade = "media"
                else:
                    severidade = "baixa"

                contador += 1
                sinais.append(
                    Sinal(
                        sinal_id=f"SIG-PBI-DOI-{contador:03d}",
                        tipo="doi_fora_politica",
                        sku=sku,
                        canal="geral",
                        metrica="doi_dias",
                        valor=doi_actual,
                        referencia=referencia,
                        desvio_pct=desvio_pct,
                        severidade=severidade,
                        pais=str(
                            _get_cell(row, "Country", "Fact_S2R Country") or ""
                        ),
                        categoria=str(
                            _get_cell(row, "Category", "Fact_S2R Category") or ""
                        ),
                        marca=str(
                            _get_cell(row, "Brand", "Fact_S2R Brand") or ""
                        ),
                        nr_impacto=sellout,
                    )
                )

    sta = resultados_pbi.get("Q3_sta_por_categoria")
    if isinstance(sta, Mapping):
        columns = sta.get("columns")
        rows = sta.get("rows")
        if isinstance(columns, list) and isinstance(rows, list):
            for row_raw in rows:
                if not isinstance(row_raw, list):
                    continue
                row = _row_as_dict([str(c) for c in columns], row_raw)
                categoria = str(
                    _get_cell(row, "Category", "Fact_S2R Category") or ""
                )
                if not categoria:
                    continue
                actual = _to_float(
                    _get_cell(row, "SellOutActualTon", "SellOut Actual (Ton)")
                )
                plan = _to_float(
                    _get_cell(row, "SellOutPlanTon", "SellOut Plan (Ton)")
                )
                sta_pct = _to_float(_get_cell(row, "StaSoPct", "% STA SO"))
                # STA as fraction (0-1) or already percent
                if 0.0 <= sta_pct <= 1.5:
                    desvio_pct = round((sta_pct - 1.0) * 100.0, 2)
                else:
                    desvio_pct = round(sta_pct - 100.0, 2)

                if abs(desvio_pct) < th.limiar_desvio_pct:
                    continue

                if abs(desvio_pct) >= th.limiar_desvio_severo_pct:
                    severidade = "alta"
                else:
                    severidade = "media"

                contador += 1
                sinais.append(
                    Sinal(
                        sinal_id=f"SIG-PBI-SO-{contador:03d}",
                        tipo="desvio_sellout",
                        sku=categoria,
                        canal="geral",
                        metrica="sellout_ton",
                        valor=actual,
                        referencia=plan,
                        desvio_pct=desvio_pct,
                        severidade=severidade,
                        categoria=categoria,
                        nr_impacto=abs(actual - plan),
                    )
                )

    return sinais


def rodar_dominion_pbi(
    *,
    catalog_path: str,
    artifact_id_env: Optional[str],
    client: PowerBIQueryClient,
    thresholds: Optional[DomainThresholds] = None,
) -> Dict[str, Any]:
    """
    Full Dominion PBI phase: load catalog, execute, adapt signals.

    Returns dict ready to merge into Nexus state.
    """
    catalog = carregar_catalogo_dax(catalog_path)
    artifact_id = resolver_artifact_id(catalog, env_value=artifact_id_env)
    exec_out = executar_catalogo_pbi(catalog, artifact_id, client)
    resultados_pbi = exec_out["resultados_pbi"]
    sinais = adaptar_resultados_pbi_para_sinais(
        resultados_pbi,
        thresholds=thresholds,
    )
    return {
        "fonte_dados": "pbi",
        "pbi_catalog_id": catalog.get("catalog_id"),
        "pbi_artifact_id": artifact_id,
        "resultados_pbi": resultados_pbi,
        "catalog_execucao": exec_out["catalog_execucao"],
        "sinais": [s.para_dict() for s in sinais],
        "resultados": {
            "dominion_pbi": {
                "catalog_id": catalog.get("catalog_id"),
                "n_queries_ok": sum(
                    1
                    for item in exec_out["catalog_execucao"]
                    if item.get("ok")
                ),
                "n_sinais": len(sinais),
            }
        },
    }
