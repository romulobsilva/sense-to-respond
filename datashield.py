"""
DataShield Lite: leitura, perfil e mapeamento semantico de datasets.

Responsabilidades:
  - Ler CSV/XLSX
  - Gerar perfil estatistico por coluna
  - Gerar amostra representativa para LLM
  - Inferir mapeamento semantico hibrido (deterministico + LLM Nivel 1)
  - Validar mapa e aplicar confidence gate
  - Normalizar dataset conforme mapa confirmado

Contrato: datashield escreve no state os campos
  dataset_csv, perfil_dados, mapa_semantico, dataset_canonico, schema_confirmado

Refs: ADR-0005, ADR-0009, ADR-0019, ADR-0020
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

EXTENSOES_SUPORTADAS = frozenset({".csv", ".xlsx", ".xls"})

# Confidence gate Nivel 1 (ADR-0005 / prompts.md secao 8).
LIMIAR_CONFIANCA_DATASHIELD_DEFAULT = 0.6
MAX_RETRIES_JSON_MAPA = 2
MAX_AMOSTRAS_POR_COLUNA = 5
ROLES_VALIDOS = frozenset({
    "temporal",
    "dimension",
    "product",
    "metric",
    "tag",
    "other",
})

SYSTEM_INFERIR_MAPA = """Voce mapeia colunas de um arquivo tabular para um schema canonico.

Regras:
1. Retorne APENAS JSON valido.
2. Use somente canonical_name da lista fornecida.
3. Use somente source_column presentes no perfil.
4. Nao invente colunas. Nao calcule metricas. Nao altere valores.
5. Prefira mapeamentos com alta confianca; se incerto, omita e avise em warnings.
6. role deve ser um de: temporal, dimension, product, metric, tag, other.

