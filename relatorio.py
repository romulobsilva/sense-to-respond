"""
Relatorio analista S&OE: HTML + PDF (WeasyPrint) em output/.

Monta apresentacao a partir de resumo_executivo, PNG e explicacao
pos-guardrail. Nao chama LLM e nao recalcula ranking/impactos.

Texto de interface ao usuario usa UTF-8 (acentos em portugues).
"""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from state_types import Proposicao

DIR_OUTPUT_DEFAULT = "output"
NOME_HTML = "relatorio_{sessao_id}.html"
NOME_PDF = "relatorio_{sessao_id}.pdf"

CHAVES_BLOCOS = (
    ("top_doi", "DOI / Estoque", "n_doi"),
    ("top_forward", "Forward / Plano", "n_forward"),
    ("top_oportunidades", "Oportunidades", "n_oportunidades"),
)

# Marcadores do bloco bruto anexado pelo output guardrail (ASCII no codigo fonte).
_RE_INICIO_CITACOES = re.compile(
    r"^===\s*Citac(?:oes|ões)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_RE_LINHA_DISCLAIMER = re.compile(
    r"^\[?(DISCLAIMER|AVISO|REVISAO OBRIGATORIA)",
    re.IGNORECASE,
)


def _as_items(valor: Any) -> List[Dict[str, Any]]:
    """Normaliza lista de itens do resumo."""
    if not isinstance(valor, list):
        return []
    return [x for x in valor if isinstance(x, dict)]


def _pt_apresentacao(texto: Any) -> str:
    """
    Normaliza termos em ingles/ASCII comuns antes de exibir no relatorio.

    Preserva UTF-8. Nao altera IDs (P1, SIG-*) nem numeros.
    """
    saida = "" if texto is None else str(texto)
    saida = saida.replace("DOI actual", "DOI atual")
    saida = saida.replace("DOI Actual", "DOI atual")
    return saida


def _esc(texto: Any) -> str:
    """Escape HTML seguro apos normalizacao PT (preserva acentos UTF-8)."""
    return html.escape(_pt_apresentacao(texto), quote=True)


def _fmt_num(valor: Any) -> str:
    """Formata numero para tabela (pt-BR)."""
    try:
        return f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace(
            "X", "."
        )
    except (TypeError, ValueError):
        return _esc(valor)


def _eh_fonte_pbi(fonte_dados: Optional[str]) -> bool:
    """True quando o run veio do caminho Power BI."""
    return (fonte_dados or "").strip().lower() == "pbi"


def _rotulo_unidade_impacto(fonte_dados: Optional[str]) -> str:
    """
    Rotulo da unidade de impacto na apresentacao.

    CSV/simulado: NR em moeda (R$).
    PBI: prefer NR USD do modelo; fallback ton em alguns sinais (STA).
    """
    if _eh_fonte_pbi(fonte_dados):
        return "NR USD / ton (PBI)"
    return "R$"


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
    """Converte PNG em data URI para embutir no HTML."""
    if caminho_png is None:
        return None
    path = Path(caminho_png)
    if not path.is_file():
        return None
    bruto = path.read_bytes()
    b64 = base64.b64encode(bruto).decode("ascii")
    return f"data:image/png;base64,{b64}"


def separar_narrativa_guardrail(texto: str) -> str:
    """
    Extrai so a narrativa LLM, removendo disclaimer e bloco de citacoes brutas.

    O dump '=== Citacoes ===' com centenas de proposicoes nao deve ir ao PDF
    como texto corrido; as evidencias do top N sao montadas em HTML estruturado.
    """
    bruto = (texto or "").strip()
    if not bruto:
        return ""

    match = _RE_INICIO_CITACOES.search(bruto)
    if match is not None:
        bruto = bruto[: match.start()].rstrip()

    linhas_uteis: List[str] = []
    for linha in bruto.splitlines():
        if _RE_LINHA_DISCLAIMER.match(linha.strip()):
            continue
        # Linha tipica do disclaimer obrigatorio (guardrails).
        if "nao constitui ordem de execucao" in linha.lower():
            continue
        if linha.strip().startswith("DISCLAIMER"):
            continue
        linhas_uteis.append(linha)
    return "\n".join(linhas_uteis).strip()


