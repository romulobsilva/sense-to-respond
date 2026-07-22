"""
Dominion PBI: execute DAX catalog via MCP/REST client and adapt to Sinal.

ADR-0025 / planning 1.7a.2-1.7a.3. Numbers come from the semantic model;
adapter only maps rows into existing signal types consumed by Optimus.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from config import DomainThresholds
from powerbi_catalog import (
    CatalogDocument,
    CatalogQuery,
    carregar_catalogo_dax,
    resolver_artifact_id,
)
from powerbi_mcp import PowerBIQueryClient, PowerBIQueryError
from state_types import Sinal

# Queries that feed Optimus prioritization (Daniel / path-B validation).
QUERIES_PRIORIZACAO: Tuple[str, ...] = (
    "Q2_top_alertas",
    "Q4_forward_risco",
    "Q5_forward_oportunidade",
)


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


def _normalize_column_key(name: str) -> str:
    """
    Normalize REST/MCP column labels for lookup.

    Handles "[DOIStatus]" and "Fact_S2R[Country]" as well as
    already-normalized "DOIStatus" / "Fact_S2R Country".
    """
    raw = str(name).strip()
    if not raw:
        return raw
    if raw.startswith("[") and raw.endswith("]") and "[" not in raw[1:-1]:
        return raw[1:-1]
    if "[" in raw and raw.endswith("]"):
        table, _sep, rest = raw.partition("[")
        col = rest[:-1].strip()
        table_s = table.strip()
        if table_s and col:
            return f"{table_s} {col}"
        if col:
            return col
    return raw


def _get_cell(row: Mapping[str, Any], *keys: str) -> Any:
    """Return first present key value (exact then suffix match)."""
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]

    normalized: Dict[str, Any] = {}
    for col, value in row.items():
        normalized[_normalize_column_key(str(col))] = value

    for key in keys:
        if key in normalized and normalized[key] is not None:
            return normalized[key]

    # Power BI often prefixes with table name: "Fact_S2R Country"
    for key in keys:
        for col, value in normalized.items():
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


def _si_gap_as_pct(raw: float) -> float:
    """
    Normalize SI Gap % from model (fraction 0-1 or percent).

    Returns percent points (e.g. -31.0 for -0.31 fraction).
    """
    if -1.5 <= raw <= 1.5:
        return round(raw * 100.0, 2)
    return round(raw, 2)


def _severidade_gap_dias(abs_gap: float, th: DomainThresholds) -> str:
    """Map absolute DOI gap days to severidade."""
    if abs_gap >= th.limiar_doi_gap_alta:
        return "alta"
    if abs_gap >= th.limiar_doi_gap_media:
        return "media"
    return "baixa"


def _iter_table_rows(
    resultados_pbi: Mapping[str, Any],
    query_id: str,
) -> List[Dict[str, Any]]:
    """Return list of row dicts for a query_id, or empty."""
    bloco = resultados_pbi.get(query_id)
    if not isinstance(bloco, Mapping):
        return []
    columns = bloco.get("columns")
    rows = bloco.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for row_raw in rows:
        if not isinstance(row_raw, list):
            continue
        out.append(_row_as_dict([str(c) for c in columns], row_raw))
    return out


def _doi_referencia_e_metrica(
    doi_actual: float,
    doi_ideal: float,
    status_l: str,
    th: DomainThresholds,
) -> Tuple[float, str]:
    """
    Resolve DOI target: Policy Ideal when available, else PoC limiar.

    Returns:
        (referencia_dias, metrica_tag)
    """
    if doi_ideal > 0:
        return doi_ideal, "doi_dias_policy"
    if status_l == "understock":
        return doi_actual + th.limiar_doi_gap_media, "doi_dias_poc"
    return max(doi_actual - th.limiar_doi_gap_media, 0.0), "doi_dias_poc"


def _adaptar_q2_doi(
    resultados_pbi: Mapping[str, Any],
    th: DomainThresholds,
    contador: int,
) -> Tuple[List[Sinal], int]:
    """Q2_top_alertas -> doi_fora_politica."""
    sinais: List[Sinal] = []
    for row in _iter_table_rows(resultados_pbi, "Q2_top_alertas"):
        status = str(_get_cell(row, "DOIStatus", "DOI Status") or "").strip()
        status_l = status.lower()
        if status_l not in ("understock", "overstock"):
            continue

        doi_actual = _to_float(
            _get_cell(row, "DOIActualDays", "DOI Actual (Days)", "DOIActual")
        )
        doi_ideal = _to_float(
            _get_cell(row, "DOIIdealDays", "DOIIdeal", "Policy DOI Ideal")
        )
        sellout = _to_float(
            _get_cell(row, "SellOutActualTon", "SellOut Actual (Ton)")
        )
        nr_usd = _to_float(
            _get_cell(row, "SellOutActualNrUsd", "NRImpact", "SellOut Actual (NR USD)")
        )
        sku = str(_get_cell(row, "SKU_Code", "Fact_S2R SKU_Code") or "")
        if not sku:
            continue

        referencia, metrica = _doi_referencia_e_metrica(
            doi_actual, doi_ideal, status_l, th
        )
        gap = doi_actual - referencia
        desvio_pct = 0.0
        if referencia > 0:
            desvio_pct = round((gap / referencia) * 100.0, 2)

        contador += 1
        sinais.append(
            Sinal(
                sinal_id=f"SIG-PBI-DOI-{contador:03d}",
                tipo="doi_fora_politica",
                sku=sku,
                canal=str(_get_cell(row, "Channel", "Fact_S2R Channel") or "geral"),
                metrica=metrica,
                valor=doi_actual,
                referencia=referencia,
                desvio_pct=desvio_pct,
                severidade=_severidade_gap_dias(abs(gap), th),
                pais=str(_get_cell(row, "Country", "Fact_S2R Country") or ""),
                categoria=str(
                    _get_cell(row, "Category", "Fact_S2R Category") or ""
                ),
                marca=str(_get_cell(row, "Brand", "Fact_S2R Brand") or ""),
                nr_impacto=nr_usd if nr_usd > 0 else sellout,
            )
        )
    return sinais, contador


def _adaptar_q3_sellout(
    resultados_pbi: Mapping[str, Any],
    th: DomainThresholds,
    contador: int,
) -> Tuple[List[Sinal], int]:
    """Q3_sta_por_categoria -> desvio_sellout."""
    sinais: List[Sinal] = []
    for row in _iter_table_rows(resultados_pbi, "Q3_sta_por_categoria"):
        categoria = str(_get_cell(row, "Category", "Fact_S2R Category") or "")
        if not categoria:
            continue
        actual = _to_float(
            _get_cell(row, "SellOutActualTon", "SellOut Actual (Ton)")
        )
        plan = _to_float(_get_cell(row, "SellOutPlanTon", "SellOut Plan (Ton)"))
        sta_pct = _to_float(_get_cell(row, "StaSoPct", "% STA SO"))
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
    return sinais, contador


def _adaptar_q4_forward(
    resultados_pbi: Mapping[str, Any],
    th: DomainThresholds,
    contador: int,
) -> Tuple[List[Sinal], int]:
    """Q4_forward_risco -> premissa_forward_furada."""
    sinais: List[Sinal] = []
    limiar = float(th.limiar_premissa_furada_pct)
    for row in _iter_table_rows(resultados_pbi, "Q4_forward_risco"):
        status = str(_get_cell(row, "DOIStatus", "DOI Status") or "").strip()
        status_l = status.lower()
        if status_l not in ("understock", "overstock"):
            continue

        sku = str(_get_cell(row, "SKU_Code", "Fact_S2R SKU_Code") or "")
        if not sku:
            continue

        doi_actual = _to_float(_get_cell(row, "DOIActual", "DOI Actual (Days)"))
        doi_plan = _to_float(_get_cell(row, "DOIPlan", "DOI Plan (Days)"))
        si_gap_pct = _si_gap_as_pct(_to_float(_get_cell(row, "SIGapPct", "SI Gap %")))
        nr_usd = _to_float(
            _get_cell(row, "NRImpact", "SellOut Actual (NR USD)")
        )
        so_actual = _to_float(_get_cell(row, "SOActual", "SellOut Actual (Ton)"))

        # Premissa furada: SI gap beyond threshold, or DOI vs plan gap.
        doi_vs_plan_pct = 0.0
        if doi_plan > 0:
            doi_vs_plan_pct = round(
                ((doi_actual - doi_plan) / doi_plan) * 100.0, 2
            )
        if abs(si_gap_pct) < limiar and abs(doi_vs_plan_pct) < limiar:
            continue

        if status_l == "understock":
            risco = "ruptura"
        else:
            risco = "overstock"

        desvio_pct = si_gap_pct if abs(si_gap_pct) >= abs(doi_vs_plan_pct) else doi_vs_plan_pct
        if abs(desvio_pct) >= th.limiar_desvio_severo_pct:
            severidade = "alta"
        else:
            severidade = "media"

        contador += 1
        sinais.append(
            Sinal(
                sinal_id=f"SIG-PBI-FWD-{contador:03d}",
                tipo="premissa_forward_furada",
                sku=sku,
                canal=str(
                    _get_cell(row, "Channel", "Fact_S2R Channel") or "geral"
                ),
                metrica="forward_doi_plan",
                valor=doi_actual,
                referencia=doi_plan if doi_plan > 0 else doi_actual,
                desvio_pct=desvio_pct,
                severidade=severidade,
                pais=str(_get_cell(row, "Country", "Fact_S2R Country") or ""),
                categoria=str(
                    _get_cell(row, "Category", "Fact_S2R Category") or ""
                ),
                marca=str(_get_cell(row, "Brand", "Fact_S2R Brand") or ""),
                risco_forward=risco,
                nr_impacto=nr_usd if nr_usd > 0 else so_actual,
            )
        )
    return sinais, contador


def _adaptar_q5_oportunidade(
    resultados_pbi: Mapping[str, Any],
    th: DomainThresholds,
    contador: int,
) -> Tuple[List[Sinal], int]:
    """Q5_forward_oportunidade -> forward_oportunidade."""
    sinais: List[Sinal] = []
    for row in _iter_table_rows(resultados_pbi, "Q5_forward_oportunidade"):
        status = str(_get_cell(row, "DOIStatus", "DOI Status") or "").strip()
        if status.lower() != "understock":
            continue

        sku = str(_get_cell(row, "SKU_Code", "Fact_S2R SKU_Code") or "")
        if not sku:
            continue

        doi_actual = _to_float(_get_cell(row, "DOIActual", "DOI Actual (Days)"))
        doi_ideal = _to_float(
            _get_cell(row, "DOIIdeal", "Policy DOI Ideal", "DOIIdealDays")
        )
        if doi_ideal <= 0 or doi_actual <= 0 or doi_actual >= doi_ideal:
            continue

        nr_usd = _to_float(
            _get_cell(row, "NRImpact", "SellOut Actual (NR USD)")
        )
        so_actual = _to_float(_get_cell(row, "SOActual", "SellOut Actual (Ton)"))
        gap = doi_actual - doi_ideal
        desvio_pct = round((gap / doi_ideal) * 100.0, 2)

        contador += 1
        sinais.append(
            Sinal(
                sinal_id=f"SIG-PBI-OPP-{contador:03d}",
                tipo="forward_oportunidade",
                sku=sku,
                canal=str(
                    _get_cell(row, "Channel", "Fact_S2R Channel") or "geral"
                ),
                metrica="doi_oportunidade",
                valor=doi_actual,
                referencia=doi_ideal,
                desvio_pct=desvio_pct,
                severidade=_severidade_gap_dias(abs(gap), th),
                pais=str(_get_cell(row, "Country", "Fact_S2R Country") or ""),
                categoria=str(
                    _get_cell(row, "Category", "Fact_S2R Category") or ""
                ),
                marca=str(_get_cell(row, "Brand", "Fact_S2R Brand") or ""),
                risco_forward="oportunidade",
                nr_impacto=nr_usd if nr_usd > 0 else so_actual,
            )
        )
    return sinais, contador


def adaptar_resultados_pbi_para_sinais(
    resultados_pbi: Mapping[str, Any],
    thresholds: Optional[DomainThresholds] = None,
) -> List[Sinal]:
    """
    Map catalog result tables into Sinal objects for Optimus.

    Mapping (Mondelez catalog):
    - Q2_top_alertas -> doi_fora_politica (Policy Ideal when present)
    - Q3_sta_por_categoria -> desvio_sellout
    - Q4_forward_risco -> premissa_forward_furada
    - Q5_forward_oportunidade -> forward_oportunidade
    """
    th = thresholds if thresholds is not None else DomainThresholds()
    sinais: List[Sinal] = []
    contador = 0

    parte, contador = _adaptar_q2_doi(resultados_pbi, th, contador)
    sinais.extend(parte)
    parte, contador = _adaptar_q3_sellout(resultados_pbi, th, contador)
    sinais.extend(parte)
    parte, contador = _adaptar_q4_forward(resultados_pbi, th, contador)
    sinais.extend(parte)
    parte, contador = _adaptar_q5_oportunidade(resultados_pbi, th, contador)
    sinais.extend(parte)

    return sinais


def _client_source_hint(resultados_pbi: Mapping[str, Any]) -> str:
    """
    Infer fixture vs rest from QueryResult.meta.source when present.
    """
    sources: List[str] = []
    for bloco in resultados_pbi.values():
        if not isinstance(bloco, Mapping):
            continue
        meta = bloco.get("meta")
        if isinstance(meta, Mapping):
            src = meta.get("source")
            if isinstance(src, str) and src.strip():
                sources.append(src.strip().lower())
    if not sources:
        return "unknown"
    uniq = sorted(set(sources))
    if len(uniq) == 1:
        return uniq[0]
    return "mixed:" + ",".join(uniq)


def exportar_resultados_pbi_para_auditoria(
    *,
    resultados_pbi: Mapping[str, Any],
    catalog_execucao: Sequence[Mapping[str, Any]],
    sessao_id: str,
    pbi_catalog_id: Optional[str],
    pbi_artifact_id: Optional[str],
    diretorio: str | Path = "auditoria",
) -> Dict[str, str]:
    """
    Persist full catalog tables for path-B / Daniel validation.

    Writes two files under ``auditoria/`` (gitignored):
      - resultados_pbi_<sessao_id>.json  (immutable per session)
      - resultados_pbi_ultima.json       (always latest; easy handoff)

    Does NOT embed row dumps into ultima_sessao.json (ADR-0012).

    Returns:
        Paths as strings: {\"sessao\": ..., \"ultima\": ...}.
    """
    out_dir = Path(diretorio)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_id = sessao_id.strip() if sessao_id.strip() else "sem_sessao"
    # Keep only safe filename chars (ASCII).
    safe_id = "".join(
        ch if (ch.isalnum() or ch in "-_") else "-" for ch in safe_id
    )

    priorizacao: Dict[str, Any] = {}
    for qid in QUERIES_PRIORIZACAO:
        bloco = resultados_pbi.get(qid)
        if isinstance(bloco, Mapping):
            priorizacao[qid] = {
                "columns": list(bloco.get("columns") or []),
                "rows": list(bloco.get("rows") or []),
                "meta": dict(bloco.get("meta") or {})
                if isinstance(bloco.get("meta"), Mapping)
                else {},
            }

    payload: Dict[str, Any] = {
        "sessao_id": safe_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "fonte_dados": "pbi",
        "pbi_catalog_id": pbi_catalog_id,
        "pbi_artifact_id": pbi_artifact_id,
        "client_source": _client_source_hint(resultados_pbi),
        "catalog_execucao": [
            dict(item) for item in catalog_execucao if isinstance(item, Mapping)
        ],
        "queries_priorizacao": list(QUERIES_PRIORIZACAO),
        "resultados_pbi": {
            str(qid): {
                "columns": list(bloco.get("columns") or []),
                "rows": list(bloco.get("rows") or []),
                "meta": dict(bloco.get("meta") or {})
                if isinstance(bloco.get("meta"), Mapping)
                else {},
            }
            for qid, bloco in resultados_pbi.items()
            if isinstance(bloco, Mapping)
        },
        "resultados_pbi_priorizacao": priorizacao,
    }

    path_sessao = out_dir / f"resultados_pbi_{safe_id}.json"
    path_ultima = out_dir / "resultados_pbi_ultima.json"
    texto = json.dumps(payload, indent=2, ensure_ascii=True)
    path_sessao.write_text(texto, encoding="utf-8")
    path_ultima.write_text(texto, encoding="utf-8")
    return {
        "sessao": str(path_sessao.resolve()),
        "ultima": str(path_ultima.resolve()),
    }


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
