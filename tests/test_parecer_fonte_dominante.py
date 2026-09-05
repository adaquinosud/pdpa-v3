"""O Parecer para de contar a mesma fonte duas vezes (+ dek, virg, população).

Medido na BEXP: dos 35 detratores de Mutualidade, **26 são do ReclameAqui** — e o
RA é 56 de 1.006 verbatins da empresa (5,6% da base). A tese apresentava o RA e
"todas as fontes" como duas leituras que se confirmam; **a segunda é 74% a
primeira**, e o agregado não confirma nada — ele CONTÉM a primeira.
"""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.relatorios.parecer import (
    _facts_sintese,
    _ferida_por_fonte,
    leituras_independentes,
    montar_dados,
)
from src.utils.fmt import virg

_ENV = Environment(loader=FileSystemLoader("templates"))
_ENV.filters["virg"] = virg


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa_com(db_session, sfx, dados):
    """dados = [(conector, tipo, n)] no subpilar Pa2."""
    e = Empresa(nome=f"EFD-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    for conector, tipo, n in dados:
        f = Fonte(
            empresa_id=e.id,
            entidade_tipo="empresa",
            entidade_id=e.id,
            conector_tipo=conector,
            url=f"u-{conector}",
            ativo=True,
            status="ativa",
        )
        db_session.add(f)
        db_session.flush()
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e.id,
                    fonte_id=f.id,
                    subpilar="Pa2",
                    tipo=tipo,
                    texto=f"t{i}",
                    tem_texto=True,
                )
            )
    db_session.commit()
    return e


# ── 1 · a quebra por fonte ─────────────────────────────────────────────────────


def test_decompoe_a_ferida_por_fonte(db_session):
    """O caso da BEXP em miniatura: 26 de 35 detratores num só lugar."""
    e = _empresa_com(
        db_session,
        "bexp",
        [("reclame_aqui", "detrator", 26), ("google", "detrator", 9), ("google", "promotor", 2)],
    )
    r = _ferida_por_fonte(db_session, e.id, "Pa2")
    assert r["det"] == 35 and r["prom"] == 2
    assert r["dominante"] == "reclame_aqui"
    assert r["dominante_det"] == 26
    assert r["dominante_pct"] == 74
    assert r["det_sem_dominante"] == 9
    assert r["prom_sem_dominante"] == 2


def test_sem_detrator_devolve_None(db_session):
    e = _empresa_com(db_session, "sodet", [("google", "promotor", 3)])
    assert _ferida_por_fonte(db_session, e.id, "Pa2") is None
    assert _ferida_por_fonte(db_session, e.id, None) is None


def test_a_quebra_CHEGA_aos_facts(db_session):
    """⚠️ Sem isto o LLM não tem como saber que está contando duas vezes."""
    e = _empresa_com(
        db_session,
        "facts",
        [("reclame_aqui", "detrator", 26), ("google", "detrator", 9)],
    )
    f = _facts_sintese(montar_dados(e.id))
    assert f["ferida_por_fonte"]["dominante_pct"] == 74
    assert f["ferida_por_fonte"]["det_sem_dominante"] == 9


# ── 3 · a dek conta INSTRUMENTOS, não linhas ───────────────────────────────────


def test_dek_conta_instrumentos_nao_linhas(db_session):
    """⚠️ Voz pública e conduta saem AMBAS do RA — contam UMA vez."""
    e = _empresa_com(
        db_session,
        "dek",
        [("reclame_aqui", "detrator", 26), ("google", "detrator", 9)],
    )
    d = montar_dados(e.id)
    lt = leituras_independentes(d)
    assert "ReclameAqui" in lt
    assert lt.count("ReclameAqui") == 1, "voz + conduta não contam duas vezes"
    assert "sondagem de IA" not in lt, "sem sonda não entra na conta"
    html = _render(d)
    assert "Quatro leituras independentes" not in html
    assert f"{len(lt)} leituras independentes" in html or "A leitura" in html


def test_dek_com_uma_leitura_nao_promete_convergencia(db_session):
    e = _empresa_com(db_session, "uma", [("reclame_aqui", "detrator", 5)])
    d = montar_dados(e.id)
    html = _render(d)
    assert "leituras independentes" not in html
    assert "A leitura disponível" in html


# ── 5a · virg no impresso ──────────────────────────────────────────────────────


def test_decimais_do_impresso_saem_com_VIRGULA(db_session):
    """⚠️ `virg` estava em 5 impressos e ZERO vezes no Parecer — a peça inteira
    ficou fora da varredura da §4.57. São QUATRO decimais, não um."""
    e = _empresa_com(
        db_session,
        "virg",
        [("reclame_aqui", "detrator", 4), ("google", "promotor", 8)],
    )
    d = montar_dados(e.id)
    d["ato2a"]["nota_media"] = 7.0
    d["ato2b"]["concentracao"]["ratio"] = 0.5
    html = _render(d)
    assert "7,0/10" in html
    assert "7.0/10" not in html
    assert "ratio 0,50" in html


# ── 5c · a população ───────────────────────────────────────────────────────────


def test_populacao_dos_45_por_cento_e_INSATISFEITOS(db_session):
    """Trocar a população infla — e com fonte citada ao lado, infla com lastro."""
    e = _empresa_com(db_session, "pop", [("reclame_aqui", "detrator", 3)])
    d = montar_dados(e.id)
    d["tem_sonda"] = True
    html = _render(d)
    assert "45% dos consumidores insatisfeitos" in html
    assert "45% já pedem" not in html
    f = _facts_sintese(d)
    assert f["consultam_ia_populacao"] == "dos consumidores insatisfeitos"
