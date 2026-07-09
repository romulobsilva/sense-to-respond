"""
Testes do DataShield Nivel 1 hibrido: payload, validacao, gate e LLM mock.
"""

from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pandas as pd
import pytest

from datashield import (
    LIMIAR_CONFIANCA_DATASHIELD_DEFAULT,
    MapaSemResult,
    PerfilDataset,
    aplicar_confidence_gate,
    gerar_perfil,
    inferir_mapa_semantico,
    mapear_semantico_deterministico,
    mapear_semantico_hibrido,
    montar_payload_llm,
    processar_arquivo,
    validar_mapa_semantico,
)


FIXTURE_CSV = Path(__file__).parent / "fixtures" / "mondelez_ficticio.csv"


def _perfil_simples() -> PerfilDataset:
    """Perfil com colunas nao canonicas para forcar LLM."""
    df = pd.DataFrame({
        "semana": ["2024-01-01", "2024-01-08"],
        "canal_venda": ["Retail", "Retail"],
        "cod_produto": ["SKU1", "SKU2"],
        "vol_cx": [10.0, 12.0],
        "Country": ["AR", "AR"],
    })
    return gerar_perfil(df)


def _mock_openai_json(payload: Dict[str, Any]) -> MagicMock:
    """Cliente OpenAI fake que devolve JSON fixo."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = __import__("json").dumps(payload)
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


class TestMontarPayloadLlm:
    """Payload compacto sem dataset completo (ADR-0009)."""

    def test_payload_sem_dataset_completo(self) -> None:
        perfil = gerar_perfil(pd.read_csv(FIXTURE_CSV))
        payload = montar_payload_llm(perfil)
        assert "dataset" not in payload
        assert "dataframe" not in payload
        assert "perfis" in payload
        assert "schema_canonico" in payload
        assert "SellOut_Actual_Ton" in payload["schema_canonico"]

    def test_payload_filtra_pendentes(self) -> None:
        perfil = _perfil_simples()
        payload = montar_payload_llm(
            perfil,
            colunas_ja_mapeadas={"Country": "Country"},
            colunas_pendentes=["semana", "vol_cx"],
        )
        nomes = [p["nome"] for p in payload["perfis"]]
        assert "semana" in nomes
        assert "vol_cx" in nomes
        assert "Country" not in nomes
        assert payload["pendentes"] == ["semana", "vol_cx"]


class TestValidarMapaSemantico:
    """Validacao deterministica do JSON do LLM."""

    def test_mapa_valido(self) -> None:
        dados = {
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "semana",
                    "confidence": 0.9,
                    "role": "temporal",
                },
                {
                    "canonical_name": "SellOut_Actual_Ton",
                    "source_column": "vol_cx",
                    "confidence": 0.85,
                    "role": "metric",
                },
            ],
            "confidence": 0.88,
            "warnings": [],
        }
        result = validar_mapa_semantico(
            dados,
            ["semana", "vol_cx", "Country"],
        )
        assert result.ok is True
        assert result.mapa["semana"] == "Date"
        assert result.mapa["vol_cx"] == "SellOut_Actual_Ton"

    def test_source_column_inexistente(self) -> None:
        dados = {
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "fantasma",
                    "confidence": 0.9,
                    "role": "temporal",
                },
            ],
            "confidence": 0.9,
            "warnings": [],
        }
        result = validar_mapa_semantico(dados, ["semana"])
        assert result.ok is False
        assert any("inexistente" in e for e in result.erros)

    def test_canonical_fora_do_schema(self) -> None:
        dados = {
            "mapeamentos": [
                {
                    "canonical_name": "periodo",
                    "source_column": "semana",
                    "confidence": 0.9,
                    "role": "temporal",
                },
            ],
            "confidence": 0.9,
            "warnings": [],
        }
        result = validar_mapa_semantico(dados, ["semana"])
        assert result.ok is False
        assert any("fora do schema" in e for e in result.erros)

    def test_confidence_fora_de_faixa(self) -> None:
        dados = {
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "semana",
                    "confidence": 0.9,
                    "role": "temporal",
                },
            ],
            "confidence": 1.5,
            "warnings": [],
        }
        result = validar_mapa_semantico(dados, ["semana"])
        assert result.ok is False

    def test_mapeamentos_vazios(self) -> None:
        dados = {"mapeamentos": [], "confidence": 0.7, "warnings": []}
        result = validar_mapa_semantico(dados, ["semana"])
        assert result.ok is False

    def test_warnings_nao_lista(self) -> None:
        dados = {
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "semana",
                    "confidence": 0.9,
                    "role": "temporal",
                },
            ],
            "confidence": 0.9,
            "warnings": "ok",
        }
        result = validar_mapa_semantico(dados, ["semana"])
        assert result.ok is False


class TestConfidenceGate:
    """Gate de confianca."""

    def test_acima_do_limiar(self) -> None:
        assert aplicar_confidence_gate(0.7) is True

    def test_abaixo_do_limiar(self) -> None:
        assert aplicar_confidence_gate(0.5) is False

    def test_igual_ao_limiar(self) -> None:
        assert aplicar_confidence_gate(
            LIMIAR_CONFIANCA_DATASHIELD_DEFAULT
        ) is True


class TestInferirMapaSemanticoMock:
    """Inferencia LLM com cliente mockado."""

    def test_inferencia_sucesso(self) -> None:
        perfil = _perfil_simples()
        client = _mock_openai_json({
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "semana",
                    "confidence": 0.91,
                    "role": "temporal",
                },
                {
                    "canonical_name": "Channel",
                    "source_column": "canal_venda",
                    "confidence": 0.88,
                    "role": "dimension",
                },
                {
                    "canonical_name": "SKU_Code",
                    "source_column": "cod_produto",
                    "confidence": 0.9,
                    "role": "product",
                },
                {
                    "canonical_name": "SellOut_Actual_Ton",
                    "source_column": "vol_cx",
                    "confidence": 0.86,
                    "role": "metric",
                },
            ],
            "confidence": 0.89,
            "warnings": [],
        })
        result, bruto = inferir_mapa_semantico(
            perfil,
            client=client,
            colunas_pendentes=[
                "semana",
                "canal_venda",
                "cod_produto",
                "vol_cx",
            ],
        )
        assert result.origem == "llm"
        assert result.mapa["semana"] == "Date"
        assert result.mapa["vol_cx"] == "SellOut_Actual_Ton"
        assert bruto != ""
        assert client.chat.completions.create.called

    def test_json_invalido_esgota_retries(self) -> None:
        perfil = _perfil_simples()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "nao-e-json"
        client = MagicMock()
        client.chat.completions.create.return_value = response

        result, _ = inferir_mapa_semantico(perfil, client=client)
        assert result.origem == "llm_falha"
        assert result.mapa == {}
        assert client.chat.completions.create.call_count == 3


class TestMapearHibrido:
    """Fluxo hibrido deterministico + LLM."""

    def test_deterministico_suficiente_sem_llm(self) -> None:
        perfil = gerar_perfil(pd.read_csv(FIXTURE_CSV))
        result = mapear_semantico_hibrido(perfil, api_key="", client=None)
        assert result.origem == "deterministico"
        assert result.confianca > 0.7
        assert result.gate_ok is True

    def test_hibrido_com_mock_llm(self) -> None:
        perfil = _perfil_simples()
        client = _mock_openai_json({
            "mapeamentos": [
                {
                    "canonical_name": "Date",
                    "source_column": "semana",
                    "confidence": 0.9,
                    "role": "temporal",
                },
                {
                    "canonical_name": "Channel",
                    "source_column": "canal_venda",
                    "confidence": 0.9,
                    "role": "dimension",
                },
                {
                    "canonical_name": "SKU_Code",
                    "source_column": "cod_produto",
                    "confidence": 0.9,
                    "role": "product",
                },
                {
                    "canonical_name": "SellOut_Actual_Ton",
                    "source_column": "vol_cx",
                    "confidence": 0.9,
                    "role": "metric",
                },
            ],
            "confidence": 0.9,
            "warnings": [],
        })
        result = mapear_semantico_hibrido(perfil, client=client)
        assert result.origem == "hibrido"
        assert "Country" in result.mapa
        assert result.mapa["semana"] == "Date"
        assert result.gate_ok is True

    def test_sem_credencial_mantem_deterministico(self) -> None:
        perfil = _perfil_simples()
        result = mapear_semantico_hibrido(perfil, api_key="", client=None)
        assert result.origem == "deterministico_sem_llm"
        assert "Country" in result.mapa
        assert any("LLM nao acionado" in w for w in result.warnings)


class TestProcessarArquivoHibrido:
    """Pipeline processar_arquivo com e sem LLM."""

    def test_fixture_sem_llm(self) -> None:
        resultado = processar_arquivo(str(FIXTURE_CSV), usar_llm=False)
        mapa: MapaSemResult = resultado["mapa"]
        assert mapa.origem == "deterministico"
        assert resultado["gate_ok"] is True
        assert resultado["nivel_adaptacao"] == 1

    def test_fixture_com_llm_nao_chama_se_match_completo(self) -> None:
        client = MagicMock()
        resultado = processar_arquivo(
            str(FIXTURE_CSV),
            usar_llm=True,
            client=client,
        )
        mapa: MapaSemResult = resultado["mapa"]
        assert mapa.origem == "deterministico"
        assert not client.chat.completions.create.called
