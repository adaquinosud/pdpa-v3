"""A sonda lê o grão e pergunta pelo nome da ENTIDADE (§6.22, fatia 2).

Esta fatia **grava** a origem (``SondaIAResposta.entidade``); quem **lê** é a fatia 3.
O consolidador (``sintetizar_leitura``/``classificar_avaliacoes``/``cruzar_defasagem``)
fica intacto de propósito — ele quebra com N entidades, e é lá que se resolve.

⚠️ O teste que mais importa aqui é o de NÃO-REGRESSÃO: no grão ``'empresa'`` a sonda
tem de produzir **exatamente** o que produz hoje (27 chamadas, ``entidade`` NULL),
porque é o grão das 24 empresas existentes e o default da fatia 1.
"""

from __future__ import annotations

import pytest

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.local import Local
from src.models.sonda_ia import SondaIAResposta
from src.sonda_ia import sonda as S


def _empresa(db_session, sfx, grao="empresa"):
    e = Empresa(nome=f"ESG-{sfx}-{id(db_session)}", sonda_grao=grao)
    db_session.add(e)
    db_session.flush()
    return e


def _local(db_session, emp, nome, ativa=True):
    lo = Local(empresa_id=emp.id, nome=nome, status="ativo", sonda_ativa=ativa)
    db_session.add(lo)
    db_session.flush()
    return lo


def _ag(db_session, emp, nome, ativa=True):
    a = Agrupamento(empresa_id=emp.id, nome=nome, sonda_ativa=ativa)
    db_session.add(a)
    db_session.flush()
    return a


def _callers(registro):
    """3 vendors que registram o prompt recebido e devolvem resposta fixa."""

    def _mk(v):
        def _c(prompt):
            registro.append((v, prompt))
            return {"vendor": v, "modelo": f"{v}-x", "texto": "ok", "tokens_in": 1, "tokens_out": 1}

        return _c

    return {v: _mk(v) for v in ("claude", "gpt", "gemini")}


# ── resolução nos três grãos ───────────────────────────────────────────────────


def test_grao_empresa_devolve_a_empresa(db_session):
    e = _empresa(db_session, "ge")
    assert S.entidades_da_sonda(db_session, e.id) == [(e.id, e.nome)]


def test_grao_agrupamento_devolve_agrupamentos_ativos(db_session):
    e = _empresa(db_session, "gag", grao="agrupamento")
    a1 = _ag(db_session, e, "Audi")
    a2 = _ag(db_session, e, "Porsche")
    assert S.entidades_da_sonda(db_session, e.id) == [(a1.id, "Audi"), (a2.id, "Porsche")]


def test_grao_loja_devolve_locais_ativos(db_session):
    e = _empresa(db_session, "glo", grao="loja")
    lo = _local(db_session, e, "Jeep Morumbi")
    assert S.entidades_da_sonda(db_session, e.id) == [(lo.id, "Jeep Morumbi")]


# ── a flag, e SÓ a flag ────────────────────────────────────────────────────────


def test_flag_desmarcada_exclui_a_entidade(db_session):
    e = _empresa(db_session, "flag", grao="loja")
    _local(db_session, e, "Canal RA", ativa=False)
    viva = _local(db_session, e, "Loja de verdade", ativa=True)
    assert S.entidades_da_sonda(db_session, e.id) == [(viva.id, "Loja de verdade")]


def test_loja_sem_verbatim_e_sem_status_ativo_ENTRA(db_session):
    """⚠️ A elegibilidade é a FLAG e só ela.

    Reconhecimento em IA independe de termos coletado — é onde a IA pode saber mais
    que nós (§6.22.10). Herdar o gate de ``_empresas_alvo`` (≥1 verbatim) ou filtrar
    por ``status`` seria importar régua de outro grão.
    """
    e = _empresa(db_session, "semverb", grao="loja")
    lo = Local(empresa_id=e.id, nome="Loja nova", status="em_obra", sonda_ativa=True)
    db_session.add(lo)
    db_session.flush()
    assert S.entidades_da_sonda(db_session, e.id) == [(lo.id, "Loja nova")]


def test_grao_com_zero_entidades_ativas_FALHA_declarando(db_session):
    """Nunca cai para o nome da empresa: fallback silencioso reproduz o defeito que
    originou a frente (perguntar pela razão social e o resultado sair artefato)."""
    e = _empresa(db_session, "zero", grao="loja")
    _local(db_session, e, "Só canal", ativa=False)
    with pytest.raises(S.SondaSemEntidade) as ex:
        S.entidades_da_sonda(db_session, e.id)
    assert "sonda_ativa" in str(ex.value)
    assert "não roda" in str(ex.value)


# ── o loop ─────────────────────────────────────────────────────────────────────


