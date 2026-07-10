"""
Agente com OpenAI: proximo passo (loop) e explicacao via LLM.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from openai import OpenAI

from audit import AuditTrail
from config import Settings
from tools import serializar_contexto_agente

FERRAMENTAS_VALIDAS: Sequence[str] = (
    "carregar_dados",
    "validar_demanda",
    "validar_custos",
)

ACAO_FIM = "fim"
CHAVES_OBRIGATORIAS_DECISAO = ("acao", "justificativa")
MAX_RETRIES_JSON_AGENTE = 2

SYSTEM_PROXIMO_PASSO = """Voce e um agente de validacao de modelagem.

A cada turno escolha UMA proxima acao com base na pergunta do usuario e no
estado atual (dados carregados, validacoes ja feitas, resultados).

Ferramentas (use exatamente estes nomes em "acao"):
- carregar_dados: carrega baseline, modelado e DRE (obrigatorio antes das validacoes)
- validar_demanda: compara demanda real vs modelada por SKU
- validar_custos: compara custo modelado total vs DRE
- fim: parar quando as validacoes pedidas na pergunta ja foram feitas

Regras:
1. Se "Dados carregados: nao", escolha carregar_dados (salvo que ja conste em acoes executadas).
2. Nao repita ferramenta listada em "Acoes ja executadas".
3. Use validar_demanda se a pergunta mencionar demanda, baseline ou SKU.
4. Use validar_custos se a pergunta mencionar custo, frete ou DRE.
5. Responda acao "fim" quando nao houver mais passos uteis para a pergunta.
6. Em "justificativa", explique em uma frase curta por que escolheu essa acao.

Responda APENAS com JSON:
{"acao": "carregar_dados", "justificativa": "Preciso carregar os dados primeiro."}
ou
{"acao": "fim", "justificativa": "Todas as validacoes pedidas ja foram feitas."}
"""

SYSTEM_EXPLICACAO = """Voce e um analista senior de S&OE (Sales & Operations Execution).

Com base no resumo por categoria, alertas forward e proposicoes fornecidos,
escreva uma explicacao executiva clara em portugues. Siga estas regras:

1. Comece com visao geral (desvio medio SO, SI, DOI).
2. PRIORIZE os ALERTAS FORWARD quando presentes:
   - OPORTUNIDADE: SO acima do plano + DOI na faixa saudavel
     (entre limiar de ruptura e overstock). Plano subdimensionado.
     Aumentar sell-in para capturar demanda. NAO classificar como ruptura.
   - RUPTURA: DOI abaixo do limiar de ruptura + SO acima do plano
     (mesmo se o plano forward estiver curto).
   - OVERSTOCK: DOI alto e subindo, plano forward ainda empurra estoque.
   - GAP_PLANO: plano forward assume reversao de tendencia sem evidencia.
3. Mencione a TENDENCIA DOI: quais SKUs estao piorando vs melhorando.
   Se DOI esta melhorando (caindo), nao alarme -- o risco esta se dissipando.
4. RITMO DE VARIACAO SO: se SO esta desacelerando (queda progressiva
   semana a semana), destacar como CAUSA-RAIZ de overstock. Exemplo:
   "SO piorou de -8% para -16% nas ultimas semanas -- desaceleracao
   explica o acumulo de estoque."
5. DESVIO PERSISTENTE: se um SKU apresenta desvio no mesmo sinal
   por 3+ meses consecutivos, classificar como problema ESTRUTURAL
   (nao pontual). Exemplo: "desvio de -17% se repete ha 4 meses --
   premissa de baseline precisa ser revisada."
6. Liste as proposicoes mais urgentes (maior impacto financeiro).
7. Se houver DOI fora da politica (gap > 7d), distinga:
   - DOI alto + SO desacelerando -> SEGURAR sell-in (causa-raiz: queda SO)
   - DOI alto + tendencia piorando -> SEGURAR sell-in (critico)
   - DOI alto + tendencia melhorando -> monitorar, sem acao urgente
   - DOI baixo + SO subindo -> RUPTURA (oportunidade so com DOI saudavel)
