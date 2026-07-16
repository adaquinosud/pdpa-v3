"""Seeder de respostas com respondentes IDENTIFICADOS (--pct-identificados).

Prova (a) o plano de identidades (split N%/6-fixos) e (b) que, pelo endpoint real
/p/<token>, o carimbo ?c=<id_cliente> vira Pessoa (pessoa_id) — 80% identificados,
20% anônimos — sem repetir POST (a trava de reenvio dá 1 resposta por pessoa)."""

from __future__ import annotations

import json
import random

from scripts.seed_respostas_pesquisa import _FIXOS_CRUZA, _planeja_identidades

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente


def test_planeja_identidades_split_e_fixos():
    """80% → 16/20 com id_cliente, 4 anônimos; os 6 IDs de cruzamento entram identificados."""
    ids = _planeja_identidades(20, 80, random.Random(1))
    assert len(ids) == 20
    ident = [c for c in ids if c is not None]
    anon = [c for c in ids if c is None]
    assert len(ident) == 16 and len(anon) == 4  # 80/20
    assert set(_FIXOS_CRUZA).issubset(set(ident))  # os 6 fixos, garantidos
    assert len(set(ident)) == 16  # todos distintos (fixos + PESQ-2xx)


def test_planeja_identidades_pct_zero_tudo_anonimo():
    """Default 0 = comportamento original: tudo anônimo, e sem tocar o RNG (stream intacto)."""
    rng = random.Random(7)
    estado = rng.getstate()
    ids = _planeja_identidades(10, 0, rng)
    assert ids == [None] * 10
    assert rng.getstate() == estado  # pct=0 não consumiu o RNG


def test_planeja_identidades_cota_menor_que_6():
    """Cota de identificados < 6 → entram só os primeiros fixos que couberem (sem PESQ-2xx)."""
    ids = _planeja_identidades(10, 30, random.Random(1))  # n_ident = 3
    ident = [c for c in ids if c is not None]
    assert ident and set(ident).issubset(set(_FIXOS_CRUZA))  # só fixos, nenhum PESQ-2xx
    assert len(ident) == 3


def _escala(pontos=5):
    return json.dumps(
        {"tipo": "nota", "pontos": pontos, "rotulos": [str(i) for i in range(1, pontos + 1)]}
    )


def test_endpoint_carimbo_c_gera_pessoa_id(client, db_session):
    """Ponta-a-ponta pelo endpoint real: os planejados com ?c= viram Pessoa (pessoa_id),
    os None ficam anônimos. --pct-identificados 80 sobre n=10 → 8 com pessoa_id, 2 sem."""
    e = Empresa(nome="ESeedIdent")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="externa",
        proposito="coleta",
        titulo="S",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
        token_publico="tok-seed-ident",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Nota?",
        formato="mista",
        subpilar_alvo="P1",
        opcoes_json=_escala(),
    )
    db_session.add(q)
    db_session.commit()

    identidades = _planeja_identidades(10, 80, random.Random(2))  # 8 ident, 2 anon
    for codigo in identidades:
        form = {f"q_{q.id}_nota": "4", f"q_{q.id}_texto": ""}
        if codigo:
            form["c"] = codigo  # carimbo do link (mesmo caminho do seeder)
        r = client.post("/p/tok-seed-ident", data=form)
        assert r.status_code == 200

    resp = db_session.query(Respondente).filter_by(pesquisa_id=p.id).all()
    com = [r for r in resp if r.pessoa_id is not None]
    sem = [r for r in resp if r.pessoa_id is None]
    assert len(com) == 8 and len(sem) == 2  # 80% com pessoa_id, 20% sem
