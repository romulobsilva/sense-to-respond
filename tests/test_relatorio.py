"""
Testes do relatorio analista HTML -> PDF.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from relatorio import (
    gerar_relatorio_analista,
    montar_html_relatorio,
    separar_narrativa_guardrail,
)
from state_types import Proposicao


def _item(
    prop_id: str,
    impacto: float,
    *,
    sku: str = "SKU-X",
    polaridade: str = "ruptura",
    tipo: str = "rebalancear_estoque_doi",
) -> Dict[str, Any]:
    """Item sintetico no contrato do resumo."""
    return {
        "proposicao_id": prop_id,
        "tipo": tipo,
        "titulo": f"Titulo {prop_id}",
        "skus": [sku],
        "impacto_financeiro": impacto,
        "impacto_priorizado": impacto,
        "urgencia_horas": 48,
        "descricao": "desc",
        "polaridade": polaridade,
    }


def _resumo() -> Dict[str, Any]:
    """Resumo minimo com tres blocos."""
    return {
        "top_doi": [
            _item("P1", 100.0, sku="SKU-A", polaridade="ruptura"),
            _item("P2", 80.0, sku="SKU-B", polaridade="overstock"),
        ],
        "top_forward": [
            _item(
                "P3",
                50.0,
                sku="SKU-C",
                polaridade="ruptura",
                tipo="questionar_premissa_plano",
            )
        ],
        "top_oportunidades": [
            _item(
                "P4",
                40.0,
                sku="SKU-D",
                polaridade="ruptura",
                tipo="capturar_oportunidade",
            )
        ],
        "n_doi": 2,
        "n_forward": 1,
        "n_oportunidades": 1,
        "total_candidatos_doi": 10,
        "total_candidatos_forward": 5,
        "total_candidatos_oportunidade": 3,
        "diversidade_doi": {
            "n_ruptura": 1,
            "n_overstock": 1,
            "candidatos_ruptura": 6,
            "candidatos_overstock": 4,
        },
        "diversidade_forward": {
            "n_ruptura": 1,
            "n_overstock": 0,
            "candidatos_ruptura": 3,
            "candidatos_overstock": 2,
        },
    }


def test_html_contem_secoes_e_ids(tmp_path: Path) -> None:
    """HTML inclui secoes obrigatorias e IDs do resumo."""
    props = [
        Proposicao(
            proposicao_id="P1",
            tipo="rebalancear_estoque_doi",
            titulo="Titulo P1",
            descricao="DOI atual 50d vs target 30d. SEGURAR sell-in.",
            impacto_financeiro=100.0,
            impacto_calculado=100.0,
            urgencia_horas=48,
            skus=["SKU-A"],
            evidencias=["SIG-DOI-1", "SIG-SO-2"],
        )
    ]
    html_doc = montar_html_relatorio(
        resumo=_resumo(),
        sessao_id="t1",
        explicacao=(
            "Narrativa de teste com acento: cen\u00e1rio.\n\n"
            "Segundo paragrafo.\n\n"
            "=== Citacoes (evidencias deterministicas) ===\n"
            "- [P1] ...\n"
            "- [P99] nao deve aparecer no dump bruto\n"
        ),
        arquivo_entrada="data/exemplo.csv",
        total_fila=12,
        revisao_obrigatoria=2,
        confianca_critic=0.9,
        critic_aprovado=True,
        proposicoes=props,
    )
    assert "Relat\u00f3rio anal\u00edtico" in html_doc
    assert "Cabe\u00e7alho da sess\u00e3o" in html_doc
    assert "DOI / Estoque" in html_doc
    assert "Forward / Plano" in html_doc
    assert "Oportunidades" in html_doc
    assert "An\u00e1lise narrativa" in html_doc
    assert "Evid\u00eancias do top N" in html_doc
    assert "Disclaimer" in html_doc
    assert "P1" in html_doc and "SKU-A" in html_doc
    assert "Narrativa de teste" in html_doc
    assert "cen\u00e1rio" in html_doc
    assert "SIG-DOI-1" in html_doc
    assert "evid-card" in html_doc
    assert "P99" not in html_doc
    assert "=== Citacoes" not in html_doc
    assert "data/exemplo.csv" in html_doc


def test_pt_apresentacao_corrige_doi_actual() -> None:
    """DOI actual (ingles) vira DOI atual na apresentacao."""
    from relatorio import _pt_apresentacao

    assert "DOI atual" in _pt_apresentacao("DOI actual 52d vs target")
    assert "DOI actual" not in _pt_apresentacao("DOI actual 52d")


def test_separar_narrativa_remove_citacoes() -> None:
    """Dump de citacoes do guardrail nao entra na narrativa."""
    texto = (
        "Visao geral com acento: an\u00e1lise.\n\n"
        "=== Citacoes (evidencias deterministicas) ===\n"
        "- [P1] muro de texto\n"
    )
    limpo = separar_narrativa_guardrail(texto)
    assert "an\u00e1lise" in limpo
    assert "Citacoes" not in limpo
    assert "P1" not in limpo


def test_gerar_html_e_pdf(tmp_path: Path) -> None:
    """Gera HTML e PDF quando WeasyPrint esta disponivel."""
    pytest.importorskip("weasyprint")
    meta = gerar_relatorio_analista(
        _resumo(),
        sessao_id="pdf-test",
        explicacao="Texto com disclaimer de teste.",
        diretorio_saida=tmp_path,
        total_fila=5,
        revisao_obrigatoria=1,
    )
    assert meta["html_ok"] is True
    assert Path(meta["caminho_html"]).is_file()
    assert "DOI / Estoque" in Path(meta["caminho_html"]).read_text(
        encoding="utf-8"
    )
    assert meta["ok"] is True, meta.get("erro")
    assert Path(meta["caminho"]).is_file()
    assert Path(meta["caminho"]).stat().st_size > 0


def test_numeros_bater_resumo(tmp_path: Path) -> None:
    """Contagens do meta refletem o resumo de entrada."""
    resumo = _resumo()
    meta = gerar_relatorio_analista(
        resumo,
        sessao_id="n-test",
        explicacao="x",
        diretorio_saida=tmp_path,
    )
    assert meta["n_doi"] == 2
    assert meta["n_forward"] == 1
    assert meta["n_oportunidades"] == 1


def test_codigo_sem_sku_hardcoded() -> None:
    """Relatorio nao hardcodar marcas de dominio."""
    fonte = Path("relatorio.py").read_text(encoding="utf-8")
    for termo in ("Belvita", "Tang", "Milka", "Oreo", "Halls"):
        assert termo not in fonte
