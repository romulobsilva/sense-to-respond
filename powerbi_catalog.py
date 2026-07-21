"""
Loader and validator for Power BI DAX catalogs (ADR-0025).

ASCII only. Network is never called here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, TypedDict

import yaml


class CatalogValidationError(ValueError):
    """Raised when a catalog YAML fails contract checks."""


class CatalogQuery(TypedDict, total=False):
    """Single catalog query entry."""

    query_id: str
    description: str
    dax: str
    max_rows: int
    expected_columns: List[str]
    grain: str
    uom: Dict[str, Any]
    maps_to_signal_types: List[str]


class CatalogDocument(TypedDict, total=False):
    """Validated catalog document."""

    catalog_id: str
    display_name: str
    artifact_id_env: str
    artifact_id_default: Optional[str]
    domain: str
    notes: str
    queries: List[CatalogQuery]


REQUIRED_TOP = (
    "catalog_id",
    "display_name",
    "artifact_id_env",
    "domain",
    "queries",
)

REQUIRED_QUERY = (
    "query_id",
    "description",
    "dax",
    "expected_columns",
)


def _as_nonempty_str(value: Any, field_name: str) -> str:
    """Validate a required non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise CatalogValidationError(
            f"Campo '{field_name}' deve ser string nao vazia."
        )
    return value.strip()


def _validate_query(raw: Any, index: int) -> CatalogQuery:
    """Validate one query object from YAML."""
    if not isinstance(raw, Mapping):
        raise CatalogValidationError(
            f"queries[{index}] deve ser um objeto."
        )
    for key in REQUIRED_QUERY:
        if key not in raw:
            raise CatalogValidationError(
                f"queries[{index}] sem campo obrigatorio '{key}'."
            )

    query_id = _as_nonempty_str(raw.get("query_id"), f"queries[{index}].query_id")
    description = _as_nonempty_str(
        raw.get("description"),
        f"queries[{index}].description",
    )
    dax = _as_nonempty_str(raw.get("dax"), f"queries[{index}].dax")
    if "EVALUATE" not in dax.upper():
        raise CatalogValidationError(
            f"queries[{index}] ({query_id}): dax deve conter EVALUATE."
        )

    expected_raw = raw.get("expected_columns")
    if not isinstance(expected_raw, list) or not expected_raw:
        raise CatalogValidationError(
            f"queries[{index}] ({query_id}): expected_columns deve ser lista nao vazia."
        )
    expected_columns: List[str] = []
    for col_i, col in enumerate(expected_raw):
        if not isinstance(col, str) or not col.strip():
            raise CatalogValidationError(
                f"queries[{index}].expected_columns[{col_i}] invalido."
            )
        expected_columns.append(col.strip())

    max_rows = 250
    if "max_rows" in raw and raw.get("max_rows") is not None:
        max_raw = raw.get("max_rows")
        if not isinstance(max_raw, int) or max_raw < 1:
            raise CatalogValidationError(
                f"queries[{index}] ({query_id}): max_rows deve ser int >= 1."
            )
        max_rows = max_raw

    query: CatalogQuery = {
        "query_id": query_id,
        "description": description,
        "dax": dax,
        "max_rows": max_rows,
        "expected_columns": expected_columns,
    }

    grain = raw.get("grain")
    if isinstance(grain, str) and grain.strip():
        query["grain"] = grain.strip()

    uom = raw.get("uom")
    if isinstance(uom, dict):
        query["uom"] = dict(uom)

    maps = raw.get("maps_to_signal_types")
    if isinstance(maps, list):
        cleaned: List[str] = []
        for item in maps:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        query["maps_to_signal_types"] = cleaned

    return query


def carregar_catalogo_dax(path: str | Path) -> CatalogDocument:
    """
    Load and validate a DAX catalog YAML against the PoC contract.

    Args:
        path: Filesystem path to the catalog YAML.

    Returns:
        Validated catalog document.

    Raises:
        CatalogValidationError: Invalid structure or missing fields.
        FileNotFoundError: Path does not exist.
        yaml.YAMLError: Invalid YAML syntax.
    """
    caminho = Path(path)
    if not caminho.is_file():
        raise FileNotFoundError(f"Catalogo DAX nao encontrado: {caminho}")

    with caminho.open("r", encoding="utf-8") as handle:
        raw_doc = yaml.safe_load(handle)

    if not isinstance(raw_doc, MutableMapping):
        raise CatalogValidationError("Catalogo deve ser um objeto YAML no topo.")

    for key in REQUIRED_TOP:
        if key not in raw_doc:
            raise CatalogValidationError(
                f"Catalogo sem campo obrigatorio '{key}'."
            )

    catalog_id = _as_nonempty_str(raw_doc.get("catalog_id"), "catalog_id")
    display_name = _as_nonempty_str(raw_doc.get("display_name"), "display_name")
    artifact_id_env = _as_nonempty_str(
        raw_doc.get("artifact_id_env"),
        "artifact_id_env",
    )
    domain = _as_nonempty_str(raw_doc.get("domain"), "domain")

    queries_raw = raw_doc.get("queries")
    if not isinstance(queries_raw, list) or not queries_raw:
        raise CatalogValidationError("queries deve ser lista nao vazia.")

    queries: List[CatalogQuery] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(queries_raw):
        query = _validate_query(item, index)
        qid = query["query_id"]
        if qid in seen_ids:
            raise CatalogValidationError(f"query_id duplicado: {qid}")
        seen_ids.add(qid)
        queries.append(query)

    artifact_default: Optional[str] = None
    default_raw = raw_doc.get("artifact_id_default")
    if isinstance(default_raw, str) and default_raw.strip():
        artifact_default = default_raw.strip()

    notes = ""
    notes_raw = raw_doc.get("notes")
    if isinstance(notes_raw, str):
        notes = notes_raw.strip()

    return {
        "catalog_id": catalog_id,
        "display_name": display_name,
        "artifact_id_env": artifact_id_env,
        "artifact_id_default": artifact_default,
        "domain": domain,
        "notes": notes,
        "queries": queries,
    }


def resolver_artifact_id(
    catalog: CatalogDocument,
    env_value: Optional[str] = None,
) -> str:
    """
    Resolve semantic model GUID from env override or catalog default.

    Args:
        catalog: Validated catalog.
        env_value: Value from settings / environment (preferred).

    Returns:
        Non-empty artifact GUID string.
    """
    if isinstance(env_value, str) and env_value.strip():
        return env_value.strip()
    default = catalog.get("artifact_id_default")
    if isinstance(default, str) and default.strip():
        return default.strip()
    env_name = catalog.get("artifact_id_env", "PBI_ARTIFACT_ID")
    raise CatalogValidationError(
        f"Artifact id ausente. Defina {env_name} ou artifact_id_default."
    )
