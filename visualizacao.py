"""
Export grafico deterministico do resumo executivo (top N).

Le apenas state.resumo_executivo / dict equivalente. Nao chama LLM e nao
recalcula ranking nem impactos financeiros.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Fonte com suporte a acentos PT-BR no PNG.
plt.rcParams["font.family"] = "DejaVu Sans"

DIR_OUTPUT_DEFAULT = "output"
NOME_ARQUIVO_PADRAO = "recomendacoes_{sessao_id}.png"

CHAVES_BLOCOS: Tuple[Tuple[str, str], ...] = (
    ("top_doi", "DOI / Estoque"),
    ("top_forward", "Forward / Plano"),
    ("top_oportunidades", "Oportunidades"),
)

COR_RUPTURA = "#C44E52"
COR_OVERSTOCK = "#4C72B0"
COR_OPORTUNIDADE = "#55A868"
COR_PADRAO = "#8172B3"


def _as_item_list(valor: Any) -> List[Dict[str, Any]]:
    """
    Normaliza um bloco do resumo para lista de dicts.

    Args:
        valor: Conteudo de top_* no resumo.

    Returns:
        Lista de itens plotaveis (dicts). Ignora entradas invalidas.
    """
    if not isinstance(valor, list):
        return []
    itens: List[Dict[str, Any]] = []
    for raw in valor:
        if isinstance(raw, dict):
            itens.append(raw)
    return itens


def _label_item(item: Mapping[str, Any], indice: int) -> str:
    """
    Monta label curto data-driven (sem hardcode de SKU/marca).

    Args:
        item: Item do top N.
        indice: Posicao 1-based no bloco.

    Returns:
        Texto para o eixo Y.
    """
    prop_id = str(item.get("proposicao_id") or f"#{indice}")
    skus = item.get("skus")
    sku_txt = ""
    if isinstance(skus, Sequence) and not isinstance(skus, (str, bytes)):
        if len(skus) > 0:
            sku_txt = str(skus[0])
    polaridade = item.get("polaridade")
    partes = [prop_id]
    if sku_txt:
        partes.append(sku_txt)
    if isinstance(polaridade, str) and polaridade:
        partes.append(polaridade)
    return " | ".join(partes)


def _impacto(item: Mapping[str, Any]) -> float:
    """
    Impacto a plotar: priorizado se existir, senao financeiro.

    Args:
        item: Item do top N.

    Returns:
        Valor numerico (0.0 se ausente/invalido).
    """
    for chave in ("impacto_priorizado", "impacto_financeiro"):
        bruto = item.get(chave)
        if isinstance(bruto, (int, float)):
            return float(bruto)
        if isinstance(bruto, str):
            try:
                return float(bruto)
            except ValueError:
                continue
    return 0.0


def _cor_item(item: Mapping[str, Any], chave_bloco: str) -> str:
    """
    Cor por polaridade ou tipo de bloco.

    Args:
        item: Item do top N.
        chave_bloco: Chave top_* do resumo.

    Returns:
        Hex color.
    """
    if chave_bloco == "top_oportunidades":
        return COR_OPORTUNIDADE
    polaridade = item.get("polaridade")
    if polaridade == "ruptura":
        return COR_RUPTURA
    if polaridade == "overstock":
        return COR_OVERSTOCK
    return COR_PADRAO


def _resolver_caminho(
    caminho_saida: Optional[Union[str, Path]],
    diretorio_saida: Union[str, Path],
    sessao_id: str,
) -> Path:
    """
    Resolve path final do PNG e garante diretorio pai.

    Args:
        caminho_saida: Path explicito do arquivo (opcional).
        diretorio_saida: Pasta default quando caminho nao e passado.
        sessao_id: Id usado no nome do arquivo.

    Returns:
        Path absoluto do PNG.
    """
    if caminho_saida is not None:
        destino = Path(caminho_saida)
    else:
        safe_id = sessao_id.strip() if sessao_id.strip() else "sem_sessao"
        destino = Path(diretorio_saida) / NOME_ARQUIVO_PADRAO.format(
            sessao_id=safe_id
        )
    destino = destino.resolve()
    if destino.suffix.lower() != ".png":
        raise ValueError("caminho_saida deve ter extensao .png")
    destino.parent.mkdir(parents=True, exist_ok=True)
    return destino


def _rotulo_eixo_impacto(fonte_dados: Optional[str]) -> str:
    """Rotulo do eixo X conforme unidade do run (PBI = ton proxy)."""
    if (fonte_dados or "").strip().lower() == "pbi":
        return "Impacto priorizado (ton SO proxy)"
    return "Impacto priorizado (NR)"


def plotar_resumo_executivo(
    resumo: Mapping[str, Any],
    *,
    caminho_saida: Optional[Union[str, Path]] = None,
    diretorio_saida: Union[str, Path] = DIR_OUTPUT_DEFAULT,
    sessao_id: str = "sessao",
    fonte_dados: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Gera PNG com tres blocos horizontais a partir do resumo executivo.

    Data-driven: plota exatamente os itens presentes em cada lista top_*.
    Variacoes de N ou do CSV de entrada refletem-se no grafico sem
    alterar esta funcao. Blocos vazios exibem aviso explicito de que o
    grafico daquele painel nao foi gerado (sem candidatos no top N).

    Args:
        resumo: Dict no formato de montar_resumo_executivo.
        caminho_saida: Arquivo PNG de destino (opcional).
        diretorio_saida: Pasta quando caminho_saida e None.
        sessao_id: Identificador da sessao (nome do arquivo / titulo).
        fonte_dados: "pbi" | "csv" | "simulado" (rotulo do eixo).

    Returns:
        Metadados: ok, caminho, contagens por bloco, erro opcional.

    Raises:
        TypeError: Se resumo nao for mapping.
        ValueError: Se extensao de saida for invalida.
    """
    if not isinstance(resumo, Mapping):
        raise TypeError("resumo deve ser um mapping (dict)")

    destino = _resolver_caminho(caminho_saida, diretorio_saida, sessao_id)
    contagens = {
        "n_doi": len(_as_item_list(resumo.get("top_doi"))),
        "n_forward": len(_as_item_list(resumo.get("top_forward"))),
        "n_oportunidades": len(_as_item_list(resumo.get("top_oportunidades"))),
    }
    eixo_impacto = _rotulo_eixo_impacto(fonte_dados)
    paineis_sem_grafico: List[str] = []

    try:
        fig, eixos = plt.subplots(
            nrows=3,
            ncols=1,
            figsize=(11.0, 9.0),
            constrained_layout=True,
        )
        fig.suptitle(
            f"Resumo executivo top N | sess\u00e3o={sessao_id}",
            fontsize=12,
        )

        for eixo, (chave, titulo) in zip(eixos, CHAVES_BLOCOS):
            itens = _as_item_list(resumo.get(chave))
            eixo.set_title(titulo, loc="left", fontsize=10)
            if not itens:
                paineis_sem_grafico.append(titulo)
                eixo.text(
                    0.5,
                    0.5,
                    "(sem itens: grafico nao gerado)",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="#555555",
                )
                eixo.set_xticks([])
                eixo.set_yticks([])
                continue

            # Ordem visual: maior impacto no topo
            ordenados = sorted(itens, key=_impacto, reverse=True)
            labels = [
                _label_item(item, idx)
                for idx, item in enumerate(ordenados, start=1)
            ]
            valores = [_impacto(item) for item in ordenados]
            cores = [_cor_item(item, chave) for item in ordenados]
            posicoes = list(range(len(ordenados)))
            eixo.barh(posicoes, valores, color=cores)
            eixo.set_yticks(posicoes)
            eixo.set_yticklabels(labels, fontsize=8)
            eixo.invert_yaxis()
            eixo.set_xlabel(eixo_impacto)
            eixo.grid(axis="x", linestyle=":", alpha=0.4)

        fig.savefig(destino, dpi=120, format="png")
        plt.close(fig)
    except Exception as exc:
        plt.close("all")
        return {
            "ok": False,
            "tipo": "resumo_executivo_png",
            "caminho": str(destino),
            "sessao_id": sessao_id,
            "erro": str(exc)[:300],
            **contagens,
        }

    return {
        "ok": True,
        "tipo": "resumo_executivo_png",
        "caminho": str(destino),
        "sessao_id": sessao_id,
        "erro": None,
        "paineis_sem_grafico": paineis_sem_grafico,
        **contagens,
    }
