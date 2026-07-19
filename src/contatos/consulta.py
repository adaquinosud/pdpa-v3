"""Leituras da base de contatos para a UI (listagem + chaves de segmentação)."""

from __future__ import annotations

from typing import Any, Dict, List

from src.coletor.excel import FONTE_CRM, FONTE_EMAIL
from src.models.contato import ContatoAtributo, ContatoEmpresa
from src.models.local import Local
from src.models.pessoa import Pessoa, PessoaIdentificador


def _identificadores(session, pessoa_ids: List[int]) -> Dict[int, Dict[str, str]]:
    """{pessoa_id: {'email':…, 'id_cliente':…}} — 1ª chave de cada fonte por pessoa."""
    out: Dict[int, Dict[str, str]] = {}
    if not pessoa_ids:
        return out
    rows = (
        session.query(PessoaIdentificador)
        .filter(PessoaIdentificador.pessoa_id.in_(pessoa_ids))
        .all()
    )
    for i in rows:
        d = out.setdefault(i.pessoa_id, {})
        if i.fonte == FONTE_EMAIL and "email" not in d:
            d["email"] = i.external_id
        elif i.fonte == FONTE_CRM and "id_cliente" not in d:
            d["id_cliente"] = i.external_id
    return out


def listar_contatos(
    session, empresa_id: int, *, incluir_inativos: bool = True
) -> List[Dict[str, Any]]:
    """Contatos da empresa com nome, email, id_cliente, unidade, status e atributos."""
    q = (
        session.query(ContatoEmpresa, Pessoa.nome_display, Local.nome)
        .join(Pessoa, Pessoa.id == ContatoEmpresa.pessoa_id)
        .outerjoin(Local, Local.id == ContatoEmpresa.local_id)
        .filter(ContatoEmpresa.empresa_id == empresa_id)
        .order_by(Pessoa.nome_display, ContatoEmpresa.id)
    )
    if not incluir_inativos:
        q = q.filter(ContatoEmpresa.status == "ativo")
    rows = q.all()
    pessoa_ids = [c.pessoa_id for c, _, _ in rows]
    idents = _identificadores(session, pessoa_ids)

    attrs: Dict[int, Dict[str, str]] = {}
    if pessoa_ids:
        for a in (
            session.query(ContatoAtributo)
            .filter(
                ContatoAtributo.empresa_id == empresa_id,
                ContatoAtributo.pessoa_id.in_(pessoa_ids),
            )
            .all()
        ):
            attrs.setdefault(a.pessoa_id, {})[a.chave] = a.valor_atual or ""

    out = []
    for c, nome, unidade in rows:
        d = idents.get(c.pessoa_id, {})
        out.append(
            {
                "pessoa_id": c.pessoa_id,
                "nome": nome or "",
                "email": d.get("email", ""),
                "id_cliente": d.get("id_cliente", ""),
                "unidade": unidade or "",
                "status": c.status,
                "atributos": attrs.get(c.pessoa_id, {}),
            }
        )
    return out


def chaves_de_atributo(session, empresa_id: int) -> List[str]:
    """Chaves distintas de atributo da empresa — alimenta o filtro de segmentação."""
    rows = (
        session.query(ContatoAtributo.chave)
        .filter(ContatoAtributo.empresa_id == empresa_id)
        .distinct()
        .order_by(ContatoAtributo.chave)
        .all()
    )
    return [c for (c,) in rows]
