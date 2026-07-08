"""
Carrega configuracao a partir de variaveis de ambiente (.env).

Inclui DomainThresholds (ADR-0024) para portabilidade multi-dominio:
thresholds de DOI, desvio, janela temporal e marcador forward sao
configuraveis por cliente via .env, com defaults Mondelez.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


HITL_MODES_VALIDOS = frozenset({"terminal", "auto", "arquivo", "streamlit"})
FORWARD_MARKERS_VALIDOS = frozenset({"nan", "zero"})


@dataclass(frozen=True)
class DomainThresholds:
    """
    Thresholds configuraveis por dominio/cliente (ADR-0024).

    Defaults calibrados para Mondelez FMCG.
    """

    doi_ruptura_dias: float = 15.0
    doi_overstock_dias: float = 40.0
    limiar_desvio_pct: float = 5.0
    limiar_desvio_severo_pct: float = 10.0
    limiar_doi_gap_media: float = 7.0
    limiar_doi_gap_alta: float = 15.0
    limiar_tendencia_estavel_pct: float = 3.0
    limiar_premissa_furada_pct: float = 15.0
    limiar_aceleracao_pct: float = 5.0
    limiar_desvio_persistente_meses: int = 3
    janela_recente_dias: int = 30
    forward_marker: str = "nan"


@dataclass(frozen=True)
class Settings:
    """Configuracao da aplicacao."""

    openai_api_key: str
    openai_model: str
    limiar_confianca_critic: float
    max_optimus_retries: int
    hitl_mode: str
    thresholds: DomainThresholds
    schema_path: Optional[str] = None


def _read_float(name: str, default: str) -> float:
    """Le float do .env com validacao."""
    raw = os.getenv(name, default).strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um numero (recebido: '{raw}').") from exc


def _read_int(name: str, default: str) -> int:
    """Le int do .env com validacao."""
    raw = os.getenv(name, default).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um inteiro (recebido: '{raw}').") from exc


def _load_thresholds() -> DomainThresholds:
    """Carrega DomainThresholds de variaveis .env (todas opcionais)."""
    forward_marker = os.getenv("FORWARD_MARKER", "nan").strip().lower()
    if forward_marker not in FORWARD_MARKERS_VALIDOS:
        raise ValueError(
            f"FORWARD_MARKER '{forward_marker}' invalido. "
            f"Validos: {', '.join(sorted(FORWARD_MARKERS_VALIDOS))}"
        )

    return DomainThresholds(
        doi_ruptura_dias=_read_float("DOI_RUPTURA_DIAS", "15.0"),
        doi_overstock_dias=_read_float("DOI_OVERSTOCK_DIAS", "40.0"),
        limiar_desvio_pct=_read_float("LIMIAR_DESVIO_PCT", "5.0"),
        limiar_desvio_severo_pct=_read_float("LIMIAR_DESVIO_SEVERO_PCT", "10.0"),
        limiar_doi_gap_media=_read_float("LIMIAR_DOI_GAP_MEDIA", "7.0"),
        limiar_doi_gap_alta=_read_float("LIMIAR_DOI_GAP_ALTA", "15.0"),
        limiar_tendencia_estavel_pct=_read_float("LIMIAR_TENDENCIA_ESTAVEL_PCT", "3.0"),
        limiar_premissa_furada_pct=_read_float("LIMIAR_PREMISSA_FURADA_PCT", "15.0"),
        limiar_aceleracao_pct=_read_float("LIMIAR_ACELERACAO_PCT", "5.0"),
        limiar_desvio_persistente_meses=_read_int("LIMIAR_DESVIO_PERSISTENTE_MESES", "3"),
        janela_recente_dias=_read_int("JANELA_RECENTE_DIAS", "30"),
        forward_marker=forward_marker,
    )


def load_settings() -> Settings:
    """
    Le o arquivo .env (se existir) e valida variaveis obrigatorias.
    """
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY nao definida. Copie .env.example para .env e "
            "informe sua chave da OpenAI."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
    if not model:
        raise ValueError("OPENAI_MODEL nao pode ser vazio.")

    limiar_raw = os.getenv("LIMIAR_CONFIANCA_CRITIC", "0.7").strip()
    try:
        limiar_confianca = float(limiar_raw)
    except ValueError as exc:
        raise ValueError(
            "LIMIAR_CONFIANCA_CRITIC deve ser um numero entre 0 e 1."
        ) from exc
    if limiar_confianca < 0.0 or limiar_confianca > 1.0:
        raise ValueError("LIMIAR_CONFIANCA_CRITIC deve estar entre 0 e 1.")

    retries_raw = os.getenv("MAX_OPTIMUS_RETRIES", "1").strip()
    try:
        max_retries = int(retries_raw)
    except ValueError as exc:
        raise ValueError("MAX_OPTIMUS_RETRIES deve ser um inteiro.") from exc
    if max_retries < 0 or max_retries > 3:
        raise ValueError("MAX_OPTIMUS_RETRIES deve estar entre 0 e 3.")

    hitl_mode = os.getenv("HITL_MODE", "terminal").strip().lower()
    if hitl_mode not in HITL_MODES_VALIDOS:
        raise ValueError(
            f"HITL_MODE '{hitl_mode}' invalido. "
            f"Validos: {', '.join(sorted(HITL_MODES_VALIDOS))}"
        )

    thresholds = _load_thresholds()

    schema_path_raw = os.getenv("SCHEMA_PATH", "").strip()
    schema_path: Optional[str] = schema_path_raw if schema_path_raw else None

    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        limiar_confianca_critic=limiar_confianca,
        max_optimus_retries=max_retries,
        hitl_mode=hitl_mode,
        thresholds=thresholds,
        schema_path=schema_path,
    )
