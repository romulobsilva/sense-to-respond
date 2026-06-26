"""
Ferramentas deterministicas (sem LLM).
"""

from typing import Any, Dict, List

import pandas as pd


def carregar_dados(_: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simula upload/leitura de arquivos.
    Em producao: CSV, XLSX, Parquet, banco etc.
    """
    baseline = pd.DataFrame(
        {
            "sku": ["SKU_1", "SKU_2", "SKU_3"],
            "demanda_real": [1000, 2000, 1500],
        }
    )

    modelado = pd.DataFrame(
        {
            "sku": ["SKU_1", "SKU_2", "SKU_3"],
            "demanda_modelada": [1100, 1800, 1500],
            "custo_modelado": [12000, 25000, 18000],
        }
    )

    dre = pd.DataFrame(
        {
            "categoria": ["frete_total"],
            "valor_dre": [50000],
        }
    )

    return {
        "baseline": baseline,
        "modelado": modelado,
        "dre": dre,
    }


def validar_demanda(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compara demanda real vs demanda modelada (calculo deterministico).
    """
    baseline = state["dados"]["baseline"]
    modelado = state["dados"]["modelado"]

    df = baseline.merge(modelado, on="sku", how="outer")
    df["delta_demanda"] = df["demanda_modelada"] - df["demanda_real"]
    df["delta_demanda_pct"] = df["delta_demanda"] / df["demanda_real"] * 100

    inconsistencias = df[df["delta_demanda_pct"].abs() > 10]

    return {
        "comparacao_demanda": df,
        "inconsistencias_demanda": inconsistencias,
    }


def validar_custos(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compara custo modelado total com valor da DRE.
    """
    modelado = state["dados"]["modelado"]
    dre = state["dados"]["dre"]

    custo_modelado_total = float(modelado["custo_modelado"].sum())
    custo_dre = float(
        dre.loc[dre["categoria"] == "frete_total", "valor_dre"].iloc[0]
    )

    delta = custo_modelado_total - custo_dre
    delta_pct = delta / custo_dre * 100

    resultado = {
        "custo_modelado_total": custo_modelado_total,
        "custo_dre": custo_dre,
        "delta": delta,
        "delta_pct": delta_pct,
    }

    return {
        "comparacao_custos": resultado,
    }


def listar_ferramentas() -> Dict[str, Any]:
    """
    Registro de ferramentas disponiveis para o harness.
    """
    return {
        "carregar_dados": carregar_dados,
        "validar_demanda": validar_demanda,
        "validar_custos": validar_custos,
    }


def resumir_estado_para_log(state: Dict[str, Any]) -> str:
    """
    Uma linha com o estado atual (para logs do harness).
    """
    acoes = state.get("acoes_executadas", [])
    tem_dados = bool(state.get("dados"))
    chaves_resultado = list(state.get("resultados", {}).keys())
    partes = [
        f"dados_carregados={'sim' if tem_dados else 'nao'}",
        f"acoes_executadas={acoes if acoes else '[]'}",
        f"chaves_em_resultados={chaves_resultado if chaves_resultado else '[]'}",
    ]
    return ", ".join(partes)


def resumir_efeito_ferramenta(
    nome_ferramenta: str,
    state: Dict[str, Any],
) -> str:
    """
    Resumo curto do que mudou no state apos executar uma tool.
    """
    if nome_ferramenta == "carregar_dados":
        dados = state.get("dados", {})
        baseline = dados.get("baseline")
        if baseline is not None:
            n = len(baseline)
            return f"state['dados'] atualizado: {n} SKUs em baseline/modelado/dre"
        return "state['dados'] atualizado"

    resultados = state.get("resultados", {})

    if nome_ferramenta == "validar_demanda":
        inc = resultados.get("inconsistencias_demanda")
        n_inc = len(inc) if inc is not None else 0
        return (
            "state['resultados'] += comparacao_demanda, inconsistencias_demanda "
            f"({n_inc} SKU(s) com divergencia > 10%)"
        )

    if nome_ferramenta == "validar_custos":
        custos = resultados.get("comparacao_custos", {})
        if custos:
            return (
                "state['resultados'] += comparacao_custos "
                f"(delta_pct={custos.get('delta_pct', 0):.2f}%)"
            )
        return "state['resultados'] += comparacao_custos"

    return f"ferramenta {nome_ferramenta} executada"


def serializar_contexto_agente(state: Dict[str, Any]) -> str:
    """
    Resume o estado atual para o LLM decidir o proximo passo.
    """
    linhas: List[str] = []
    acoes = state.get("acoes_executadas", [])
    if acoes:
        linhas.append(f"Acoes ja executadas: {', '.join(acoes)}")
    else:
        linhas.append("Acoes ja executadas: nenhuma")

    dados = state.get("dados", {})
    if dados:
        linhas.append("Dados carregados: sim (baseline, modelado, dre)")
    else:
        linhas.append("Dados carregados: nao")

    resultados = serializar_resultados_para_llm(state)
    if resultados != "Nenhum resultado de validacao disponivel.":
        linhas.append("")
        linhas.append(resultados)

    return "\n".join(linhas)


def serializar_resultados_para_llm(state: Dict[str, Any]) -> str:
    """
    Converte resultados numericos em texto para o prompt do LLM.
    """
    linhas: List[str] = []
    resultados = state.get("resultados", {})

    if "comparacao_demanda" in resultados:
        df = resultados["comparacao_demanda"]
        linhas.append("=== Comparacao de demanda ===")
        linhas.append(df.to_string(index=False))

        inc = resultados.get("inconsistencias_demanda")
        if inc is not None and len(inc) > 0:
            linhas.append("\nSKUs com divergencia > 10%:")
            linhas.append(inc.to_string(index=False))
        else:
            linhas.append("\nNenhum SKU com divergencia > 10%.")

    if "comparacao_custos" in resultados:
        custos = resultados["comparacao_custos"]
        linhas.append("\n=== Comparacao de custos ===")
        linhas.append(
            f"custo_modelado_total: {custos['custo_modelado_total']:.2f}"
        )
        linhas.append(f"custo_dre: {custos['custo_dre']:.2f}")
        linhas.append(f"delta: {custos['delta']:.2f}")
        linhas.append(f"delta_pct: {custos['delta_pct']:.2f}%")

    if not linhas:
        return "Nenhum resultado de validacao disponivel."

    return "\n".join(linhas)
