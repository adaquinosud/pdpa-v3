"""Rodapé de período dos impressos (decisão de 15/11): cada impresso declara o período de cada
número, com "desde o primeiro registro coletado" no lugar de "todo o histórico", e os períodos
com janela própria lidos das constantes (não reescritos na copy)."""

from __future__ import annotations

from datetime import datetime

from src.relatorios.rodape import DESDE_PRIMEIRO, rodape_periodo
from tests.test_item17_pacotes import _CENARIO, _empresa_com, _quarters_fixos


def test_faixa_dos_registros_e_rotulo_de_cada_impresso(client_loyall, db_session, monkeypatch):
    eid = _empresa_com(client_loyall, db_session, "rod", _CENARIO)
    desde = f"{DESDE_PRIMEIRO} (08/2026–10/2026)"
    assert rodape_periodo(eid, "diagnostico_pontual") == f"Razão, índice e assuntos: {desde}"
    assert rodape_periodo(eid, "resumo_executivo") == f"Razão, índice e assuntos: {desde}"
    assert rodape_periodo(eid, "plano_executivo").endswith(" · Ações: últimos 6 meses")
    assert rodape_periodo(eid, "diagnostico_longitudinal", quarters=["2025-Q3", "2026-Q4"]) == (
        f"2 trimestres: T3/2025 a T4/2026 · Gargalo atual: {desde}"
    )
    assert rodape_periodo(eid, "parecer", ra=("06/2026", "07/2026")) == (
        f"Razão e assuntos: {desde} · Reclame Aqui: 06/2026–07/2026"
    )
    assert rodape_periodo(eid, "parecer", ra=(None, None)) == f"Razão e assuntos: {desde}"
    assert rodape_periodo(eid, "em_construcao") is None
    assert "todo o histórico" not in rodape_periodo(eid, "painel_governanca")


def test_janelas_proprias_vem_das_constantes(client_loyall, db_session, monkeypatch):
    import src.api.painel as PA
    import src.governanca.leitura as GL

    monkeypatch.setattr(PA, "JANELA_CONCENTRACAO_MESES", 7)
    monkeypatch.setattr(PA, "JANELA_PREVISIBILIDADE_MESES", 13)
    monkeypatch.setattr(GL, "TRAJETORIA_JANELA_MESES", 4)
    monkeypatch.setenv("PDPA_TEMAS_JANELA_DIAS", "45")
    eid = _empresa_com(client_loyall, db_session, "const", _CENARIO)
    gov = rodape_periodo(eid, "painel_governanca")
    assert gov.startswith(
        "Trajetória: 4 contra 4 meses · Concentração: 7 meses · Previsibilidade: 13 meses"
    )
    assert rodape_periodo(eid, "plano_executivo").endswith("Ações: últimos 45 dias")


def test_empresa_sem_registro_nao_inventa_faixa(client_loyall, db_session):
    e = client_loyall.post("/api/empresas/", json={"nome": "Rod-vazia"}).get_json()
    assert rodape_periodo(e["id"], "diagnostico_pontual") == (
        f"Razão, índice e assuntos: {DESDE_PRIMEIRO}"
    )


def test_pdf_longitudinal_rodape_com_os_trimestres_usados(client_loyall, db_session, monkeypatch):
    eid = _empresa_com(client_loyall, db_session, "pdfrod", _CENARIO)
    _quarters_fixos(monkeypatch)
    h = client_loyall.get(f"/empresas/{eid}/relatorios/diagnostico_longitudinal").get_data(
        as_text=True
    )
    assert "6 trimestres: T3/2025 a T4/2026 · Gargalo atual: " + DESDE_PRIMEIRO in h


def test_parecer_rodape_declara_reclame_aqui(client_loyall, db_session, monkeypatch):
    """Caminho feliz do Parecer pela rota: a faixa do Reclame Aqui vem dos casos (MM/AAAA)."""
    from src.models.caso import Caso
    from src.models.fonte import Fonte
    from src.models.verbatim import Verbatim
    import src.relatorios.parecer as PR

    monkeypatch.setattr(PR, "sintetizar_parecer", lambda eid, d: None)
    e = client_loyall.post("/api/empresas/", json={"nome": "Rod-parecer"}).get_json()
    f = Fonte(
        empresa_id=e["id"],
        entidade_tipo="empresa",
        entidade_id=e["id"],
        conector_tipo="reclame_aqui",
        url="https://www.reclameaqui.com.br/x/",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    for i, dt in enumerate((datetime(2026, 6, 23), datetime(2026, 7, 9))):
        db_session.add(
            Caso(empresa_id=e["id"], fonte_id=f.id, origem_id=f"R{i}", criado_em_origem=dt)
        )
    for i in range(30):  # 30: a ferida exige base (sem ela o Parecer é bloqueado)
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                fonte_id=f.id,
                texto="cobrança errada e ninguém resolveu",
                tem_texto=True,
                subpilar="Pa2",
                tipo="detrator",
                hash_dedup=f"rodpar{i}",
                data_criacao_original=datetime(2026, 7, 1),
            )
        )
    db_session.commit()
    h = client_loyall.get(f"/empresas/{e['id']}/relatorios/parecer").get_data(as_text=True)
    assert f"Razão e assuntos: {DESDE_PRIMEIRO} (07/2026) · Reclame Aqui: 06/2026–07/2026" in h
