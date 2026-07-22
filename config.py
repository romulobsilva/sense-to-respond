"""
Carrega configuracao a partir de variaveis de ambiente (.env).

Inclui DomainThresholds (ADR-0024) para portabilidade multi-dominio:
thresholds de DOI, desvio, janela temporal, marcador forward e pesos
de priorizacao sao configuraveis por cliente via .env, com defaults
Mondelez.
"""

import os
from dataclasses import dataclass
from typing import Dict, Optional

from dotenv import load_dotenv


HITL_MODES_VALIDOS = frozenset({"terminal", "auto", "arquivo", "streamlit"})
FORWARD_MARKERS_VALIDOS = frozenset({"nan", "zero"})
CHAT_PBI_TRANSPORTS_VALIDOS = frozenset({"mcp", "rest", "mock"})

# Defaults de peso de ordenacao (heuristica; so afetam sort, nao R$ bruto)
PESO_QUESTIONAR_PREMISSA_DEFAULT = 1.5
PESO_CAPTURAR_OPORTUNIDADE_DEFAULT = 1.4
PESO_INVESTIGAR_DESVIO_PERSISTENTE_DEFAULT = 1.1
PESO_TIPO_DEFAULT = 1.0


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
    peso_questionar_premissa_plano: float = PESO_QUESTIONAR_PREMISSA_DEFAULT
    peso_capturar_oportunidade: float = PESO_CAPTURAR_OPORTUNIDADE_DEFAULT
    peso_investigar_desvio_persistente: float = (
        PESO_INVESTIGAR_DESVIO_PERSISTENTE_DEFAULT
    )
    top_n_doi: int = 5
    top_n_forward: int = 5
    top_n_oportunidades: int = 5
    limiar_persistente_impacto: float = 100.0
    limiar_persistente_desvio_pct: float = 5.0

    def peso_tipo(self, tipo: str) -> float:
        """
        Multiplicador de prioridade por tipo de proposicao.

        Tipos sem peso explicito usam 1.0. Nao altera impacto financeiro.
        """
        mapa: Dict[str, float] = {
            "questionar_premissa_plano": self.peso_questionar_premissa_plano,
            "capturar_oportunidade": self.peso_capturar_oportunidade,
            "investigar_desvio_persistente": self.peso_investigar_desvio_persistente,
        }
        return float(mapa.get(tipo, PESO_TIPO_DEFAULT))


