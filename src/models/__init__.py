"""Modelos SQLAlchemy do PDPA v3.

Importar este pacote registra todas as classes no `Base.metadata`, permitindo
que `configure_mappers()` resolva as relationships string-based e que
`Base.metadata.create_all()` crie todas as tabelas (usado em testes e seeds).
"""

from src.models.agrupamento import Agrupamento
from src.models.anomalia import AnomaliaDetectada
from src.models.base import Base
from src.models.classifier_metric import ClassifierMetric
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local, LocalMetadado
from src.models.temas import TemaCache, TemaCruzamento
from src.models.usuario import Usuario
from src.models.verbatim import Verbatim

__all__ = [
    "Agrupamento",
    "AnomaliaDetectada",
    "Base",
    "ClassifierMetric",
    "Empresa",
    "Fonte",
    "Local",
    "LocalMetadado",
    "TemaCache",
    "TemaCruzamento",
    "Usuario",
    "Verbatim",
]
