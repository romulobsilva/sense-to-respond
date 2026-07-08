"""
DataShield Lite: leitura, perfil e mapeamento semantico de datasets.

Responsabilidades:
  - Ler CSV/XLSX
  - Gerar perfil estatistico por coluna
  - Gerar amostra representativa para LLM
  - Inferir mapeamento semantico (Nivel 1, futuro)
  - Normalizar dataset conforme mapa confirmado

Contrato: datashield escreve no state os campos
  dataset_csv, perfil_dados, mapa_semantico, dataset_canonico, schema_confirmado

Refs: ADR-0019, ADR-0020
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd


EXTENSOES_SUPORTADAS = frozenset({".csv", ".xlsx", ".xls"})

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

    def para_dict(self) -> Dict[str, object]:
        """Serializa para JSON."""
        return {
            "mapa": self.mapa,
            "colunas_mapeadas": self.colunas_mapeadas,
            "colunas_nao_mapeadas": self.colunas_nao_mapeadas,
            "confianca": round(self.confianca, 4),
            "warnings": self.warnings,
        }


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
        amostra_raw = nao_nulos.head(5).tolist()
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
    Usado como fallback ou quando o match e direto (alta confianca).

    Para datasets com colunas nao reconhecidas, o LLM sera acionado
    na funcao inferir_mapa_semantico (Nivel 1, futuro).

    Args:
        nomes_colunas: nomes das colunas do dataset.
        schema_canonico: schema canonico (default: Mondelez).

    Returns:
        MapaSemResult com mapa, colunas mapeadas/nao mapeadas e confianca.
    """
    if schema_canonico is None:
        schema_canonico = SCHEMA_CANONICO_MONDELEZ

    lookup: Dict[str, str] = {}
    for grupo in schema_canonico.values():
        for col_can, descricao in grupo.items():
            lookup[col_can.lower()] = col_can

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
        cobertura_schema = len(mapeadas) / total_canonico if total_canonico > 0 else 0.0
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
) -> Dict[str, object]:
    """
    Pipeline completo DataShield Lite (Nivel 1 deterministico).

    1. Le o arquivo
    2. Gera perfil
    3. Gera amostra
    4. Faz mapeamento semantico deterministico
    5. Retorna tudo para o Nexus decidir HITL

    Args:
        caminho: caminho do arquivo CSV/XLSX.
        schema_canonico: schema canonico (default: Mondelez).

    Returns:
        Dict com df, perfil, amostra, mapa e status.
    """
    df = ler_arquivo(caminho)
    perfil = gerar_perfil(df)
    amostra = amostrar(df, n=5)
    mapa_result = mapear_semantico_deterministico(
        perfil.nomes_colunas,
        schema_canonico=schema_canonico,
    )

    return {
        "df": df,
        "perfil": perfil,
        "amostra": amostra,
        "mapa": mapa_result,
        "nivel_adaptacao": 1,
        "schema_confirmado": False,
    }