def _narrativa_html(texto: str) -> str:
    """Converte narrativa em paragrafos HTML (UTF-8 / acentos preservados)."""
    bruto = separar_narrativa_guardrail(texto)
    if not bruto:
        return "<p><em>(sem narrativa LLM neste run)</em></p>"

    paragrafos = [b.strip() for b in re.split(r"\n\s*\n", bruto) if b.strip()]
    if not paragrafos:
        paragrafos = [bruto]

    html_parts: List[str] = []
    for bloco in paragrafos:
        # Quebras simples viram <br> dentro do paragrafo.
        linhas = [_esc(ln.strip()) for ln in bloco.split("\n") if ln.strip()]
        html_parts.append("<p>" + "<br/>\n".join(linhas) + "</p>")
    return "\n".join(html_parts)


def _ids_top_n(resumo: Mapping[str, Any]) -> List[str]:
    """Lista ordenada e unica de proposicao_id presentes nos tops."""
    vistos: set[str] = set()
    ordenados: List[str] = []
    for chave, _titulo, _meta in CHAVES_BLOCOS:
        for item in _as_items(resumo.get(chave)):
            pid = item.get("proposicao_id")
            if isinstance(pid, str) and pid and pid not in vistos:
                vistos.add(pid)
                ordenados.append(pid)
    return ordenados


def _mapa_proposicoes(
    proposicoes: Optional[Sequence[Proposicao]],
) -> Dict[str, Proposicao]:
    """Indexa proposicoes por id."""
    mapa: Dict[str, Proposicao] = {}
    if not proposicoes:
        return mapa
    for prop in proposicoes:
        mapa[prop.proposicao_id] = prop
    return mapa


def _evidencias_top_n_html(
    resumo: Mapping[str, Any],
    proposicoes: Optional[Sequence[Proposicao]],
    *,
    fonte_dados: Optional[str] = None,
) -> str:
    """
    Cards HTML so para o top N (nao a fila inteira).

    Cada card: ID, titulo, descricao, impacto, urgencia, evidencias.
    """
    ids = _ids_top_n(resumo)
    if not ids:
        return (
            "<p><em>(nenhum item no top N para evid\u00eancias)</em></p>"
        )

    unidade = _rotulo_unidade_impacto(fonte_dados)
    mapa = _mapa_proposicoes(proposicoes)
    # polaridade por id a partir do resumo
    pol_por_id: Dict[str, str] = {}
    for chave, _t, _m in CHAVES_BLOCOS:
        for item in _as_items(resumo.get(chave)):
            pid = item.get("proposicao_id")
            if isinstance(pid, str) and item.get("polaridade"):
                pol_por_id[pid] = str(item.get("polaridade"))

    cards: List[str] = [
        "<p class='aviso'>Evid\u00eancias determin\u00edsticas apenas das "
        "proposi\u00e7\u00f5es do top N (recorte executivo). "
        "A fila completa permanece no HITL.</p>"
    ]

    for pid in ids:
        prop = mapa.get(pid)
        if prop is None:
            # Fallback a partir do item do resumo.
            item_resumo: Optional[Dict[str, Any]] = None
            for chave, _t, _m in CHAVES_BLOCOS:
                for item in _as_items(resumo.get(chave)):
                    if item.get("proposicao_id") == pid:
                        item_resumo = item
                        break
                if item_resumo is not None:
                    break
            if item_resumo is None:
                continue
            cards.append(
                "<article class='evid-card'>"
                f"<h3>{_esc(pid)} — {_esc(item_resumo.get('titulo'))}</h3>"
                f"<p><strong>Tipo:</strong> {_esc(item_resumo.get('tipo'))} "
                f"| <strong>Polaridade:</strong> "
                f"{_esc(pol_por_id.get(pid, '-'))}</p>"
                f"<p>{_esc(item_resumo.get('descricao'))}</p>"
                f"<p><strong>Impacto:</strong> {_esc(unidade)} "
                f"{_fmt_num(item_resumo.get('impacto_financeiro'))} "
                f"| <strong>Urg\u00eancia:</strong> "
                f"{_esc(item_resumo.get('urgencia_horas'))}h</p>"
                "<p><strong>Evid\u00eancias:</strong> "
                "<em>(detalhe SIG indispon\u00edvel neste fallback)</em></p>"
                "</article>"
            )
            continue

        evid_lis = "".join(
            f"<li><code>{_esc(ev)}</code></li>" for ev in prop.evidencias
        )
        if not evid_lis:
            evid_lis = (
                "<li><em>(sem evid\u00eancias listadas)</em></li>"
            )

        pol = pol_por_id.get(pid, "-")
        cards.append(
            "<article class='evid-card'>"
            f"<h3>{_esc(prop.proposicao_id)} — {_esc(prop.titulo)}</h3>"
            f"<p><strong>Tipo:</strong> {_esc(prop.tipo)} "
            f"| <strong>Polaridade:</strong> {_esc(pol)} "
            f"| <strong>SKUs:</strong> {_esc(', '.join(prop.skus))}</p>"
            f"<p class='desc'>{_esc(prop.descricao)}</p>"
            f"<p><strong>Impacto:</strong> {_esc(unidade)} "
            f"{_fmt_num(prop.impacto_financeiro)} "
            f"| <strong>Urg\u00eancia:</strong> {_esc(prop.urgencia_horas)}h</p>"
            "<p><strong>Evid\u00eancias (IDs de sinal):</strong></p>"
            f"<ul class='evid-list'>{evid_lis}</ul>"
            "</article>"
        )

    return "\n".join(cards)


