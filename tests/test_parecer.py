"""Parecer Loyall F1 (atos 1-3): montar_dados agrega reuso read-only e degrada
com honestidade; o template renderiza sem quebrar com a forma real dos dados."""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader

from src.models.caso import Caso
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.relatorios.parecer import montar_dados


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
        )
    )
    for i in range(3):  # 3 detratores em Pa1 → concentração 100%
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="reclamação",
                tem_texto=True,
                subpilar="Pa1",
                tipo="detrator",
                hash_dedup=f"h{i}",
            )
        )
    db_session.commit()

    d = montar_dados(e.id)
    assert d["empresa_nome"] == e.nome
    assert d["ato1"]["essencia"]["tem"] is True and d["ato1"]["ia"] is None  # sem sonda
    assert d["ato2"]["ra_tem"] is True and d["ato2"]["ra"].total == 1
    conc = d["ato2"]["concentracao"]
    assert conc and conc[0]["nome"] and conc[0]["det_pct"] == 100
    assert d["ato2"]["gaps"] is None and d["ato2"]["tem_pesquisa"] is False  # sem pesquisa
    assert d["ato3"]["quadro"].tem_dado is True


def test_montar_dados_degrada_sem_dado(db_session):
    e = _empresa(db_session, "vazia")  # sem essência, sem casos, sem verbatins
    db_session.commit()
    d = montar_dados(e.id)
    assert d is not None
    assert d["ato1"]["essencia"]["tem"] is False and d["ato1"]["ia"] is None
    assert d["ato2"]["ra_tem"] is False and d["ato2"]["concentracao"] == []
    assert d["ato2"]["gaps"] is None
    assert d["ato3"]["quadro"].tem_dado is False


def test_montar_dados_empresa_inexistente(db_session):
    assert montar_dados(999999) is None


def test_template_renderiza_com_dados_reais(db_session):
    """O template não quebra com a forma real do montar_dados (guarda contra
    drift entre o dict e o HTML)."""
    e = _empresa(db_session, "tpl", missao="M", valores="V")
    f = _fonte(db_session, e)
    db_session.add(Caso(empresa_id=e.id, fonte_id=f.id, origem_id="T1", desfecho=None))
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            texto="x",
            tem_texto=True,
            subpilar="D2",
            tipo="detrator",
            hash_dedup="ht",
        )
    )
    db_session.commit()
    d = montar_dados(e.id)

    env = Environment(loader=FileSystemLoader("templates"))
    html = env.get_template("relatorios/parecer.html").render(d=d)
    assert "Parecer Loyall" in html and e.nome in html
    assert "Ato 1" in html and "Ato 2" in html and "Ato 3" in html