Formato:
{
  "mapeamentos": [
    {
      "canonical_name": "Date",
      "source_column": "semana",
      "confidence": 0.92,
      "role": "temporal"
    }
  ],
  "confidence": 0.87,
  "warnings": []
}
"""

SCHEMA_CANONICO_MONDELEZ: Dict[str, Dict[str, str]] = {
    "temporal": {
        "Date": "data do registro",
    },
    "dimensoes": {
        "Country": "pais",
        "Channel": "canal de venda",
        "Category": "categoria de produto",
        "Brand": "marca",
        "SKU_Code": "codigo do SKU",
        "SKU_Description": "descricao do SKU",
        "Cluster": "cluster/regiao",
        "CountryCode": "codigo ISO do pais",
    },
    "metricas_sellout": {
        "SellOut_Plan_Ton": "sell-out planejado (toneladas)",
        "SellOut_Actual_Ton": "sell-out realizado (toneladas)",
        "SellOut_Plan_NR_USD": "sell-out planejado (NR USD)",
        "SellOut_Actual_NR_USD": "sell-out realizado (NR USD)",
    },
    "metricas_sellin": {
        "SellIn_Plan_Ton": "sell-in planejado (toneladas)",
        "SellIn_Actual_Ton": "sell-in realizado (toneladas)",
        "SellIn_Plan_NR_USD": "sell-in planejado (NR USD)",
        "SellIn_Actual_NR_USD": "sell-in realizado (NR USD)",
    },
    "metricas_inventario": {
        "TradeInventory_Plan_Ton": "inventario trade planejado (ton)",
        "TradeInventory_Actual_Ton": "inventario trade realizado (ton)",
        "MDLZInventory_Plan_Ton": "inventario MDLZ planejado (ton)",
        "MDLZInventory_Actual_Ton": "inventario MDLZ realizado (ton)",
    },
    "metricas_doi": {
        "DOI_Plan_Days": "DOI planejado (dias)",
        "DOI_Actual_Days": "DOI realizado (dias)",
    },
    "tags": {
        "ScenarioTag": "tag de cenario (opcional)",
    },
}


def _todas_colunas_canonicas(
    schema: Optional[Dict[str, Dict[str, str]]] = None,
) -> List[str]:
    """Retorna lista flat de todas as colunas do schema canonico."""
    if schema is None:
        schema = SCHEMA_CANONICO_MONDELEZ
    colunas: List[str] = []
    for grupo in schema.values():
        colunas.extend(grupo.keys())
    return colunas


def _lookup_canonico(
    schema: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, str]:
    """Mapa lower(canonical) -> canonical preservando capitalizacao."""
    if schema is None:
        schema = SCHEMA_CANONICO_MONDELEZ
    lookup: Dict[str, str] = {}
    for grupo in schema.values():
        for col_can in grupo.keys():
            lookup[col_can.lower()] = col_can
    return lookup


def carregar_schema_de_json(caminho: str) -> Dict[str, Dict[str, str]]:
    """
    Carrega schema canonico de um arquivo JSON externo (ADR-0024).

    O JSON deve ter a mesma estrutura do SCHEMA_CANONICO_MONDELEZ:
    dicionario de grupos, cada grupo com {coluna: descricao}.

    Args:
        caminho: caminho do arquivo JSON.

    Returns:
        Schema canonico como Dict[str, Dict[str, str]].

    Raises:
        FileNotFoundError: se o arquivo nao existe.
        ValueError: se o formato e invalido.
    """
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Schema JSON nao encontrado: {caminho}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Schema JSON deve ser um dicionario de grupos, "
            f"recebido: {type(raw).__name__}"
        )

    for grupo_nome, grupo_val in raw.items():
        if not isinstance(grupo_val, dict):
            raise ValueError(
                f"Grupo '{grupo_nome}' deve ser dicionario "
                f"{{coluna: descricao}}, recebido: {type(grupo_val).__name__}"
            )

    return raw


@dataclass
class PerfilColuna:
    """Perfil estatistico de uma coluna do dataset."""

    nome: str
    dtype: str
    nulos: int
    nulos_pct: float
    unicos: int
    amostra_valores: List[str]

    def para_dict(self) -> Dict[str, object]:
        """Serializa para JSON."""
        return {
            "nome": self.nome,
            "dtype": self.dtype,
            "nulos": self.nulos,
            "nulos_pct": round(self.nulos_pct, 2),
            "unicos": self.unicos,
            "amostra_valores": self.amostra_valores,
        }


@dataclass
class PerfilDataset:
    """Perfil completo do dataset."""

    linhas: int
    colunas_total: int
    nomes_colunas: List[str]
    perfis: List[PerfilColuna]

    def para_dict(self) -> Dict[str, object]:
        """Serializa para JSON."""
        return {
            "linhas": self.linhas,
            "colunas_total": self.colunas_total,
            "nomes_colunas": self.nomes_colunas,
            "perfis": [p.para_dict() for p in self.perfis],
        }


@dataclass
class MapaSemResult:
    """Resultado do mapeamento semantico (Nivel 1)."""

    mapa: Dict[str, str]
    colunas_mapeadas: List[str]
    colunas_nao_mapeadas: List[str]
    confianca: float
    warnings: List[str] = field(default_factory=list)
    origem: str = "deterministico"
    gate_ok: bool = True
    json_bruto: str = ""

    def para_dict(self) -> Dict[str, object]:
        """Serializa para JSON."""
        return {
            "mapa": self.mapa,
            "colunas_mapeadas": self.colunas_mapeadas,
            "colunas_nao_mapeadas": self.colunas_nao_mapeadas,
            "confianca": round(self.confianca, 4),
            "warnings": self.warnings,
            "origem": self.origem,
            "gate_ok": self.gate_ok,
        }


@dataclass
class ResultadoValidacaoMapa:
    """Resultado da validacao deterministica do JSON do LLM."""

    ok: bool
    erros: List[str] = field(default_factory=list)
    mapa: Dict[str, str] = field(default_factory=dict)
    confianca: float = 0.0
    warnings: List[str] = field(default_factory=list)


def ler_arquivo(caminho: str) -> pd.DataFrame:
    """
    Le CSV ou XLSX e retorna DataFrame.

    Args:
        caminho: caminho do arquivo (csv ou xlsx).

    Returns:
        pd.DataFrame com conteudo do arquivo.

    Raises:
        FileNotFoundError: se o arquivo nao existe.
        ValueError: se a extensao nao e suportada ou arquivo esta vazio.
    """
    path = Path(caminho)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {caminho}")

    sufixo = path.suffix.lower()
    if sufixo not in EXTENSOES_SUPORTADAS:
        raise ValueError(
            f"Extensao '{sufixo}' nao suportada. "
            f"Validas: {', '.join(sorted(EXTENSOES_SUPORTADAS))}"
        )

    if sufixo == ".csv":
        df = pd.read_csv(caminho, encoding="utf-8")
    else:
        df = pd.read_excel(caminho)

    if df.empty:
        raise ValueError(f"Arquivo vazio: {caminho}")

    return df


def gerar_perfil(df: pd.DataFrame) -> PerfilDataset:
    """
    Gera perfil estatistico por coluna do DataFrame.

    Args:
        df: DataFrame de entrada.

    Returns:
        PerfilDataset com estatisticas por coluna.
    """
    perfis: List[PerfilColuna] = []

    for col in df.columns:
        serie = df[col]
        nulos = int(serie.isna().sum())
        total = len(serie)
        nulos_pct = (nulos / total * 100.0) if total > 0 else 0.0
        unicos = int(serie.nunique())

        nao_nulos = serie.dropna()
        amostra_raw = nao_nulos.head(MAX_AMOSTRAS_POR_COLUNA).tolist()
        amostra_valores = [str(v) for v in amostra_raw]

        perfis.append(PerfilColuna(
            nome=str(col),
            dtype=str(serie.dtype),
            nulos=nulos,
            nulos_pct=nulos_pct,
            unicos=unicos,
            amostra_valores=amostra_valores,
        ))

    return PerfilDataset(
        linhas=len(df),
        colunas_total=len(df.columns),
        nomes_colunas=[str(c) for c in df.columns],
        perfis=perfis,
    )


def amostrar(df: pd.DataFrame, n: int = 5) -> List[Dict[str, object]]:
    """
    Retorna n primeiras linhas como lista de dicts.

    Args:
        df: DataFrame de entrada.
        n: numero de linhas (default 5).

    Returns:
        Lista de dicionarios, um por linha.
    """
    if n < 1:
        n = 1
    amostra_df = df.head(n)
    registros: List[Dict[str, object]] = []
    for _, row in amostra_df.iterrows():
        registro: Dict[str, object] = {}
        for col in amostra_df.columns:
            val = row[col]
            if pd.isna(val):
                registro[str(col)] = None
            else:
                registro[str(col)] = val
        registros.append(registro)
    return registros


def mapear_semantico_deterministico(
    nomes_colunas: Sequence[str],
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
) -> MapaSemResult:
    """
    Mapeamento semantico deterministico (case-insensitive, exact match).

    Faz match exato das colunas do dataset contra o schema canonico.
    Usado como primeira etapa do fluxo hibrido Nivel 1.

    Args:
        nomes_colunas: nomes das colunas do dataset.
        schema_canonico: schema canonico (default: Mondelez).

    Returns:
        MapaSemResult com mapa, colunas mapeadas/nao mapeadas e confianca.
    """
    if schema_canonico is None:
        schema_canonico = SCHEMA_CANONICO_MONDELEZ

    lookup = _lookup_canonico(schema_canonico)

    mapa: Dict[str, str] = {}
    mapeadas: List[str] = []
    nao_mapeadas: List[str] = []
    warnings: List[str] = []

    for col in nomes_colunas:
        col_str = str(col)
        chave = col_str.lower()
        if chave in lookup:
            col_canonica = lookup[chave]
            mapa[col_str] = col_canonica
            mapeadas.append(col_str)
        else:
            nao_mapeadas.append(col_str)

    total = len(nomes_colunas)
    total_canonico = len(lookup)

    if total == 0:
        confianca = 0.0
    else:
        cobertura_dataset = len(mapeadas) / total
        cobertura_schema = (
            len(mapeadas) / total_canonico if total_canonico > 0 else 0.0
        )
        confianca = (cobertura_dataset + cobertura_schema) / 2.0

    if nao_mapeadas:
        warnings.append(
            f"{len(nao_mapeadas)} coluna(s) nao mapeada(s): "
            f"{', '.join(nao_mapeadas[:10])}"
        )

    colunas_canonicas_ausentes = [
        col_can for col_can in lookup.values()
        if col_can not in mapa.values()
    ]
    if colunas_canonicas_ausentes:
        warnings.append(
            f"{len(colunas_canonicas_ausentes)} coluna(s) do schema ausente(s): "
            f"{', '.join(colunas_canonicas_ausentes[:10])}"
        )

    return MapaSemResult(
        mapa=mapa,
        colunas_mapeadas=mapeadas,
        colunas_nao_mapeadas=nao_mapeadas,
        confianca=round(confianca, 4),
        warnings=warnings,
        origem="deterministico",
        gate_ok=True,
    )


def montar_payload_llm(
    perfil: PerfilDataset,
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
    colunas_ja_mapeadas: Optional[Dict[str, str]] = None,
    colunas_pendentes: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """
    Monta payload compacto para o LLM (ADR-0009).

    Nunca inclui o DataFrame completo -- apenas perfil e amostra limitada.

    Args:
        perfil: perfil estatistico do dataset.
        schema_canonico: schema alvo.
        colunas_ja_mapeadas: mapa flat ja resolvido deterministicamente.
        colunas_pendentes: colunas ainda sem mapeamento.

    Returns:
        Dict serializavel seguro para prompt.
    """
    if schema_canonico is None:
        schema_canonico = SCHEMA_CANONICO_MONDELEZ

    schema_flat: Dict[str, str] = {}
    for grupo, cols in schema_canonico.items():
        for nome, desc in cols.items():
            schema_flat[nome] = f"[{grupo}] {desc}"

    perfis_payload: List[Dict[str, object]] = []
    pendentes_set = (
        set(colunas_pendentes)
        if colunas_pendentes is not None
        else set(perfil.nomes_colunas)
    )
    for p in perfil.perfis:
        if p.nome not in pendentes_set and colunas_pendentes is not None:
            continue
        perfis_payload.append({
            "nome": p.nome,
            "dtype": p.dtype,
            "nulos_pct": round(p.nulos_pct, 2),
            "unicos": p.unicos,
            "amostra_valores": p.amostra_valores[:MAX_AMOSTRAS_POR_COLUNA],
        })

    return {
        "linhas": perfil.linhas,
        "colunas_total": perfil.colunas_total,
        "perfis": perfis_payload,
        "schema_canonico": schema_flat,
        "ja_mapeadas": dict(colunas_ja_mapeadas or {}),
        "pendentes": list(colunas_pendentes or []),
    }


def validar_mapa_semantico(
    dados: Dict[str, Any],
    nomes_colunas: Sequence[str],
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
) -> ResultadoValidacaoMapa:
    """
    Valida JSON do LLM contra schema e colunas do dataset.

    Args:
        dados: objeto JSON parseado do LLM.
        nomes_colunas: colunas reais do DataFrame.
        schema_canonico: schema permitido.

    Returns:
        ResultadoValidacaoMapa com mapa flat se ok.
    """
    erros: List[str] = []
    if schema_canonico is None:
        schema_canonico = SCHEMA_CANONICO_MONDELEZ

    lookup = _lookup_canonico(schema_canonico)
    colunas_set = {str(c) for c in nomes_colunas}

    for chave in ("mapeamentos", "confidence", "warnings"):
        if chave not in dados:
            erros.append(f"Chave obrigatoria ausente: {chave}")

    if erros:
        return ResultadoValidacaoMapa(ok=False, erros=erros)

    mapeamentos_raw = dados.get("mapeamentos")
    if not isinstance(mapeamentos_raw, list):
        return ResultadoValidacaoMapa(
            ok=False,
            erros=["mapeamentos deve ser uma lista."],
        )

    warnings_raw = dados.get("warnings", [])
    warnings: List[str] = []
    if isinstance(warnings_raw, list):
        for item in warnings_raw:
            if isinstance(item, str):
                warnings.append(item)
            else:
                erros.append("warnings deve conter apenas strings.")
    else:
        erros.append("warnings deve ser list[str].")

    try:
        confianca = float(dados.get("confidence", 0.0))
    except (TypeError, ValueError):
        confianca = 0.0
        erros.append("confidence deve ser numerico.")

    if confianca < 0.0 or confianca > 1.0:
        erros.append(f"confidence fora de [0,1]: {confianca}")

    mapa: Dict[str, str] = {}
    canonicos_usados: Dict[str, str] = {}

    for idx, item in enumerate(mapeamentos_raw):
        if not isinstance(item, dict):
            erros.append(f"mapeamentos[{idx}] nao e objeto.")
            continue

        source = item.get("source_column")
        canonical = item.get("canonical_name")
        conf_item = item.get("confidence", 0.0)
        role = item.get("role", "other")

        if not isinstance(source, str) or not source:
            erros.append(f"mapeamentos[{idx}].source_column invalido.")
            continue
        if source not in colunas_set:
            erros.append(
                f"source_column inexistente no dataset: {source}"
            )
            continue

        if not isinstance(canonical, str) or not canonical:
            erros.append(f"mapeamentos[{idx}].canonical_name invalido.")
            continue

        can_norm = lookup.get(canonical.lower())
        if can_norm is None:
            erros.append(
                f"canonical_name fora do schema: {canonical}"
            )
            continue

        try:
            conf_f = float(conf_item)
        except (TypeError, ValueError):
            erros.append(
                f"mapeamentos[{idx}].confidence invalido."
            )
            continue
        if conf_f < 0.0 or conf_f > 1.0:
            erros.append(
                f"mapeamentos[{idx}].confidence fora de [0,1]."
            )
            continue

        if not isinstance(role, str) or role not in ROLES_VALIDOS:
            erros.append(
                f"mapeamentos[{idx}].role invalido: {role}"
            )
            continue

        if can_norm in canonicos_usados and canonicos_usados[can_norm] != source:
            erros.append(
                f"canonical_name duplicado: {can_norm} "
                f"({canonicos_usados[can_norm]} e {source})"
            )
            continue

        if source in mapa and mapa[source] != can_norm:
            erros.append(
                f"source_column mapeada duas vezes: {source}"
            )
            continue

        mapa[source] = can_norm
        canonicos_usados[can_norm] = source

    if not mapa:
        erros.append("mapeamentos vazio ou nenhum item valido.")

    return ResultadoValidacaoMapa(
        ok=len(erros) == 0,
        erros=erros,
        mapa=mapa if len(erros) == 0 else {},
        confianca=confianca if len(erros) == 0 else 0.0,
        warnings=warnings,
    )


def aplicar_confidence_gate(
    confianca: float,
    limiar: float = LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
) -> bool:
    """
    Confidence gate do DataShield Nivel 1.

    Args:
        confianca: score em [0, 1].
        limiar: limiar minimo (default 0.6).

    Returns:
        True se confianca >= limiar.
    """
    return confianca >= limiar


def _mesclar_mapas(
    base: Dict[str, str],
    extra: Dict[str, str],
) -> Dict[str, str]:
    """Mescla mapas; extra nao sobrescreve chaves ja presentes em base."""
    mesclado = dict(base)
    for src, can in extra.items():
        if src not in mesclado:
            if can in mesclado.values():
                continue
            mesclado[src] = can
    return mesclado


def _mapa_para_result(
    mapa: Dict[str, str],
    nomes_colunas: Sequence[str],
    confianca: float,
    warnings: List[str],
    origem: str,
    limiar_gate: float,
    json_bruto: str = "",
) -> MapaSemResult:
    """Monta MapaSemResult a partir de mapa flat."""
    mapeadas = [c for c in nomes_colunas if str(c) in mapa]
    nao_mapeadas = [str(c) for c in nomes_colunas if str(c) not in mapa]
    gate_ok = aplicar_confidence_gate(confianca, limiar_gate)
    warns = list(warnings)
    if not gate_ok:
        warns.append(
            f"confidence gate falhou: {confianca:.2f} < limiar {limiar_gate:.2f}"
        )
    return MapaSemResult(
        mapa=mapa,
        colunas_mapeadas=mapeadas,
        colunas_nao_mapeadas=nao_mapeadas,
        confianca=round(confianca, 4),
        warnings=warns,
        origem=origem,
        gate_ok=gate_ok,
        json_bruto=json_bruto,
    )


def inferir_mapa_semantico(
    perfil: PerfilDataset,
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    colunas_ja_mapeadas: Optional[Dict[str, str]] = None,
    colunas_pendentes: Optional[Sequence[str]] = None,
    registrar_log: Optional[Callable[[str], None]] = None,
    client: Optional[Any] = None,
) -> Tuple[MapaSemResult, str]:
    """
    Infere mapa semantico via LLM (Nivel 1).

    Args:
        perfil: perfil do dataset.
        schema_canonico: schema alvo.
        api_key: chave OpenAI (ignorada se client for injetado).
        model: modelo OpenAI.
        colunas_ja_mapeadas: mapa deterministico previo.
        colunas_pendentes: colunas a inferir.
        registrar_log: callback de log.
        client: cliente OpenAI injetavel (testes).

    Returns:
        Tupla (MapaSemResult parcial so do LLM, json_bruto).
        Em falha apos retries, retorna mapa vazio com warnings.
    """
    def log(msg: str) -> None:
        if registrar_log is not None:
            registrar_log(msg)

    if schema_canonico is None:
        schema_canonico = SCHEMA_CANONICO_MONDELEZ

    payload = montar_payload_llm(
        perfil,
        schema_canonico=schema_canonico,
        colunas_ja_mapeadas=colunas_ja_mapeadas,
        colunas_pendentes=colunas_pendentes,
    )
    if "dataset" in payload or "dataframe" in payload:
        raise ValueError("Payload LLM nao pode conter dataset completo.")

    user_content = (
        "Mapeie as colunas pendentes para o schema canonico.\n\n"
        f"{json.dumps(payload, ensure_ascii=True, indent=2)}"
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_INFERIR_MAPA},
        {"role": "user", "content": user_content},
    ]

    if client is None:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

    json_bruto = ""
    log(f"DataShield LLM: inferir_mapa_semantico modelo={model}")

    for tentativa in range(MAX_RETRIES_JSON_MAPA + 1):
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=messages,
        )
        content = response.choices[0].message.content
        if content is None:
            if tentativa < MAX_RETRIES_JSON_MAPA:
                messages.append({
                    "role": "user",
                    "content": "Retorne APENAS um objeto JSON completo.",
                })
                continue
            break

        json_bruto = content
        log(f"DataShield LLM JSON tentativa {tentativa + 1}")

        try:
            dados = json.loads(content)
        except json.JSONDecodeError:
            if tentativa < MAX_RETRIES_JSON_MAPA:
                messages.append({
                    "role": "user",
                    "content": "JSON invalido. Retorne APENAS JSON valido.",
                })
                continue
            break

        if not isinstance(dados, dict):
            if tentativa < MAX_RETRIES_JSON_MAPA:
                messages.append({
                    "role": "user",
                    "content": "Retorne um objeto JSON (nao lista).",
                })
                continue
            break

        validacao = validar_mapa_semantico(
            dados,
            perfil.nomes_colunas,
            schema_canonico=schema_canonico,
        )
        if not validacao.ok:
            if tentativa < MAX_RETRIES_JSON_MAPA:
                messages.append({
                    "role": "user",
                    "content": (
                        "Validacao falhou: "
                        + "; ".join(validacao.erros)
                        + ". Corrija e retorne JSON completo."
                    ),
                })
                continue
            vazio = _mapa_para_result(
                {},
                perfil.nomes_colunas,
                0.0,
                validacao.erros,
                "llm_falha",
                LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
                json_bruto=json_bruto,
            )
            return vazio, json_bruto

        resultado = _mapa_para_result(
            validacao.mapa,
            perfil.nomes_colunas,
            validacao.confianca,
            validacao.warnings,
            "llm",
            LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
            json_bruto=json_bruto,
        )
        return resultado, json_bruto

    falha = _mapa_para_result(
        {},
        perfil.nomes_colunas,
        0.0,
        ["LLM esgotou retries de JSON/validacao."],
        "llm_falha",
        LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
        json_bruto=json_bruto,
    )
    return falha, json_bruto


def mapear_semantico_hibrido(
    perfil: PerfilDataset,
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    limiar_gate: float = LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
    forcar_llm: bool = False,
    registrar_log: Optional[Callable[[str], None]] = None,
    client: Optional[Any] = None,
) -> MapaSemResult:
    """
    Fluxo hibrido Nivel 1: deterministico primeiro, LLM residual.

    Chama LLM se:
      - houver colunas nao mapeadas, ou
      - confianca deterministica < limiar, ou
      - forcar_llm=True.

    Se nao houver api_key/client e LLM for necessario, mantem
    resultado deterministico com warning.

    Args:
        perfil: perfil do dataset.
        schema_canonico: schema alvo.
        api_key: chave OpenAI.
        model: modelo.
        limiar_gate: limiar do confidence gate.
        forcar_llm: forca chamada LLM mesmo com match completo.
        registrar_log: callback de log.
        client: cliente OpenAI injetavel.

    Returns:
        MapaSemResult consolidado.
    """
    def log(msg: str) -> None:
        if registrar_log is not None:
            registrar_log(msg)

    det = mapear_semantico_deterministico(
        perfil.nomes_colunas,
        schema_canonico=schema_canonico,
    )

    precisa_llm = (
        forcar_llm
        or len(det.colunas_nao_mapeadas) > 0
        or det.confianca < limiar_gate
    )

    if not precisa_llm:
        log("DataShield: mapeamento deterministico suficiente.")
        return _mapa_para_result(
            det.mapa,
            perfil.nomes_colunas,
            det.confianca,
            det.warnings,
            "deterministico",
            limiar_gate,
        )

    if client is None and not api_key:
        log(
            "DataShield: LLM necessario mas sem api_key/client; "
            "mantendo mapa deterministico."
        )
        warns = list(det.warnings)
        warns.append(
            "LLM nao acionado (sem credencial); mapa apenas deterministico."
        )
        return _mapa_para_result(
            det.mapa,
            perfil.nomes_colunas,
            det.confianca,
            warns,
            "deterministico_sem_llm",
            limiar_gate,
        )

    log(
        f"DataShield: acionando LLM para "
        f"{len(det.colunas_nao_mapeadas)} coluna(s) pendente(s)."
    )
    llm_result, json_bruto = inferir_mapa_semantico(
        perfil,
        schema_canonico=schema_canonico,
        api_key=api_key,
        model=model,
        colunas_ja_mapeadas=det.mapa,
        colunas_pendentes=det.colunas_nao_mapeadas,
        registrar_log=registrar_log,
        client=client,
    )

    if llm_result.origem == "llm_falha" or not llm_result.mapa:
        warns = list(det.warnings) + list(llm_result.warnings)
        warns.append("Fallback: mantido mapa deterministico apos falha LLM.")
        return _mapa_para_result(
            det.mapa,
            perfil.nomes_colunas,
            det.confianca,
            warns,
            "hibrido_fallback_det",
            limiar_gate,
            json_bruto=json_bruto,
        )

    mesclado = _mesclar_mapas(det.mapa, llm_result.mapa)
    # Recomputa confianca pela cobertura do mapa mesclado.
    total = len(perfil.nomes_colunas)
    total_canonico = len(_lookup_canonico(schema_canonico))
    n_map = len(mesclado)
    if total == 0:
        conf_final = 0.0
    else:
        cobertura_dataset = n_map / total
        cobertura_schema = (
            n_map / total_canonico if total_canonico > 0 else 0.0
        )
        conf_cobertura = (cobertura_dataset + cobertura_schema) / 2.0
        # Usa o max entre cobertura e confianca do LLM quando o merge
        # resolveu pendencias com sucesso.
        conf_final = max(conf_cobertura, llm_result.confianca)
    warns = list(det.warnings) + list(llm_result.warnings)
    warns.append(
        f"Mapa hibrido: {len(det.mapa)} det + "
        f"{len(llm_result.mapa)} llm -> {len(mesclado)} total."
    )
    return _mapa_para_result(
        mesclado,
        perfil.nomes_colunas,
        conf_final,
        warns,
        "hibrido",
        limiar_gate,
        json_bruto=json_bruto,
    )


def normalizar_dataset(
    df: pd.DataFrame,
    mapa: Dict[str, str],
) -> pd.DataFrame:
    """
    Renomeia colunas do DataFrame conforme mapa confirmado.

    Colunas nao presentes no mapa sao mantidas sem alteracao.

    Args:
        df: DataFrame original.
        mapa: dicionario {coluna_original: coluna_canonica}.

    Returns:
        DataFrame com colunas renomeadas.
    """
    renomear: Dict[str, str] = {}
    for col_orig, col_canon in mapa.items():
        if col_orig in df.columns and col_orig != col_canon:
            renomear[col_orig] = col_canon

    if renomear:
        return df.rename(columns=renomear)
    return df.copy()


def processar_arquivo(
    caminho: str,
    schema_canonico: Optional[Dict[str, Dict[str, str]]] = None,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    limiar_gate: float = LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
    usar_llm: bool = True,
    registrar_log: Optional[Callable[[str], None]] = None,
    client: Optional[Any] = None,
) -> Dict[str, object]:
    """
    Pipeline completo DataShield Lite (Nivel 1 hibrido).

    1. Le o arquivo
    2. Gera perfil
    3. Gera amostra
    4. Mapeamento hibrido (deterministico + LLM residual)
    5. Retorna tudo para o Nexus decidir HITL / gate

    Args:
        caminho: caminho do arquivo CSV/XLSX.
        schema_canonico: schema canonico (default: Mondelez).
        api_key: chave OpenAI para inferencia residual.
        model: modelo OpenAI.
        limiar_gate: limiar do confidence gate.
        usar_llm: se False, forca apenas deterministico.
        registrar_log: callback de log.
        client: cliente OpenAI injetavel (testes).

    Returns:
        Dict com df, perfil, amostra, mapa e status.
    """
    df = ler_arquivo(caminho)
    perfil = gerar_perfil(df)
    amostra = amostrar(df, n=5)

    if usar_llm:
        mapa_result = mapear_semantico_hibrido(
            perfil,
            schema_canonico=schema_canonico,
            api_key=api_key,
            model=model,
            limiar_gate=limiar_gate,
            registrar_log=registrar_log,
            client=client,
        )
    else:
        det = mapear_semantico_deterministico(
            perfil.nomes_colunas,
            schema_canonico=schema_canonico,
        )
        mapa_result = _mapa_para_result(
            det.mapa,
            perfil.nomes_colunas,
            det.confianca,
            det.warnings,
            "deterministico",
            limiar_gate,
        )

    return {
        "df": df,
        "perfil": perfil,
        "amostra": amostra,
        "mapa": mapa_result,
        "nivel_adaptacao": 1,
        "schema_confirmado": False,
        "gate_ok": mapa_result.gate_ok,
    }
