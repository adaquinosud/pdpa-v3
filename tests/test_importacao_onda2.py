"""Onda 2 — lote de import desfazível.

Cobre: carimbo do lote nos imports, regras do desfazer (verbatim apaga; pessoa que
respondeu mantém+inativa; pessoa vazia apaga; atributo reverte), guarda de duplo
desfazer, resumo pré-undo, agendamento do reprocesso, e a rota com confirmação forte.
"""

from __future__ import annotations

import pandas as pd

from src.contatos.importar import importar_contatos
from src.importacao.desfazer import desfazer_lote, resumo_lote
from src.models.contato import ContatoAtributo, ContatoEmpresa
from src.models.empresa import Empresa
from src.models.importacao import ImportacaoLote
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.pessoa import Pessoa
from src.models.respondente import Respondente
from src.models.verbatim import Verbatim
from src.pesquisa.coleta import registrar_respostas

_NOTA = '{"tipo":"nota","pontos":5,"rotulos":["1","2","3","4","5"],"ponto_medio_idx":2}'


def _empresa(db_session, nome="EmpL"):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    return e


def _xlsx(tmp_path, rows, cols, nome="c.xlsx"):
    p = tmp_path / nome
    pd.DataFrame(rows, columns=cols).to_excel(p, index=False, sheet_name="contatos")
    return str(p)


def _pesquisa(db_session, empresa_id):
    p = Pesquisa(
        empresa_id=empresa_id,
        natureza="externa",
        proposito="coleta",
        titulo="P",
        status="pronta",
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id,
        ordem=1,
        enunciado="Nota?",
        formato="mista",
        opcoes_json=_NOTA,
        subpilar_alvo="D1",
    )
    db_session.add(q)
    db_session.flush()
    return p, q


# ── Carimbo ─────────────────────────────────────────────────────────────────────


def test_import_contatos_cria_lote_e_carimba(db_session, tmp_path):
    e = _empresa(db_session)
    cols = ["email", "id_cliente", "nome", "plano"]
    rows = [{"email": "ana@x.com", "id_cliente": "", "nome": "Ana", "plano": "premium"}]
    st = importar_contatos(
        db_session, _xlsx(tmp_path, rows, cols), e.id, atributos_marcados=["plano"]
    )
    db_session.flush()
    lote_id = st["lote_id"]
    assert db_session.get(ImportacaoLote, lote_id).tipo == "contatos"
    assert db_session.query(ContatoEmpresa).filter_by(import_lote_id=lote_id).count() == 1
    assert db_session.query(ContatoAtributo).filter_by(import_lote_id=lote_id).count() == 1


# ── Desfazer contatos ───────────────────────────────────────────────────────────


def test_desfazer_contatos_sem_voz_apaga_tudo(db_session, tmp_path):
    e = _empresa(db_session)
    cols = ["email", "nome", "plano"]
    rows = [{"email": "ana@x.com", "nome": "Ana", "plano": "premium"}]
    st = importar_contatos(
        db_session, _xlsx(tmp_path, rows, cols), e.id, atributos_marcados=["plano"]
    )
    db_session.flush()
    res = desfazer_lote(db_session, st["lote_id"])
    db_session.flush()
    assert res["contatos_apagados"] == 1 and res["pessoas_apagadas"] == 1
    assert db_session.query(ContatoEmpresa).count() == 0
    assert db_session.query(ContatoAtributo).count() == 0
    assert db_session.query(Pessoa).count() == 0
    assert db_session.get(ImportacaoLote, st["lote_id"]).status == "desfeito"


def test_desfazer_contatos_com_voz_inativa_e_reverte(db_session):
    e = _empresa(db_session)
    lote = ImportacaoLote(empresa_id=e.id, tipo="contatos", arquivo_nome="c")
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add_all([lote, ana])
    db_session.flush()
    db_session.add(
        ContatoEmpresa(empresa_id=e.id, pessoa_id=ana.id, status="ativo", import_lote_id=lote.id)
    )
    db_session.add(
        ContatoAtributo(
            empresa_id=e.id,
            pessoa_id=ana.id,
            chave="plano",
            valor_atual="vip",
            valor_anterior="premium",
            import_lote_id=lote.id,
        )
    )
    p, _q = _pesquisa(db_session, e.id)
    db_session.add(Respondente(pesquisa_id=p.id, pessoa_id=ana.id, entidade_tipo="empresa"))
    db_session.flush()
    res = desfazer_lote(db_session, lote.id)
    db_session.flush()
    assert res["contatos_inativados"] == 1 and res["contatos_apagados"] == 0
    assert res["pessoas_apagadas"] == 0
    assert db_session.query(ContatoEmpresa).filter_by(pessoa_id=ana.id).one().status == "inativo"
    attr = db_session.query(ContatoAtributo).filter_by(pessoa_id=ana.id, chave="plano").one()
    assert attr.valor_atual == "premium" and attr.import_lote_id is None


# ── Desfazer respostas / verbatins ──────────────────────────────────────────────