@dataclass(frozen=True)
class Settings:
    """Configuracao da aplicacao."""

    openai_api_key: str
    openai_model: str
    limiar_confianca_critic: float
    limiar_confianca_datashield: float
    max_optimus_retries: int
    hitl_mode: str
    thresholds: DomainThresholds
    schema_path: Optional[str] = None
    pbi_artifact_id: Optional[str] = None
    pbi_catalog_path: Optional[str] = None
    pbi_access_token: Optional[str] = None
    pbi_fixture_path: Optional[str] = None
    chat_pbi_transport: str = "mcp"
    pbi_mcp_url: Optional[str] = None
    chat_openai_model: Optional[str] = None


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

    peso_q = _read_float(
        "PESO_QUESTIONAR_PREMISSA",
        str(PESO_QUESTIONAR_PREMISSA_DEFAULT),
    )
    peso_o = _read_float(
        "PESO_CAPTURAR_OPORTUNIDADE",
        str(PESO_CAPTURAR_OPORTUNIDADE_DEFAULT),
    )
    peso_p = _read_float(
        "PESO_INVESTIGAR_DESVIO_PERSISTENTE",
        str(PESO_INVESTIGAR_DESVIO_PERSISTENTE_DEFAULT),
    )
    for nome, valor in (
        ("PESO_QUESTIONAR_PREMISSA", peso_q),
        ("PESO_CAPTURAR_OPORTUNIDADE", peso_o),
        ("PESO_INVESTIGAR_DESVIO_PERSISTENTE", peso_p),
    ):
        if valor <= 0.0:
            raise ValueError(f"{nome} deve ser > 0 (recebido: {valor}).")

    top_n_doi = _read_int("TOP_N_DOI", "5")
    top_n_fwd = _read_int("TOP_N_FORWARD", "5")
    top_n_o = _read_int("TOP_N_OPORTUNIDADES", "5")
    # Legado: se so TOP_N_RISCOS estiver setado, replica para doi e forward
    legado_raw = os.getenv("TOP_N_RISCOS", "").strip()
    if legado_raw and not os.getenv("TOP_N_DOI", "").strip() and not os.getenv("TOP_N_FORWARD", "").strip():
        top_n_doi = int(legado_raw)
        top_n_fwd = int(legado_raw)
    for nome, valor in (
        ("TOP_N_DOI", top_n_doi),
        ("TOP_N_FORWARD", top_n_fwd),
        ("TOP_N_OPORTUNIDADES", top_n_o),
    ):
        if valor < 1:
            raise ValueError(f"{nome} deve ser >= 1 (recebido: {valor}).")

    lim_imp = _read_float("LIMIAR_PERSISTENTE_IMPACTO", "100.0")
    lim_dev = _read_float("LIMIAR_PERSISTENTE_DESVIO_PCT", "5.0")
    if lim_imp < 0.0:
        raise ValueError(
            f"LIMIAR_PERSISTENTE_IMPACTO deve ser >= 0 (recebido: {lim_imp})."
        )
    if lim_dev < 0.0:
        raise ValueError(
            f"LIMIAR_PERSISTENTE_DESVIO_PCT deve ser >= 0 (recebido: {lim_dev})."
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
        peso_questionar_premissa_plano=peso_q,
        peso_capturar_oportunidade=peso_o,
        peso_investigar_desvio_persistente=peso_p,
        top_n_doi=top_n_doi,
        top_n_forward=top_n_fwd,
        top_n_oportunidades=top_n_o,
        limiar_persistente_impacto=lim_imp,
        limiar_persistente_desvio_pct=lim_dev,
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

    limiar_ds_raw = os.getenv("LIMIAR_CONFIANCA_DATASHIELD", "0.6").strip()
    try:
        limiar_confianca_ds = float(limiar_ds_raw)
    except ValueError as exc:
        raise ValueError(
            "LIMIAR_CONFIANCA_DATASHIELD deve ser um numero entre 0 e 1."
        ) from exc
    if limiar_confianca_ds < 0.0 or limiar_confianca_ds > 1.0:
        raise ValueError("LIMIAR_CONFIANCA_DATASHIELD deve estar entre 0 e 1.")

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

    pbi_artifact_raw = os.getenv("PBI_ARTIFACT_ID", "").strip()
    pbi_catalog_raw = os.getenv("PBI_CATALOG_PATH", "").strip()
    pbi_token_raw = os.getenv("PBI_ACCESS_TOKEN", "").strip()
    pbi_fixture_raw = os.getenv("PBI_FIXTURE_PATH", "").strip()
    chat_transport = os.getenv("CHAT_PBI_TRANSPORT", "mcp").strip().lower()
    if chat_transport not in CHAT_PBI_TRANSPORTS_VALIDOS:
        raise ValueError(
            f"CHAT_PBI_TRANSPORT '{chat_transport}' invalido. "
            f"Validos: {', '.join(sorted(CHAT_PBI_TRANSPORTS_VALIDOS))}"
        )
    pbi_mcp_url_raw = os.getenv("PBI_MCP_URL", "").strip()
    # Chat PBI (ADR-0026): default gpt-5.4 para paridade com chat IDE rico.
    # Batch / Critic continuam em OPENAI_MODEL. Override: CHAT_OPENAI_MODEL.
    chat_model_env = os.getenv("CHAT_OPENAI_MODEL")
    if chat_model_env is None:
        chat_model_raw = "gpt-5.4"
    else:
        chat_model_raw = chat_model_env.strip()
        if not chat_model_raw:
            chat_model_raw = model

    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        limiar_confianca_critic=limiar_confianca,
        limiar_confianca_datashield=limiar_confianca_ds,
        max_optimus_retries=max_retries,
        hitl_mode=hitl_mode,
        thresholds=thresholds,
        schema_path=schema_path,
        pbi_artifact_id=pbi_artifact_raw or None,
        pbi_catalog_path=pbi_catalog_raw or None,
        pbi_access_token=pbi_token_raw or None,
        pbi_fixture_path=pbi_fixture_raw or None,
        chat_pbi_transport=chat_transport,
        pbi_mcp_url=pbi_mcp_url_raw or None,
        chat_openai_model=chat_model_raw,
    )


def aplicar_overrides_thresholds(
    thresholds: DomainThresholds,
    top_n_doi: Optional[int] = None,
    top_n_forward: Optional[int] = None,
    top_n_oportunidades: Optional[int] = None,
    top_n_riscos: Optional[int] = None,
) -> DomainThresholds:
    """
    Aplica overrides de sessao (CLI) sobre DomainThresholds imutavel.

    ``top_n_riscos`` e legado: se informado sem doi/forward, aplica aos dois.
    """
    from dataclasses import replace

    kwargs: Dict[str, int] = {}
    if top_n_riscos is not None and top_n_doi is None and top_n_forward is None:
        if top_n_riscos < 1:
            raise ValueError("top_n_riscos deve ser >= 1.")
        kwargs["top_n_doi"] = top_n_riscos
        kwargs["top_n_forward"] = top_n_riscos
    if top_n_doi is not None:
        if top_n_doi < 1:
            raise ValueError("top_n_doi deve ser >= 1.")
        kwargs["top_n_doi"] = top_n_doi
    if top_n_forward is not None:
        if top_n_forward < 1:
            raise ValueError("top_n_forward deve ser >= 1.")
        kwargs["top_n_forward"] = top_n_forward
    if top_n_oportunidades is not None:
        if top_n_oportunidades < 1:
            raise ValueError("top_n_oportunidades deve ser >= 1.")
        kwargs["top_n_oportunidades"] = top_n_oportunidades
    if not kwargs:
        return thresholds
    return replace(thresholds, **kwargs)
