"""
Extracao de sinais estruturados a partir dos resultados do Dominion.
"""

from typing import Any, Dict, List

import pandas as pd

from state_types import Sinal


LIMIAR_SEVERIDADE_ALTA = 10.0
LIMIAR_SEVERIDADE_MEDIA = 5.0


def _classificar_severidade(desvio_pct: float) -> str:
    """
    Classifica severidade com base no desvio percentual absoluto.
    """
    abs_desvio = abs(desvio_pct)
    if abs_desvio >= LIMIAR_SEVERIDADE_ALTA:
        return "alta"
    if abs_desvio >= LIMIAR_SEVERIDADE_MEDIA:
        return "media"
    return "baixa"


def extrair_sinais_de_resultados(resultados: Dict[str, Any]) -> List[Sinal]:
    """
    Converte resultados deterministicos do Dominion em sinais estruturados.
    """
    sinais: List[Sinal] = []
    contador = 0

    if "comparacao_demanda" in resultados:
        df = resultados["comparacao_demanda"]
        if isinstance(df, pd.DataFrame):
            for _, linha in df.iterrows():
                sku_val = linha.get("sku", "")
                sku = str(sku_val) if sku_val is not None else ""
                demanda_real = float(linha.get("demanda_real", 0) or 0)
                demanda_modelada = float(linha.get("demanda_modelada", 0) or 0)
                desvio_pct = float(linha.get("delta_demanda_pct", 0) or 0)
                contador += 1
                sinais.append(Sinal(
                    sinal_id=f"SIG-DEM-{contador:03d}",
                    tipo="desvio_demanda",
                    sku=sku,
                    canal="geral",
                    metrica="demanda",
                    valor=demanda_modelada,
                    referencia=demanda_real,
                    desvio_pct=desvio_pct,
                    severidade=_classificar_severidade(desvio_pct),
                ))

    if "comparacao_custos" in resultados:
        custos = resultados["comparacao_custos"]
        if isinstance(custos, dict):
            custo_modelado = float(custos.get("custo_modelado_total", 0) or 0)
            custo_dre = float(custos.get("custo_dre", 0) or 0)
            desvio_pct = float(custos.get("delta_pct", 0) or 0)
            contador += 1
            sinais.append(Sinal(
                sinal_id=f"SIG-CUS-{contador:03d}",
                tipo="desvio_custo",
                sku="TOTAL",
                canal="geral",
                metrica="custo_frete",
                valor=custo_modelado,
                referencia=custo_dre,
                desvio_pct=desvio_pct,
                severidade=_classificar_severidade(desvio_pct),
            ))

    return sinais
