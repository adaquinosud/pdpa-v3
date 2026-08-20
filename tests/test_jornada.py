"""Frente Jornada — testes: config, classificador (etapa 4ª dim), 3 pontos de escrita,
caminho feliz RENDER (trava §7: ausência não prova presença), piso/knob, filtro por fonte.
"""

from src.classifier.classifier_v3 import (
    ResultadoClassificacao,
    _build_user_prompt,
    _parse_response,
)
from src.jornada import ETAPA_NENHUMA, jornada_da_empresa, normalizar_etapa
from src.jornada.leitura import LIMIAR_CONFIANCA_PROVISORIO, agregar_jornada
from src.models.empresa import Empresa
from src.models.empresa_jornada_etapa import EmpresaJornadaEtapa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim

ROT = ["reservar", "retirar", "devolver", "pós-serviço"]


def _empresa_com_jornada(db_session, versao=1, rotulos=ROT):
    e = Empresa(nome="Loc Jornada", setor="locadora")
    db_session.add(e)
    db_session.flush()
    for i, r in enumerate(rotulos):
        db_session.add(
            EmpresaJornadaEtapa(empresa_id=e.id, versao=versao, ordem=i, rotulo=r, ativo=True)
        )
    db_session.commit()
    return e


def _fonte(db_session, empresa_id, conector):
    f = Fonte(
        empresa_id=empresa_id,
        entidade_tipo="empresa",
        entidade_id=1,
        conector_tipo=conector,
        url=f"http://{conector}",
    )
    db_session.add(f)
    db_session.flush()
    return f


def _verb(db_session, e_id, fonte_id, etapa, tipo, econf, sub="P1", n=1, versao=1):
    for _ in range(n):
        db_session.add(
            Verbatim(
                empresa_id=e_id,
                fonte_id=fonte_id,
                texto="x",
                tem_texto=True,
                subpilar=sub,
                tipo=tipo,
                confianca=0.9,
                etapa=etapa,
                etapa_confianca=econf,
                etapa_versao=versao,
            )
        )


# ── 1. Config / jornada_da_empresa ──────────────────────────────────────


def test_jornada_da_empresa_ordenada_e_versao(db_session):
    e = _empresa_com_jornada(db_session)
    versao, rotulos = jornada_da_empresa(db_session, e.id)
    assert versao == 1
    assert rotulos == ROT  # ordem preservada


def test_jornada_da_empresa_sem_jornada_dark(db_session):
    e = Empresa(nome="Sem Jornada")
    db_session.add(e)
    db_session.commit()
    assert jornada_da_empresa(db_session, e.id) == (None, [])


def test_jornada_versao_ativa_mais_recente(db_session):
    e = _empresa_com_jornada(db_session, versao=1, rotulos=["a", "b"])
    for i, r in enumerate(["x", "y", "z"]):
        db_session.add(
            EmpresaJornadaEtapa(empresa_id=e.id, versao=2, ordem=i, rotulo=r, ativo=True)
        )
    db_session.commit()
    versao, rotulos = jornada_da_empresa(db_session, e.id)
    assert versao == 2 and rotulos == ["x", "y", "z"]  # v2 vence


# ── 2. normalizar_etapa (validação lenient) ─────────────────────────────


def test_normalizar_etapa_na_lista_case_insensitive():
    assert normalizar_etapa("Retirar", ["retirar", "devolver"]) == "retirar"


def test_normalizar_etapa_fora_da_lista_vira_none():
    assert normalizar_etapa("almoço", ["retirar"]) is None  # nunca força


def test_normalizar_etapa_nenhuma_valida():
    assert normalizar_etapa("nenhuma", ["retirar"]) == ETAPA_NENHUMA


# ── 3. Classificador (4ª dimensão, backward-compat, parse lenient) ──────


def test_prompt_injeta_etapas():
    p = _build_user_prompt("t", empresa_nome="E", etapas=["retirar", "devolver"])
    assert "retirar" in p and "devolver" in p and "nenhuma" in p


