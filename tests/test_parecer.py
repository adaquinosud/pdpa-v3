"""Parecer Loyall (forma editorial P1-P7 + P9): montar_dados agrega reuso das
funções vivas + melhor-esforço nos campos editoriais, degrada sem quebrar, e o
template renderiza com a forma real (completo E degradado)."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.relatorios.parecer import montar_dados

_ENV = Environment(loader=FileSystemLoader("templates"))


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa(db_session, sfx, **kw):
    e = Empresa(nome=f"EP-{sfx}-{id(db_session)}", **kw)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


def test_montar_dados_completo(db_session):
    e = _empresa(db_session, "full", missao="Servir bem", visao="Ser referência", valores="Cuidado")
    f = _fonte(db_session, e)
    db_session.add(
        Caso(
            empresa_id=e.id,
            fonte_id=f.id,
            origem_id="C1",
            desfecho="resolvido",
            evaluated=True,
            score=8,
            interactions_count=2,
        )
    )
    for i in range(3):  # 3 detratores RA em Pa1 → é a "ferida"
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="atendimento péssimo, cobraram valor errado e não resolveram nada",
                tem_texto=True,
                subpilar="Pa1",
                tipo="detrator",
                hash_dedup=f"h{i}",
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["empresa_nome"] == e.nome and "Capital Relacional" in d["subtitulo"]
    # tese: a ferida é um subpilar real (não o fallback), com voz RA
    assert d["tese"]["subpilar_nome"] != "Relação"
    assert d["tese"]["voz"]["total"] == 3 and d["tese"]["voz"]["pct"] == 100
    assert d["tese"]["voz"]["detratores"] == 3
    assert isinstance(d["tese"]["conduta"]["resolve"], int)
    # ato2a: funil + desfechos + citações (melhor-esforço)
    assert d["ato2a"]["funil"]["responde"] == 100
    assert d["ato2a"]["desfechos"] and d["ato2a"]["desfechos"][0]["n"] == 1
    assert len(d["ato2a"]["citacoes"]) >= 1  # verbatim detrator vira citação
    # ato3: quadro com sinal
    assert d["ato3"]["topo"]["subpilares"] or d["ato3"]["base"]["subpilares"]
    assert "A tese" in _render(d) and e.nome in _render(d)


def test_montar_dados_degrada_sem_dado(db_session):
    e = _empresa(db_session, "vazia")  # nada
    db_session.commit()
    d = montar_dados(e.id)
    assert d is not None
    assert d["tese"]["subpilar_nome"] == "Relação"  # fallback
    assert d["tese"]["voz"]["total"] == 0 and d["tese"]["voz"]["ratio"] == "—"
    assert d["ato2b"]["gap"] is None and d["ato2b"]["corrente"] == []
    assert d["ato2c"]["encaminhamentos"] == []
    # degradação NÃO pode quebrar o template
    html = _render(d)
    assert "Parecer Loyall" in html and "A tese" in html


def test_montar_dados_empresa_inexistente(db_session):
    assert montar_dados(999999) is None