def _leitura_bloco(
    titulo: str,
    chave: str,
    itens: List[Dict[str, Any]],
    *,
    fonte_dados: Optional[str] = None,
) -> str:
    """Texto deterministico de interpretacao do bloco (ja escapado)."""
    unidade = _rotulo_unidade_impacto(fonte_dados)
    modo_pbi = _eh_fonte_pbi(fonte_dados)
    if not itens:
        if modo_pbi and chave in ("top_forward", "top_oportunidades"):
            return _esc(
                f"{titulo}: nenhum item no top N. No PoC PBI o recorte "
                f"executivo prioriza DOI; desvio de sell-out por categoria "
                f"pode existir na fila HITL sem entrar neste bloco "
                f"estratificado."
            )
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
            "Prioridade operacional de estoque: ruptura pede "
            "reposi\u00e7\u00e3o/rebalanceamento; overstock pede conter "
            "sell-in."
        )
    elif chave == "top_forward":
        papel = (
            "Prioridade de plano: questionar premissas forward que "
            "desalinham demanda e estoque."
        )
    else:
        papel = (
            "Prioridade de captura: demanda acima do plano com espa\u00e7o "
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
        f"{topo_i:,.2f} {unidade}."
    )
    return _esc(" ".join(partes))


def _tabela_bloco(
    itens: List[Dict[str, Any]],
    *,
    fonte_dados: Optional[str] = None,
) -> str:
    """HTML table para um bloco top N."""
    if not itens:
        return "<p><em>(sem itens)</em></p>"
    unidade = _rotulo_unidade_impacto(fonte_dados)
    ordenados = sorted(itens, key=_impacto, reverse=True)
    linhas = [
        "<table>",
        "<thead><tr>"
        "<th>ID</th><th class='sku'>SKU</th><th>Tipo</th>"
        "<th>Polaridade</th>"
        f"<th>Impacto prio. ({_esc(unidade)})</th>"
        "<th>Urg\u00eancia (h)</th>"
        "<th>T\u00edtulo</th>"
        "</tr></thead><tbody>",
    ]
    for item in ordenados:
        linhas.append(
            "<tr>"
            f"<td>{_esc(item.get('proposicao_id'))}</td>"
            f"<td class='sku'>{_esc(_sku(item))}</td>"
            f"<td>{_esc(item.get('tipo'))}</td>"
            f"<td>{_esc(item.get('polaridade') or '-')}</td>"
            f"<td class='num'>{_fmt_num(_impacto(item))}</td>"
            f"<td class='num'>{_esc(item.get('urgencia_horas'))}</td>"
            f"<td>{_esc(item.get('titulo'))}</td>"
            "</tr>"
        )
    linhas.append("</tbody></table>")
    return "\n".join(linhas)


