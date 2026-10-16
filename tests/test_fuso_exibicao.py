"""Horário de exibição (15/10): o banco guarda UTC, a tela e o impresso mostram Brasília.
Data que vem da FONTE (Reclame Aqui, rede social, planilha) não é convertida: não está
garantidamente em UTC, e a decisão está pendente."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

from src.utils.fuso import hora_br, para_brasilia
from tests.test_ui_avaliador import _pronta, _url, empresa, teto  # noqa: F401

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_utc_sem_fuso_vira_brasilia_tres_horas_antes():
    assert para_brasilia(datetime(2026, 10, 15, 23, 51)) == datetime(2026, 10, 15, 20, 51)
    # vira o dia para trás
    assert hora_br(datetime(2026, 10, 16, 1, 30), "%d/%m %H:%M") == "15/10 22:30"


def test_com_fuso_converte_e_date_puro_passa():
    assert para_brasilia(datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)) == datetime(
        2026, 10, 15, 9, 0
    )
    assert para_brasilia(date(2026, 10, 15)) == date(2026, 10, 15)
    assert hora_br(date(2026, 10, 15), "%d/%m/%Y") == "15/10/2026"


def test_iso_das_apis_e_vazio():
    assert hora_br("2026-10-15T23:51:07.123456") == "15/10/2026 20:51"
    assert hora_br("2026-10-15T23:51:07Z", "%H:%M") == "20:51"
    assert hora_br(None) == "" and hora_br("") == ""
    assert hora_br("não é data") == "não é data"


def test_tela_do_avaliador_mostra_horario_de_brasilia(
    client_loyall, db_session, empresa, teto  # noqa: F811
):
    from src.models.avaliador import AvaliadorAnalise

    aid = _pronta(client_loyall, db_session, empresa)
    a = db_session.get(AvaliadorAnalise, aid)
    a.criado_em = datetime(2026, 10, 16, 1, 30)  # UTC, como o app grava
    db_session.commit()
    analise = client_loyall.get(_url(empresa, f"/{aid}")).get_data(as_text=True)
    lista = client_loyall.get(_url(empresa)).get_data(as_text=True)
    for html in (analise, lista):
        assert "15/10/2026 22:30" in html
        assert "16/10/2026 01:30" not in html


# Formatação direta que SOBRA nos templates é só de data da fonte, nenhuma do app.
# Linha nova aqui exige decidir: é horário do app (usa ``| hora_br``) ou da fonte?
DATA_DA_FONTE = {
    ("casos/detalhe.html", "criado.strftime("),  # Caso.criado_em_origem (RA)
    ("casos/detalhe.html", "i.created[:16]"),  # interação do RA, texto cru
    ("partials/explorar_casos.html", "casos.janela[0].strftime("),  # RA
    ("partials/explorar_casos.html", "casos.janela[1].strftime("),  # RA
    ("partials/explorar_casos.html", "c.criado.strftime("),  # RA
    ("partials/explorar_loja_drill.html", "d.data.strftime("),  # Verbatim.data_criacao_original
    ("partials/verbatim_detalhes_modal.html", "v.data_criacao_original[:10]"),
    ("partials/verbatim_item.html", "v.data_criacao_original[:10]"),
}


def test_nenhum_template_formata_horario_do_app_sem_passar_por_brasilia():
    achados = set()
    for arq in TEMPLATES.rglob("*.html"):
        nome = arq.relative_to(TEMPLATES).as_posix()
        for m in re.finditer(r"[\w.\[\]0-9]+\.strftime\(|[\w.]+\[:1[06]\]", arq.read_text()):
            achados.add((nome, m.group(0)))
    assert achados == DATA_DA_FONTE