def test_prompt_sem_etapas_backward_compat():
    p = _build_user_prompt("t", empresa_nome="E")
    assert "jornada" not in p.lower()  # sem etapas: prompt inalterado


def test_parse_sem_etapa_none():
    r = _parse_response(
        '{"subpilar":"P1","tipo":"promotor","confianca":0.9,"justificativa_curta":"ok"}'
    )
    assert r.etapa is None and r.etapa_confianca is None


def test_parse_com_etapa_lenient():
    r = _parse_response(
        '{"subpilar":"P1","tipo":"detrator","confianca":0.8,'
        '"justificativa_curta":"x","etapa":"Retirar","etapa_confianca":0.95}'
    )
    assert r.etapa == "retirar" and r.etapa_confianca == 0.95


# ── 4. Persistência — TRÊS pontos de escrita ────────────────────────────


def test_persist_batch_aplicar_resultado_grava_etapa(db_session):
    """Ponto de escrita do BATCH (_aplicar_resultado, usado por passe1/sonnet/sem-sonnet)."""
    from src.temas.pos_coleta import _aplicar_resultado

    e = _empresa_com_jornada(db_session)
    f = _fonte(db_session, e.id, "google")
    v = Verbatim(empresa_id=e.id, fonte_id=f.id, texto="x", tem_texto=True)
    db_session.add(v)
    db_session.flush()
    r = ResultadoClassificacao(
        subpilar="D1",
        tipo="detrator",
        confianca=0.8,
        justificativa="",
        etapa="retirar",
        etapa_confianca=0.95,
    )
    _aplicar_resultado(v, r)
    assert v.etapa == "retirar" and v.etapa_confianca == 0.95 and v.etapa_versao == 1


def test_persist_batch_sem_jornada_etapa_none(db_session):
    from src.temas.pos_coleta import _aplicar_resultado

    e = Empresa(nome="Sem Jornada 2")
    db_session.add(e)
    db_session.flush()
    f = _fonte(db_session, e.id, "google")
    v = Verbatim(empresa_id=e.id, fonte_id=f.id, texto="x", tem_texto=True)
    db_session.add(v)
    db_session.flush()
    r = ResultadoClassificacao(
        subpilar="D1",
        tipo="detrator",
        confianca=0.8,
        justificativa="",
        etapa="retirar",
        etapa_confianca=0.95,
    )
    _aplicar_resultado(v, r)
    assert v.etapa is None  # sem jornada → não escreve


def test_persist_batch_etapa_fora_da_jornada_vira_none(db_session):
    from src.temas.pos_coleta import _aplicar_resultado

    e = _empresa_com_jornada(db_session)
    f = _fonte(db_session, e.id, "google")
    v = Verbatim(empresa_id=e.id, fonte_id=f.id, texto="x", tem_texto=True)
    db_session.add(v)
    db_session.flush()
    r = ResultadoClassificacao(
        subpilar="D1",
        tipo="detrator",
        confianca=0.8,
        justificativa="",
        etapa="etapa_inventada",
        etapa_confianca=0.9,
    )
    _aplicar_resultado(v, r)
    assert v.etapa is None  # etapa fora da jornada não é forçada


def test_persist_serial_grava_etapa(db_session, monkeypatch):
    """Ponto de escrita SERIAL (_classificar_pendentes_serial inline)."""
    import src.temas.pos_coleta as pc

    e = _empresa_com_jornada(db_session)
    f = _fonte(db_session, e.id, "reclame_aqui")
    v = Verbatim(empresa_id=e.id, fonte_id=f.id, texto="relato longo", tem_texto=True)
    db_session.add(v)
    db_session.commit()
    monkeypatch.setenv("ANTHROPIC_BATCH_ENABLED", "false")

    def fake_classificar(**kw):
        # o serial passa etapas=jornada_rotulos; confirma que recebeu a jornada
        assert kw.get("etapas") == ROT
        return ResultadoClassificacao(
            subpilar="Pa1",
            tipo="detrator",
            confianca=0.9,
            justificativa="",
            etapa="pós-serviço",
            etapa_confianca=0.95,
        )

    monkeypatch.setattr(pc, "classificar", fake_classificar, raising=False)
    monkeypatch.setattr("src.classifier.classifier_v3.classificar", fake_classificar)
    pc._classificar_pendentes_serial(e.id)
    db_session.expire_all()
    v2 = db_session.get(Verbatim, v.id)
    assert v2.etapa == "pós-serviço" and v2.etapa_versao == 1


