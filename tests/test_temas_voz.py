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


# ── retoque 1: citação on-label + preferir português ──

from src.relatorios.parecer import (  # noqa: E402
    _casa_label,
    _parece_espanhol,
    _tokens_label,
)


def test_parece_espanhol():
    assert _parece_espanhol("quiero saber cuando resuelven esto") is True
    assert _parece_espanhol("quero saber quando resolvem isso") is False


def test_casa_label_raiz():
    tokens = _tokens_label("cobrança adicional")
    assert _casa_label("fui cobrado a mais sem aviso", tokens) is True  # cobra*
    assert _casa_label("atendimento excelente, nota dez", tokens) is False


def test_temas_voz_prefere_onlabel_pt(db_session):
    """[0] espanhol, [1] PT off-label, [2] PT on-label → escolhe o on-label PT."""
    e = _emp(db_session)
    v_es = _vb(db_session, e, "quiero saber cuando resuelven el error de registro")
    v_off = _vb(db_session, e, "atendimento excelente, tudo perfeito, obrigado")
    v_on = _vb(db_session, e, "fui cobrado a mais e ninguém estorna o valor")
    _cache(db_session, e, "Pa2", "detrator", "cobrança adicional", 40, [v_es.id, v_off.id, v_on.id])
    db_session.commit()

    cit = _temas_voz(db_session, e.id)["detrator"][0]["citacao"]
    assert "cobrado" in cit and "quiero" not in cit and "excelente" not in cit


def test_temas_voz_fallback_quando_nenhum_casa(db_session):
    """Nenhum exemplo casa o label → fallback pro 1º (o mais central)."""
    e = _emp(db_session)
    v0 = _vb(db_session, e, "coisa genérica sem relação alguma aqui")
    v1 = _vb(db_session, e, "outra frase qualquer distante do tema")
    _cache(db_session, e, "Pa2", "detrator", "reembolso travado", 10, [v0.id, v1.id])
    db_session.commit()

    cit = _temas_voz(db_session, e.id)["detrator"][0]["citacao"]
    assert cit == "coisa genérica sem relação alguma aqui"