def test_NAO_REGRESSAO_grao_empresa_produz_27_e_entidade_NULL(db_session):
    """⚠️ O teste que importa: as 24 empresas existentes não podem mudar de
    comportamento. 3 modelos × 3 perguntas × 3 reps = 27, ``entidade`` NULL."""
    e = _empresa(db_session, "naoreg")
    db_session.commit()
    reg = []
    st = S.sondar_empresa(e.id, "2026-09", callers=_callers(reg))
    assert st["respostas"] == 27
    assert len(reg) == 27
    db_session.expire_all()
    linhas = db_session.query(SondaIAResposta).filter_by(execucao_id=st["execucao_id"]).all()
    assert len(linhas) == 27
    assert {r.entidade for r in linhas} == {None}
    assert {r.pergunta_tipo for r in linhas} == {"identidade", "avaliacao", "encaminhamento"}
    assert {r.repeticao for r in linhas} == {1, 2, 3}
    assert all(e.nome in p for _, p in reg)


def test_grao_loja_3_entidades_da_18_chamadas(db_session):
    """3 entidades × 3 modelos × 2 perguntas × 1 repetição = 18.

    'avaliacao' fica FORA no grão entidade: ela alimenta as avaliações, que o leitor
    conta por PONTO — N entidades mudariam a escala da régua sem ninguém tocar nela.
    """
    e = _empresa(db_session, "loja3", grao="loja")
    for nome in ("Audi Alphaville", "Jeep Morumbi", "Porsche SP Oeste"):
        _local(db_session, e, nome)
    db_session.commit()
    reg = []
    st = S.sondar_empresa(e.id, "2026-09", callers=_callers(reg))
    assert st["respostas"] == 18
    db_session.expire_all()
    linhas = db_session.query(SondaIAResposta).filter_by(execucao_id=st["execucao_id"]).all()
    assert len(linhas) == 18
    assert {r.pergunta_tipo for r in linhas} == {"identidade", "encaminhamento"}
    assert {r.repeticao for r in linhas} == {1}


def test_entidade_gravada_com_o_nome_certo_por_resposta(db_session):
    """A origem tem de casar com o nome que foi de fato perguntado — é o que a fatia
    3 vai usar para a consolidação distinguir as entidades."""
    e = _empresa(db_session, "nomes", grao="loja")
    for nome in ("Audi Alphaville", "Jeep Morumbi"):
        _local(db_session, e, nome)
    db_session.commit()
    reg = []
    st = S.sondar_empresa(e.id, "2026-09", callers=_callers(reg))
    db_session.expire_all()
    linhas = db_session.query(SondaIAResposta).filter_by(execucao_id=st["execucao_id"]).all()
    assert {r.entidade for r in linhas} == {"Audi Alphaville", "Jeep Morumbi"}
    # cada resposta carrega o nome que ESTAVA no prompt dela
    for r in linhas:
        assert r.entidade is not None
    for _, prompt in reg:
        assert ("Audi Alphaville" in prompt) or ("Jeep Morumbi" in prompt)
        assert e.nome not in prompt, "no grão loja a razão social não deve ser perguntada"


# ── telas ──────────────────────────────────────────────────────────────────────


def test_local_nasce_com_sonda_ativa_e_a_tela_desmarca(db_session, client_loyall):
    e = _empresa(db_session, "tela-loc")
    lo = _local(db_session, e, "L1")
    db_session.commit()
    assert lo.sonda_ativa is True
    r = client_loyall.put(f"/ui/locais/{lo.id}", data={"nome": "L1", "sonda_ativa": "0"})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Local, lo.id).sonda_ativa is False


def test_local_sem_o_campo_MANTEM(db_session, client_loyall):
    """Form antigo/parcial não rebaixa a escolha — só o companion hidden torna
    'ausente' distinguível de 'desmarcado'."""
    e = _empresa(db_session, "tela-mant")
    lo = _local(db_session, e, "L2", ativa=False)
    db_session.commit()
    r = client_loyall.put(f"/ui/locais/{lo.id}", data={"nome": "L2"})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Local, lo.id).sonda_ativa is False


def test_agrupamento_desmarca_pela_tela(db_session, client_loyall):
    e = _empresa(db_session, "tela-ag")
    a = _ag(db_session, e, "Marca X")
    db_session.commit()
    r = client_loyall.put(
        f"/ui/agrupamentos/{a.id}", data={"nome": "Marca X", "sonda_ativa": ["0", "1"]}
    )
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Agrupamento, a.id).sonda_ativa is True
    r = client_loyall.put(f"/ui/agrupamentos/{a.id}", data={"nome": "Marca X", "sonda_ativa": "0"})
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Agrupamento, a.id).sonda_ativa is False
