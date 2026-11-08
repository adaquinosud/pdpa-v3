"""Botões de coleta respeitam o gate da empresa; só o Reprocessar força — e os avisos dizem
o tamanho com número do código (não estimativa em R$)."""

from __future__ import annotations

import src.coletor.orquestrador as orq
import src.temas.pos_coleta as pc
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim


def _capturar(monkeypatch):
    chamadas = []
    monkeypatch.setattr(orq, "_rodar_async", lambda fn, app=None, label="": fn())
    monkeypatch.setattr(pc, "executar_pos_coleta", lambda eid, **kw: chamadas.append((eid, kw)))
    return chamadas


def test_coleta_e_import_nao_forcam(monkeypatch):
    chamadas = _capturar(monkeypatch)
    orq.disparar_pos_coleta_async(7)
    monkeypatch.setattr(orq, "_coletar_fonte_direto", lambda fid, **kw: {"falhou_apify": False})
    orq._coletar_fonte_e_pos(1, 7)
    orq._coletar_aberturas_e_pos(1, 7)
    assert chamadas == [(7, {}), (7, {}), (7, {})]  # sem force: limiar efetivo da empresa


def test_so_o_reprocessar_forca(monkeypatch):
    chamadas = _capturar(monkeypatch)
    orq.disparar_reprocessamento_async(7)
    assert chamadas == [(7, {"limiar": 1, "force": True})]


def test_tamanho_reprocessamento_conta(db_session):
    e = Empresa(nome="TamReproc")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="ChIJtam",
    )
    db_session.add(f)
    db_session.flush()
    for i, (sub, txt) in enumerate([(None, True), (None, True), ("P1", True), ("P1", False)]):
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="t" if txt else "",
                tem_texto=txt,
                subpilar=sub,
                hash_dedup=f"tam{i}",
            )
        )
    db_session.commit()
    assert pc.tamanho_reprocessamento(e.id) == {"pendentes": 2, "com_texto": 3, "lojas": 0}


def test_avisos_dos_botoes_tem_numero_do_codigo(client_loyall, db_session):
    e = client_loyall.post("/api/empresas/", json={"nome": "AvisoBotoes"}).get_json()
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJaviso"}
    )
    h = client_loyall.get(f"/empresas/{e['id']}").get_data(as_text=True)
    assert "só rodam se as pendências chegarem a 10." in h  # limiar efetivo (default)
    assert "Reprocessar TODA a empresa, ignorando o limiar? Classifica 0 pendentes" in h
    assert "Pode consumir LLM (alguns centavos)" not in h
