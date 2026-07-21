"""
Testes do export PNG do resumo executivo (plotagem deterministica).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from visualizacao import plotar_resumo_executivo


def _item(
    prop_id: str,
    impacto: float,
    *,
    sku: str = "SKU-X",
    polaridade: Optional[str] = "ruptura",
) -> Dict[str, Any]:
    """Monta um item sinteticamente no contrato do resumo."""
    dados: Dict[str, Any] = {
        "proposicao_id": prop_id,
        "tipo": "rebalancear_estoque_doi",
        "titulo": f"Titulo {prop_id}",
        "skus": [sku],
        "impacto_financeiro": impacto,
        "impacto_priorizado": impacto,
        "urgencia_horas": 48,
        "descricao": "desc",
    }
    if polaridade is not None:
        dados["polaridade"] = polaridade
    return dados


def _resumo(
    n_doi: int,
    n_fwd: int,
    n_opps: int,
) -> Dict[str, Any]:
    """Resumo sinteticamente dimensionado por N."""
    doi: List[Dict[str, Any]] = [
        _item(f"D{i}", float(1000 * (n_doi - i + 1)), sku=f"SKU-D{i}")
        for i in range(1, n_doi + 1)
    ]
    fwd: List[Dict[str, Any]] = [
        _item(
            f"F{i}",
            float(500 * (n_fwd - i + 1)),
            sku=f"SKU-F{i}",
            polaridade="overstock",
        )
        for i in range(1, n_fwd + 1)
    ]
    opps: List[Dict[str, Any]] = [
        _item(
            f"O{i}",
            float(300 * (n_opps - i + 1)),
            sku=f"SKU-O{i}",
            polaridade=None,
        )
        for i in range(1, n_opps + 1)
    ]
    for item in opps:
        item["tipo"] = "capturar_oportunidade"
    return {
        "top_doi": doi,
        "top_forward": fwd,
        "top_oportunidades": opps,
        "n_doi": n_doi,
        "n_forward": n_fwd,
        "n_oportunidades": n_opps,
        "total_candidatos_doi": n_doi,
        "total_candidatos_forward": n_fwd,
        "total_candidatos_oportunidade": n_opps,
        "diversidade_doi": {},
        "diversidade_forward": {},
    }


def test_plot_gera_png_e_contagens(tmp_path: Path) -> None:
    """Resumo nao vazio produz PNG com contagens corretas."""
    resumo = _resumo(3, 2, 1)
    destino = tmp_path / "rec.png"
    meta = plotar_resumo_executivo(
        resumo,
        caminho_saida=destino,
        sessao_id="teste-abc",
    )
    assert meta["ok"] is True
    assert meta["erro"] is None
    assert meta["n_doi"] == 3
    assert meta["n_forward"] == 2
    assert meta["n_oportunidades"] == 1
    assert Path(meta["caminho"]).is_file()
    assert Path(meta["caminho"]).stat().st_size > 0


def test_plot_n_diferente_muda_contagens(tmp_path: Path) -> None:
    """Alterar N muda o numero de itens reportados no metadado."""
    meta3 = plotar_resumo_executivo(
        _resumo(3, 3, 3),
        caminho_saida=tmp_path / "n3.png",
        sessao_id="n3",
    )
    meta5 = plotar_resumo_executivo(
        _resumo(5, 5, 5),
        caminho_saida=tmp_path / "n5.png",
        sessao_id="n5",
    )
    assert meta3["ok"] and meta5["ok"]
    assert meta3["n_doi"] == 3
    assert meta5["n_doi"] == 5
    assert Path(meta3["caminho"]).stat().st_size != Path(
        meta5["caminho"]
    ).stat().st_size


def test_plot_listas_vazias_ainda_gera_arquivo(tmp_path: Path) -> None:
    """Blocos vazios nao quebram a geracao."""
    meta = plotar_resumo_executivo(
        _resumo(0, 0, 0),
        caminho_saida=tmp_path / "vazio.png",
        sessao_id="vazio",
    )
    assert meta["ok"] is True
    assert meta["n_doi"] == 0
    assert meta.get("paineis_sem_grafico") == [
        "DOI / Estoque",
        "Forward / Plano",
        "Oportunidades",
    ]
    assert Path(meta["caminho"]).is_file()


def test_plot_rejeita_extensao_invalida(tmp_path: Path) -> None:
    """Extensao diferente de .png e erro de contrato."""
    with pytest.raises(ValueError, match="\\.png"):
        plotar_resumo_executivo(
            _resumo(1, 0, 0),
            caminho_saida=tmp_path / "x.jpg",
            sessao_id="x",
        )


def test_plot_codigo_fonte_sem_sku_hardcoded() -> None:
    """Plotter nao deve hardcodar marcas/SKUs de dominio."""
    fonte = Path("visualizacao.py").read_text(encoding="utf-8")
    proibidos = ("Belvita", "Tang", "Milka", "Oreo", "Halls", "Diamante")
    for termo in proibidos:
        assert termo not in fonte


def test_titulo_png_usa_sessao_com_acento() -> None:
    """Rotulo visivel do titulo usa 'sessao' acentuado (UTF-8)."""
    fonte = Path("visualizacao.py").read_text(encoding="utf-8")
    assert "sess\\u00e3o=" in fonte or "sessão=" in fonte
