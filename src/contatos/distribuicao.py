"""Distribuição de pesquisa — recorte da base, token opaco por-pessoa, export e
"quem faltou".

PDPA NÃO dispara e-mail: gera o TOKEN OPACO por pessoa (sem dado na URL) e EXPORTA a
planilha (nome, email, link); o cliente dispara. O universo de convidados nasce aqui
(``PesquisaConvite``) — é o que permite o "quem faltou" (anti-join com ``Respondente``
por ``pessoa_id + pesquisa_id``, que pega quem respondeu por QUALQUER caminho, não só
pelo link individual).
"""

from __future__ import annotations

import io
import secrets
from typing import Any, Dict, List, Optional

import pandas as pd

from src.coletor.excel import FONTE_EMAIL
from src.models.contato import ContatoAtributo, ContatoEmpresa, PesquisaConvite
from src.models.pessoa import Pessoa, PessoaIdentificador


def recorte(
    session,
    empresa_id: int,
    *,
    filtros_atributo: Optional[Dict[str, str]] = None,
    local_ids: Optional[List[int]] = None,
) -> List[int]:
    """pessoa_ids dos contatos ATIVOS da empresa que casam o recorte: por unidade
    (``local_ids``) e/ou por atributo (``{chave: valor}`` em AND, consulta em SQL)."""
    q = session.query(ContatoEmpresa.pessoa_id).filter(
        ContatoEmpresa.empresa_id == empresa_id, ContatoEmpresa.status == "ativo"
    )
    if local_ids:
        q = q.filter(ContatoEmpresa.local_id.in_(local_ids))
    for chave, valor in (filtros_atributo or {}).items():
        sub = session.query(ContatoAtributo.pessoa_id).filter(
            ContatoAtributo.empresa_id == empresa_id,
            ContatoAtributo.chave == chave,
            ContatoAtributo.valor_atual == valor,
        )
        q = q.filter(ContatoEmpresa.pessoa_id.in_(sub))
    return [pid for (pid,) in q.all()]


def gerar_convites(session, pesquisa, pessoa_ids: List[int]) -> Dict[str, Any]:
    """Cria um ``PesquisaConvite`` (token opaco) por pessoa do recorte que ainda não
    tem convite nesta pesquisa (UNIQUE pesquisa,pessoa é idempotente). Retorna contagem
    de novos + total de convidados da pesquisa."""
    existentes = {
        c.pessoa_id
        for c in session.query(PesquisaConvite.pessoa_id).filter_by(pesquisa_id=pesquisa.id)
    }
    novos = 0
    for pid in pessoa_ids:
        if pid in existentes:
            continue
        session.add(
            PesquisaConvite(
                empresa_id=pesquisa.empresa_id,
                pesquisa_id=pesquisa.id,
                pessoa_id=pid,
                token=secrets.token_urlsafe(16),
            )
        )
        existentes.add(pid)
        novos += 1
    session.flush()
    total = session.query(PesquisaConvite).filter_by(pesquisa_id=pesquisa.id).count()
    return {"novos": novos, "total_convidados": total}


def _email_da_pessoa(session, pessoa_id: int) -> Optional[str]:
    """E-mail global da pessoa, SÓ se NÃO-ambíguo (§5.5): a pessoa tem 1 e-mail → retorna;
    ≥2 e-mails distintos (deu e-mails diferentes por empresa) → None (nunca inventa
    procedência — o export mostra a nota de reimportar, jamais o e-mail de outro tenant)."""
    emails = {
        e
        for (e,) in session.query(PessoaIdentificador.external_id).filter_by(
            pessoa_id=pessoa_id, fonte=FONTE_EMAIL
        )
    }
    return next(iter(emails)) if len(emails) == 1 else None


def _linhas_convites(session, pesquisa_id: int) -> List[Dict[str, Any]]:
    """Junta convite + nome + email de cada convidado da pesquisa (ordem estável)."""
    rows = (
        session.query(PesquisaConvite, Pessoa.nome_display)
        .join(Pessoa, Pessoa.id == PesquisaConvite.pessoa_id)
        .filter(PesquisaConvite.pesquisa_id == pesquisa_id)
        .order_by(PesquisaConvite.id)
        .all()
    )
    out = []
    for c, nome in rows:
        out.append(
            {
                "pessoa_id": c.pessoa_id,
                "nome": nome or "",
                "email": _email_da_pessoa(session, c.pessoa_id),  # None = ambíguo (§5.5)
                "token": c.token,
                "respondido_em": c.respondido_em,
            }
        )
    return out


def exportar_convites_xlsx(session, pesquisa, base_url: str) -> io.BytesIO:
    """Planilha do recorte convidado: nome, email, link individualizado. É o que o
    cliente usa para disparar (PDPA não envia). Link = ``<base_url>/p/<token>``."""
    base = base_url.rstrip("/")
    # §7: e-mail ambíguo (None) NUNCA sai como e-mail de outro tenant — vai uma nota
    # acionável no lugar (o arquivo SAI do sistema, então a regra é mais estrita aqui).
    linhas = [
        {
            "nome": r["nome"],
            "email": r["email"] or "— (reimporte os contatos desta empresa)",
            "link": f"{base}/p/{r['token']}",
        }
        for r in _linhas_convites(session, pesquisa.id)
    ]
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame(linhas, columns=["nome", "email", "link"]).to_excel(
            writer, index=False, sheet_name="convites"
        )
    bio.seek(0)
    return bio


def quem_faltou(session, pesquisa_id: int) -> List[Dict[str, Any]]:
    """Convidados que NÃO responderam — anti-join convites × Respondente por
    ``pessoa_id`` naquela pesquisa. Pega quem respondeu por qualquer caminho (link
    antigo por-pesquisa, e-mail digitado), não só pelo link individual."""
    from src.models.respondente import Respondente

    respondidos = {
        pid
        for (pid,) in session.query(Respondente.pessoa_id).filter(
            Respondente.pesquisa_id == pesquisa_id, Respondente.pessoa_id.isnot(None)
        )
    }
    # ``respondido_em`` cobre o caso ANÔNIMO (resposta via convite sem pessoa_id no
    # Respondente); o anti-join cobre respostas por qualquer outro caminho.
    return [
        r
        for r in _linhas_convites(session, pesquisa_id)
        if r["pessoa_id"] not in respondidos and r["respondido_em"] is None
    ]