def test_desfazer_respostas_apaga_e_agenda_reprocesso(db_session):
    e = _empresa(db_session)
    p, q = _pesquisa(db_session, e.id)
    lote = ImportacaoLote(empresa_id=e.id, tipo="respostas", arquivo_nome="r")
    bruno = Pessoa(tipo="interno_consentido", nome_display="Bruno")
    db_session.add_all([lote, bruno])
    db_session.flush()
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=bruno.id,
        respostas=[{"pergunta_id": q.id, "texto": "ruim demais", "nota": 2, "opcao": None}],
        conector="pesquisa_excel",
        lote_id=lote.id,
    )
    db_session.flush()
    bruno_id = bruno.id
    resumo = resumo_lote(db_session, lote.id)
    assert resumo["em_diagnostico"] is True and resumo["classificados"] == 1
    res = desfazer_lote(db_session, lote.id)
    db_session.flush()
    assert res["verbatins_apagados"] == 1 and res["respondentes_apagados"] == 1
    assert res["pessoas_apagadas"] == 1
    assert db_session.query(Verbatim).filter_by(import_lote_id=lote.id).count() == 0
    assert db_session.query(Pessoa).filter_by(id=bruno_id).first() is None
    assert db_session.get(Empresa, e.id).reprocessar_em is not None


def test_desfazer_verbatins_mantem_pessoa_com_outra_voz(db_session):
    e = _empresa(db_session)
    from src.models.fonte import Fonte

    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_interno",
        url="u",
    )
    lote = ImportacaoLote(empresa_id=e.id, tipo="verbatins", arquivo_nome="v")
    ana = Pessoa(tipo="interno_consentido", nome_display="Ana")
    db_session.add_all([f, lote, ana])
    db_session.flush()
    # verbatim do lote + verbatim ANTIGO (fora do lote) da mesma pessoa
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            pessoa_id=ana.id,
            texto="do lote",
            tem_texto=True,
            hash_dedup="h1",
            import_lote_id=lote.id,
        )
    )
    db_session.add(
        Verbatim(
            empresa_id=e.id,
            fonte_id=f.id,
            pessoa_id=ana.id,
            texto="antigo",
            tem_texto=True,
            hash_dedup="h2",
        )
    )
    db_session.flush()
    res = desfazer_lote(db_session, lote.id)
    db_session.flush()
    assert res["verbatins_apagados"] == 1 and res["pessoas_apagadas"] == 0  # Ana tem outra voz
    assert db_session.query(Verbatim).filter_by(pessoa_id=ana.id).count() == 1


def test_desfazer_ja_desfeito_erro(db_session):
    e = _empresa(db_session)
    lote = ImportacaoLote(empresa_id=e.id, tipo="contatos", status="desfeito")
    db_session.add(lote)
    db_session.flush()
    import pytest

    with pytest.raises(ValueError):
        desfazer_lote(db_session, lote.id)


# ── Rota (confirmação forte) ────────────────────────────────────────────────────


def _seed_lote_contatos(db_session, empresa_id):
    lote = ImportacaoLote(empresa_id=empresa_id, tipo="contatos", arquivo_nome="c.xlsx")
    pess = Pessoa(tipo="interno_consentido", nome_display="Zed")
    db_session.add_all([lote, pess])
    db_session.flush()
    db_session.add(
        ContatoEmpresa(
            empresa_id=empresa_id, pessoa_id=pess.id, status="ativo", import_lote_id=lote.id
        )
    )
    db_session.commit()
    return lote.id


def test_route_lista_render(client_loyall, db_session):
    e = _empresa(db_session)
    _seed_lote_contatos(db_session, e.id)
    resp = client_loyall.get(f"/empresas/{e.id}/importacoes")
    assert resp.status_code == 200
    assert "Lotes de import" in resp.get_data(as_text=True)


def test_route_desfazer_confirmacao_fraca_400(client_loyall, db_session):
    e = _empresa(db_session)
    lote_id = _seed_lote_contatos(db_session, e.id)
    resp = client_loyall.post(
        f"/empresas/{e.id}/importacoes/{lote_id}/desfazer", data={"confirmacao": "xxx"}
    )
    assert resp.status_code == 400
    assert db_session.get(ImportacaoLote, lote_id).status == "ativo"  # não desfez


def test_route_desfazer_forte_executa(client_loyall, db_session):
    e = _empresa(db_session)
    lote_id = _seed_lote_contatos(db_session, e.id)
    resp = client_loyall.post(
        f"/empresas/{e.id}/importacoes/{lote_id}/desfazer", data={"confirmacao": "DESFAZER"}
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.get(ImportacaoLote, lote_id).status == "desfeito"
    assert db_session.query(ContatoEmpresa).filter_by(import_lote_id=lote_id).count() == 0


def test_route_desfazer_respostas_dispara_recompute(client_loyall, db_session):
    """Undo de respostas pela rota → apaga verbatins E roda o recálculo síncrono
    (limpar_acumulo_temas + ratios) sem estourar, agendando o reprocesso noturno."""
    e = _empresa(db_session)
    p, q = _pesquisa(db_session, e.id)
    lote = ImportacaoLote(empresa_id=e.id, tipo="respostas", arquivo_nome="r.xlsx")
    bruno = Pessoa(tipo="interno_consentido", nome_display="Bruno")
    db_session.add_all([lote, bruno])
    db_session.flush()
    registrar_respostas(
        db_session,
        p,
        escopo=("empresa", None),
        pessoa_id=bruno.id,
        respostas=[{"pergunta_id": q.id, "texto": "pessimo", "nota": 1, "opcao": None}],
        conector="pesquisa_excel",
        lote_id=lote.id,
    )
    db_session.commit()
    resp = client_loyall.post(
        f"/empresas/{e.id}/importacoes/{lote.id}/desfazer", data={"confirmacao": str(lote.id)}
    )
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(Verbatim).filter_by(import_lote_id=lote.id).count() == 0
    assert db_session.get(Empresa, e.id).reprocessar_em is not None
