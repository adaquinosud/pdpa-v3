"""Tests do CP impacto-rs: liga os 2 R$ (estoque + fluxo) sem reescrita.

Determinísticos (sem LLM real). A estimativa IA é mockada via monkeypatch do
``_get_client`` do classifier. Cobre: LTV derivado, taxas por empresa, estoque no
grão (loja,subpilar) com cobertura parcial, fluxo em simular_impacto_acao, parse +
fallback da IA, hierarquia de pré-preenchimento, fiação de cadastro (API/serialize).
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from src.governanca.impacto_rs import (
    estimar_ltv_agrupamento,
    formatar_brl,
    formatar_estoque,
    ltv_loja,
    prefill_ltv,
    rs_estoque,
    taxas_empresa,
)
from src.governanca.metricas import simular_impacto_acao
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.verbatim import Verbatim


# ── Helpers ──────────────────────────────────────────────────────────────
def _empresa(db_session, **kw):
    ts = datetime.utcnow().timestamp()
    e = Empresa(nome=kw.pop("nome", f"EImp-{ts}"), setor="aeroporto", **kw)
    db_session.add(e)
    db_session.commit()
    return e


def _local(db_session, e, ag=None, **kw):
    loc = Local(
        empresa_id=e.id, nome=kw.pop("nome", "Loja"), agrupamento_id=(ag.id if ag else None), **kw
    )
    db_session.add(loc)
    db_session.commit()
    return loc


def _fonte(db_session, e, loc):
    ts = datetime.utcnow().timestamp()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="local",
        entidade_id=loc.id,
        conector_tipo="google",
        url=f"ChIJ_{loc.id}_{ts}",
        ativo=True,
    )
    db_session.add(f)
    db_session.commit()
    return f


def _conv(db_session, e, loc, f, sub, n, tipo="conversivel"):
    ts = datetime.utcnow().timestamp()
    for i in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                local_id=loc.id,
                texto=f"{tipo}-{sub}-{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                data_criacao_original=datetime(2026, 5, 1),
                hash_dedup=f"h{loc.id}{sub}{tipo}{i}-{ts}",
            )
        )
    db_session.commit()


# ── LTV derivado ─────────────────────────────────────────────────────────
def test_ltv_loja_deriva_e_falta_vira_none():
    assert ltv_loja(SimpleNamespace(ticket_medio=50.0, frequencia=12.0)) == 600.0
    assert ltv_loja(SimpleNamespace(ticket_medio=50.0, frequencia=None)) is None
    assert ltv_loja(SimpleNamespace(ticket_medio=None, frequencia=12.0)) is None
    assert ltv_loja(SimpleNamespace(ticket_medio=0, frequencia=12.0)) is None  # não-positivo


# ── Taxas por empresa ────────────────────────────────────────────────────
def test_taxas_empresa_le_da_empresa_e_cai_no_default():
    assert taxas_empresa(SimpleNamespace(taxa_alto=0.7, taxa_medio=0.4, taxa_baixo=0.1)) == {
        "alto": 0.7,
        "medio": 0.4,
        "baixo": 0.1,
    }
    # atributos ausentes/None → fallback na constante
    d = taxas_empresa(SimpleNamespace(taxa_alto=None, taxa_medio=None, taxa_baixo=None))
    assert d == {"alto": 0.50, "medio": 0.35, "baixo": 0.20}


# ── Estoque no grão (loja, subpilar) + cobertura parcial ─────────────────
def test_rs_estoque_grao_loja_e_cobertura_parcial(client_loyall, db_session):
    e = _empresa(db_session)
    ag = Agrupamento(empresa_id=e.id, nome="Cafeteria")
    db_session.add(ag)
    db_session.commit()
    lA = _local(db_session, e, ag, nome="A", ticket_medio=50.0, frequencia=10.0)  # LTV 500
    lB = _local(db_session, e, ag, nome="B")  # sem LTV
    fA, fB = _fonte(db_session, e, lA), _fonte(db_session, e, lB)
    _conv(db_session, e, lA, fA, "D2", 3)  # 3 conv × 500 = 1500
    _conv(db_session, e, lB, fB, "D2", 4)  # sem LTV → não soma, mas conta na cobertura

    est = rs_estoque(db_session, e.id)
    assert est["D2"]["valor"] == 1500.0  # só a loja com LTV
    assert est["D2"]["n_ltv"] == 1 and est["D2"]["n_total"] == 2  # cobertura parcial


def test_rs_estoque_nenhuma_loja_com_ltv_vira_none(client_loyall, db_session):
    e = _empresa(db_session)
    loc = _local(db_session, e, nome="X")  # sem LTV
    f = _fonte(db_session, e, loc)
    _conv(db_session, e, loc, f, "P1", 2)
    est = rs_estoque(db_session, e.id)
    assert est["P1"]["valor"] is None  # → "—" honesto
    assert est["P1"]["n_ltv"] == 0 and est["P1"]["n_total"] == 1


# ── Formatação ───────────────────────────────────────────────────────────
def test_formatacao_brl_e_estoque():
    assert formatar_brl(1_234_567) == "R$ 1,2 mi"
    assert formatar_brl(12_000) == "R$ 12 mil"
    assert formatar_brl(850) == "R$ 850"
    assert formatar_brl(None) is None
    assert formatar_estoque({"valor": 1_200_000.0, "n_ltv": 3, "n_total": 5}) == (
        "R$ 1,2 mi · 3 de 5 lojas c/ LTV"
    )
    assert formatar_estoque({"valor": 800.0, "n_ltv": 2, "n_total": 2}) == "R$ 800"  # cheia
    assert formatar_estoque({"valor": None, "n_ltv": 0, "n_total": 1}) is None


# ── Fluxo no simular_impacto_acao ────────────────────────────────────────
def test_simular_impacto_acao_fluxo_rs():
    agg = {"D2": {"prom": 2, "conv": 1, "det": 10, "total": 13, "ratio": 0.2}}
    # taxa alto = 0.5 → recuperados = round(10×0.5) = 5; LTV 600 → R$ 3000
    out = simular_impacto_acao(agg, "D2", "alto", taxas={"alto": 0.5}, ltv=600.0)
    assert out["recuperados"] == 5
    assert out["rs_fluxo"] == 3000
    assert out["rs_fluxo_fmt"] == "R$ 3 mil"
    # sem LTV → rs_fluxo None ("—")
    out2 = simular_impacto_acao(agg, "D2", "alto", taxas={"alto": 0.5}, ltv=None)
    assert out2["rs_fluxo"] is None and out2["rs_fluxo_fmt"] is None


# ── Estimativa IA: parse + fallback ──────────────────────────────────────
class _FakeResp:
    def __init__(self, text):
        self.content = [SimpleNamespace(type="text", text=text)]
        self.usage = SimpleNamespace(input_tokens=10, output_tokens=10)


def _fake_client(text=None, raise_exc=False):
    class _C:
        @property
        def messages(self):
            return self

        def create(self, **kw):
            if raise_exc:
                raise RuntimeError("boom")
            return _FakeResp(text)

    return _C()


def test_estimar_ltv_parse_ok(monkeypatch):
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client",
        lambda: _fake_client('{"ticket_medio": 45.0, "frequencia": 8}'),
    )
    r = estimar_ltv_agrupamento("Cafeteria")
    assert r == {"ticket_medio": 45.0, "frequencia": 8.0}


def test_estimar_ltv_fallback_nao_injeta_numero(monkeypatch):
    # falha de rede/cliente → None (não injeta número sem origem)
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client", lambda: _fake_client(raise_exc=True)
    )
    assert estimar_ltv_agrupamento("Cafeteria") is None
    # JSON sem os campos → None
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client", lambda: _fake_client('{"foo": 1}')
    )
    assert estimar_ltv_agrupamento("Cafeteria") is None
    # valor não-positivo → None
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client",
        lambda: _fake_client('{"ticket_medio": 0, "frequencia": 8}'),
    )
    assert estimar_ltv_agrupamento("Cafeteria") is None
    # categoria vazia → nem chama
    assert estimar_ltv_agrupamento("") is None


# ── Hierarquia de pré-preenchimento ──────────────────────────────────────
def test_prefill_hierarquia_proprio_agrupamento_ia(client_loyall, db_session, monkeypatch):
    e = _empresa(db_session)
    ag = Agrupamento(empresa_id=e.id, nome="Cafeteria")
    db_session.add(ag)
    db_session.commit()

    # (i) próprio
    proprio = _local(db_session, e, ag, nome="Própria", ticket_medio=30.0, frequencia=6.0)
    r = prefill_ltv(db_session, proprio)
    assert r["origem"] == "proprio" and r["ticket_medio"] == 30.0

    # (ii) herda da última loja do mesmo agrupamento (irmã tem LTV)
    nova = _local(db_session, e, ag, nome="Nova")
    r = prefill_ltv(db_session, nova, usar_ia=False)
    assert r["origem"] == "agrupamento" and r["ticket_medio"] == 30.0

    # (iii) IA quando não há irmã com LTV (agrupamento novo)
    ag2 = Agrupamento(empresa_id=e.id, nome="Livraria")
    db_session.add(ag2)
    db_session.commit()
    sozinha = _local(db_session, e, ag2, nome="Sozinha")
    monkeypatch.setattr(
        "src.governanca.impacto_rs.estimar_ltv_agrupamento",
        lambda nome, **kw: {"ticket_medio": 70.0, "frequencia": 4.0},
    )
    r = prefill_ltv(db_session, sozinha, usar_ia=True)
    assert r["origem"] == "ia" and r["ticket_medio"] == 70.0


def test_prefill_sem_agrupamento_e_sem_ia_vira_none(client_loyall, db_session):
    e = _empresa(db_session)
    loc = _local(db_session, e, nome="Avulsa")  # sem agrupamento
    assert prefill_ltv(db_session, loc, usar_ia=False) is None  # → manual/"—"


# ── Fiação de cadastro (API + serialize) ─────────────────────────────────
def test_local_put_seta_ltv_e_marca_origem_proprio(client_loyall, db_session):
    e = _empresa(db_session)
    loc = _local(db_session, e, nome="Edit")
    r = client_loyall.put(
        f"/api/locais/{loc.id}", json={"nome": "Edit", "ticket_medio": 40, "frequencia": 9}
    )
    assert r.status_code == 200
    j = r.get_json()
    assert j["ticket_medio"] == 40 and j["frequencia"] == 9
    assert j["ltv"] == 360 and j["ltv_origem"] == "proprio"  # edição manual = próprio


def test_empresa_put_seta_taxas(client_loyall, db_session):
    e = _empresa(db_session)
    r = client_loyall.put(
        f"/api/empresas/{e.id}",
        json={"nome": e.nome, "taxa_alto": 0.6, "taxa_medio": 0.4, "taxa_baixo": 0.15},
    )
    assert r.status_code == 200
    j = r.get_json()
    assert (j["taxa_alto"], j["taxa_medio"], j["taxa_baixo"]) == (0.6, 0.4, 0.15)


def test_empresa_default_taxas_sugeridas(client_loyall, db_session):
    e = _empresa(db_session)
    db_session.refresh(e)
    assert (e.taxa_alto, e.taxa_medio, e.taxa_baixo) == (0.50, 0.35, 0.20)


def test_ltv_sugestao_endpoint(client_loyall, db_session, monkeypatch):
    e = _empresa(db_session)
    ag = Agrupamento(empresa_id=e.id, nome="Cafeteria")
    db_session.add(ag)
    db_session.commit()
    _local(db_session, e, ag, nome="Irmã", ticket_medio=25.0, frequencia=5.0)
    nova = _local(db_session, e, ag, nome="Nova")
    r = client_loyall.get(f"/api/locais/{nova.id}/ltv-sugestao?ia=0")
    assert r.status_code == 200
    j = r.get_json()
    assert j["origem"] == "agrupamento" and j["ticket_medio"] == 25.0
