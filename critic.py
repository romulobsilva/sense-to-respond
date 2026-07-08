"""
Critic LLM: auditoria somente leitura pos-Optimus.
"""

import json
from dataclasses import dataclass
from typing import Callable, List, Optional

from openai import OpenAI

from audit import AuditTrail
from config import Settings
from state_types import (
    Proposicao,
    ResultadoCritica,
    Sinal,
    serializar_proposicoes_para_llm,
    serializar_sinais_para_llm,
)

SYSTEM_CRITIC = """Voce e um auditor de proposicoes de supply chain.

Sua funcao e APENAS validar se as proposicoes sao coerentes com os sinais.
Voce NAO gera novas proposicoes. Voce NAO inventa numeros.

Verifique:
1. Cada proposicao cita evidencias que existem nos sinais?
2. O impacto financeiro e plausivel dado o desvio nos sinais?
3. A conclusao e exagerada em relacao a evidencia?
4. Ha limitacoes nao mencionadas?

Responda APENAS com JSON:
{
  "aprovado": true,
  "confianca": 0.85,
  "problemas": ["lista de problemas ou vazia"]
}
"""

CHAVES_OBRIGATORIAS = ("aprovado", "confianca", "problemas")
MAX_RETRIES_JSON = 2
MAX_PROPOSICOES_CRITIC = 50


@dataclass
class CriticAgent:
    """Agente Critic: uma chamada LLM de auditoria."""

    settings: Settings

    def __post_init__(self) -> None:
        """Inicializa cliente OpenAI."""
        self._client = OpenAI(api_key=self.settings.openai_api_key)
        self._model = self.settings.openai_model

    def auditar(
        self,
        sinais: List[Sinal],
        proposicoes: List[Proposicao],
        registrar_log: Optional[Callable[[str], None]] = None,
        auditoria: Optional[AuditTrail] = None,
        resumo_compacto: Optional[str] = None,
    ) -> ResultadoCritica:
        """
        Audita proposicoes contra sinais (leitura only, sem gerar proposicoes).

        Args:
            sinais: lista de sinais (usada se resumo_compacto nao fornecido).
            proposicoes: lista de proposicoes (top N selecionado se > 50).
            registrar_log: callback de log.
            auditoria: trilha de auditoria.
            resumo_compacto: se fornecido, substitui sinais serializados.
                Deve conter o resumo Nivel 3 (Categoria x Pais x Canal).
        """
        def log(msg: str) -> None:
            if registrar_log is not None:
                registrar_log(msg)

        if resumo_compacto is not None:
            contexto_sinais = resumo_compacto
            log(f"Critic: usando resumo compacto ({len(resumo_compacto)} chars)")
        else:
            contexto_sinais = serializar_sinais_para_llm(sinais)

        props_para_critic = proposicoes
        if len(proposicoes) > MAX_PROPOSICOES_CRITIC:
            props_para_critic = sorted(
                proposicoes,
                key=lambda p: p.impacto_financeiro,
                reverse=True,
            )[:MAX_PROPOSICOES_CRITIC]
            log(
                f"Critic: truncado {len(proposicoes)} proposicoes "
                f"para top {MAX_PROPOSICOES_CRITIC} por impacto"
            )
        contexto_props = serializar_proposicoes_para_llm(props_para_critic)

        log("Chamada OpenAI: Critic auditar (leitura only)")
        log(f"Modelo: {self._model}")

        messages = [
            {"role": "system", "content": SYSTEM_CRITIC},
            {
                "role": "user",
                "content": (
                    f"SINAIS DOMINION:\n{contexto_sinais}\n\n"
                    f"PROPOSICOES OPTIMUS:\n{contexto_props}"
                ),
            },
        ]

        json_bruto = ""
        for tentativa in range(MAX_RETRIES_JSON + 1):
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=messages,
            )
            content = response.choices[0].message.content
            if content is None:
                if tentativa < MAX_RETRIES_JSON:
                    messages.append({
                        "role": "user",
                        "content": "Retorne APENAS um objeto JSON completo.",
                    })
                    continue
                raise ValueError("Resposta vazia do Critic.")

            json_bruto = content
            log(f"JSON bruto Critic (tentativa {tentativa + 1}): {content}")

            try:
                dados = json.loads(content)
            except json.JSONDecodeError:
                if tentativa < MAX_RETRIES_JSON:
                    messages.append({
                        "role": "user",
                        "content": "JSON invalido. Retorne APENAS JSON valido.",
                    })
                    continue
                return ResultadoCritica(
                    aprovado=False,
                    confianca=0.0,
                    problemas=["JSON invalido do Critic apos retries."],
                    json_bruto=json_bruto,
                )

            faltando = [k for k in CHAVES_OBRIGATORIAS if k not in dados]
            if faltando:
                if tentativa < MAX_RETRIES_JSON:
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Faltam chaves: {', '.join(faltando)}. "
                            "Retorne JSON completo."
                        ),
                    })
                    continue
                return ResultadoCritica(
                    aprovado=False,
                    confianca=0.0,
                    problemas=[f"Chaves faltando: {', '.join(faltando)}"],
                    json_bruto=json_bruto,
                )

            aprovado_raw = dados.get("aprovado", False)
            confianca_raw = dados.get("confianca", 0.0)
            problemas_raw = dados.get("problemas", [])

            if isinstance(aprovado_raw, bool):
                aprovado = aprovado_raw
            elif isinstance(aprovado_raw, str):
                aprovado = aprovado_raw.lower() in ("true", "1", "sim", "yes")
            else:
                aprovado = False

            try:
                confianca = float(confianca_raw)
            except (TypeError, ValueError):
                confianca = 0.0

            if confianca < 0.0 or confianca > 1.0:
                log(
                    f"Confianca fora do range 0-1: {confianca}. "
                    "Clamped para [0.0, 1.0]."
                )
                confianca = max(0.0, min(1.0, confianca))

            problemas: List[str] = []
            if isinstance(problemas_raw, list):
                for item in problemas_raw:
                    if isinstance(item, str):
                        problemas.append(item)

            resultado = ResultadoCritica(
                aprovado=aprovado,
                confianca=confianca,
                problemas=problemas,
                json_bruto=json_bruto,
            )

            if auditoria is not None:
                auditoria.registrar(
                    "critic_auditoria",
                    {
                        "aprovado": resultado.aprovado,
                        "confianca": resultado.confianca,
                        "problemas": resultado.problemas,
                        "modelo": self._model,
                    },
                )

            log(
                f"Critic: aprovado={resultado.aprovado}, "
                f"confianca={resultado.confianca:.2f}"
            )
            return resultado

        return ResultadoCritica(
            aprovado=False,
            confianca=0.0,
            problemas=["Critic esgotou retries."],
            json_bruto=json_bruto,
        )