# ── 5. Leitura — piso, knob, gargalo/volume, fonte ──────────────────────


def _cenario_leitura(db_session):
    e = _empresa_com_jornada(db_session)
    fg = _fonte(db_session, e.id, "google")
    fra = _fonte(db_session, e.id, "reclame_aqui")
    _verb(db_session, e.id, fg.id, "retirar", "detrator", 0.95, "D1", 10)
    _verb(db_session, e.id, fg.id, "retirar", "promotor", 0.95, "P1", 2)
    _verb(db_session, e.id, fra.id, "pós-serviço", "detrator", 0.95, "Pa1", 18)
    _verb(db_session, e.id, fra.id, "pós-serviço", "promotor", 0.95, "P1", 2)
    _verb(db_session, e.id, fg.id, "devolver", "detrator", 0.60, "D2", 5)  # knob → nenhuma
    _verb(db_session, e.id, fg.id, "reservar", "promotor", 0.95, "P1", 3)  # < piso 10
    db_session.commit()
    return e


def test_leitura_gargalo_montante_volume_divergem(db_session):
    e = _cenario_leitura(db_session)
    j = agregar_jornada(db_session, e.id)
    assert j.gargalo.rotulo == "retirar"  # travado E mais a montante
    assert j.volume.rotulo == "pós-serviço"  # mais detratores
    assert j.divergem is True  # o achado


def test_leitura_piso_10(db_session):
    e = _cenario_leitura(db_session)
    j = agregar_jornada(db_session, e.id)
    reservar = next(x for x in j.etapas if x.rotulo == "reservar")
    assert reservar.sem_lastro and reservar.ratio is None  # 3 < 10


def test_leitura_knob_baixa_confianca_vira_nenhuma(db_session):
    e = _cenario_leitura(db_session)
    j = agregar_jornada(db_session, e.id)
    devolver = next(x for x in j.etapas if x.rotulo == "devolver")
    assert devolver.total == 0  # 5 verbatins conf 0.60 < 0.80 saíram
    assert j.nenhuma_n == 5


def test_leitura_filtro_por_fonte(db_session):
    e = _cenario_leitura(db_session)
    jg = agregar_jornada(db_session, e.id, fonte="google")
    pos = next(x for x in jg.etapas if x.rotulo == "pós-serviço")
    assert pos.total == 0  # pós-serviço é só RA → some no google-only


def test_leitura_sem_jornada_none(db_session):
    e = Empresa(nome="Nada")
    db_session.add(e)
    db_session.commit()
    assert agregar_jornada(db_session, e.id) is None


def test_limiar_provisorio_declarado():
    assert LIMIAR_CONFIANCA_PROVISORIO == 0.80  # provisório, documentado


# ── 6. RENDER — caminho feliz (trava §7: presença PRODUZ a leitura) ─────


def test_render_jornada_caminho_feliz(db_session, client_loyall):
    e = _cenario_leitura(db_session)
    html = client_loyall.get(f"/empresas/{e.id}/explorar?tab=jornada").get_data(as_text=True)
    # A aba RENDERIZA a leitura (não só o guard de ausência): gargalo, matriz, divergência.
    assert "retirar" in html and "pós-serviço" in html
    assert "Gargalo" in html and "Jornada" in html
    assert "manifestações" in html  # linha de declaração de mix


def test_render_tab_dark_sem_jornada(db_session, client_loyall):
    e = Empresa(nome="Sem Aba")
    db_session.add(e)
    db_session.commit()
    html = client_loyall.get(f"/empresas/{e.id}/explorar?tab=painel").get_data(as_text=True)
    # A aba Jornada NÃO aparece na tab bar quando não há jornada configurada.
    assert "tab=jornada" not in html
