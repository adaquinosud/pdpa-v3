"""Seção "A voz, em detalhe": _temas_voz agrega TemaCache por valência (top-N,
cross-subpilar) e traz citação representativa MASCARADA."""

from __future__ import annotations

import json
from datetime import date

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim
from src.relatorios.parecer import _temas_voz


def _emp(db_session):
    e = Empresa(nome=f"EVoz-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="ChIJ_voz",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    e._fonte_id = f.id
    return e


def _vb(db_session, e, texto):
    v = Verbatim(
        empresa_id=e.id,
        fonte_id=e._fonte_id,
        texto=texto,
        tem_texto=True,
        subpilar="Pa2",
        tipo="detrator",
        hash_dedup=f"voz-{id(texto)}-{texto[:8]}",
    )
    db_session.add(v)
    db_session.flush()
    return v


def _cache(db_session, e, sub, tipo, label, vol, exemplos, ag=None):
    db_session.add(
        TemaCache(
            empresa_id=e.id,
            agrupamento_id=ag,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=vol,
            percentual=10.0,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 30),
            exemplos_verbatim_ids=json.dumps(exemplos),
            hash_escopo=f"h-{ag}-{sub}-{tipo}-{label}",
        )
    )


def test_temas_voz_agrega_ordena_e_mascara(db_session):
    e = _emp(db_session)
    # citação com PII embutida → deve sair mascarada
    v_pii = _vb(db_session, e, "cobrança indevida no cartão 1234 5678 9012 3456 e ninguém resolve")
    v_lisa = _vb(db_session, e, "demora absurda no reembolso, semanas de espera sem retorno")
    v_prom = _vb(db_session, e, "atendente resolveu na hora, muito atenciosa")

    # "reembolso" aparece em DOIS subpilares → agrega cross-subpilar (5+4=9)
    _cache(db_session, e, "Pa2", "detrator", "reembolso travado", 5, [v_lisa.id])
    _cache(db_session, e, "D2", "detrator", "reembolso travado", 4, [v_lisa.id])
    _cache(db_session, e, "Pa2", "detrator", "cobrança indevida", 7, [v_pii.id])
    _cache(db_session, e, "Pa1", "promotor", "atendimento resolutivo", 3, [v_prom.id])
    db_session.commit()

    out = _temas_voz(db_session, e.id)

    # detrator: top por volume somado → cobrança(7) > reembolso(9)? 9>7, então reembolso 1º
    nomes_det = [t["nome"] for t in out["detrator"]]
    vols_det = {t["nome"]: t["volume"] for t in out["detrator"]}
    assert (
        nomes_det[0] == "reembolso travado" and vols_det["reembolso travado"] == 9
    )  # cross-subpilar
    assert vols_det["cobrança indevida"] == 7
    assert out["detrator"][0]["volume"] >= out["detrator"][1]["volume"]  # ordenado desc

    # citação da "cobrança indevida" vem do verbatim com PII → MASCARADA
    cit = next(t["citacao"] for t in out["detrator"] if t["nome"] == "cobrança indevida")
    assert "1234 5678 9012 3456" not in cit and "[cartão]" in cit
    assert "cobrança indevida" in cit  # conteúdo da queixa preservado

    # promotor separado
    assert [t["nome"] for t in out["promotor"]] == ["atendimento resolutivo"]


def test_temas_voz_agrega_cross_grao(db_session):
    """Bug real: promotores viviam só em grãos de agrupamento (não IS NULL). O
    _temas_voz deve agregar cross-grão — e como os grãos são DISJUNTOS (cada
    verbatim num só), somar não duplica."""
    from src.models.agrupamento import Agrupamento

    e = _emp(db_session)
    ags = []
    for nome in ("Loja A", "Loja B", "Loja C"):
        a = Agrupamento(empresa_id=e.id, nome=nome)
        db_session.add(a)
        db_session.flush()
        ags.append(a.id)
    v_prom = _vb(db_session, e, "atendimento personalizado impecável, me senti cuidado")
    v_det = _vb(db_session, e, "cobrança errada de novo, ninguém corrige")

    # promotor SÓ em grãos de agrupamento — nenhuma linha IS NULL
    _cache(
        db_session, e, "Pa1", "promotor", "atendimento personalizado", 200, [v_prom.id], ag=ags[0]
    )
    _cache(
        db_session, e, "Pa1", "promotor", "atendimento personalizado", 134, [v_prom.id], ag=ags[1]
    )
    # detrator dividido entre grão NULL (RA) e grão de loja — soma disjunta
    _cache(db_session, e, "Pa2", "detrator", "cobrança errada", 30, [v_det.id], ag=None)
    _cache(db_session, e, "D2", "detrator", "cobrança errada", 12, [v_det.id], ag=ags[2])
    db_session.commit()

    out = _temas_voz(db_session, e.id)

    # promotor APARECE (antes saía vazio) e soma os grãos de agrupamento: 200+134=334
    assert out["promotor"] and out["promotor"][0]["nome"] == "atendimento personalizado"
    assert out["promotor"][0]["volume"] == 334
    # detrator soma cross-grão sem duplicar: 30+12=42
    assert out["detrator"][0]["nome"] == "cobrança errada"
    assert out["detrator"][0]["volume"] == 42


def test_temas_voz_vazio_degrada(db_session):
    e = _emp(db_session)
    db_session.commit()
    out = _temas_voz(db_session, e.id)
    assert out == {"detrator": [], "promotor": []}
