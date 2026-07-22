"""
Thin Power BI query connector for Dominion PBI (ADR-0025).

Batch path uses ExecuteQuery semantics only (no GenerateQuery).
Auth tokens are never logged or written to git.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, runtime_checkable


class PowerBIQueryError(RuntimeError):
    """Raised when a Power BI query cannot be executed."""


@dataclass(frozen=True)
class QueryResult:
    """Normalized ExecuteQuery result."""

    columns: List[str]
    rows: List[List[Any]]
    meta: Dict[str, Any]


@runtime_checkable
class PowerBIQueryClient(Protocol):
    """Minimal client used by dominion_pbi."""

    def execute_query(
        self,
        artifact_id: str,
        dax: str,
        max_rows: int = 250,
        query_id: Optional[str] = None,
    ) -> QueryResult:
        """Execute one EVALUATE statement against a semantic model."""


class FixturePowerBIClient:
    """
    Offline client for CI: returns canned rows keyed by query_id.
    """

    def __init__(self, fixture_path: str | Path) -> None:
        """
        Args:
            fixture_path: JSON file with {query_id: {columns, rows}} map.
        """
        caminho = Path(fixture_path)
        if not caminho.is_file():
            raise FileNotFoundError(f"Fixture PBI nao encontrada: {caminho}")
        with caminho.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, Mapping):
            raise PowerBIQueryError("Fixture PBI deve ser um objeto JSON.")
        self._data: Dict[str, Any] = dict(raw)

    def execute_query(
        self,
        artifact_id: str,
        dax: str,
        max_rows: int = 250,
        query_id: Optional[str] = None,
    ) -> QueryResult:
        """Return fixture payload for query_id (required in fixture mode)."""
        del dax  # catalog DAX is authoritative; fixture is keyed by id
        if not query_id:
            raise PowerBIQueryError(
                "FixturePowerBIClient exige query_id para localizar a resposta."
            )
        payload = self._data.get(query_id)
        if not isinstance(payload, Mapping):
            raise PowerBIQueryError(
                f"Fixture sem entrada para query_id='{query_id}'."
            )
        columns_raw = payload.get("columns")
        rows_raw = payload.get("rows")
        if not isinstance(columns_raw, list) or not isinstance(rows_raw, list):
            raise PowerBIQueryError(
                f"Fixture '{query_id}' precisa de columns[] e rows[]."
            )
        columns = [str(c) for c in columns_raw]
        rows: List[List[Any]] = []
        for row in rows_raw[:max_rows]:
            if isinstance(row, list):
                rows.append(list(row))
            elif isinstance(row, Mapping):
                rows.append([row.get(col) for col in columns])
            else:
                raise PowerBIQueryError(
                    f"Fixture '{query_id}' tem row invalida."
                )
        return QueryResult(
            columns=columns,
            rows=rows,
            meta={
                "source": "fixture",
                "artifact_id": artifact_id,
                "query_id": query_id,
                "n_rows": len(rows),
            },
        )


class RestPowerBIClient:
    """
    Live client using Power BI REST executeQueries.

    Requires a bearer token in memory (from env). Never persists the token.
    """

    def __init__(
        self,
        access_token: str,
        api_base: str = "https://api.powerbi.com/v1.0/myorg",
        timeout_sec: float = 60.0,
    ) -> None:
        """
        Args:
            access_token: Entra bearer token with Dataset.Read.All.
            api_base: Power BI REST base URL.
            timeout_sec: HTTP timeout.
        """
        token = access_token.strip()
        if not token:
            raise PowerBIQueryError("PBI_ACCESS_TOKEN vazio.")
        self._token = token
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout_sec

    def execute_query(
        self,
        artifact_id: str,
        dax: str,
        max_rows: int = 250,
        query_id: Optional[str] = None,
    ) -> QueryResult:
        """POST executeQueries and normalize table rows."""
        if not artifact_id.strip():
            raise PowerBIQueryError("artifact_id vazio.")
        if "EVALUATE" not in dax.upper():
            raise PowerBIQueryError("DAX deve conter EVALUATE.")

        url = f"{self._api_base}/datasets/{artifact_id}/executeQueries"
        body = {
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise PowerBIQueryError(
                f"Power BI HTTP {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise PowerBIQueryError(
                f"Falha de rede no Power BI: {exc.reason}"
            ) from exc

        return _parse_execute_queries_payload(
            payload,
            artifact_id=artifact_id,
            query_id=query_id,
            max_rows=max_rows,
        )


def _normalize_rest_column_name(name: str) -> str:
    """
    Map REST executeQueries keys to catalog/fixture style names.

    Power BI REST often returns:
      - "[DOIStatus]" -> "DOIStatus"
      - "Fact_S2R[Country]" -> "Fact_S2R Country"
    MCP/fixture use the unbracketed / space form; without this remap
    the Dominion adapter drops every row (sinais=0).
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


def _parse_execute_queries_payload(
    payload: Mapping[str, Any],
    *,
    artifact_id: str,
    query_id: Optional[str],
    max_rows: int,
) -> QueryResult:
    """Normalize Power BI executeQueries JSON into QueryResult."""
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise PowerBIQueryError("Resposta Power BI sem results[].")
    first = results[0]
    if not isinstance(first, Mapping):
        raise PowerBIQueryError("results[0] invalido.")
    if first.get("error"):
        raise PowerBIQueryError(f"Erro DAX: {first.get('error')}")
    tables = first.get("tables")
    if not isinstance(tables, list) or not tables:
        return QueryResult(
            columns=[],
            rows=[],
            meta={
                "source": "rest",
                "artifact_id": artifact_id,
                "query_id": query_id,
                "n_rows": 0,
            },
        )
    table0 = tables[0]
    if not isinstance(table0, Mapping):
        raise PowerBIQueryError("tables[0] invalido.")
    rows_raw = table0.get("rows")
    if not isinstance(rows_raw, list):
        rows_raw = []

    raw_keys: List[str] = []
    columns: List[str] = []
    rows: List[List[Any]] = []
    for row in rows_raw[:max_rows]:
        if not isinstance(row, Mapping):
            continue
        if not raw_keys:
            raw_keys = [str(k) for k in row.keys()]
            columns = [_normalize_rest_column_name(k) for k in raw_keys]
        rows.append([row.get(k) for k in raw_keys])

    return QueryResult(
        columns=columns,
        rows=rows,
        meta={
            "source": "rest",
            "artifact_id": artifact_id,
            "query_id": query_id,
            "n_rows": len(rows),
        },
    )


def criar_cliente_pbi(
    *,
    fixture_path: Optional[str] = None,
    access_token: Optional[str] = None,
) -> PowerBIQueryClient:
    """
    Factory: prefer fixture (CI), else REST token (smoke manual).

    Raises:
        PowerBIQueryError: Neither fixture nor token configured.
    """
    if fixture_path and fixture_path.strip():
        return FixturePowerBIClient(fixture_path.strip())
    if access_token and access_token.strip():
        return RestPowerBIClient(access_token.strip())
    raise PowerBIQueryError(
        "Configure PBI_FIXTURE_PATH (CI) ou PBI_ACCESS_TOKEN (live)."
    )
