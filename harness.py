"""
Orquestrador: loop agente -> ferramentas -> explicacao LLM.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agent import ACAO_FIM, AgenteOpenAI, DecisaoAgente
from audit import AuditTrail, gerar_sessao_id
from tools import (
    listar_ferramentas,
    resumir_efeito_ferramenta,
    resumir_estado_para_log,
    serializar_resultados_para_llm,
)

MAX_ITERACOES_AGENTE = 10

TIPOS_RESUMO_AUDITORIA = frozenset({
    "llm_decisao",
    "harness_correcao",
    "harness_bloqueio",
    "harness_fim_loop",
    "tool_fim",
    "llm_explicacao",
    "sessao_fim",
})


@dataclass
class Harness:
    """
    Controla execucao: loop perceive-act-observe -> explicacao LLM -> logs.
    """

    agente: AgenteOpenAI
    ferramentas: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = field(
        default_factory=listar_ferramentas
    )
    logs: List[str] = field(default_factory=list)
    max_iteracoes: int = MAX_ITERACOES_AGENTE
    auditoria: Optional[AuditTrail] = None

    def _log(self, mensagem: str) -> None:
        """Registra uma linha de log."""
        self.logs.append(mensagem)

    def _executar_ferramenta(
        self,
        state: Dict[str, Any],
        nome_ferramenta: str,
        iteracao: Optional[int] = None,
    ) -> None:
        """Executa uma tool e atualiza o state."""
        if nome_ferramenta not in self.ferramentas:
            raise KeyError(
                f"Ferramenta desconhecida: {nome_ferramenta}"
            )

        if self.auditoria is not None:
            self.auditoria.registrar(
                "tool_inicio",
                {
                    "ferramenta": nome_ferramenta,
                    "estado_antes": resumir_estado_para_log(state),
                },
                iteracao=iteracao,
            )

        inicio = time.perf_counter()
        ferramenta = self.ferramentas[nome_ferramenta]
        saida = ferramenta(state)

        if nome_ferramenta == "carregar_dados":
            state["dados"].update(saida)
        else:
            state["resultados"].update(saida)

        acoes: List[str] = state.setdefault("acoes_executadas", [])
        acoes.append(nome_ferramenta)
        duracao_ms = round((time.perf_counter() - inicio) * 1000, 2)

        self._log(f"Tool concluida: {nome_ferramenta}")
        efeito = resumir_efeito_ferramenta(nome_ferramenta, state)
        self._log(f"Efeito no state: {efeito}")
        self._log(f"Estado apos tool: {resumir_estado_para_log(state)}")

        if self.auditoria is not None:
            self.auditoria.registrar(
                "tool_fim",
                {
                    "ferramenta": nome_ferramenta,
                    "duracao_ms": duracao_ms,
                    "efeito": efeito,
                    "estado_depois": resumir_estado_para_log(state),
                },
                iteracao=iteracao,
            )

    def executar_dominion(
        self,
        pergunta_usuario: str,
        preservar_logs: bool = False,
    ) -> Dict[str, Any]:
        """
        Executa apenas a fase Dominion (loop perceive-act-observe), sem Optimus.
        """
        state = self._executar_loop_dominion(
            pergunta_usuario,
            preservar_logs=preservar_logs,
        )
        state["logs"] = list(self.logs)
        if self.auditoria is not None:
            state["auditoria"] = self.auditoria.para_dict()
        return state

    def _executar_loop_dominion(
        self,
        pergunta_usuario: str,
        preservar_logs: bool = False,
    ) -> Dict[str, Any]:
        """
        Loop interno do Dominion: perceive -> act -> observe ate fim ou limite.
        """
        state: Dict[str, Any] = {
            "pergunta": pergunta_usuario,
            "dados": {},
            "resultados": {},
            "acoes_executadas": [],
        }

        self.auditoria = AuditTrail(sessao_id=gerar_sessao_id())
        if not preservar_logs:
            self.logs.clear()
        self._log("=== INICIO FASE DOMINION ===")
        self._log(f"Pergunta: {pergunta_usuario}")
        self._log(
            f"Ferramentas registradas: {', '.join(sorted(self.ferramentas.keys()))}"
        )
        self._log(f"Max iteracoes do loop: {self.max_iteracoes}")
        self._log(f"Sessao auditoria: {self.auditoria.sessao_id}")
        self._log(f"Estado inicial: {resumir_estado_para_log(state)}")
        self._log("=== LOOP DOMINION (perceive -> act -> observe) ===")

        self.auditoria.registrar(
            "sessao_inicio",
            {
                "fase": "dominion",
                "pergunta": pergunta_usuario,
                "ferramentas": sorted(self.ferramentas.keys()),
                "max_iteracoes": self.max_iteracoes,
                "modelo": self.agente.modelo,
            },
        )

        limite_atingido = False

        for iteracao in range(1, self.max_iteracoes + 1):
            self._log("")
            self._log(f"--- Iteracao {iteracao}/{self.max_iteracoes} ---")
            resumo_estado = resumir_estado_para_log(state)
            self._log(
                f"[PERCEIVE] Estado antes da decisao: {resumo_estado}"
            )
            self.auditoria.registrar(
                "estado_snapshot",
                {"fase": "perceive", "resumo": resumo_estado},
                iteracao=iteracao,
            )
            self._log("[DECIDE] Consultando LLM (proximo_passo)...")

            decisao: DecisaoAgente = self.agente.proximo_passo(
                pergunta_usuario,
                state,
                registrar_log=self._log,
                auditoria=self.auditoria,
                iteracao=iteracao,
            )
            acao = decisao.acao

            self._log(f"[DECIDE] Acao retornada pelo agente: {acao}")
            if decisao.justificativa:
                self._log(
                    f"[DECIDE] Justificativa: {decisao.justificativa}"
                )

            if acao == ACAO_FIM:
                self._log(
                    "[ACT] Nenhuma tool; agente pediu fim do loop."
                )
                self.auditoria.registrar(
                    "harness_fim_loop",
                    {
                        "motivo": "llm_pediu_fim",
                        "justificativa_llm": decisao.justificativa,
                    },
                    iteracao=iteracao,
                )
                break

            acoes_executadas: List[str] = state["acoes_executadas"]
            if acao in acoes_executadas:
                self._log(
                    f"[ACT] Bloqueado: '{acao}' ja esta em acoes_executadas="
                    f"{acoes_executadas}. Volta ao PERCEIVE sem executar."
                )
                self.auditoria.registrar(
                    "harness_bloqueio",
                    {
                        "acao_solicitada": acao,
                        "motivo": "ferramenta_ja_executada",
                        "acoes_executadas": list(acoes_executadas),
                        "justificativa_llm": decisao.justificativa,
                    },
                    iteracao=iteracao,
                )
                continue

            acao_original = acao
            if not state["dados"] and acao != "carregar_dados":
                acao = "carregar_dados"
                self._log(
                    f"[ACT] Correcao do harness: '{acao_original}' -> "
                    f"'{acao}' (dados ainda vazios)"
                )
                self.auditoria.registrar(
                    "harness_correcao",
                    {
                        "de": acao_original,
                        "para": acao,
                        "motivo": "dados_vazios",
                        "justificativa_llm": decisao.justificativa,
                    },
                    iteracao=iteracao,
                )

            self._log(
                f"[ACT] Executando ferramenta Python: {acao}()"
            )
            self._executar_ferramenta(state, acao, iteracao=iteracao)
            self._log(
                f"[OBSERVE] Iteracao {iteracao} concluida; "
                "proxima volta envia este state ao LLM"
            )
        else:
            limite_atingido = True
            self._log(
                f"[ACT] Limite de {self.max_iteracoes} iteracoes atingido; "
                "encerrando loop sem acao 'fim' do LLM."
            )
            self.auditoria.registrar(
                "loop_limite",
                {
                    "max_iteracoes": self.max_iteracoes,
                    "acoes_executadas": list(state["acoes_executadas"]),
                },
            )

        self._log("")
        self._log("=== FIM DO LOOP ===")
        estado_final = resumir_estado_para_log(state)
        self._log(f"Estado final: {estado_final}")
        self._log(f"Acoes executadas no total: {state['acoes_executadas']}")
        self.auditoria.registrar(
            "loop_fim",
            {
                "fase": "dominion",
                "limite_atingido": limite_atingido,
                "acoes_executadas": list(state["acoes_executadas"]),
                "estado_final": estado_final,
            },
        )
        self._log("=== FIM FASE DOMINION ===")
        return state

    def executar(self, pergunta_usuario: str) -> Dict[str, Any]:
        """
        Fluxo legado: Dominion + explicacao LLM (sem Optimus/Critic).
        """
        state = self._executar_loop_dominion(pergunta_usuario)
        self._log("=== EXPLICACAO FINAL (LLM) ===")

        contexto = serializar_resultados_para_llm(state)
        texto = self.agente.gerar_explicacao(
            pergunta_usuario,
            contexto,
            registrar_log=self._log,
            auditoria=self.auditoria,
        )
        state["resultados"]["explicacao"] = texto
        self._log(
            f"Explicacao gerada ({len(texto)} caracteres)."
        )
        self._log("=== FIM DO HARNESS ===")

        if self.auditoria is not None:
            self.auditoria.registrar(
                "sessao_fim",
                {
                    "sucesso": True,
                    "total_eventos": len(self.auditoria.eventos),
                },
            )

        state["logs"] = list(self.logs)
        if self.auditoria is not None:
            state["auditoria"] = self.auditoria.para_dict()
        return state
