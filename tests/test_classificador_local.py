"""Tests do CP local-no-prompt: o classificador passa a receber o LOCAL, pra não
descartar reviews de loja-tenant como sem_lastro em empresa multi-tenant.

Determinísticos (sem LLM): fiação do prompt + propagação + seleção do comando.
Golden (marca `golden`, consome crédito): comportamento real do LLM."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.classifier.classifier_v3 import _build_user_prompt, classificar
from src.models.verbatim import Verbatim
from src.temas.pos_coleta import classificar_pendentes


# ── Fiação do prompt (puro, sem LLM) ─────────────────────────────────────
def test_prompt_inclui_local_e_instrucao_tenant():
    p = _build_user_prompt(
        "Preço justo e atendimento ótimo",
        empresa_nome="BH Airport",
        empresa_setor="aeroporto",
        local_nome="Unidas Aluguel de Carros",
    )
    assert "Local: Unidas Aluguel de Carros" in p
    assert "DENTRO de BH Airport" in p
    assert "SÃO parte dela" in p  # instrução: loja-tenant é parte da empresa
    # salvaguarda anti-inversão presente
    assert "NÃO obriga ancoragem" in p


def test_prompt_sem_local_compat():
    p = _build_user_prompt("x", empresa_nome="BH Airport", empresa_setor="aeroporto")
    assert "Local:" not in p  # sem local → sem a linha (compat v3.0)


# ── Propagação do local no pós-coleta ────────────────────────────────────
def _ctx(client_loyall, sfx):
    e = client_loyall.post(
        "/api/empresas/", json={"nome": f"ELoc-{sfx}", "setor": "aeroporto"}
    ).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais",
        json={"nome": "Unidas Aluguel de Carros", "agrupamento_id": a["id"]},
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": f"ChIJ_{sfx}"}
    ).get_json()
    return e, a, loc, f


def _verb(db_session, e, f, loc, **kw):
    v = Verbatim(
        empresa_id=e["id"],
        fonte_id=f["id"],
        local_id=loc["id"],
        tem_texto=True,
        data_criacao_original=datetime(2026, 5, 1),
        hash_dedup=f"h{kw.get('texto','')[:8]}-{datetime.utcnow().timestamp()}",
        **kw,
    )
    db_session.add(v)
    db_session.commit()
    return v


def test_classificar_pendentes_propaga_local(client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "prop")
    _verb(db_session, e, f, loc, texto="A Unidas tem preço justo", subpilar=None)
    captured = {}

    def fake(**kw):
        captured.update(kw)
        return SimpleNamespace(
            subpilar="P1", tipo="promotor", confianca=0.8, justificativa="ok", prompt_versao="v3.2"
        )

    monkeypatch.setattr("src.classifier.classifier_v3.classificar", fake)
    classificar_pendentes(e["id"])
    assert captured.get("local_nome") == "Unidas Aluguel de Carros"  # local chegou no classificar


# ── Seleção do comando reclassificar-tenant-rejection ────────────────────
def test_comando_mira_so_loja_fisica(app, client_loyall, db_session, monkeypatch):
    e, a, loc, f = _ctx(client_loyall, "cmd")
    # A) tenant-rejection COM rating → alvo
    vA = _verb(
        db_session,
        e,
        f,
        loc,
        texto="Preço justo, atendimento especial e carro novinho",
        subpilar="sem_lastro",
        tipo="inativo",
        confianca=0.95,
        prompt_versao="v3.0",
        rating=5,
        justificativa="Verbatim refere-se a locadora (Unidas), não ao aeroporto BH Airport.",
    )
    # B) vago-genérico (sem 'refere-se a') → NÃO mexer
    vB = _verb(
        db_session,
        e,
        f,
        loc,
        texto="Bom",
        subpilar="sem_lastro",
        tipo="inativo",
        confianca=0.95,
        prompt_versao="v3.0",
        rating=5,
        justificativa="Texto vago sem ancoragem identificável à experiência do aeroporto.",
    )
    # C) social tenant-rejection SEM rating → listar, não mexer
    vC = _verb(
        db_session,
        e,
        f,
        loc,
        texto="Parabéns equipe",
        subpilar="sem_lastro",
        tipo="inativo",
        confianca=0.95,
        prompt_versao="v3.0",
        rating=None,
        justificativa="Refere-se a comentário social, não ao aeroporto BH Airport.",
    )

    monkeypatch.setattr(
        "src.classifier.classifier_v3.classificar",
        lambda **kw: SimpleNamespace(
            subpilar="P1",
            tipo="promotor",
            confianca=0.85,
            justificativa="ancorado",
            prompt_versao="v3.2",
        ),
    )
    res = app.test_cli_runner().invoke(
        args=["reclassificar-tenant-rejection", "--empresa", str(e["id"])]
    )
    assert res.exit_code == 0, res.output
    assert "alvos (c/rating)=1" in res.output
    assert "reancorados=1" in res.output
    assert f"v{vC.id}" in res.output and "SOCIAL não reprocessado" in res.output  # C listado

    db_session.expire_all()
    get = (
        lambda vid: db_session.query(Verbatim.subpilar, Verbatim.prompt_versao)
        .filter(Verbatim.id == vid)
        .first()
    )
    assert get(vA.id) == ("P1", "v3.2")  # A reancorado
    assert get(vB.id) == ("sem_lastro", "v3.0")  # B intacto (vago-genérico)
    assert get(vC.id) == ("sem_lastro", "v3.0")  # C intacto (social)


# ── Golden (LLM real — roda com `pytest -m golden`) ──────────────────────
@pytest.mark.golden
def test_golden_tenant_ancora_em_pilar():
    r = classificar(
        "Preço justo, atendimento especial e carro novinho.",
        empresa_nome="BH Airport",
        empresa_setor="aeroporto",
        local_nome="Unidas Aluguel de Carros",
    )
    assert r.subpilar != "sem_lastro"  # com o local, ancora num pilar (não descarta)


@pytest.mark.golden
def test_golden_fora_de_lugar_mantem_sem_lastro():
    r = classificar(
        "A velocidade de cruzeiro do avião durante o voo foi impressionante.",
        empresa_nome="BH Airport",
        empresa_setor="aeroporto",
        local_nome="Unidas Aluguel de Carros",
    )
    assert r.subpilar == "sem_lastro"  # local válido NÃO obriga ancoragem (não inverteu)
