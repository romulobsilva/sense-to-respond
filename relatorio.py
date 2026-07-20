"""
Relatorio analista S&OE: HTML + PDF (WeasyPrint) em output/.

Monta apresentacao a partir de resumo_executivo, PNG e explicacao
pos-guardrail. Nao chama LLM e nao recalcula ranking/impactos.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

DIR_OUTPUT_DEFAULT = "output"
NOME_HTML = "relatorio_{sessao_id}.html"
NOME_PDF = "relatorio_{sessao_id}.pdf"

CHAVES_BLOCOS = (
    ("top_doi", "DOI / Estoque", "n_doi"),
    ("top_forward", "Forward / Plano", "n_forward"),
    ("top_oportunidades", "Oportunidades", "n_oportunidades"),
)


def _as_items(valor: Any) -> List[Dict[str, Any]]:
    """Normaliza lista de itens do resumo."""
    if not isinstance(valor, list):
        return []
    return [x for x in valor if isinstance(x, dict)]


def _esc(texto: Any) -> str:
    """Escape HTML seguro."""
    return html.escape("" if texto is None else str(texto), quote=True)


def _fmt_num(valor: Any) -> str:
    """Formata numero para tabela."""
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace(
            "X", "."
        )
    except (TypeError, ValueError):
        return _esc(valor)


def _impacto(item: Mapping[str, Any]) -> float:
    """Impacto priorizado ou financeiro."""
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


def _sku(item: Mapping[str, Any]) -> str:
    """Primeiro SKU do item, se houver."""
    skus = item.get("skus")
    if isinstance(skus, Sequence) and not isinstance(skus, (str, bytes)):
        if len(skus) > 0:
            return str(skus[0])
    return "-"


def _png_data_uri(caminho_png: Optional[Union[str, Path]]) -> Optional[str]:
    """
    Converte PNG em data URI para embutir no HTML.

    Returns:
        data:image/png;base64,... ou None se arquivo ausente.
    """
    if caminho_png is None:
        return None
    path = Path(caminho_png)
    if not path.is_file():
        return None
    bruto = path.read_bytes()
    b64 = base64.b64encode(bruto).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _leitura_bloco(titulo: str, chave: str, itens: List[Dict[str, Any]]) -> str:
    """
    Texto deterministico de interpretacao do bloco (sem LLM).

    Args:
        titulo: Nome do bloco.
        chave: Chave top_*.
        itens: Itens do bloco.

    Returns:
        Paragrafo ASCII-safe para HTML (ja escapado).
    """
    if not itens:
        return _esc(
            f"{titulo}: nenhum item no top N deste run "
            f"(sem candidatos ou N=0)."
        )

    n_rup = sum(1 for i in itens if i.get("polaridade") == "ruptura")
    n_over = sum(1 for i in itens if i.get("polaridade") == "overstock")
    ordenados = sorted(itens, key=_impacto, reverse=True)
    topo = ordenados[0]
    topo_sku = _sku(topo)
    topo_id = str(topo.get("proposicao_id") or "?")
    topo_i = _impacto(topo)

    if chave == "top_doi":
        papel = (
            "Prioridade operacional de estoque: ruptura pede reposicao/"
            "rebalanceamento; overstock pede conter sell-in."
        )
    elif chave == "top_forward":
        papel = (
            "Prioridade de plano: questionar premissas forward que "
            "desalinha demanda e estoque."
        )
    else:
        papel = (
            "Prioridade de captura: demanda acima do plano com espaco "
            "para aumentar sell-in / alinhar baseline."
        )

    partes = [
        f"{titulo}: {len(itens)} item(ns) no top N.",
        papel,
    ]
    if n_rup or n_over:
        partes.append(
            f"Polaridade no bloco: ruptura={n_rup}, overstock={n_over}."
        )
    partes.append(
        f"Maior impacto priorizado: {topo_id} ({topo_sku}) = "
        f"{topo_i:,.2f} NR."
    )
    return _esc(" ".join(partes))


def _tabela_bloco(itens: List[Dict[str, Any]]) -> str:
    """HTML table para um bloco top N."""
    if not itens:
        return "<p><em>(sem itens)</em></p>"
    ordenados = sorted(itens, key=_impacto, reverse=True)
    linhas = [
        "<table>",
        "<thead><tr>"
        "<th>ID</th><th>SKU</th><th>Tipo</th><th>Polaridade</th>"
        "<th>Impacto prio.</th><th>Urgencia (h)</th><th>Titulo</th>"
        "</tr></thead><tbody>",
    ]
    for item in ordenados:
        linhas.append(
            "<tr>"
            f"<td>{_esc(item.get('proposicao_id'))}</td>"
            f"<td>{_esc(_sku(item))}</td>"
            f"<td>{_esc(item.get('tipo'))}</td>"
            f"<td>{_esc(item.get('polaridade') or '-')}</td>"
            f"<td class='num'>{_fmt_num(_impacto(item))}</td>"
            f"<td class='num'>{_esc(item.get('urgencia_horas'))}</td>"
            f"<td>{_esc(item.get('titulo'))}</td>"
            "</tr>"
        )
    linhas.append("</tbody></table>")
    return "\n".join(linhas)


def _narrativa_html(texto: str) -> str:
    """Converte texto narrativo em paragrafos HTML escapados."""
    bruto = (texto or "").strip()
    if not bruto:
        return "<p><em>(sem narrativa LLM neste run)</em></p>"
    blocos = [b.strip() for b in bruto.split("\n\n") if b.strip()]
    if len(blocos) <= 1:
        blocos = [b.strip() for b in bruto.split("\n") if b.strip()]
    return "\n".join(f"<p>{_esc(b)}</p>" for b in blocos)


def montar_html_relatorio(
    *,
    resumo: Mapping[str, Any],
    sessao_id: str,
    explicacao: str,
    caminho_png: Optional[Union[str, Path]] = None,
    arquivo_entrada: Optional[str] = None,
    total_fila: int = 0,
    revisao_obrigatoria: int = 0,
    confianca_critic: Optional[float] = None,
    critic_aprovado: Optional[bool] = None,
) -> str:
    """
    Monta HTML completo do relatorio analista.

    Args:
        resumo: Dict resumo_executivo.
        sessao_id: Id da sessao.
        explicacao: Texto pos-output-guardrail.
        caminho_png: PNG do top N (opcional).
        arquivo_entrada: Path do CSV/XLSX.
        total_fila: Tamanho da fila Nexus.
        revisao_obrigatoria: Itens com revisao obrigatoria.
        confianca_critic: Score do Critic, se houver.
        critic_aprovado: Flag de aprovacao do Critic.

    Returns:
        Documento HTML como string.
    """
    if not isinstance(resumo, Mapping):
        raise TypeError("resumo deve ser um mapping")

    data_uri = _png_data_uri(caminho_png)
    img_html = (
        f'<img class="chart" src="{data_uri}" alt="Grafico top N"/>'
        if data_uri
        else "<p><em>Grafico PNG nao disponivel neste run.</em></p>"
    )

    div_d = resumo.get("diversidade_doi") or {}
    div_f = resumo.get("diversidade_forward") or {}
    if not isinstance(div_d, dict):
        div_d = {}
    if not isinstance(div_f, dict):
        div_f = {}

    critic_txt = "n/d"
    if confianca_critic is not None:
        aprov = "aprovado" if critic_aprovado else "nao aprovado"
        if critic_aprovado is None:
            aprov = "n/d"
        critic_txt = f"{confianca_critic:.2f} ({aprov})"

    secoes_blocos: List[str] = []
    for idx, (chave, titulo, _meta) in enumerate(CHAVES_BLOCOS, start=3):
        itens = _as_items(resumo.get(chave))
        secoes_blocos.append(
            f"<section class='bloco'>"
            f"<h2>{idx}. {_esc(titulo)}</h2>"
            f"{_tabela_bloco(itens)}"
            f"<h3>Leitura do bloco</h3>"
            f"<p>{_leitura_bloco(titulo, chave, itens)}</p>"
            f"</section>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Relatorio S&amp;OE - {_esc(sessao_id)}</title>
<style>
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt;
         color: #222; margin: 24px; line-height: 1.35; }}
  h1 {{ font-size: 18pt; margin-bottom: 4px; }}
  h2 {{ font-size: 13pt; margin-top: 22px; border-bottom: 1px solid #ccc;
        padding-bottom: 4px; }}
  h3 {{ font-size: 11pt; margin-top: 12px; }}
  .meta {{ background: #f5f5f5; padding: 10px 12px; margin: 12px 0; }}
  .meta dt {{ font-weight: bold; }}
  .meta dd {{ margin: 0 0 6px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 12px;
           font-size: 9pt; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 6px; text-align: left;
            vertical-align: top; }}
  th {{ background: #eee; }}
  td.num {{ text-align: right; white-space: nowrap; }}
  img.chart {{ max-width: 100%; height: auto; margin: 10px 0; }}
  .aviso {{ background: #fff8e6; border-left: 4px solid #c90;
            padding: 8px 10px; margin: 14px 0; }}
  .disclaimer {{ background: #f0f0f0; padding: 10px; margin-top: 18px;
                 font-size: 9pt; }}
</style>
</head>
<body>
<h1>Relatorio analitico Sense to Respond</h1>
<p>Sessao <strong>{_esc(sessao_id)}</strong></p>

<section>
<h2>1. Cabecalho da sessao</h2>
<dl class="meta">
  <dt>Arquivo de entrada</dt><dd>{_esc(arquivo_entrada or "(simulacao / n/d)")}</dd>
  <dt>Top N (DOI / Forward / Opps)</dt>
  <dd>{_esc(resumo.get("n_doi"))} / {_esc(resumo.get("n_forward"))} /
      {_esc(resumo.get("n_oportunidades"))}</dd>
  <dt>Candidatos (DOI / Forward / Opps)</dt>
  <dd>{_esc(resumo.get("total_candidatos_doi"))} /
      {_esc(resumo.get("total_candidatos_forward"))} /
      {_esc(resumo.get("total_candidatos_oportunidade"))}</dd>
  <dt>Diversidade DOI (ruptura/overstock no top)</dt>
  <dd>{_esc(div_d.get("n_ruptura", "-"))} /
      {_esc(div_d.get("n_overstock", "-"))}</dd>
  <dt>Diversidade Forward (ruptura/overstock no top)</dt>
  <dd>{_esc(div_f.get("n_ruptura", "-"))} /
      {_esc(div_f.get("n_overstock", "-"))}</dd>
  <dt>Fila Nexus</dt>
  <dd>{_esc(total_fila)} proposicoes
      ({_esc(revisao_obrigatoria)} com revisao obrigatoria)</dd>
  <dt>Critic</dt><dd>{_esc(critic_txt)}</dd>
</dl>
</section>

<section>
<h2>2. Grafico de priorizacao (top N)</h2>
{img_html}
<p>Barras por impacto priorizado. Vermelho=ruptura, azul=overstock,
verde=oportunidade. Ordem visual por impacto dentro de cada bloco;
o ranking oficial permanece o de <code>resumo_executivo</code>.</p>
</section>

{"".join(secoes_blocos)}

<section>
<h2>6. Analise narrativa</h2>
<p class="aviso">Texto gerado pelo LLM a partir de evidencias deterministicas.
Nao recalcula NR nem reordena o top N. Passou pelo output guardrail.</p>
{_narrativa_html(explicacao)}
</section>

<section>
<h2>7. HITL e limitacoes</h2>
<ul>
  <li>Este relatorio e apoio a decisao; nao executa acoes em ERP/WMS.</li>
  <li>A fila completa ({_esc(total_fila)} itens) permanece disponivel para
      revisao humana; o top N e um recorte executivo.</li>
  <li>Itens com revisao obrigatoria: {_esc(revisao_obrigatoria)}.</li>
  <li>Validar evidencias e contexto de negocio antes de aprovar proposicoes.</li>
</ul>
<div class="disclaimer">
<strong>Disclaimer:</strong> recomendacoes automatizadas com base em dados
do periodo carregado. Exige revisao humana. Numeros de impacto e ranking
sao deterministicos (Optimus/resumo executivo).
</div>
</section>
</body>
</html>
"""
    return html_doc