def _aviso_paineis_sem_grafico(resumo: Mapping[str, Any]) -> str:
    """
    HTML de aviso quando blocos do top N estao vazios (grafico nao gerado).

    Returns:
        Paragrafo HTML escapado, ou string vazia se todos os blocos tem itens.
    """
    vazios: List[str] = []
    for chave, titulo, _meta in CHAVES_BLOCOS:
        if not _as_items(resumo.get(chave)):
            vazios.append(titulo)
    if not vazios:
        return ""
    lista = ", ".join(vazios)
    return (
        "<p class='aviso'><strong>Graficos nao gerados:</strong> "
        f"paineis sem candidatos no top N — {_esc(lista)}. "
        "O PNG mostra o texto "
        "<em>(sem itens: grafico nao gerado)</em> nesses blocos; "
        "nao e falha de renderizacao do WeasyPrint.</p>"
    )


def _texto_fonte_entrada(
    *,
    arquivo_entrada: Optional[str],
    fonte_dados: Optional[str],
    pbi_catalog_id: Optional[str],
    pbi_artifact_id: Optional[str],
) -> Tuple[str, str]:
    """
    Rotulo e valor do campo de fonte no cabecalho.

    Returns:
        (rotulo_dt, valor_dd) em texto plano (sem escape HTML).
    """
    if _eh_fonte_pbi(fonte_dados):
        catalog = pbi_catalog_id or "n/d"
        artifact = pbi_artifact_id or "n/d"
        return (
            "Fonte de dados",
            f"pbi | catalog={catalog} | artifact={artifact}",
        )
    if arquivo_entrada:
        return ("Arquivo de entrada", str(arquivo_entrada))
    rotulo_sim = "(simula\u00e7\u00e3o / n/d)"
    return ("Arquivo de entrada", rotulo_sim)


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
    proposicoes: Optional[Sequence[Proposicao]] = None,
    fonte_dados: Optional[str] = None,
    pbi_catalog_id: Optional[str] = None,
    pbi_artifact_id: Optional[str] = None,
) -> str:
    """
    Monta HTML completo do relatorio analista (UTF-8).

    A narrativa remove o dump bruto de citacoes do guardrail.
    Evidencias estruturadas cobrem apenas o top N.
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
        aprov = (
            "aprovado" if critic_aprovado else "n\u00e3o aprovado"
        )
        if critic_aprovado is None:
            aprov = "n/d"
        critic_txt = f"{confianca_critic:.2f} ({aprov})"

    unidade = _rotulo_unidade_impacto(fonte_dados)
    modo_pbi = _eh_fonte_pbi(fonte_dados)

    secoes_blocos: List[str] = []
    for idx, (chave, titulo, _meta) in enumerate(CHAVES_BLOCOS, start=3):
        itens = _as_items(resumo.get(chave))
        secoes_blocos.append(
            f"<section class='bloco'>"
            f"<h2>{idx}. {_esc(titulo)}</h2>"
            f"{_tabela_bloco(itens, fonte_dados=fonte_dados)}"
            f"<h3>Leitura do bloco</h3>"
            f"<p>{_leitura_bloco(titulo, chave, itens, fonte_dados=fonte_dados)}</p>"
            f"</section>"
        )

    evid_html = _evidencias_top_n_html(
        resumo, proposicoes, fonte_dados=fonte_dados
    )
    narrativa = _narrativa_html(explicacao)
    rotulo_fonte, entrada_txt = _texto_fonte_entrada(
        arquivo_entrada=arquivo_entrada,
        fonte_dados=fonte_dados,
        pbi_catalog_id=pbi_catalog_id,
        pbi_artifact_id=pbi_artifact_id,
    )

    def _linha_diversidade(meta: Mapping[str, Any], vazio_ok: bool) -> str:
        n_r = meta.get("n_ruptura", "-")
        n_o = meta.get("n_overstock", "-")
        cota_r = meta.get("cota_ruptura")
        cota_o = meta.get("cota_overstock")
        if vazio_ok and n_r == 0 and n_o == 0:
            return "0 / 0 (sem candidatos no top)"
        if cota_r is not None and cota_o is not None:
            return f"{n_r} / {n_o} (cota {cota_r}/{cota_o})"
        return f"{n_r} / {n_o}"

    div_doi_txt = _linha_diversidade(div_d, vazio_ok=False)
    div_fwd_txt = _linha_diversidade(div_f, vazio_ok=True)

    aviso_narrativa = (
        "Texto gerado pelo LLM a partir de evid\u00eancias "
        "determin\u00edsticas. N\u00e3o recalcula impactos nem reordena "
        "o top N. O bloco bruto de cita\u00e7\u00f5es da fila inteira "
        "foi omitido desta se\u00e7\u00e3o (ver se\u00e7\u00e3o 7)."
    )
    if modo_pbi:
        aviso_narrativa = (
            aviso_narrativa
            + " Caminho PBI PoC: mencoes a sell-out por categoria na "
            "narrativa podem referir a fila HITL mesmo com Forward/"
            "Oportunidades vazios no top N."
        )

    lim_pbi_html = ""
    if modo_pbi:
        lim_pbi_html = (
            "<li>PBI: impacto preferencialmente em "
            f"<strong>{_esc(unidade)}</strong> a partir de measures do "
            "modelo (NR USD); STA por categoria pode usar ton.</li>"
            "<li>PBI 1.7a.3: DOI usa <code>Policy DOI Ideal</code> quando "
            "a query traz a coluna; senao fallback "
            "<code>limiar_doi_gap_media</code>.</li>"
            "<li>PBI 1.7a.3: Forward/Oportunidades vêm de Q4/Q5 "
            "(aproximacao vs serie temporal CSV "
            "<code>analisar_forward</code>).</li>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<title>Relat\u00f3rio S&amp;OE - {_esc(sessao_id)}</title>
<style>
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 11pt;
         color: #222; margin: 24px; line-height: 1.4; }}
  h1 {{ font-size: 18pt; margin-bottom: 4px; }}
  h2 {{ font-size: 13pt; margin-top: 22px; border-bottom: 1px solid #ccc;
        padding-bottom: 4px; page-break-after: avoid; }}
  h3 {{ font-size: 11pt; margin-top: 10px; margin-bottom: 4px; }}
  .meta {{ background: #f5f5f5; padding: 10px 12px; margin: 12px 0; }}
  .meta dt {{ font-weight: bold; }}
  .meta dd {{ margin: 0 0 6px 0; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 12px;
           font-size: 8.5pt; table-layout: fixed; }}
  th, td {{ border: 1px solid #ccc; padding: 3px 5px; text-align: left;
            vertical-align: top; overflow-wrap: anywhere;
            word-break: break-word; }}
  th {{ background: #eee; }}
  td.num {{ text-align: right; white-space: nowrap; }}
  td.sku, th.sku {{ width: 14%; }}
  tr {{ page-break-inside: avoid; break-inside: avoid; }}
  img.chart {{ max-width: 100%; height: auto; margin: 10px 0; }}
  .aviso {{ background: #fff8e6; border-left: 4px solid #c90;
            padding: 8px 10px; margin: 14px 0; }}
  .disclaimer {{ background: #f0f0f0; padding: 10px; margin-top: 18px;
                 font-size: 9pt; }}
  .evid-card {{ border: 1px solid #ddd; padding: 10px 12px; margin: 10px 0;
                page-break-inside: avoid; background: #fafafa; }}
  .evid-card h3 {{ margin-top: 0; color: #1a1a1a; }}
  .evid-card .desc {{ margin: 6px 0; }}
  .evid-list {{ margin: 4px 0 0 18px; padding: 0; }}
  .evid-list code {{ font-size: 9pt; }}
  .narrativa p {{ margin: 0 0 10px 0; text-align: justify; }}
</style>
</head>
<body>
<h1>Relat\u00f3rio anal\u00edtico Sense to Respond</h1>
<p>Sess\u00e3o <strong>{_esc(sessao_id)}</strong></p>

<section>
<h2>1. Cabe\u00e7alho da sess\u00e3o</h2>
<dl class="meta">
  <dt>{_esc(rotulo_fonte)}</dt>
  <dd>{_esc(entrada_txt)}</dd>
  <dt>Unidade de impacto</dt>
  <dd>{_esc(unidade)}</dd>
  <dt>Top N (DOI / Forward / Opps)</dt>
  <dd>{_esc(resumo.get("n_doi"))} / {_esc(resumo.get("n_forward"))} /
      {_esc(resumo.get("n_oportunidades"))}</dd>
  <dt>Candidatos (DOI / Forward / Opps)</dt>
  <dd>{_esc(resumo.get("total_candidatos_doi"))} /
      {_esc(resumo.get("total_candidatos_forward"))} /
      {_esc(resumo.get("total_candidatos_oportunidade"))}</dd>
  <dt>Polaridade no top DOI (ruptura/overstock)</dt>
  <dd>{_esc(div_doi_txt)}</dd>
  <dt>Polaridade no top Forward (ruptura/overstock)</dt>
  <dd>{_esc(div_fwd_txt)}</dd>
  <dt>Fila Nexus</dt>
  <dd>{_esc(total_fila)} proposi\u00e7\u00f5es
      ({_esc(revisao_obrigatoria)} com revis\u00e3o obrigat\u00f3ria)</dd>
  <dt>Critic</dt><dd>{_esc(critic_txt)}</dd>
</dl>
</section>

<section>
<h2>2. Gr\u00e1fico de prioriza\u00e7\u00e3o (top N)</h2>
{img_html}
<p>Barras por impacto priorizado ({_esc(unidade)}). Vermelho=ruptura,
azul=overstock, verde=oportunidade. Ordem visual por impacto dentro
de cada bloco; o ranking oficial permanece o de
<code>resumo_executivo</code>.</p>
{_aviso_paineis_sem_grafico(resumo)}
</section>

{"".join(secoes_blocos)}

<section class="narrativa">
<h2>6. An\u00e1lise narrativa</h2>
<p class="aviso">{_esc(aviso_narrativa)}</p>
{narrativa}
</section>

<section>
<h2>7. Evid\u00eancias do top N</h2>
{evid_html}
</section>

<section>
<h2>8. HITL e limita\u00e7\u00f5es</h2>
<ul>
  <li>Este relat\u00f3rio \u00e9 apoio \u00e0 decis\u00e3o; n\u00e3o
      executa a\u00e7\u00f5es em ERP/WMS.</li>
  <li>A fila completa ({_esc(total_fila)} itens) permanece dispon\u00edvel
      para revis\u00e3o humana; o top N \u00e9 um recorte executivo.</li>
  <li>Itens com revis\u00e3o obrigat\u00f3ria:
      {_esc(revisao_obrigatoria)}.</li>
  <li>Validar evid\u00eancias e contexto de neg\u00f3cio antes de aprovar
      proposi\u00e7\u00f5es.</li>
  {lim_pbi_html}
</ul>
<div class="disclaimer">
<strong>Disclaimer:</strong> recomenda\u00e7\u00f5es automatizadas com base
em dados do per\u00edodo carregado. Exige revis\u00e3o humana. N\u00fameros
de impacto e ranking s\u00e3o determin\u00edsticos (Optimus/resumo
executivo).
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
    proposicoes: Optional[Sequence[Proposicao]] = None,
    fonte_dados: Optional[str] = None,
    pbi_catalog_id: Optional[str] = None,
    pbi_artifact_id: Optional[str] = None,
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
        "n_evidencias_top": len(_ids_top_n(resumo)),
        "fonte_dados": fonte_dados,
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
            proposicoes=proposicoes,
            fonte_dados=fonte_dados,
            pbi_catalog_id=pbi_catalog_id,
            pbi_artifact_id=pbi_artifact_id,
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
