"""
Carrega configuracao a partir de variaveis de ambiente (.env).
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv


HITL_MODES_VALIDOS = frozenset({"terminal", "auto", "arquivo", "streamlit"})


@dataclass(frozen=True)
class Settings:
    """Configuracao da aplicacao."""

    openai_api_key: str
    openai_model: str
    limiar_confianca_critic: float
    max_optimus_retries: int
    hitl_mode: str


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

    return Settings(
        openai_api_key=api_key,
        openai_model=model,
        limiar_confianca_critic=limiar_confianca,
        max_optimus_retries=max_retries,
        hitl_mode=hitl_mode,
    )