def gerar_relatorio_analista(
    resumo: Mapping[str, Any],
    *,
    sessao_id: str = "sessao",
    explicacao: str = "",
    caminho_png: Optional[Union[str, Path]] = None,
    diretorio_saida: Union[str, Path] = DIR_OUTPUT_DEFAULT,
    arquivo_entrada: Optional[str] = None,
    total_fila: int = 0,
    revisao_obrigatoria: int = 0,
    confianca_critic: Optional[float] = None,
    critic_aprovado: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Gera HTML e tenta exportar PDF via WeasyPrint.

    Returns:
        Metadados com ok/html_ok, caminhos e erro opcional.
    """
    safe_id = sessao_id.strip() if sessao_id.strip() else "sem_sessao"
    out_dir = Path(diretorio_saida)
    out_dir.mkdir(parents=True, exist_ok=True)
    path_html = (out_dir / NOME_HTML.format(sessao_id=safe_id)).resolve()
    path_pdf = (out_dir / NOME_PDF.format(sessao_id=safe_id)).resolve()

    meta: Dict[str, Any] = {
        "tipo": "relatorio_analista_pdf",
        "sessao_id": safe_id,
        "caminho": str(path_pdf),
        "caminho_pdf": str(path_pdf),
        "caminho_html": str(path_html),
        "ok": False,
        "html_ok": False,
        "erro": None,
        "n_doi": len(_as_items(resumo.get("top_doi"))),
        "n_forward": len(_as_items(resumo.get("top_forward"))),
        "n_oportunidades": len(_as_items(resumo.get("top_oportunidades"))),
    }

    try:
        html_doc = montar_html_relatorio(
            resumo=resumo,
            sessao_id=safe_id,
            explicacao=explicacao,
            caminho_png=caminho_png,
            arquivo_entrada=arquivo_entrada,
            total_fila=total_fila,
            revisao_obrigatoria=revisao_obrigatoria,
            confianca_critic=confianca_critic,
            critic_aprovado=critic_aprovado,
        )
        path_html.write_text(html_doc, encoding="utf-8")
        meta["html_ok"] = True
    except Exception as exc:
        meta["erro"] = f"html: {str(exc)[:300]}"
        return meta

    try:
        from weasyprint import HTML

        HTML(filename=str(path_html)).write_pdf(str(path_pdf))
        meta["ok"] = path_pdf.is_file() and path_pdf.stat().st_size > 0
        if not meta["ok"]:
            meta["erro"] = "pdf: arquivo vazio ou nao criado"
    except Exception as exc:
        meta["ok"] = False
        meta["erro"] = f"pdf: {str(exc)[:300]}"

    return meta
