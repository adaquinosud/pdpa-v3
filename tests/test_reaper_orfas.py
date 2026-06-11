"""CP reaper-orfas: ColetaExecucao presa em 'rodando' (worker morto/deploy/coleta
interrompida) é órfã eterna e o guard execucao_em_andamento bloquearia a recoleta.

O reaper marca como 'erro' as 'rodando' além do limite (1h = timeout-por-fonte
45min + margem), liberando o lock. Roda no topo de execucao_em_andamento
(auto-cura). NÃO toca execução recente (legítima em andamento).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.coletor.orquestrador import (
    REAPER_LIMITE_SEGUNDOS,
    execucao_em_andamento,
    re_marca_orfas,
)
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _empresa_fonte(db_session):
    e = Empresa(nome="Reaper Co")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id, entidade_tipo="empresa", entidade_id=e.id, conector_tipo="google", url="x"
    )
    db_session.add(f)
    db_session.commit()
    return e.id, f.id


def _exec(db_session, emp, fid, idade_segundos):
    ce = ColetaExecucao(
        empresa_id=emp,
        fonte_id=fid,
        status="rodando",
        iniciado_em=datetime.utcnow() - timedelta(seconds=idade_segundos),
    )
    db_session.add(ce)
    db_session.commit()
    return ce.id


def test_reaper_marca_orfa_antiga_poupa_recente(db_session):
    emp, fid = _empresa_fonte(db_session)
    orfa = _exec(db_session, emp, fid, REAPER_LIMITE_SEGUNDOS + 3600)  # 1h além do limite
    recente = _exec(db_session, emp, fid, 300)  # 5 min — legítima

    n = re_marca_orfas()

    assert n == 1
    db_session.expire_all()
    o = db_session.get(ColetaExecucao, orfa)
    assert o.status == "erro"
    assert "órfã" in (o.mensagem_erro or "")
    assert o.concluido_em is not None
    assert db_session.get(ColetaExecucao, recente).status == "rodando"  # intacta


def test_guard_auto_cura_libera_recoleta(db_session):
    """Órfã antiga 'rodando' → o guard reapa e devolve False (fonte recoletável)."""
    emp, fid = _empresa_fonte(db_session)
    oid = _exec(db_session, emp, fid, REAPER_LIMITE_SEGUNDOS + 60)

    assert execucao_em_andamento("fonte", fid) is False  # reapada → lock liberado
    db_session.expire_all()
    assert db_session.get(ColetaExecucao, oid).status == "erro"


def test_guard_respeita_execucao_recente(db_session):
    """Execução recente (dentro do limite) NÃO é reapada — lock legítimo segue."""
    emp, fid = _empresa_fonte(db_session)
    rid = _exec(db_session, emp, fid, 300)  # 5 min

    assert execucao_em_andamento("fonte", fid) is True  # bloqueia (legítima)
    db_session.expire_all()
    assert db_session.get(ColetaExecucao, rid).status == "rodando"


def test_limite_acima_do_timeout_por_fonte(db_session):
    """O limite é > o teto legítimo por-fonte (2700s) — não mata coleta longa-mas-viva."""
    assert REAPER_LIMITE_SEGUNDOS > 2700
    emp, fid = _empresa_fonte(db_session)
    # execução de 44 min (abaixo do timeout-por-fonte de 45) → NÃO reapa
    _exec(db_session, emp, fid, 44 * 60)
    assert re_marca_orfas() == 0


def test_polling_da_tela_auto_cura_orfa(db_session, client_loyall):
    """CP-status-preso: o polling da tela (/ui/.../coletas-em-andamento) reapa a
    órfã >1h ANTES de listar → ela some de 'em_andamento' (a tela para de mostrar
    "Coletando..." sem precisar de novo disparo), mas a coleta viva <1h fica."""
    emp, fid = _empresa_fonte(db_session)
    orfa = _exec(db_session, emp, fid, REAPER_LIMITE_SEGUNDOS + 600)  # presa há >1h
    viva = _exec(db_session, emp, fid, 300)  # 5 min — legítima

    r = client_loyall.get(f"/ui/empresas/{emp}/coletas-em-andamento")
    assert r.status_code == 200
    ids = {c["id"] for c in r.get_json()["em_andamento"]}

    assert orfa not in ids  # reapada → some da lista (tela auto-cura)
    assert viva in ids  # coleta viva continua "Coletando..."
    db_session.expire_all()
    assert db_session.get(ColetaExecucao, orfa).status == "erro"
    assert db_session.get(ColetaExecucao, viva).status == "rodando"
