"""
Nexus: orquestrador MVP com state compartilhado, validador, critic e fila.

Pipeline: DataShield (opcional) -> Dominion -> Sinais -> Optimus ->
          Validador -> Critic -> Fila -> Resumo executivo -> PNG ->
          Output Guardrail -> Relatorio PDF -> HITL
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent import AgenteOpenAI
from audit import AuditTrail
from config import Settings
from critic import CriticAgent
from datashield import (
    MapaSemResult,
    carregar_schema_de_json,
    normalizar_dataset,
    processar_arquivo,
)
from dominion_pbi import (
    exportar_resultados_pbi_para_auditoria,
    rodar_dominion_pbi,
)
from powerbi_mcp import PowerBIQueryClient, criar_cliente_pbi
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
from optimus import (
    _impacto_priorizado,
    formatar_resumo_executivo_texto,
    gerar_proposicoes,
    montar_resumo_executivo,
    proposicoes_para_state,
)
from sinais import extrair_sinais_de_resultados
from state_types import (
    criar_state_inicial,
    proposicoes_do_state,
    registrar_handoff,
    sinais_do_state,
)
from tools import serializar_resultados_para_llm
from relatorio import gerar_relatorio_analista
from visualizacao import plotar_resumo_executivo
from tools_parametrizadas import (
    analisar_desvio_persistente,
    analisar_doi,
    analisar_forward,
    analisar_sellin,
    analisar_sellout,
    analisar_tendencia,
    detectar_capacidades,
    resumir_por_categoria,
)
from validator import validar_proposicoes

MAX_PROPOSICOES_EXPLICACAO = 30

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
    "resumo_executivo",
    "visualizacao_png",
    "output_guardrail",
    "relatorio_pdf",
    "sessao_fim",
    "input_guardrail_blocked",
    "catalog_execucao",
    "dominion_pbi",
    "resultados_pbi_export",
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
    fonte_dados: Optional[str] = None
    pbi_client: Optional[PowerBIQueryClient] = None
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

        schema_externo = None
        if self.settings.schema_path:
            try:
                schema_externo = carregar_schema_de_json(self.settings.schema_path)
                self._log(f"DataShield: schema externo carregado de '{self.settings.schema_path}'")
            except (FileNotFoundError, ValueError) as exc:
                self._log(f"DataShield: erro ao carregar schema: {exc}, usando default")

        try:
            resultado_ds = processar_arquivo(
                self.arquivo_entrada,
                schema_canonico=schema_externo,
                api_key=self.settings.openai_api_key,
                model=self.settings.openai_model,
                limiar_gate=self.settings.limiar_confianca_datashield,
                usar_llm=True,
                registrar_log=self._log,
            )
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
            f"confianca mapeamento={mapa_result.confianca:.2f}, "
            f"origem={mapa_result.origem}, gate_ok={mapa_result.gate_ok}"
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
                    "origem": mapa_result.origem,
                    "gate_ok": mapa_result.gate_ok,
                },
            )

        # Confidence gate: em modo auto, bloqueia se confianca baixa.
        if (
            not mapa_result.gate_ok
            and self.settings.hitl_mode == "auto"
        ):
            self._log(
                "DataShield: confidence gate BLOQUEOU avanco automatico "
                f"(confianca={mapa_result.confianca:.2f} < "
                f"{self.settings.limiar_confianca_datashield:.2f})."
            )
            if auditoria is not None:
                auditoria.registrar(
                    "datashield_gate",
                    {
                        "gate_ok": False,
                        "confianca": mapa_result.confianca,
                        "limiar": self.settings.limiar_confianca_datashield,
                    },
                )
            state["schema_confirmado"] = False
            return False

        pedido = PedidoAprovacao(
            tipo="mapeamento_semantico",
            resumo=(
                f"Confirme o mapeamento de {len(mapa_result.colunas_mapeadas)} "
                f"coluna(s) (confianca: {mapa_result.confianca:.0%}, "
                f"origem: {mapa_result.origem})"
            ),
            detalhes={
                "mapa": mapa_result.mapa,
                "colunas_nao_mapeadas": mapa_result.colunas_nao_mapeadas,
                "warnings": mapa_result.warnings,
                "confianca": mapa_result.confianca,
                "origem": mapa_result.origem,
                "gate_ok": mapa_result.gate_ok,
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

    def _fase_dominion_pbi(
        self,
        state: Dict[str, Any],
        auditoria: Optional[AuditTrail],
    ) -> None:
        """
        Dominion PBI: catalogo DAX + ExecuteQuery (ADR-0025).

        Nao usa DataShield nem GenerateQuery. Client injetavel
        (fixture CI ou REST com token).
        """
        catalog_path = self.settings.pbi_catalog_path
        if not catalog_path:
            raise ValueError(
                "PBI_CATALOG_PATH nao definido para --fonte pbi."
            )

        client = self.pbi_client
        if client is None:
            client = criar_cliente_pbi(
                fixture_path=self.settings.pbi_fixture_path,
                access_token=self.settings.pbi_access_token,
            )

        self._log(
            f"Dominion PBI: catalogo='{catalog_path}' "
            f"artifact='{self.settings.pbi_artifact_id or 'default'}'"
        )
        out = rodar_dominion_pbi(
            catalog_path=catalog_path,
            artifact_id_env=self.settings.pbi_artifact_id,
            client=client,
            thresholds=self.settings.thresholds,
        )
        state["fonte_dados"] = out.get("fonte_dados", "pbi")
        state["pbi_catalog_id"] = out.get("pbi_catalog_id")
        state["pbi_artifact_id"] = out.get("pbi_artifact_id")
        state["resultados_pbi"] = out.get("resultados_pbi")
        state["catalog_execucao"] = out.get("catalog_execucao")
        state["sinais"] = out.get("sinais", [])
        resultados = state.get("resultados")
        if not isinstance(resultados, dict):
            resultados = {}
            state["resultados"] = resultados
        dominion_meta = out.get("resultados", {})
        if isinstance(dominion_meta, dict):
            resultados.update(dominion_meta)

        n_ok = 0
        execucao = state.get("catalog_execucao")
        if isinstance(execucao, list):
            n_ok = sum(
                1
                for item in execucao
                if isinstance(item, dict) and item.get("ok")
            )
        self._log(
            f"Dominion PBI: queries_ok={n_ok}, "
            f"sinais={len(state.get('sinais', []))}"
        )
        registrar_handoff(
            state,
            "dominion_pbi",
            "state",
            ["resultados_pbi", "catalog_execucao", "sinais"],
        )
        self._registrar_handoff_audit(
            auditoria,
            "dominion_pbi",
            "state",
            ["resultados_pbi", "catalog_execucao", "sinais"],
        )
        if auditoria is not None:
            auditoria.registrar(
                "catalog_execucao",
                {
                    "pbi_catalog_id": state.get("pbi_catalog_id"),
                    "pbi_artifact_id": state.get("pbi_artifact_id"),
                    "execucao": state.get("catalog_execucao"),
                },
            )
            auditoria.registrar(
                "dominion_pbi",
                {
                    "n_sinais": len(state.get("sinais", [])),
                    "n_queries_ok": n_ok,
                },
            )

        # Full table dump for path-B validation (separate file; ADR-0012).
        resultados_pbi = state.get("resultados_pbi")
        execucao_list = state.get("catalog_execucao")
        if isinstance(resultados_pbi, dict) and isinstance(execucao_list, list):
            sessao_export = "sem_sessao"
            if auditoria is not None and getattr(auditoria, "sessao_id", None):
                sessao_export = str(auditoria.sessao_id)
            try:
                caminhos = exportar_resultados_pbi_para_auditoria(
                    resultados_pbi=resultados_pbi,
                    catalog_execucao=execucao_list,
                    sessao_id=sessao_export,
                    pbi_catalog_id=(
                        str(state["pbi_catalog_id"])
                        if state.get("pbi_catalog_id") is not None
                        else None
                    ),
                    pbi_artifact_id=(
                        str(state["pbi_artifact_id"])
                        if state.get("pbi_artifact_id") is not None
                        else None
                    ),
                )
                state["resultados_pbi_export"] = caminhos
                self._log(
                    f"Export resultados_pbi: {caminhos.get('ultima')}"
                )
                if auditoria is not None:
                    auditoria.registrar(
                        "resultados_pbi_export",
                        {
                            "caminho_sessao": caminhos.get("sessao"),
                            "caminho_ultima": caminhos.get("ultima"),
                            "n_queries": len(resultados_pbi),
                        },
                    )
            except (OSError, TypeError, ValueError) as exc:
                self._log(f"Falha export resultados_pbi: {exc}")
                if auditoria is not None:
                    auditoria.registrar(
                        "resultados_pbi_export",
                        {"ok": False, "erro": str(exc)},
                    )

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
            res_so = analisar_sellout(
                df, mapa, thresholds=self.settings.thresholds
            )
            resultados["analise_sellout"] = res_so
            n_desvios = len(res_so.get("desvios", []))
            self._log(f"Sellout: {n_desvios} desvio(s) calculado(s)")

        if "sellin" in caps:
            res_si = analisar_sellin(
                df, mapa, thresholds=self.settings.thresholds
            )
            resultados["analise_sellin"] = res_si
            n_desvios = len(res_si.get("desvios", []))
            self._log(f"Sellin: {n_desvios} desvio(s) calculado(s)")

        if "doi" in caps:
            res_doi = analisar_doi(
                df, mapa, thresholds=self.settings.thresholds
            )
            resultados["analise_doi"] = res_doi
            n_desvios = len(res_doi.get("desvios", []))
            self._log(f"DOI: {n_desvios} desvio(s) calculado(s)")

        resumo_cat = resumir_por_categoria(df, mapa)
        resultados["resumo_categorias"] = resumo_cat
        n_cats = len(resumo_cat.get("resumo_categorias", []))
        self._log(f"Resumo Nivel 3: {n_cats} categoria(s) x pais x canal")

        res_tend = analisar_tendencia(df, mapa, thresholds=self.settings.thresholds)
        resultados["analise_tendencia"] = res_tend
        n_tend = len(res_tend.get("tendencias", []))
        self._log(
            f"Tendencia: {n_tend} SKU(s), "
            f"piorando={res_tend.get('resumo', {}).get('doi_piorando', 0)}, "
            f"melhorando={res_tend.get('resumo', {}).get('doi_melhorando', 0)}"
        )

        res_fwd = analisar_forward(df, mapa, thresholds=self.settings.thresholds)
        resultados["analise_forward"] = res_fwd
        n_alertas = len(res_fwd.get("alertas_forward", []))
        resumo_fwd = res_fwd.get("resumo", {})
        self._log(
            f"Forward: {n_alertas} alerta(s), "
            f"rupturas={resumo_fwd.get('rupturas_projetadas', 0)}, "
            f"overstocks={resumo_fwd.get('overstocks_projetados', 0)}, "
            f"gaps_plano={resumo_fwd.get('gaps_plano', 0)}, "
            f"oportunidades={resumo_fwd.get('oportunidades', 0)}"
        )

        res_pers = analisar_desvio_persistente(df, mapa, thresholds=self.settings.thresholds)
        resultados["analise_desvio_persistente"] = res_pers
        n_pers = res_pers.get("resumo", {}).get("total", 0)
        self._log(
            f"Desvio persistente: {n_pers} SKU(s) com desvio recorrente "
            f"(acima={res_pers.get('resumo', {}).get('acima', 0)}, "
            f"abaixo={res_pers.get('resumo', {}).get('abaixo', 0)})"
        )

        state["resultados"] = resultados
        state["acoes_executadas"] = [
            f"analisar_{cap}" for cap in caps
        ] + ["analisar_tendencia", "analisar_forward", "analisar_desvio_persistente"]

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

    def _montar_resumo_compacto_critic(
        self,
        state: Dict[str, Any],
    ) -> Optional[str]:
        """
        Monta texto compacto do resumo Nivel 3 para o Critic.

        Se resumo_categorias estiver disponivel no state, retorna
        texto formatado (~124 linhas). Caso contrario retorna None
        e o Critic usa sinais brutos (fluxo legado).
        """
        resultados = state.get("resultados", {})
        if not isinstance(resultados, dict):
            return None

        rc = resultados.get("resumo_categorias", {})
        if not isinstance(rc, dict):
            return None

        cats = rc.get("resumo_categorias", [])
        if not cats:
            return None

        linhas: List[str] = [
            f"RESUMO POR CATEGORIA ({len(cats)} combinacoes Categoria x Pais x Canal):",
            "",
        ]
        for item in cats:
            if not isinstance(item, dict):
                continue
            cat = item.get("categoria", "?")
            pais = item.get("pais", "?")
            canal = item.get("canal", "?")
            partes = [f"{cat} | {pais} | {canal}"]

            so_pct = item.get("so_desvio_pct")
            if so_pct is not None:
                partes.append(f"SO={so_pct:+.1f}%")
            si_pct = item.get("si_desvio_pct")
            if si_pct is not None:
                partes.append(f"SI={si_pct:+.1f}%")
            doi_gap = item.get("doi_gap_dias")
            if doi_gap is not None:
                partes.append(f"DOI_gap={doi_gap:+.1f}d")
            nr = item.get("nr_total")
            if nr is not None:
                partes.append(f"NR=${nr:,.0f}")

            linhas.append(" | ".join(partes))

        totais = rc.get("totais", {})
        if totais:
            linhas.append("")
            linhas.append(
                f"TOTAIS: SO plan={totais.get('so_plan_total', 0):,.0f} "
                f"actual={totais.get('so_actual_total', 0):,.0f} | "
                f"SI plan={totais.get('si_plan_total', 0):,.0f} "
                f"actual={totais.get('si_actual_total', 0):,.0f}"
            )

        resumo = state.get("resultados", {})
        for key in ["analise_sellout", "analise_sellin", "analise_doi"]:
            r = resumo.get(key, {}).get("resumo", {})
            if isinstance(r, dict) and "total_registros" in r:
                linhas.append(
                    f"{key}: {r.get('total_registros', 0)} grupos agregados, "
                    f"impacto total NR=${r.get('total_nr_impacto', 0):,.0f}"
                )

        # Alertas forward
        fwd = resumo.get("analise_forward", {})
        if isinstance(fwd, dict):
            alertas_fwd = fwd.get("alertas_forward", [])
            if alertas_fwd:
                linhas.append("")
                linhas.append(
                    f"=== ALERTAS FORWARD ({len(alertas_fwd)} SKUs com risco) ==="
                )
                for a in alertas_fwd:
                    if not isinstance(a, dict):
                        continue
                    risco = a.get("risco_projetado", "")
                    sku = a.get("sku", "?")
                    pais = a.get("pais", "?")
                    canal = a.get("canal", "?")
                    doi = a.get("doi_atual", 0)
                    div = a.get("divergencia_forward_pct", 0)
                    linhas.append(
                        f"- {sku} ({pais}, {canal}): "
                        f"RISCO={risco.upper()} | DOI_atual={doi:.0f}d | "
                        f"divergencia_plano={div:+.1f}%"
                    )

        # Tendencias DOI
        tend = resumo.get("analise_tendencia", {})
        if isinstance(tend, dict):
            tendencias = tend.get("tendencias", [])
            piorando = [
                t for t in tendencias
                if isinstance(t, dict) and t.get("direcao_doi") == "piorando"
            ]
            melhorando = [
                t for t in tendencias
                if isinstance(t, dict) and t.get("direcao_doi") == "melhorando"
            ]
            if piorando or melhorando:
                linhas.append("")
                linhas.append("=== TENDENCIA DOI ===")
                for t in piorando:
                    ritmo_txt = ""
                    if t.get("so_ritmo") == "desacelerando":
                        ritmo_txt = f" [SO DESACELERANDO {t.get('so_aceleracao_pct', 0):+.1f}pp]"
                    linhas.append(
                        f"- {t.get('sku', '?')} ({t.get('pais', '?')}, "
                        f"{t.get('canal', '?')}): DOI PIORANDO "
                        f"{t.get('doi_anterior', 0):.0f}d -> "
                        f"{t.get('doi_recente', 0):.0f}d{ritmo_txt}"
                    )
                for t in melhorando:
                    linhas.append(
                        f"- {t.get('sku', '?')} ({t.get('pais', '?')}, "
                        f"{t.get('canal', '?')}): DOI melhorando "
                        f"{t.get('doi_anterior', 0):.0f}d -> "
                        f"{t.get('doi_recente', 0):.0f}d"
                    )

            # SKUs com SO acelerando ou desacelerando
            desacelerando = [
                t for t in tendencias
                if isinstance(t, dict) and t.get("so_ritmo") == "desacelerando"
            ]
            acelerando = [
                t for t in tendencias
                if isinstance(t, dict) and t.get("so_ritmo") == "acelerando"
            ]
            if desacelerando or acelerando:
                linhas.append("")
                linhas.append("=== RITMO DE VARIACAO SO ===")
                for t in desacelerando:
                    linhas.append(
                        f"- {t.get('sku', '?')} ({t.get('pais', '?')}, "
                        f"{t.get('canal', '?')}): SO DESACELERANDO "
                        f"({t.get('so_aceleracao_pct', 0):+.1f}pp entre semanas)"
                    )
                for t in acelerando:
                    linhas.append(
                        f"- {t.get('sku', '?')} ({t.get('pais', '?')}, "
                        f"{t.get('canal', '?')}): SO acelerando "
                        f"({t.get('so_aceleracao_pct', 0):+.1f}pp entre semanas)"
                    )

        # Desvio persistente
        pers = resumo.get("analise_desvio_persistente", {})
        if isinstance(pers, dict):
            persistentes = pers.get("persistentes", [])
            if persistentes:
                linhas.append("")
                linhas.append(
                    f"=== DESVIO PERSISTENTE ({len(persistentes)} SKU(s)) ==="
                )
                for p in persistentes:
                    if not isinstance(p, dict):
                        continue
                    linhas.append(
                        f"- {p.get('sku', '?')} ({p.get('pais', '?')}, "
                        f"{p.get('canal', '?')}): SO {p.get('direcao', '?')} do plano "
                        f"por {p.get('meses_consecutivos', 0)} meses "
                        f"(media {p.get('media_desvio_pct', 0):+.1f}%)"
                    )

        n_sinais = len(state.get("sinais", []))
        n_props = len(state.get("proposicoes", []))
        linhas.append(f"\nTotal sinais gerados: {n_sinais}")
        linhas.append(f"Total proposicoes geradas: {n_props}")

        return "\n".join(linhas)

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
                thresholds=self.settings.thresholds,
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

            resumo_compacto = self._montar_resumo_compacto_critic(state)

            critica = self.critic.auditar(
                sinais,
                proposicoes,
                registrar_log=self._log,
                auditoria=auditoria,
                resumo_compacto=resumo_compacto,
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

        Fluxo: Input guardrail -> (DataShield|Dominion PBI|legado) ->
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
        modo_pbi = (self.fonte_dados or "").strip().lower() == "pbi"
        if modo_pbi and self.arquivo_entrada:
            self._log("=== FIM NEXUS MVP (--fonte pbi e --input sao exclusivos) ===")
            return {
                "bloqueado": True,
                "motivo": "--fonte pbi e --input sao mutuamente exclusivos.",
                "logs": list(self.logs),
            }

        auditoria_pre: Optional[AuditTrail] = None
        auditoria: Optional[AuditTrail] = None

        if modo_pbi:
            from audit import AuditTrail as AT, gerar_sessao_id
            auditoria = AT(sessao_id=gerar_sessao_id())
            try:
                self._fase_dominion_pbi(state, auditoria)
            except (ValueError, FileNotFoundError) as exc:
                self._log(f"Dominion PBI bloqueado: {exc}")
                state["logs"] = list(self.logs)
                state["auditoria"] = auditoria.para_dict()
                return {
                    "bloqueado": True,
                    "motivo": str(exc),
                    "logs": list(self.logs),
                    "auditoria": auditoria.para_dict(),
                }
            sinais_pbi = state.get("sinais")
            n_sinais = len(sinais_pbi) if isinstance(sinais_pbi, list) else 0
            self._log(f"Sinais PBI adaptados: {n_sinais}")
        else:
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

            if state.get("dataset_canonico") is not None:
                if auditoria_pre is not None:
                    auditoria = auditoria_pre
                else:
                    from audit import AuditTrail as AT, gerar_sessao_id
                    auditoria = AT(sessao_id=gerar_sessao_id())
                state["fonte_dados"] = "csv"
                self._fase_dominion_mondelez(state, auditoria)
            else:
                dominion_state = self.harness.executar_dominion(
                    pergunta_usuario,
                    preservar_logs=True,
                )
                state["fonte_dados"] = "simulado"
                state["dados"] = dominion_state.get("dados", {})
                state["resultados"] = dominion_state.get("resultados", {})
                state["acoes_executadas"] = dominion_state.get(
                    "acoes_executadas", []
                )

                auditoria_raw = dominion_state.get("auditoria")
                if isinstance(auditoria_raw, dict):
                    auditoria = self.harness.auditoria

            sinais = extrair_sinais_de_resultados(
                state["resultados"],
                thresholds=self.settings.thresholds,
            )
            state["sinais"] = [s.para_dict() for s in sinais]
            self._log(f"Sinais extraidos: {len(sinais)}")
            registrar_handoff(state, "dominion", "state", ["sinais"])
            self._registrar_handoff_audit(
                auditoria, "dominion", "state", ["sinais"]
            )

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
            thresholds=self.settings.thresholds,
        )
        state["fila_nexus"] = [item.para_dict() for item in fila]
        self._log(f"Fila Nexus montada: {len(fila)} itens")
        unidade_impacto = (
            "NR USD"
            if str(state.get("fonte_dados") or "").strip().lower() == "pbi"
            else "R$"
        )
        for item in fila:
            flag = "REVISAO OBRIGATORIA" if item.revisao_obrigatoria else "ok"
            self._log(
                f"  {item.proposicao.proposicao_id} [{flag}] "
                f"{item.proposicao.titulo} | "
                f"{unidade_impacto} {item.proposicao.impacto_financeiro:.2f}"
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

        resumo_exec = montar_resumo_executivo(
            proposicoes, thresholds=self.settings.thresholds
        )
        state["resumo_executivo"] = resumo_exec
        texto_resumo = formatar_resumo_executivo_texto(resumo_exec)
        self._log(texto_resumo)
        if auditoria is not None:
            auditoria.registrar("resumo_executivo", resumo_exec)

        sessao_id_viz = "sessao"
        if auditoria is not None:
            sessao_id_viz = auditoria.sessao_id
        fonte_viz = state.get("fonte_dados")
        meta_viz = plotar_resumo_executivo(
            resumo_exec,
            sessao_id=sessao_id_viz,
            fonte_dados=(
                str(fonte_viz) if isinstance(fonte_viz, str) else None
            ),
        )
        artefatos = state.get("artefatos_visuais")
        if not isinstance(artefatos, list):
            artefatos = []
            state["artefatos_visuais"] = artefatos
        artefatos.append(meta_viz)
        if meta_viz.get("ok"):
            self._log(f"PNG resumo executivo: {meta_viz.get('caminho')}")
        else:
            self._log(
                f"Falha ao gerar PNG do resumo: {meta_viz.get('erro')}"
            )
        if auditoria is not None:
            auditoria.registrar("visualizacao_png", meta_viz)

        resumo_compacto = self._montar_resumo_compacto_critic(state)
        if resumo_compacto is not None:
            contexto = resumo_compacto
        else:
            contexto = serializar_resultados_para_llm(state)

        top_props = sorted(
            proposicoes,
            key=lambda p: (
                _impacto_priorizado(
                    p.impacto_financeiro,
                    p.tipo,
                    self.settings.thresholds,
                ),
                -p.urgencia_horas,
            ),
            reverse=True,
        )[:MAX_PROPOSICOES_EXPLICACAO]
        unidade_impacto = (
            "NR USD"
            if str(state.get("fonte_dados") or "").strip().lower() == "pbi"
            else "R$"
        )
        contexto_props = "\n".join(
            f"- {p.proposicao_id}: {p.titulo} "
            f"({unidade_impacto} {p.impacto_financeiro:.2f})"
            for p in top_props
        )
        texto_llm = self.agente.gerar_explicacao(
            pergunta_usuario,
            f"{contexto}\n\n{texto_resumo}\n\n"
            f"=== Top {len(top_props)} Proposicoes Optimus "
            f"(de {len(proposicoes)} total) ===\n{contexto_props}",
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

        fila_state = state.get("fila_nexus")
        total_fila = len(fila_state) if isinstance(fila_state, list) else 0
        revisao_ob = 0
        if isinstance(fila_state, list):
            for item_fila in fila_state:
                if isinstance(item_fila, dict) and item_fila.get(
                    "revisao_obrigatoria"
                ):
                    revisao_ob += 1
        critic_aprovado: Optional[bool] = None
        if isinstance(critica_raw, dict) and "aprovado" in critica_raw:
            critic_aprovado = bool(critica_raw.get("aprovado"))
        caminho_png = None
        if isinstance(meta_viz, dict) and meta_viz.get("ok"):
            caminho_png = meta_viz.get("caminho")
        fonte_rel = state.get("fonte_dados")
        fonte_rel_str = (
            str(fonte_rel) if isinstance(fonte_rel, str) else None
        )
        catalog_rel = state.get("pbi_catalog_id")
        artifact_rel = state.get("pbi_artifact_id")
        meta_rel = gerar_relatorio_analista(
            resumo_exec,
            sessao_id=sessao_id_viz,
            explicacao=texto_final,
            caminho_png=caminho_png if isinstance(caminho_png, str) else None,
            arquivo_entrada=self.arquivo_entrada,
            total_fila=total_fila,
            revisao_obrigatoria=revisao_ob,
            confianca_critic=confianca,
            critic_aprovado=critic_aprovado,
            proposicoes=proposicoes,
            fonte_dados=fonte_rel_str,
            pbi_catalog_id=(
                str(catalog_rel) if isinstance(catalog_rel, str) else None
            ),
            pbi_artifact_id=(
                str(artifact_rel) if isinstance(artifact_rel, str) else None
            ),
        )
        artefatos.append(meta_rel)
        if meta_rel.get("html_ok"):
            self._log(f"Relatorio HTML: {meta_rel.get('caminho_html')}")
        if meta_rel.get("ok"):
            self._log(f"Relatorio PDF: {meta_rel.get('caminho')}")
        else:
            self._log(
                f"Falha PDF do relatorio: {meta_rel.get('erro')}"
            )
        if auditoria is not None:
            auditoria.registrar("relatorio_pdf", meta_rel)
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
