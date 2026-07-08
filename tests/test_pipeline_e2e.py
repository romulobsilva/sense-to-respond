"""
Teste E2E do pipeline completo com dados Mondelez (fixture CSV).

Fluxo testado:
  DataShield (leitura + perfil + mapeamento + normalizacao)
  -> HITL AutoApprove (mapeamento aprovado automaticamente)
  -> Dominion Mondelez (tools parametrizadas: sellout, sellin, doi)
  -> Sinais (extracao de desvios)
  -> Optimus (proposicoes priorizadas)
  -> Validador (deterministico)
  -> Critic (mockado - LLM)
  -> Fila Nexus (com flags de revisao)
  -> Output Guardrail (disclaimer)

LLM e mockado para evitar dependencia de API key nos testes.
Todas as fases deterministicas rodam sem mock.
"""

import sys
import os
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from config import Settings
from hitl import HITLAutoApprove
from nexus import Nexus
from state_types import TIPOS_DECISAO_MVP


FIXTURE_CSV = str(
    Path(__file__).parent / "fixtures" / "mondelez_ficticio.csv"
)


def _settings_teste() -> Settings:
    """Settings para teste sem API key real."""
    return Settings(
        openai_api_key="sk-test-fake-key-for-e2e",
        openai_model="gpt-4o-mini",
        limiar_confianca_critic=0.6,
        max_optimus_retries=1,
        hitl_mode="auto",
    )


def _mock_critic_response() -> MagicMock:
    """Simula resposta do Critic LLM."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = (
        '{"aprovado": true, "confianca": 0.85, "problemas": []}'
    )
    return response


def _mock_explicacao_response() -> MagicMock:
    """Simula resposta de explicacao do agente LLM."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = (
        "Analise concluida. Foram identificados desvios de sell-out, "
        "sell-in e DOI no dataset Mondelez. As proposicoes de acao "
        "estao priorizadas por impacto financeiro."
    )
    return response


