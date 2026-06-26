"""
Nexus: orquestrador MVP com state compartilhado, validador, critic e fila.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent import AgenteOpenAI
from audit import AuditTrail
from config import Settings
from critic import CriticAgent
from guardrails import (
    aplicar_output_guardrail,
    montar_fila_com_flags,
    verificar_input,
)
from harness import Harness
from optimus import gerar_proposicoes, proposicoes_para_state
from sinais import extrair_sinais_de_resultados
from state_types import (
    criar_state_inicial,
    proposicoes_do_state,
    registrar_handoff,
    sinais_do_state,
)
from tools import serializar_resultados_para_llm
from validator import validar_proposicoes

TIPOS_RESUMO_AUDITORIA = frozenset({
    "llm_decisao",
    "harness_correcao",
    "harness_bloqueio",
    "harness_fim_loop",
    "tool_fim",
    "llm_explicacao",
    "critic_auditoria",
    "handoff",
    "validacao_deterministica",
    "optimus_retry",
    "fila_nexus",
    "output_guardrail",
    "sessao_fim",
    "input_guardrail_blocked",
})


@dataclass
class Nexus:
    """
    Control plane MVP: Dominion -> Optimus -> Validador -> Critic -> Fila.
    """

    agente: AgenteOpenAI
    settings: Settings
    harness: Harness = field(init=False)
    critic: CriticAgent = field(init=False)
    logs: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Inicializa sub-componentes."""
        self.harness = Harness(agente=self.agente)
        self.critic = CriticAgent(settings=self.settings)

    def _log(self, mensagem: str) -> None:
        """Registra log do Nexus."""
        self.logs.append(mensagem)
        self.harness._log(mensagem)

    def _registrar_handoff_audit(
        self,
        auditoria: Optional[AuditTrail],
        origem: str,
        destino: str,
        chaves: List[str],
    ) -> None:
        """Registra handoff na auditoria."""
        if auditoria is None:
            return
        auditoria.registrar(
            "handoff",
            {"origem": origem, "destino": destino, "payload_chaves": chaves},
        )

    def _fase_optimus_com_validacao(
        self,
        state: Dict[str, Any],
        auditoria: Optional[AuditTrail],
    ) -> None:
        """
        Optimus + validador deterministico + critic com max 1 retry.
        """
        sinais = sinais_do_state(state)
        max_tentativas = 1 + self.settings.max_optimus_retries
        feedback_validacao: Optional[List[str]] = None
        feedback_critic: Optional[List[str]] = None

        for tentativa in range(1, max_tentativas + 1):
            state["optimus_tentativas"] = tentativa
            self._log(f"=== OPTIMUS tentativa {tentativa}/{max_tentativas} ===")

            proposicoes = gerar_proposicoes(
                sinais,
                feedback_validacao=feedback_validacao,
                feedback_critic=feedback_critic,
            )
            state["proposicoes"] = proposicoes_para_state(proposicoes)
            registrar_handoff(state, "dominion", "optimus", ["sinais", "proposicoes"])
            self._registrar_handoff_audit(
                auditoria, "dominion", "optimus", ["sinais", "proposicoes"]
            )

            validacao = validar_proposicoes(proposicoes, sinais)
            state["validacao"] = validacao.para_dict()
            self._log(
                f"Validador deterministico: ok={validacao.ok}, "
                f"erros={len(validacao.erros)}"
            )
            if auditoria is not None:
                auditoria.registrar(
                    "validacao_deterministica",
                    {
                        "tentativa": tentativa,
                        "ok": validacao.ok,
                        "erros": validacao.erros,
                    },
                )

            registrar_handoff(
                state, "optimus", "validador", ["proposicoes", "validacao"]
            )
            self._registrar_handoff_audit(
                auditoria, "optimus", "validador", ["proposicoes", "validacao"]
            )

            precisa_retry_validador = (
                not validacao.ok and tentativa < max_tentativas
            )
            if precisa_retry_validador:
                feedback_validacao = validacao.erros
                if auditoria is not None:
                    auditoria.registrar(
                        "optimus_retry",
                        {
                            "motivo": "validador",
                            "tentativa": tentativa,
                            "erros": validacao.erros,
                        },
                    )
                self._log("Retry Optimus por falha do validador deterministico.")
                continue

            critica = self.critic.auditar(
                sinais,
                proposicoes,
                registrar_log=self._log,
                auditoria=auditoria,
            )
            state["critica"] = critica.para_dict()
            registrar_handoff(
                state, "validador", "critic", ["proposicoes", "critica"]
            )
            self._registrar_handoff_audit(
                auditoria, "validador", "critic", ["proposicoes", "critica"]
            )

            critic_falhou = (
                (not critica.aprovado or critica.confianca < self.settings.limiar_confianca_critic)
                and tentativa < max_tentativas
            )
            if critic_falhou:
                feedback_critic = critica.problemas or [
                    f"confianca {critica.confianca:.2f} abaixo do limiar"
                ]
                if auditoria is not None:
                    auditoria.registrar(
                        "optimus_retry",
                        {
                            "motivo": "critic",
                            "tentativa": tentativa,
                            "problemas": feedback_critic,
                            "confianca": critica.confianca,
                        },
                    )
                self._log("Retry Optimus por falha do Critic.")
                continue

            break

    def executar(self, pergunta_usuario: str) -> Dict[str, Any]:
        """
        Pipeline MVP completo com guardrails, validacao e fila Nexus.
        """
        self.logs.clear()
        self.harness.logs.clear()
        self._log("=== INICIO NEXUS MVP ===")

        input_check = verificar_input(pergunta_usuario)
        if not input_check.ok:
            self._log(f"Input guardrail BLOQUEADO: {input_check.detalhe}")
            return {
                "bloqueado": True,
                "motivo": input_check.detalhe,
                "logs": list(self.logs),
            }

        self._log(f"Input guardrail OK: {input_check.detalhe}")

        state = criar_state_inicial(pergunta_usuario)

        dominion_state = self.harness.executar_dominion(
            pergunta_usuario,
            preservar_logs=True,
        )
        state["dados"] = dominion_state.get("dados", {})
        state["resultados"] = dominion_state.get("resultados", {})
        state["acoes_executadas"] = dominion_state.get("acoes_executadas", [])

        auditoria_raw = dominion_state.get("auditoria")
        auditoria: Optional[AuditTrail] = None
        if isinstance(auditoria_raw, dict):
            auditoria = self.harness.auditoria

        sinais = extrair_sinais_de_resultados(state["resultados"])
        state["sinais"] = [s.para_dict() for s in sinais]
        self._log(f"Sinais extraidos: {len(sinais)}")
        registrar_handoff(state, "dominion", "state", ["sinais"])
        self._registrar_handoff_audit(auditoria, "dominion", "state", ["sinais"])

        self._fase_optimus_com_validacao(state, auditoria)

        proposicoes = proposicoes_do_state(state)
        critica_raw = state.get("critica")
        confianca: Optional[float] = None
        if isinstance(critica_raw, dict):
            conf_raw = critica_raw.get("confianca")
            if isinstance(conf_raw, (int, float)):
                confianca = float(conf_raw)

        validacao_raw = state.get("validacao")
        validacao_ok = False
        if isinstance(validacao_raw, dict):
            validacao_ok = bool(validacao_raw.get("ok", False))

        fila = montar_fila_com_flags(
            proposicoes,
            confianca_critic=confianca,
            limiar_confianca=self.settings.limiar_confianca_critic,
            validacao_ok=validacao_ok,
        )
        state["fila_nexus"] = [item.para_dict() for item in fila]
        self._log(f"Fila Nexus montada: {len(fila)} itens")
        for item in fila:
            flag = "REVISAO OBRIGATORIA" if item.revisao_obrigatoria else "ok"
            self._log(
                f"  {item.proposicao.proposicao_id} [{flag}] "
                f"{item.proposicao.titulo} | R$ {item.proposicao.impacto_financeiro:.2f}"
            )

        if auditoria is not None:
            auditoria.registrar(
                "fila_nexus",
                {
                    "total": len(fila),
                    "revisao_obrigatoria": sum(
                        1 for i in fila if i.revisao_obrigatoria
                    ),
                    "itens": state["fila_nexus"],
                },
            )

        contexto = serializar_resultados_para_llm(state)
        contexto_props = "\n".join(
            f"- {p.proposicao_id}: {p.titulo} (R$ {p.impacto_financeiro:.2f})"
            for p in proposicoes
        )
        texto_llm = self.agente.gerar_explicacao(
            pergunta_usuario,
            f"{contexto}\n\n=== Proposicoes Optimus ===\n{contexto_props}",
            registrar_log=self._log,
            auditoria=auditoria,
        )

        texto_final = aplicar_output_guardrail(
            texto_llm,
            proposicoes,
            confianca_critic=confianca,
            limiar_confianca=self.settings.limiar_confianca_critic,
        )
        state["resultados"]["explicacao"] = texto_final
        state["resultados"]["explicacao_llm_bruta"] = texto_llm

        if auditoria is not None:
            auditoria.registrar(
                "output_guardrail",
                {
                    "disclaimer_aplicado": True,
                    "confianca_critic": confianca,
                    "limiar": self.settings.limiar_confianca_critic,
                },
            )
            auditoria.registrar(
                "sessao_fim",
                {
                    "sucesso": True,
                    "fase": "nexus_mvp",
                    "total_eventos": len(auditoria.eventos),
                    "handoffs": len(state.get("handoffs", [])),
                },
            )

        self._log("=== FIM NEXUS MVP ===")
        state["logs"] = list(self.harness.logs)
        if auditoria is not None:
            state["auditoria"] = auditoria.para_dict()
        return state
