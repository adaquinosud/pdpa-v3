"""Desfazer um lote de import (Onda 2) — apaga o que o lote criou e recompõe o
estado derivado, sem deixar o diagnóstico inconsistente.

Regras travadas (Alexandre):
- Verbatim APAGA (mesmo classificado/em tema); o recálculo conserta.
- Pessoa que RESPONDEU nunca apaga — no máximo o vínculo vira ``inativo``. Pessoa que
  ficou VAZIA após a undo (sem Respondente, sem Verbatim, sem vínculo) = lixo do erro,
  apaga (checagem de vazio).
- Atributo do lote REVERTE ao ``valor_anterior`` (ou some se o lote o criou / se a
  Pessoa for apagada).
- Merges de Pessoa NÃO são desfeitos (a absorvida já não existe) — só avisa.

Split de recálculo (aprovado): a parte destrutiva + o barato/quantitativo (desativar
tema órfão + regen de cache + ratios) rodam na hora; o caro/LLM (ações, leituras,
editorial de anomalia) rebuilda na noturna via ``reprocessar_em``. Assim o diagnóstico
nunca fica na inconsistência "verbatim sumiu mas tema-fantasma continua no Mapa".
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import func

from src.models.contato import ContatoAtributo, ContatoEmpresa
from src.models.importacao import ImportacaoLote
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente
from src.models.temas import VerbatimTema
from src.models.verbatim import Verbatim


def resumo_lote(session, lote_id: int) -> Optional[Dict[str, Any]]:
    """Aviso PRÉ-undo: o que o lote criou e o quanto já entrou em diagnóstico
    (classificados/temas) — alimenta a confirmação forte. Read-only."""
    lote = session.get(ImportacaoLote, lote_id)
    if lote is None:
        return None
    out: Dict[str, Any] = {
        "id": lote.id,
        "tipo": lote.tipo,
        "status": lote.status,
        "arquivo_nome": lote.arquivo_nome,
        "criado_em": lote.criado_em,
        "contadores": json.loads(lote.contadores_json) if lote.contadores_json else {},
        "em_diagnostico": False,
    }
    if lote.tipo in ("verbatins", "respostas"):
        vq = session.query(Verbatim).filter_by(import_lote_id=lote.id)
        out["verbatins"] = vq.count()
        out["classificados"] = vq.filter(Verbatim.subpilar.isnot(None)).count()
        base = (
            session.query(func.count(func.distinct(VerbatimTema.tema_id)))
            .join(Verbatim, Verbatim.id == VerbatimTema.verbatim_id)
            .filter(Verbatim.import_lote_id == lote.id)
        )
        out["temas_afetados"] = base.scalar() or 0
        if lote.tipo == "respostas":
            out["respondentes"] = (
                session.query(Respondente).filter_by(import_lote_id=lote.id).count()
            )
        out["em_diagnostico"] = bool(out["classificados"] or out["temas_afetados"])
    else:  # contatos
        out["contatos"] = session.query(ContatoEmpresa).filter_by(import_lote_id=lote.id).count()
        out["atributos"] = session.query(ContatoAtributo).filter_by(import_lote_id=lote.id).count()
    return out


def _pessoa_tem_voz(session, pessoa_id: int) -> bool:
    """Tem manifestação REMANESCENTE (Respondente ou Verbatim) — a voz é dela."""
    if session.query(Respondente.id).filter_by(pessoa_id=pessoa_id).first() is not None:
        return True
    return session.query(Verbatim.id).filter_by(pessoa_id=pessoa_id).first() is not None


def _limpar_pessoas_orfas(session, pessoa_ids: set, resultado: Dict[str, Any]) -> None:
    """Apaga as Pessoas que ficaram VAZIAS (sem Respondente, Verbatim nem vínculo) —
    lixo do erro. Deletar a Pessoa cascateia identificadores e atributos (FK CASCADE)."""
    session.flush()
    apagadas = 0
    for pid in pessoa_ids:
        if pid is None:
            continue
        tem_vinc = session.query(ContatoEmpresa.id).filter_by(pessoa_id=pid).first() is not None
        if tem_vinc or _pessoa_tem_voz(session, pid):
            continue
        session.query(Pessoa).filter_by(id=pid).delete(synchronize_session=False)
        apagadas += 1
    resultado["pessoas_apagadas"] = apagadas


def _reverter_atributos_do_lote(session, lote_id: int, resultado: Dict[str, Any]) -> None:
    """Reverte os atributos escritos pelo lote: ``valor_anterior`` existe → volta;
    o lote criou (anterior NULL) → apaga."""
    rev = ap = 0
    for a in session.query(ContatoAtributo).filter_by(import_lote_id=lote_id).all():
        if a.valor_anterior is not None:
            a.valor_atual = a.valor_anterior
            a.valor_anterior = None
            a.import_lote_id = None
            a.data_mudanca = datetime.utcnow()
            rev += 1
        else:
            session.delete(a)
            ap += 1
    resultado["atributos_revertidos"] = rev
    resultado["atributos_apagados"] = ap


def _desfazer_verbatins(session, lote: ImportacaoLote, resultado: Dict[str, Any]) -> None:
    pessoa_ids = {
        pid
        for (pid,) in session.query(Verbatim.pessoa_id).filter(
            Verbatim.import_lote_id == lote.id, Verbatim.pessoa_id.isnot(None)
        )
    }
    n = (
        session.query(Verbatim)
        .filter(Verbatim.import_lote_id == lote.id)
        .delete(synchronize_session=False)  # CASCADE: embeddings, verbatim_temas, reclassif.
    )
    resultado["verbatins_apagados"] = n
    _limpar_pessoas_orfas(session, pessoa_ids, resultado)


def _desfazer_respostas(session, lote: ImportacaoLote, resultado: Dict[str, Any]) -> None:
    pessoa_ids = {
        pid
        for (pid,) in session.query(Respondente.pessoa_id).filter(
            Respondente.import_lote_id == lote.id, Respondente.pessoa_id.isnot(None)
        )
    }
    # Verbatins (coleta) ANTES dos respondentes; CASCADE leva embeddings/temas.
    nv = (
        session.query(Verbatim)
        .filter(Verbatim.import_lote_id == lote.id)
        .delete(synchronize_session=False)
    )
    nr = (
        session.query(Respondente)
        .filter(Respondente.import_lote_id == lote.id)
        .delete(synchronize_session=False)  # CASCADE: Resposta (confronto)
    )
    resultado["verbatins_apagados"] = nv
    resultado["respondentes_apagados"] = nr
    _limpar_pessoas_orfas(session, pessoa_ids, resultado)


def _desfazer_contatos(session, lote: ImportacaoLote, resultado: Dict[str, Any]) -> None:
    _reverter_atributos_do_lote(session, lote.id, resultado)
    contatos = session.query(ContatoEmpresa).filter_by(import_lote_id=lote.id).all()
    pessoa_ids = {c.pessoa_id for c in contatos}
    apagados = inativados = 0
    for c in contatos:
        if _pessoa_tem_voz(session, c.pessoa_id):
            c.status = "inativo"  # respondeu → no máximo inativa o vínculo
            inativados += 1
        else:
            session.delete(c)  # nunca respondeu → apaga o vínculo (lixo do erro)
            apagados += 1
    resultado["contatos_apagados"] = apagados
    resultado["contatos_inativados"] = inativados
    _limpar_pessoas_orfas(session, pessoa_ids, resultado)


def desfazer_lote(session, lote_id: int) -> Dict[str, Any]:
    """PARTE DESTRUTIVA (na sessão do caller, atômica). Apaga o que o lote criou pelas
    regras travadas, marca o lote ``desfeito`` e agenda o recálculo caro na noturna
    (``reprocessar_em``). O recálculo barato/síncrono roda depois via
    ``recompute_apos_desfazer`` (fora desta transação, pra ver os deletes commitados)."""
    lote = session.get(ImportacaoLote, lote_id)
    if lote is None:
        raise ValueError(f"Lote {lote_id} não existe.")
    if lote.status != "ativo":
        raise ValueError("Este lote já foi desfeito.")

    resultado: Dict[str, Any] = {
        "lote_id": lote.id,
        "tipo": lote.tipo,
        "empresa_id": lote.empresa_id,
    }
    if lote.tipo == "verbatins":
        _desfazer_verbatins(session, lote, resultado)
    elif lote.tipo == "respostas":
        _desfazer_respostas(session, lote, resultado)
    elif lote.tipo == "contatos":
        _desfazer_contatos(session, lote, resultado)

    lote.status = "desfeito"
    lote.desfeito_em = datetime.utcnow()

    # Agenda o rebuild do estado derivado LLM (ações/leituras/editorial) na noturna.
    if lote.tipo in ("verbatins", "respostas"):
        from src.models.empresa import Empresa

        emp = session.get(Empresa, lote.empresa_id)
        if emp is not None:
            emp.reprocessar_em = datetime.utcnow()
    session.flush()
    return resultado


def recompute_apos_desfazer(empresa_id: int) -> None:
    """Recálculo SÍNCRONO barato (sem LLM), chamado pela rota APÓS o commit da parte
    destrutiva — cada função abre a própria sessão e vê os deletes já commitados.
    Fecha o gap (C) do L5/L6: desativa temas que perderam todos os membros + regenera
    o cache total + reconstrói os ratios mensais do histórico."""
    from src.anomalias.ratios import recomputar_ratios_mensais
    from src.temas.limpeza import limpar_acumulo_temas

    limpar_acumulo_temas(empresa_id)  # desativa tema órfão + _regenerar_cache_por_vinculos
    recomputar_ratios_mensais(empresa_id)
