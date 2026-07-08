"""
Nexus: orquestrador MVP com state compartilhado, validador, critic e fila.

Pipeline: DataShield (opcional) -> Dominion -> Sinais -> Optimus ->
          Validador -> Critic -> Fila -> Output Guardrail -> HITL
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent import AgenteOpenAI
from audit import AuditTrail
from config import Settings
from critic import CriticAgent
from datashield import (
    MapaSemResult,
    normalizar_dataset,
    processar_arquivo,
)
from guardrails import (
    aplicar_output_guardrail,
    montar_fila_com_flags,
    verificar_input,
)
from harness import Harness
from hitl import (
    DecisaoHumana,
    InterfaceHITL,
    HITLAutoApprove,
    PedidoAprovacao,
)
from optimus import gerar_proposicoes, proposicoes_para_state
from sinais import extrair_sinais_de_resultados
from state_types import (
    criar_state_inicial,
    proposicoes_do_state,
    registrar_handoff,
    sinais_do_state,
)
from tools import serializar_resultados_para_llm
from tools_parametrizadas import (
    analisar_doi,
    analisar_sellin,
    analisar_sellout,
    detectar_capacidades,
)
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
    Control plane MVP: DataShield -> Dominion -> Optimus -> Validador ->
    Critic -> Fila -> HITL.
    """

    agente: AgenteOpenAI
    settings: Settings
    hitl: InterfaceHITL = field(default_factory=HITLAutoApprove)
    arquivo_entrada: Optional[str] = None
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

    def _fase_datashield(
        self,
        state: Dict[str, Any],
        auditoria: Optional[AuditTrail],
    ) -> bool:
        """
        Executa DataShield Lite se arquivo_entrada foi fornecido.

        Retorna True se o pipeline pode continuar, False se deve parar
        (ex: schema rejeitado pelo humano).
        """
        if not self.arquivo_entrada:
            self._log("DataShield: sem arquivo de entrada, usando dados simulados.")
            return True

        self._log(f"DataShield: processando '{self.arquivo_entrada}'...")

        try:
            resultado_ds = processar_arquivo(self.arquivo_entrada)
        except (FileNotFoundError, ValueError) as exc:
            self._log(f"DataShield: erro ao processar arquivo: {exc}")
            if auditoria is not None:
                auditoria.registrar(
                    "datashield_erro",
                    {"arquivo": self.arquivo_entrada, "erro": str(exc)},
                )
            return False

        perfil = resultado_ds["perfil"]
        mapa_result: MapaSemResult = resultado_ds["mapa"]
        df = resultado_ds["df"]

        state["dataset_csv"] = df
        state["perfil_dados"] = perfil.para_dict()
        state["mapa_semantico"] = mapa_result.para_dict()
        state["nivel_adaptacao"] = resultado_ds["nivel_adaptacao"]

        self._log(
            f"DataShield: {perfil.linhas} linhas, {perfil.colunas_total} colunas, "
            f"confianca mapeamento={mapa_result.confianca:.2f}"
        )

        if auditoria is not None:
            auditoria.registrar(
                "datashield_perfil",
                {
                    "arquivo": self.arquivo_entrada,
                    "linhas": perfil.linhas,
                    "colunas": perfil.colunas_total,
                    "confianca": mapa_result.confianca,
                    "mapeadas": len(mapa_result.colunas_mapeadas),
                    "nao_mapeadas": len(mapa_result.colunas_nao_mapeadas),
                    "warnings": mapa_result.warnings,
                },
            )

        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo=(
                f"Confirme o mapeamento de {len(mapa_result.colunas_mapeadas)} "
                f"coluna(s) (confianca: {mapa_result.confianca:.0%})"
            ),
            detalhes={
                "mapa": mapa_result.mapa,
                "colunas_nao_mapeadas": mapa_result.colunas_nao_mapeadas,
                "warnings": mapa_result.warnings,
                "confianca": mapa_result.confianca,
            },
        )

        pedido_resolvido = self.hitl.solicitar_aprovacao(pedido)

        hitl_pendentes: List[Dict[str, object]] = state.get("hitl_pendentes", [])
        hitl_resolvidos: List[Dict[str, object]] = state.get("hitl_resolvidos", [])
        hitl_resolvidos.append(pedido_resolvido.para_dict())
        state["hitl_pendentes"] = hitl_pendentes
        state["hitl_resolvidos"] = hitl_resolvidos

        if auditoria is not None:
            auditoria.registrar(
                "hitl_decisao",
                {
                    "tipo": pedido_resolvido.tipo,
                    "decisao": pedido_resolvido.decisao.value if pedido_resolvido.decisao else None,
                    "comentario": pedido_resolvido.comentario,
                    "decidido_por": pedido_resolvido.decidido_por,
                },
            )

        if pedido_resolvido.decisao == DecisaoHumana.REJEITADO:
            self._log("DataShield: mapeamento REJEITADO pelo humano. Pipeline encerrado.")
            state["schema_confirmado"] = False
            return False

        if pedido_resolvido.decisao == DecisaoHumana.POSTERGADO:
            self._log("DataShield: mapeamento POSTERGADO. Pipeline encerrado.")
            state["schema_confirmado"] = False
            return False

        state["schema_confirmado"] = True
        df_canonico = normalizar_dataset(df, mapa_result.mapa)
        state["dataset_canonico"] = df_canonico

        registrar_handoff(
            state, "datashield", "dominion",
            ["dataset_canonico", "mapa_semantico", "schema_confirmado"],
        )
        self._registrar_handoff_audit(
            auditoria, "datashield", "dominion",
            ["dataset_canonico", "mapa_semantico", "schema_confirmado"],
        )

        self._log(
            f"DataShield: schema confirmado. Dataset normalizado com "
            f"{len(df_canonico)} linhas."
        )

        return True

    def _fase_dominion_mondelez(
        self,
        state: Dict[str, Any],
        auditoria: Optional[AuditTrail],
    ) -> None:
        """
        Fase Dominion para dados Mondelez: chama tools parametrizadas
        diretamente (deterministico, sem loop LLM).

        Requer que DataShield ja tenha preenchido dataset_canonico e
        mapa_semantico no state.
        """
        import pandas as pd

        df = state.get("dataset_canonico")
        if not isinstance(df, pd.DataFrame) or df.empty:
            self._log("Dominion Mondelez: dataset_canonico vazio ou ausente.")
            return

        mapa_raw = state.get("mapa_semantico", {})
        if isinstance(mapa_raw, dict):
            mapa = mapa_raw.get("mapa", {})
        else:
            mapa = {}
        if not isinstance(mapa, dict):
            mapa = {}

        self._log("=== DOMINION MONDELEZ (tools parametrizadas) ===")

        caps = detectar_capacidades(mapa)
        state["capacidades"] = caps
        self._log(f"Capacidades detectadas: {', '.join(caps) if caps else 'nenhuma'}")

        resultados: Dict[str, Any] = {}

        if "sellout" in caps:
            res_so = analisar_sellout(df, mapa)
            resultados["analise_sellout"] = res_so
            n_desvios = len(res_so.get("desvios", []))
            self._log(f"Sellout: {n_desvios} desvio(s) calculado(s)")

        if "sellin" in caps:
            res_si = analisar_sellin(df, mapa)
            resultados["analise_sellin"] = res_si
            n_desvios = len(res_si.get("desvios", []))
            self._log(f"Sellin: {n_desvios} desvio(s) calculado(s)")

        if "doi" in caps:
            res_doi = analisar_doi(df, mapa)
            resultados["analise_doi"] = res_doi
            n_desvios = len(res_doi.get("desvios", []))
            self._log(f"DOI: {n_desvios} desvio(s) calculado(s)")

        state["resultados"] = resultados
        state["acoes_executadas"] = [
            f"analisar_{cap}" for cap in caps
        ]

        if auditoria is not None:
            auditoria.registrar(
                "dominion_mondelez",
                {
                    "capacidades": caps,
                    "chaves_resultados": list(resultados.keys()),
                    "total_desvios": sum(
                        len(r.get("desvios", []))
                        for r in resultados.values()
                        if isinstance(r, dict)
                    ),
                },
            )

        registrar_handoff(
            state, "datashield", "dominion_mondelez",
            ["dataset_canonico", "capacidades", "resultados"],
        )
        self._registrar_handoff_audit(
            auditoria, "datashield", "dominion_mondelez",
            ["dataset_canonico", "capacidades", "resultados"],
        )

        self._log("=== FIM DOMINION MONDELEZ ===")

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

        Fluxo: Input guardrail -> DataShield (se arquivo) -> Dominion ->
               Sinais -> Optimus -> Validador -> Critic -> Fila -> Output guardrail
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

        auditoria_pre: Optional[AuditTrail] = None

        if self.arquivo_entrada:
            from audit import AuditTrail as AT, gerar_sessao_id
            auditoria_pre = AT(sessao_id=gerar_sessao_id())
            pode_continuar = self._fase_datashield(state, auditoria_pre)
            if not pode_continuar:
                self._log("=== FIM NEXUS MVP (DataShield bloqueou) ===")
                state["logs"] = list(self.logs)
                if auditoria_pre is not None:
                    state["auditoria"] = auditoria_pre.para_dict()
                return state

        auditoria: Optional[AuditTrail] = None

        if state.get("dataset_canonico") is not None:
            if auditoria_pre is not None:
                auditoria = auditoria_pre
            else:
                from audit import AuditTrail as AT, gerar_sessao_id
                auditoria = AT(sessao_id=gerar_sessao_id())
            self._fase_dominion_mondelez(state, auditoria)
        else:
            dominion_state = self.harness.executar_dominion(
                pergunta_usuario,
                preservar_logs=True,
            )
            state["dados"] = dominion_state.get("dados", {})
            state["resultados"] = dominion_state.get("resultados", {})
            state["acoes_executadas"] = dominion_state.get("acoes_executadas", [])

            auditoria_raw = dominion_state.get("auditoria")
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
