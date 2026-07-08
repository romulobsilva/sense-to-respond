"""
Contrato do state compartilhado (blackboard) entre agentes do MVP.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


TIPOS_DECISAO_MVP = frozenset({
    "rebalancear_estoque",
    "priorizar_skus",
    "ajustar_cobertura",
    "proteger_promocao",
    "gerenciar_falta_excesso",
    "ajustar_custo",
    "ajustar_demanda",
    "ajustar_plano_sellout",
    "ajustar_plano_sellin",
    "rebalancear_estoque_doi",
    "investigar_desvio_canal",
    "questionar_premissa_plano",
})


@dataclass
class Sinal:
    """Sinal estruturado produzido pelo Dominion."""

    sinal_id: str
    tipo: str
    sku: str
    canal: str
    metrica: str
    valor: float
    referencia: float
    desvio_pct: float
    severidade: str
    pais: str = ""
    categoria: str = ""
    marca: str = ""
    tendencia: str = ""
    semanas_consecutivas: int = 0
    risco_forward: str = ""

    def para_dict(self) -> Dict[str, Any]:
        """Serializa o sinal para JSON."""
        return asdict(self)


@dataclass
class Proposicao:
    """Proposicao priorizada produzida pelo Optimus."""

    proposicao_id: str
    tipo: str
    titulo: str
    descricao: str
    impacto_financeiro: float
    impacto_calculado: float
    urgencia_horas: int
    skus: List[str]
    evidencias: List[str]

    def para_dict(self) -> Dict[str, Any]:
        """Serializa a proposicao para JSON."""
        return asdict(self)


@dataclass
class ResultadoValidacao:
    """Resultado do validador deterministico pos-Optimus."""

    ok: bool
    erros: List[str] = field(default_factory=list)

    def para_dict(self) -> Dict[str, Any]:
        """Serializa o resultado para JSON."""
        return asdict(self)


@dataclass
class ResultadoCritica:
    """Resultado do Critic LLM (auditoria somente leitura)."""

    aprovado: bool
    confianca: float
    problemas: List[str] = field(default_factory=list)
    json_bruto: str = ""

    def para_dict(self) -> Dict[str, Any]:
        """Serializa o resultado para JSON."""
        return asdict(self)


@dataclass
class ItemFilaNexus:
    """Item da fila unificada para decisao humana."""

    proposicao: Proposicao
    prioridade: int
    revisao_obrigatoria: bool
    motivo_revisao: str

    def para_dict(self) -> Dict[str, Any]:
        """Serializa o item da fila para JSON."""
        return {
            "proposicao": self.proposicao.para_dict(),
            "prioridade": self.prioridade,
            "revisao_obrigatoria": self.revisao_obrigatoria,
            "motivo_revisao": self.motivo_revisao,
        }


def criar_state_inicial(pergunta: str) -> Dict[str, Any]:
    """
    Inicializa o blackboard compartilhado do Nexus.

    Campos de DataShield e HITL sao inicializados como None/lista vazia
    e preenchidos apenas quando um arquivo de entrada e fornecido.
    """
    return {
        "pergunta": pergunta,
        "dados": {},
        "resultados": {},
        "acoes_executadas": [],
        "sinais": [],
        "proposicoes": [],
        "validacao": None,
        "critica": None,
        "fila_nexus": [],
        "optimus_tentativas": 0,
        "handoffs": [],
        "dataset_csv": None,
        "perfil_dados": None,
        "mapa_semantico": None,
        "schema_confirmado": False,
        "dataset_canonico": None,
        "nivel_adaptacao": None,
        "capacidades": [],
        "hitl_pendentes": [],
        "hitl_resolvidos": [],
    }


def registrar_handoff(
    state: Dict[str, Any],
    origem: str,
    destino: str,
    payload_chaves: List[str],
) -> None:
    """
    Registra um handoff entre agentes na trilha do state.
    """
    handoffs: List[Dict[str, Any]] = state.setdefault("handoffs", [])
    handoffs.append({
        "origem": origem,
        "destino": destino,
        "payload_chaves": payload_chaves,
    })


def sinais_do_state(state: Dict[str, Any]) -> List[Sinal]:
    """
    Converte sinais do state para objetos tipados.
    """
    brutos = state.get("sinais", [])
    if not isinstance(brutos, list):
        return []
    resultado: List[Sinal] = []
    for item in brutos:
        if isinstance(item, Sinal):
            resultado.append(item)
        elif isinstance(item, dict):
            resultado.append(Sinal(**item))
    return resultado


def proposicoes_do_state(state: Dict[str, Any]) -> List[Proposicao]:
    """
    Converte proposicoes do state para objetos tipados.
    """
    brutos = state.get("proposicoes", [])
    if not isinstance(brutos, list):
        return []
    resultado: List[Proposicao] = []
    for item in brutos:
        if isinstance(item, Proposicao):
            resultado.append(item)
        elif isinstance(item, dict):
            resultado.append(Proposicao(**item))
    return resultado


def serializar_sinais_para_llm(sinais: List[Sinal]) -> str:
    """
    Formata sinais para prompt do Critic ou Optimus.
    """
    if not sinais:
        return "Nenhum sinal disponivel."
    linhas: List[str] = []
    for s in sinais:
        linhas.append(
            f"- [{s.sinal_id}] {s.tipo} | SKU={s.sku} | "
            f"metrica={s.metrica} | valor={s.valor:.2f} | "
            f"ref={s.referencia:.2f} | desvio={s.desvio_pct:.2f}% | "
            f"severidade={s.severidade}"
        )
    return "\n".join(linhas)


def serializar_proposicoes_para_llm(proposicoes: List[Proposicao]) -> str:
    """
    Formata proposicoes para prompt do Critic.
    """
    if not proposicoes:
        return "Nenhuma proposicao disponivel."
    linhas: List[str] = []
    for p in proposicoes:
        skus_txt = ", ".join(p.skus)
        evid_txt = ", ".join(p.evidencias)
        linhas.append(
            f"- [{p.proposicao_id}] {p.tipo} | {p.titulo}\n"
            f"  descricao: {p.descricao}\n"
            f"  impacto: R$ {p.impacto_financeiro:.2f} "
            f"(calc: R$ {p.impacto_calculado:.2f})\n"
            f"  urgencia: {p.urgencia_horas}h | skus: {skus_txt}\n"
            f"  evidencias: {evid_txt}"
        )
    return "\n".join(linhas)
