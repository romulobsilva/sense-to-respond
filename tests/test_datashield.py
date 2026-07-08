"""
Testes para datashield.py: leitura, perfil, mapeamento e normalizacao.
"""

from pathlib import Path
from typing import Dict, List

import pandas as pd
import pytest

from datashield import (
    EXTENSOES_SUPORTADAS,
    SCHEMA_CANONICO_MONDELEZ,
    MapaSemResult,
    PerfilColuna,
    PerfilDataset,
    amostrar,
    gerar_perfil,
    ler_arquivo,
    mapear_semantico_deterministico,
    normalizar_dataset,
    processar_arquivo,
)


FIXTURE_CSV = Path(__file__).parent / "fixtures" / "mondelez_ficticio.csv"


# ---------------------------------------------------------------------------
# ler_arquivo
# ---------------------------------------------------------------------------


class TestLerArquivo:
    """Testes para leitura de arquivos CSV/XLSX."""

    def test_ler_csv_valido(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 20
        assert "Country" in df.columns
        assert "SellOut_Actual_Ton" in df.columns

    def test_arquivo_inexistente(self) -> None:
        with pytest.raises(FileNotFoundError, match="nao encontrado"):
            ler_arquivo("/caminho/que/nao/existe.csv")

    def test_extensao_invalida(self, tmp_path: Path) -> None:
        arq = tmp_path / "dados.json"
        arq.write_text("{}")
        with pytest.raises(ValueError, match="nao suportada"):
            ler_arquivo(str(arq))

    def test_csv_vazio(self, tmp_path: Path) -> None:
        arq = tmp_path / "vazio.csv"
        arq.write_text("col_a,col_b\n")
        with pytest.raises(ValueError, match="vazio"):
            ler_arquivo(str(arq))

    def test_extensoes_suportadas(self) -> None:
        assert ".csv" in EXTENSOES_SUPORTADAS
        assert ".xlsx" in EXTENSOES_SUPORTADAS
        assert ".xls" in EXTENSOES_SUPORTADAS


# ---------------------------------------------------------------------------
# gerar_perfil
# ---------------------------------------------------------------------------


class TestGerarPerfil:
    """Testes para geracao de perfil estatistico."""

    def test_perfil_fixture(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        perfil = gerar_perfil(df)

        assert isinstance(perfil, PerfilDataset)
        assert perfil.linhas == 20
        assert perfil.colunas_total >= 20
        assert len(perfil.perfis) == perfil.colunas_total

    def test_perfil_colunas_conhecidas(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        perfil = gerar_perfil(df)

        nomes = [p.nome for p in perfil.perfis]
        assert "Country" in nomes
        assert "SellOut_Plan_Ton" in nomes
        assert "DOI_Actual_Days" in nomes

    def test_perfil_nulos_correto(self) -> None:
        df = pd.DataFrame({
            "a": [1, 2, None, 4],
            "b": ["x", None, None, "w"],
        })
        perfil = gerar_perfil(df)
        perfil_a = next(p for p in perfil.perfis if p.nome == "a")
        perfil_b = next(p for p in perfil.perfis if p.nome == "b")
        assert perfil_a.nulos == 1
        assert perfil_b.nulos == 2
        assert perfil_b.nulos_pct == 50.0

    def test_perfil_unicos(self) -> None:
        df = pd.DataFrame({"x": [1, 1, 2, 3]})
        perfil = gerar_perfil(df)
        assert perfil.perfis[0].unicos == 3

    def test_perfil_para_dict(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        perfil = gerar_perfil(df)
        d = perfil.para_dict()
        assert isinstance(d, dict)
        assert d["linhas"] == 20
        assert isinstance(d["perfis"], list)
        assert len(d["perfis"]) > 0
        assert "nome" in d["perfis"][0]

    def test_perfil_amostra_valores_sao_strings(self) -> None:
        df = pd.DataFrame({"nums": [1, 2, 3], "txts": ["a", "b", "c"]})
        perfil = gerar_perfil(df)
        for p in perfil.perfis:
            for v in p.amostra_valores:
                assert isinstance(v, str)


# ---------------------------------------------------------------------------
# amostrar
# ---------------------------------------------------------------------------


class TestAmostrar:
    """Testes para amostragem de linhas."""

    def test_amostra_padrao_5(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        amostra = amostrar(df)
        assert len(amostra) == 5
        assert isinstance(amostra[0], dict)

    def test_amostra_personalizada(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        amostra = amostrar(df, n=3)
        assert len(amostra) == 3

    def test_amostra_maior_que_df(self) -> None:
        df = pd.DataFrame({"a": [1, 2]})
        amostra = amostrar(df, n=10)
        assert len(amostra) == 2

    def test_amostra_n_zero_vira_um(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3]})
        amostra = amostrar(df, n=0)
        assert len(amostra) == 1

    def test_amostra_preserva_colunas(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        amostra = amostrar(df, n=1)
        assert "Country" in amostra[0]
        assert "SellOut_Actual_Ton" in amostra[0]


# ---------------------------------------------------------------------------
# mapear_semantico_deterministico
# ---------------------------------------------------------------------------


class TestMapeamentoDeterministico:
    """Testes para mapeamento semantico sem LLM."""

    def test_colunas_mondelez_match_completo(self) -> None:
        df = ler_arquivo(str(FIXTURE_CSV))
        resultado = mapear_semantico_deterministico(list(df.columns))

        assert isinstance(resultado, MapaSemResult)
        assert len(resultado.colunas_mapeadas) > 15
        assert resultado.confianca > 0.7

    def test_colunas_exatas_confianca_maxima(self) -> None:
        todas: List[str] = []
        for grupo in SCHEMA_CANONICO_MONDELEZ.values():
            todas.extend(grupo.keys())

        resultado = mapear_semantico_deterministico(todas)
        assert resultado.confianca == 1.0
        assert len(resultado.colunas_nao_mapeadas) == 0

    def test_colunas_desconhecidas(self) -> None:
        resultado = mapear_semantico_deterministico(
            ["col_x", "col_y", "col_z"]
        )
        assert len(resultado.colunas_mapeadas) == 0
        assert len(resultado.colunas_nao_mapeadas) == 3
        assert resultado.confianca == 0.0
        assert len(resultado.warnings) > 0

    def test_case_insensitive(self) -> None:
        resultado = mapear_semantico_deterministico(
            ["country", "CHANNEL", "Date"]
        )
        assert len(resultado.colunas_mapeadas) == 3

    def test_misto_mapeado_e_nao_mapeado(self) -> None:
        resultado = mapear_semantico_deterministico(
            ["Country", "Channel", "coluna_extra_qualquer"]
        )
        assert len(resultado.colunas_mapeadas) == 2
        assert len(resultado.colunas_nao_mapeadas) == 1
        assert resultado.confianca > 0.0

    def test_para_dict(self) -> None:
        resultado = mapear_semantico_deterministico(["Country", "Channel"])
        d = resultado.para_dict()
        assert isinstance(d, dict)
        assert "mapa" in d
        assert "confianca" in d
        assert isinstance(d["warnings"], list)

    def test_schema_customizado(self) -> None:
        schema_custom: Dict[str, Dict[str, str]] = {
            "dims": {"pais": "pais", "cidade": "cidade"},
        }
        resultado = mapear_semantico_deterministico(
            ["pais", "estado"],
            schema_canonico=schema_custom,
        )
        assert len(resultado.colunas_mapeadas) == 1
        assert "estado" in resultado.colunas_nao_mapeadas

    def test_lista_vazia(self) -> None:
        resultado = mapear_semantico_deterministico([])
        assert resultado.confianca == 0.0
        assert len(resultado.colunas_mapeadas) == 0


# ---------------------------------------------------------------------------
# normalizar_dataset
# ---------------------------------------------------------------------------


class TestNormalizarDataset:
    """Testes para normalizacao (renomear colunas)."""

    def test_renomear_colunas(self) -> None:
        df = pd.DataFrame({"col_orig": [1, 2], "outra": [3, 4]})
        mapa = {"col_orig": "col_canonica"}
        resultado = normalizar_dataset(df, mapa)
        assert "col_canonica" in resultado.columns
        assert "outra" in resultado.columns
        assert "col_orig" not in resultado.columns

    def test_mapa_vazio_retorna_copia(self) -> None:
        df = pd.DataFrame({"a": [1]})
        resultado = normalizar_dataset(df, {})
        assert list(resultado.columns) == ["a"]
        resultado.iloc[0, 0] = 999
        assert df.iloc[0, 0] == 1

    def test_coluna_inexistente_no_mapa_ignorada(self) -> None:
        df = pd.DataFrame({"a": [1], "b": [2]})
        mapa = {"a": "A", "col_fantasma": "X"}
        resultado = normalizar_dataset(df, mapa)
        assert "A" in resultado.columns
        assert "X" not in resultado.columns
        assert "b" in resultado.columns

    def test_coluna_ja_canonicada_nao_duplica(self) -> None:
        df = pd.DataFrame({"Country": [1]})
        mapa = {"Country": "Country"}
        resultado = normalizar_dataset(df, mapa)
        assert list(resultado.columns) == ["Country"]


# ---------------------------------------------------------------------------
# processar_arquivo (pipeline completo)
# ---------------------------------------------------------------------------


class TestProcessarArquivo:
    """Testes para o pipeline completo DataShield Lite."""

    def test_pipeline_com_fixture(self) -> None:
        resultado = processar_arquivo(str(FIXTURE_CSV))

        assert isinstance(resultado["df"], pd.DataFrame)
        assert isinstance(resultado["perfil"], PerfilDataset)
        assert isinstance(resultado["amostra"], list)
        assert isinstance(resultado["mapa"], MapaSemResult)
        assert resultado["nivel_adaptacao"] == 1
        assert resultado["schema_confirmado"] is False

    def test_confianca_alta_com_fixture_mondelez(self) -> None:
        resultado = processar_arquivo(str(FIXTURE_CSV))
        mapa: MapaSemResult = resultado["mapa"]
        assert mapa.confianca > 0.7

    def test_perfil_tem_20_linhas(self) -> None:
        resultado = processar_arquivo(str(FIXTURE_CSV))
        perfil: PerfilDataset = resultado["perfil"]
        assert perfil.linhas == 20

    def test_amostra_tem_5_linhas(self) -> None:
        resultado = processar_arquivo(str(FIXTURE_CSV))
        assert len(resultado["amostra"]) == 5

    def test_arquivo_inexistente(self) -> None:
        with pytest.raises(FileNotFoundError):
            processar_arquivo("/nao/existe.csv")

    def test_extensao_invalida(self, tmp_path: Path) -> None:
        arq = tmp_path / "dados.txt"
        arq.write_text("a,b\n1,2\n")
        with pytest.raises(ValueError, match="nao suportada"):
            processar_arquivo(str(arq))
