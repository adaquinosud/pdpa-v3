"""Modelos SQLAlchemy do PDPA v3.

Importar este pacote registra todas as classes no `Base.metadata`, permitindo
que `configure_mappers()` resolva as relationships string-based e que
`Base.metadata.create_all()` crie todas as tabelas (usado em testes e seeds).
"""

from src.models.agrupamento import Agrupamento
from src.models.anomalia import (
    AnomaliaDetectada,
    CruzamentoSnapshot,
    RatioMensal,
    TemaSnapshot,
)
from src.models.base import Base
from src.models.caso import Caso
from src.models.chat_cache import ChatCache
from src.models.classificacao_batch import ClassificacaoBatch
from src.models.classifier_metric import ClassifierMetric
from src.models.coleta_execucao import ColetaExecucao
from src.models.diagnostico import LeituraDiagnostico
from src.models.empresa import Empresa
from src.models.evento_manutencao import EventoManutencao
from src.models.fonte import Fonte
from src.models.fonte_coorte_coleta import FonteCoorteColeta
from src.models.fonte_reputacao import FonteReputacao
from src.models.glossario_termo import GlossarioTermo
from src.models.governanca import (
    GiniConcentracao,
    PrevisibilidadeCalculation,
    ProximityCalculation,
)
from src.models.local import Local, LocalMetadado
from src.models.origem import OrigemAnalise, OrigemSintese
from src.models.pesquisa import Pesquisa, PesquisaEscopo, PesquisaPergunta
from src.models.pessoa import Pessoa, PessoaIdentificador, PessoaMerge
from src.models.plano_acao import AcaoStatus
from src.models.respondente import Respondente, Resposta
from src.models.relatorio_cache import RelatorioCache
from src.models.sonda_ia import (
    SondaIAAvaliacao,
    SondaIAExecucao,
    SondaIALeitura,
    SondaIAResposta,
)
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.models.temas import (
    AcaoVenda,
    Tema,
    TemaCache,
    TemaCruzamento,
    TemaMerge,
    VerbatimEmbedding,
    VerbatimTema,
)
from src.models.usuario import Usuario
from src.models.verbatim import Verbatim
from src.models.verbatim_reclassificacao import VerbatimReclassificacao
from src.models.visao_financeira import VisaoFinanceiraInput, VisaoFinanceiraSnapshot

__all__ = [
    "AcaoStatus",
    "AcaoVenda",
    "Agrupamento",
    "AnomaliaDetectada",
    "CruzamentoSnapshot",
    "RatioMensal",
    "TemaSnapshot",
    "Base",
    "Caso",
    "FonteCoorteColeta",
    "ChatCache",
    "ClassificacaoBatch",
    "ClassifierMetric",
    "ColetaExecucao",
    "Empresa",
    "EventoManutencao",
    "Fonte",
    "FonteReputacao",
    "GlossarioTermo",
    "GiniConcentracao",
    "LeituraDiagnostico",
    "PrevisibilidadeCalculation",
    "ProximityCalculation",
    "Local",
    "LocalMetadado",
    "Pesquisa",
    "PesquisaEscopo",
    "OrigemAnalise",
    "OrigemSintese",
    "PesquisaPergunta",
    "Pessoa",
    "PessoaIdentificador",
    "PessoaMerge",
    "RelatorioCache",
    "Respondente",
    "Resposta",
    "SondaIAAvaliacao",
    "SondaIAExecucao",
    "SondaIALeitura",
    "SondaIAResposta",
    "SugestaoEstrutural",
    "Tema",
    "TemaCache",
    "TemaCruzamento",
    "TemaMerge",
    "VerbatimEmbedding",
    "VerbatimTema",
    "Usuario",
    "Verbatim",
    "VerbatimReclassificacao",
    "VisaoFinanceiraInput",
    "VisaoFinanceiraSnapshot",
]