8. Seja objetivo: paragrafos curtos e bullets quando fizer sentido.
9. NAO invente numeros. Use apenas os dados fornecidos no contexto.
"""


@dataclass
class DecisaoAgente:
    """Resultado estruturado de uma decisao do LLM no loop."""

    acao: str
    justificativa: str
    json_bruto: str
    modelo: str
    contexto_enviado: str
    fallback_aplicado: bool
    acao_original_llm: str


class AgenteOpenAI:
    """Agente que usa a API OpenAI para decidir passos e explicar."""

    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    @property
    def modelo(self) -> str:
        """Nome do modelo OpenAI em uso."""
        return self._model

    def proximo_passo(
        self,
        pergunta_usuario: str,
        state: Dict[str, Any],
        registrar_log: Optional[Callable[[str], None]] = None,
        auditoria: Optional[AuditTrail] = None,
        iteracao: Optional[int] = None,
    ) -> DecisaoAgente:
        """
        Pede ao LLM a proxima acao (uma tool ou fim) com base no state atual.
        """
        def log(msg: str) -> None:
            if registrar_log is not None:
                registrar_log(msg)

        contexto = serializar_contexto_agente(state)
        log("Chamada OpenAI: proximo_passo (decisao da acao)")
        log(f"Modelo: {self._model}")
        log("Contexto enviado ao LLM:")
        for linha in contexto.split("\n"):
            log(f"  | {linha}")

        messages = [
            {"role": "system", "content": SYSTEM_PROXIMO_PASSO},
            {
                "role": "user",
                "content": (
                    f"Pergunta do usuario: {pergunta_usuario}\n\n"
                    f"Estado atual:\n{contexto}"
                ),
            },
        ]

        content = ""
        dados: Dict[str, str] = {}
        for tentativa in range(MAX_RETRIES_JSON_AGENTE + 1):
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=messages,
            )

            content = response.choices[0].message.content or ""
            if not content:
                if tentativa < MAX_RETRIES_JSON_AGENTE:
                    log(f"Resposta vazia (tentativa {tentativa + 1}). Retry.")
                    messages.append({
                        "role": "user",
                        "content": "Retorne APENAS um objeto JSON completo.",
                    })
                    continue
                raise ValueError(
                    "Resposta vazia do modelo ao decidir proximo passo."
                )

            log(f"JSON bruto do LLM (tentativa {tentativa + 1}): {content}")

            try:
                dados = json.loads(content)
            except json.JSONDecodeError:
                if tentativa < MAX_RETRIES_JSON_AGENTE:
                    log(f"JSON invalido (tentativa {tentativa + 1}). Retry.")
                    messages.append({
                        "role": "user",
                        "content": (
                            "JSON invalido. Retorne APENAS JSON valido "
                            "com as chaves: acao, justificativa."
                        ),
                    })
                    continue
                log("JSON invalido apos retries. Usando fallback.")
                dados = {}
                break

            faltando = [
                k for k in CHAVES_OBRIGATORIAS_DECISAO if k not in dados
            ]
            if faltando:
                if tentativa < MAX_RETRIES_JSON_AGENTE:
                    log(
                        f"Chaves faltando: {', '.join(faltando)} "
                        f"(tentativa {tentativa + 1}). Retry."
                    )
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Faltam chaves: {', '.join(faltando)}. "
                            "Retorne JSON completo."
                        ),
                    })
                    continue
                log("Chaves faltando apos retries. Usando fallback.")
                break

            break

        acao_bruta = dados.get("acao", "")
        if not isinstance(acao_bruta, str):
            acao_bruta = str(acao_bruta)

        justificativa_bruta = dados.get("justificativa", "")
        if not isinstance(justificativa_bruta, str):
            justificativa_bruta = str(justificativa_bruta)

        acao_original_llm = acao_bruta.strip()
        justificativa = justificativa_bruta.strip()
        acao_final = acao_original_llm
        fallback_aplicado = False

        if acao_final == ACAO_FIM:
            log("Decisao interpretada: encerrar loop (acao=fim)")
        elif acao_final in FERRAMENTAS_VALIDAS:
            log(f"Decisao interpretada: executar ferramenta '{acao_final}'")
        else:
            dados_vazios = not state.get("dados")
            fallback_aplicado = True
            if dados_vazios:
                acao_final = "carregar_dados"
                log(
                    f"Acao invalida ou desconhecida ('{acao_original_llm}'); "
                    "fallback do agente: carregar_dados (sem dados no state)"
                )
            else:
                acao_final = ACAO_FIM
                log(
                    f"Acao invalida ou desconhecida ('{acao_original_llm}'); "
                    "fallback do agente: fim"
                )

        if justificativa:
            log(f"Justificativa do LLM: {justificativa}")

        decisao = DecisaoAgente(
            acao=acao_final,
            justificativa=justificativa,
            json_bruto=content,
            modelo=self._model,
            contexto_enviado=contexto,
            fallback_aplicado=fallback_aplicado,
            acao_original_llm=acao_original_llm,
        )

        if auditoria is not None:
            auditoria.registrar(
                "llm_decisao",
                {
                    "pergunta": pergunta_usuario,
                    "acao": decisao.acao,
                    "justificativa": decisao.justificativa,
                    "json_bruto": decisao.json_bruto,
                    "modelo": decisao.modelo,
                    "fallback_aplicado": decisao.fallback_aplicado,
                    "acao_original_llm": decisao.acao_original_llm,
                    "contexto_enviado": decisao.contexto_enviado,
                },
                iteracao=iteracao,
            )

        return decisao

    def gerar_explicacao(
        self,
        pergunta_usuario: str,
        contexto_resultados: str,
        registrar_log: Optional[Callable[[str], None]] = None,
        auditoria: Optional[AuditTrail] = None,
    ) -> str:
        """
        Gera explicacao em linguagem natural a partir dos resultados.
        """
        def log(msg: str) -> None:
            if registrar_log is not None:
                registrar_log(msg)

        log("Chamada OpenAI: gerar_explicacao (texto final para o usuario)")
        log(f"Modelo: {self._model}")
        log("Resultados deterministicos enviados ao LLM:")
        for linha in contexto_resultados.split("\n"):
            log(f"  | {linha}")

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_EXPLICACAO},
                {
                    "role": "user",
                    "content": (
                        f"Pergunta original: {pergunta_usuario}\n\n"
                        f"Resultados:\n{contexto_resultados}"
                    ),
                },
            ],
        )

        content = response.choices[0].message.content
        if content is None:
            raise ValueError("Resposta vazia do modelo ao explicar.")

        texto = content.strip()

        if auditoria is not None:
            auditoria.registrar(
                "llm_explicacao",
                {
                    "modelo": self._model,
                    "pergunta": pergunta_usuario,
                    "tamanho_contexto": len(contexto_resultados),
                    "tamanho_resposta": len(texto),
                    "contexto_resultados": contexto_resultados,
                    "resposta_completa": texto,
                },
            )

        return texto
