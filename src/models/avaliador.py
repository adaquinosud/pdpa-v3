"""Análise do Avaliador — uma linha por peça lida (arquivo ou texto colado).

Retenção (decisão do Alexandre, 12/10): ``texto_json`` guarda o texto extraído só
enquanto a análise está aberta (refazer com outra descrição / retomar sem reenviar).
Concluir apaga na hora; ``AVALIADOR_DIAS_RETENCAO_TEXTO`` sem uso apaga sozinho
(housekeeping do watchdog), menos nas peças de medição (``servico.PECAS_DE_MEDICAO``).
Depois disso ficam resumo, itens, trechos citados, custo e hash.

Apagar a leitura (decisão do Alexandre, 16/10): sai tudo o que é da peça (descrição,
nome do arquivo, resumo, itens com trechos, texto, hash) e a linha fica APAGADA, fora da
lista, só com empresa, data, custo, modelo e versões. A linha não sai porque o teto mensal
soma o ``custo_usd`` destas linhas: apagar não pode devolver gasto ao teto.

``custo_usd`` é NOT NULL e acumula a cada chamada: custo nulo parece grátis (CLAUDE.md §13).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base

if TYPE_CHECKING:
    from src.models.empresa import Empresa

# Estados. Finais: PRONTA e FALHOU — o polling da tela para neles.
STATUS_PENDENTE = "pendente"
STATUS_LENDO = "lendo"
STATUS_PRONTA = "pronta"
STATUS_FALHOU = "falhou"
STATUS_APAGADA = "apagada"  # só o registro de gasto; nunca aparece na tela
STATUS_EM_PROCESSAMENTO = (STATUS_PENDENTE, STATUS_LENDO)


class AvaliadorAnalise(Base):
    __tablename__ = "avaliador_analises"
    __table_args__ = (Index("ix_avaliador_analises_empresa_criado", "empresa_id", "criado_em"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("empresas.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # Heartbeat do processamento: o housekeeping marca FALHOU o que parou de bater.
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    # Último uso pela pessoa (abrir, refazer, retomar): conta os dias da retenção.
    usado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    origem: Mapped[str] = mapped_column(String(8), nullable=False)  # arquivo | texto
    descricao: Mapped[str] = mapped_column(Text, nullable=False)  # o que é e para que serve
    # A peça foi feita para um cliente com nome? Respondido no formulário (18/10); NULL nas
    # leituras de antes. Só agrupa as marcas na tela, não muda o que é conferido.
    cliente_nomeado: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    arquivo_nome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    conteudo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    formato: Mapped[str] = mapped_column(String(8), nullable=False)  # pptx | pdf | texto
    n_paginas: Mapped[int] = mapped_column(Integer, nullable=False)
    paginas_sem_texto_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    texto_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    texto_apagado_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    texto_apagado_motivo: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDENTE)
    # Nunca contém texto da peça nem resposta do modelo: tipo de erro + etapa.
    erro_motivo: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    resumo: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    itens_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    modelo: Mapped[str] = mapped_column(String, nullable=False)
    regua_versao: Mapped[str] = mapped_column(String, nullable=False)
    prompt_versao: Mapped[str] = mapped_column(String, nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_cache_criacao: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_cache_leitura: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    custo_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    empresa: Mapped["Empresa"] = relationship("Empresa")


# Correção à mão de uma leitura no formato 3 (fatia 1 do parecer no app, 22/10). Cada
# recusa de trecho e cada trecho incluído pela pessoa vira uma linha, e a linha não some:
# desfazer só marca ``desfeita_em``. É o gabarito de erros reais, em peças variadas, que um
# conferidor de resposta precisa para ser medido contra peça que nunca viu. O resultado
# gravado da leitura (``itens_json``) nunca é alterado: a tela aplica as correções por cima.
# Guarda trecho de peça de cliente: nada daqui vira fixture nem vai para o repositório.
CORRECAO_RECUSA = "recusa"  # um trecho citado pela leitura não responde à marca
CORRECAO_INCLUSAO = "inclusao"  # a pessoa achou na peça o trecho que responde
# a pessoa devolve ao Word um trecho que a verificação tirou (24/10): é a medida de uso da
# verificação, quantas exclusões as pessoas desfazem
CORRECAO_DEVOLUCAO = "devolucao"


class AvaliadorCorrecao(Base):
    __tablename__ = "avaliador_correcoes"
    __table_args__ = (Index("ix_avaliador_correcoes_analise", "analise_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analise_id: Mapped[int] = mapped_column(
        ForeignKey("avaliador_analises.id", ondelete="CASCADE"), nullable=False
    )
    # o texto exato a que a correção se refere: o mesmo número de leitura pode ter tido outro
    # conteúdo, e a correção vale para este
    conteudo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    marca_codigo: Mapped[str] = mapped_column(String(16), nullable=False)
    marca_texto: Mapped[str] = mapped_column(Text, nullable=False)  # como foi perguntada
    tipo: Mapped[str] = mapped_column(String(16), nullable=False)
    trecho: Mapped[str] = mapped_column(Text, nullable=False)  # como está na peça
    pagina: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    desfeita_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# O parecer de uma leitura (fatia 2 do parecer no app, 22/10): o que a pessoa escreve. O resto
# do parecer (o que a peça diz e o que não diz) sai da leitura com as correções, na hora de
# gerar o Word (``src/avaliador/parecer.py``). Uma linha por leitura. Texto da Loyall sobre peça
# de cliente: apagar a leitura apaga o texto daqui.
class AvaliadorParecer(Base):
    __tablename__ = "avaliador_pareceres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analise_id: Mapped[int] = mapped_column(
        ForeignKey("avaliador_analises.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # o nome que sai no título do Word, escrito pela pessoa: NUNCA o da empresa da conta, que
    # não é a da peça quando se lê um prospect (#32, 22/10)
    empresa_da_peca: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ordem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    achados_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )  # subpilar → frase
    nota_c: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # marca → trecho que a pessoa escolheu para o parecer ("usar este no parecer"). Não é
    # correção: trocar de trecho não diz que o outro está errado, e por isso não vai para
    # avaliador_correcoes (a tabela de erros não pode receber troca de gosto).
    escolhas_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # o rascunho do modelo (fatia 3, 22/10): campo → {"rascunho": texto do modelo, "estado":
    # "pendente" | "aceito" | "editado", "base": hash da tela que o modelo leu}. O estado fica
    # guardado depois de passado: é ele que diz se o rascunho merece confiança.
    rascunho_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    rascunho_custo_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rascunho_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rascunho_versao: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # a verificação dos trechos (24/10, ``src/avaliador/sozinho.py``): {"versao", "trechos":
    # {texto impresso normalizado: {"decisao": "passa" | "exclui", "tipo", "por_que"}}}. O
    # custo entra no teto mensal pela data da verificação, como o rascunho.
    verificacao_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    verificacao_custo_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verificacao_em: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
