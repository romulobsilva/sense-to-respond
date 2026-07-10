"""
Ponto de entrada: Nexus MVP com validador, critic e fila human-in-the-loop.
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from agent import AgenteOpenAI
from config import aplicar_overrides_thresholds, load_settings
from dataclasses import replace
from harness import Harness, TIPOS_RESUMO_AUDITORIA as TIPOS_HARNESS
from hitl import (
    HITLArquivo,
    HITLAutoApprove,
    HITLTerminal,
    InterfaceHITL,
)
from nexus import Nexus, TIPOS_RESUMO_AUDITORIA as TIPOS_NEXUS
from optimus import formatar_resumo_executivo_texto


def _formatar_dados_resumo(dados: Dict[str, Any]) -> str:
    """
    Formata payload de evento para exibicao compacta no terminal.
    """
    partes: List[str] = []
    for chave, valor in dados.items():
        if chave in ("contexto_enviado", "contexto_resultados", "json_bruto"):
            continue
        texto = str(valor)
        if len(texto) > 120:
            texto = f"{texto[:120]}..."
        partes.append(f"{chave}={texto}")
    return ", ".join(partes)


def _imprimir_resumo_auditoria(
    auditoria: Dict[str, Any],
    tipos: frozenset[str],
) -> None:
    """
    Mostra eventos-chave da trilha de auditoria no terminal.
    """
    eventos: List[Dict[str, Any]] = auditoria.get("eventos", [])
    if not eventos:
        return

    print("\n==============================")
    print("RESUMO AUDITORIA (eventos-chave)")
    print("==============================")
    print(f"sessao_id: {auditoria.get('sessao_id', '')}")

    for evento in eventos:
        tipo = evento.get("tipo", "")
        if tipo not in tipos:
            continue
        iteracao = evento.get("iteracao")
        iter_txt = f"iter={iteracao}" if iteracao is not None else "iter=-"
        dados = evento.get("dados", {})
        if not isinstance(dados, dict):
            dados = {}
        print(f"[{tipo}] {iter_txt} {_formatar_dados_resumo(dados)}")


MAX_FILA_TERMINAL = 30


def _imprimir_fila_nexus(fila: List[Dict[str, Any]]) -> None:
    """
    Exibe fila ranqueada para decisao humana (top-N + resumo).
    """
    if not fila:
        print("Nenhum item na fila.")
        return

    total = len(fila)
    exibir = fila[:MAX_FILA_TERMINAL]

    print("\n==============================")
    print(f"FILA NEXUS - top {len(exibir)} de {total} (human-in-the-loop)")
    print("==============================")
    for item in exibir:
        prop = item.get("proposicao", {})
        if not isinstance(prop, dict):
            prop = {}
        revisao = item.get("revisao_obrigatoria", False)
        flag = "REVISAO OBRIGATORIA" if revisao else "OK"
        motivo = item.get("motivo_revisao", "")
        prop_id = prop.get("proposicao_id", "")
        titulo = prop.get("titulo", "")
        impacto = prop.get("impacto_financeiro", 0)
        print(f"[{flag}] {prop_id} | {titulo} | R$ {impacto}")
        if motivo:
            print(f"  motivo: {motivo}")

    if total > MAX_FILA_TERMINAL:
        print(f"\n... +{total - MAX_FILA_TERMINAL} proposicoes omitidas. "
              f"Consulte auditoria para lista completa.")


def _criar_hitl(hitl_mode: str) -> InterfaceHITL:
    """
    Instancia a implementacao de HITL conforme configuracao.

    Args:
        hitl_mode: modo de HITL (terminal, auto, arquivo, streamlit).

    Returns:
        Implementacao de InterfaceHITL.
    """
    if hitl_mode == "auto":
        return HITLAutoApprove()
    if hitl_mode in ("arquivo", "streamlit"):
        return HITLArquivo()
    return HITLTerminal()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sense to Respond MVP: Nexus com validador e critic."
    )
    parser.add_argument(
        "--audit-out",
        default="auditoria/ultima_sessao.json",
        help="Caminho para salvar JSON da auditoria (vazio para nao salvar).",
    )
    parser.add_argument(
        "--modo",
        choices=("nexus", "legado"),
        default="nexus",
        help="nexus=MVP completo; legado=harness sem Optimus/Critic.",
    )
    parser.add_argument(
        "--input",
        default=None,
        dest="arquivo_entrada",
        help="Caminho para CSV/XLSX de entrada (ativa DataShield).",
    )
    parser.add_argument(
        "--top-doi",
        type=int,
        default=None,
        dest="top_doi",
        help="Override TOP_N_DOI do resumo executivo.",
    )
    parser.add_argument(
        "--top-forward",
        type=int,
        default=None,
        dest="top_forward",
        help="Override TOP_N_FORWARD do resumo executivo.",
    )
    parser.add_argument(
        "--top-opps",
        type=int,
        default=None,
        dest="top_opps",
        help="Override TOP_N_OPORTUNIDADES do resumo executivo.",
    )
    parser.add_argument(
        "--top-riscos",
        type=int,
        default=None,
        dest="top_riscos",
        help="Legado: aplica o mesmo N a DOI e FORWARD.",
    )
    args = parser.parse_args()

    settings = load_settings()
    thresholds = aplicar_overrides_thresholds(
        settings.thresholds,
        top_n_doi=args.top_doi,
        top_n_forward=args.top_forward,
        top_n_oportunidades=args.top_opps,
        top_n_riscos=args.top_riscos,
    )
    if thresholds is not settings.thresholds:
        settings = replace(settings, thresholds=thresholds)
    agente = AgenteOpenAI(settings)

    pergunta = (
        "Compare a demanda modelada com o baseline e compare o custo "
        "modelado com a DRE."
    )

    if args.arquivo_entrada:
        pergunta = (
            "Analise os dados do arquivo fornecido, identifique desvios "
            "e gere proposicoes de acao."
        )

    if args.modo == "legado":
        harness = Harness(agente=agente)
        resultado = harness.executar(pergunta)
        tipos_auditoria = TIPOS_HARNESS
    else:
        hitl = _criar_hitl(settings.hitl_mode)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=hitl,
            arquivo_entrada=args.arquivo_entrada,
        )
        resultado = nexus.executar(pergunta)
        tipos_auditoria = TIPOS_NEXUS

    if resultado.get("bloqueado"):
        print(f"\nExecucao bloqueada: {resultado.get('motivo', '')}")
        for log in resultado.get("logs", []):
            print(log)
        return

    auditoria = resultado.get("auditoria", {})

    if args.audit_out and auditoria:
        caminho = Path(args.audit_out)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(auditoria, arquivo, indent=2, ensure_ascii=True)
        print(f"\nAuditoria salva em: {caminho.resolve()}")

    print("\n==============================")
    print("LOGS (fluxo passo a passo)")
    print("==============================")
    for log in resultado.get("logs", []):
        print(log)

    if isinstance(auditoria, dict):
        _imprimir_resumo_auditoria(auditoria, tipos_auditoria)

    print("\n" + "=" * 60)
    print("  RESPOSTA FINAL (sumario executivo com output guardrail)")
    print("=" * 60)
    resultados = resultado.get("resultados", {})
    if isinstance(resultados, dict):
        explicacao = resultados.get("explicacao", "")
        print(explicacao)
    print("=" * 60)

    resumo_exec = resultado.get("resumo_executivo")
    if isinstance(resumo_exec, dict):
        print("\n" + formatar_resumo_executivo_texto(resumo_exec))

    fila = resultado.get("fila_nexus", [])
    if isinstance(fila, list):
        _imprimir_fila_nexus(fila)


if __name__ == "__main__":
    main()