class TestPipelineE2EMondelez:
    """Teste end-to-end com fixture CSV Mondelez."""

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_pipeline_completo_com_fixture(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """
        Roda o pipeline completo e valida invariantes em cada fase.
        """
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )

        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)

        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido, identifique desvios "
            "e gere proposicoes de acao."
        )

        assert not resultado.get("bloqueado", False), (
            f"Pipeline bloqueado: {resultado.get('motivo', '')}"
        )

        assert resultado.get("schema_confirmado") is True

        assert resultado.get("dataset_canonico") is not None
        df = resultado["dataset_canonico"]
        assert len(df) == 20

        caps = resultado.get("capacidades", [])
        assert "sellout" in caps
        assert "sellin" in caps
        assert "doi" in caps

        resultados = resultado.get("resultados", {})
        assert "analise_sellout" in resultados
        assert "analise_sellin" in resultados
        assert "analise_doi" in resultados

        sinais = resultado.get("sinais", [])
        assert len(sinais) > 0, "Deve haver sinais extraidos"

        tipos_sinais = {s["tipo"] for s in sinais if isinstance(s, dict)}
        assert "desvio_sellout" in tipos_sinais
        assert "desvio_sellin" in tipos_sinais
        assert "doi_fora_politica" in tipos_sinais

        proposicoes = resultado.get("proposicoes", [])
        assert len(proposicoes) > 0, "Deve haver proposicoes geradas"

        for prop in proposicoes:
            if isinstance(prop, dict):
                assert prop["tipo"] in TIPOS_DECISAO_MVP, (
                    f"Tipo '{prop['tipo']}' fora da whitelist"
                )
                assert prop["impacto_financeiro"] == prop["impacto_calculado"]
                assert len(prop["evidencias"]) > 0
                assert len(prop["skus"]) > 0

        validacao = resultado.get("validacao", {})
        assert isinstance(validacao, dict)

        critica = resultado.get("critica", {})
        assert isinstance(critica, dict)
        assert critica.get("aprovado") is True

        fila = resultado.get("fila_nexus", [])
        assert len(fila) > 0, "Fila Nexus deve ter itens"

        explicacao = resultados.get("explicacao", "")
        assert len(explicacao) > 0

        handoffs = resultado.get("handoffs", [])
        assert len(handoffs) >= 2

        hitl_resolvidos = resultado.get("hitl_resolvidos", [])
        assert len(hitl_resolvidos) == 1
        assert hitl_resolvidos[0].get("decisao") == "aprovado"

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_sinais_tem_dimensoes(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """Sinais devem conter dimensoes (pais, canal, marca)."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )
        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido."
        )

        sinais = resultado.get("sinais", [])
        sinais_com_pais = [
            s for s in sinais
            if isinstance(s, dict) and s.get("pais")
        ]
        assert len(sinais_com_pais) > 0, (
            "Ao menos um sinal deve ter pais preenchido"
        )

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_proposicoes_ordenadas_por_impacto(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """Proposicoes devem estar ordenadas por impacto decrescente."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )
        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido."
        )

        proposicoes = resultado.get("proposicoes", [])
        impactos = [
            p["impacto_financeiro"]
            for p in proposicoes
            if isinstance(p, dict)
        ]
        assert impactos == sorted(impactos, reverse=True), (
            f"Proposicoes fora de ordem: {impactos}"
        )

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_ids_proposicoes_sequenciais(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """IDs de proposicoes devem ser P1, P2, P3..."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )
        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido."
        )

        proposicoes = resultado.get("proposicoes", [])
        ids = [
            p["proposicao_id"]
            for p in proposicoes
            if isinstance(p, dict)
        ]
        expected = [f"P{i}" for i in range(1, len(ids) + 1)]
        assert ids == expected, f"IDs fora de sequencia: {ids}"

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_auditoria_presente(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """Resultado deve conter trilha de auditoria."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )
        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido."
        )

        auditoria = resultado.get("auditoria")
        assert auditoria is not None, "Auditoria deve estar presente"
        assert isinstance(auditoria, dict)
        assert "sessao_id" in auditoria
        assert "eventos" in auditoria
        assert len(auditoria["eventos"]) > 0

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_disclaimer_presente_na_explicacao(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """Output guardrail deve adicionar disclaimer."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client
        mock_agent_client.chat.completions.create.return_value = (
            _mock_explicacao_response()
        )
        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=FIXTURE_CSV,
        )

        resultado = nexus.executar(
            "Analise os dados do arquivo fornecido."
        )

        explicacao = resultado.get("resultados", {}).get("explicacao", "")
        assert "AVISO" in explicacao or "aviso" in explicacao.lower() or "disclaimer" in explicacao.lower(), (
            "Explicacao deve conter disclaimer do output guardrail"
        )

    @patch("critic.OpenAI")
    @patch("agent.OpenAI")
    def test_sem_arquivo_usa_dominion_legado(
        self,
        mock_agent_openai: MagicMock,
        mock_critic_openai: MagicMock,
    ) -> None:
        """Sem arquivo_entrada, pipeline deve usar Dominion legado (LLM)."""
        mock_agent_client = MagicMock()
        mock_agent_openai.return_value = mock_agent_client

        decisao_response = MagicMock()
        decisao_response.choices = [MagicMock()]
        decisao_response.choices[0].message.content = (
            '{"acao": "carregar_dados", "justificativa": "preciso dos dados"}'
        )

        fim_response = MagicMock()
        fim_response.choices = [MagicMock()]
        fim_response.choices[0].message.content = (
            '{"acao": "fim", "justificativa": "dados ja carregados"}'
        )

        mock_agent_client.chat.completions.create.side_effect = [
            decisao_response,
            fim_response,
            _mock_explicacao_response(),
        ]

        mock_critic_client = MagicMock()
        mock_critic_openai.return_value = mock_critic_client
        mock_critic_client.chat.completions.create.return_value = (
            _mock_critic_response()
        )

        settings = _settings_teste()
        from agent import AgenteOpenAI
        agente = AgenteOpenAI(settings)
        nexus = Nexus(
            agente=agente,
            settings=settings,
            hitl=HITLAutoApprove(),
            arquivo_entrada=None,
        )

        resultado = nexus.executar(
            "Compare a demanda modelada com o baseline."
        )

        assert not resultado.get("bloqueado", False)
        assert resultado.get("dataset_canonico") is None
        assert "carregar_dados" in resultado.get("acoes_executadas", [])
