"""Fatia 2 — a falha de coleta te encontra: aviso no card (todas as fontes, self-clearing)
+ painel de rollup por empresa no Monitoramento + fix do filtro `desde`."""

from __future__ import annotations

from datetime import datetime, timedelta

import src.ui as ui
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte


def _emp(db_session, nome):
    e = Empresa(nome=nome)
    db_session.add(e)
    db_session.flush()
    return e


def _fonte(db_session, e, conector="reclame_aqui"):
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo=conector,
        url="https://www.reclameaqui.com.br/x/" if conector == "reclame_aqui" else "ChIJ_x",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return f


def _exe(db_session, e, f, status, *, dias=0, custo=None, motivo=None):
    db_session.add(
        ColetaExecucao(
            empresa_id=e.id,
            fonte_id=f.id,
            status=status,
            iniciado_em=datetime.utcnow() - timedelta(days=dias),
            custo_apify_centavos=custo,
            mensagem_erro=motivo,
        )
    )


# ── Card: aviso de falha (todas as fontes, self-clearing) ───────────────────


def test_card_aviso_cobre_fonte_nao_ra(client_loyall, db_session):
    """A noturna derruba google/linkedin etc. → o aviso cobre todo conector, não só RA."""
    e = _emp(db_session, "Carbel")
    f = _fonte(db_session, e, conector="google")
    _exe(db_session, e, f, "erro", dias=2, motivo="Apify falhou (falhou_apify=true)")
    db_session.commit()
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "última coleta falhou" in body
    assert "há 2d" in body
    assert "Apify falhou" in body


def test_card_aviso_self_clearing(client_loyall, db_session):
    """Erro antigo + coleta OK depois → a última é 'concluido' → aviso some sozinho."""
    e = _emp(db_session, "SelfClear")
    f = _fonte(db_session, e, conector="google")
    _exe(db_session, e, f, "erro", dias=3, motivo="Apify falhou")
    _exe(db_session, e, f, "concluido", dias=1)  # mais recente
    db_session.commit()
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "última coleta falhou" not in body


def test_card_sem_execucao_sem_aviso(client_loyall, db_session):
    """Nunca coletou (sem execução) → sem aviso (distingue de falha)."""
    e = _emp(db_session, "NuncaColetou")
    f = _fonte(db_session, e, conector="google")
    db_session.commit()
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "última coleta falhou" not in body


def test_card_query_combinada_gasto_e_aviso(client_loyall, db_session):
    """Uma leitura entrega os dois: gasto do mês (RA) + aviso (última=erro)."""
    e = _emp(db_session, "Combina")
    f = _fonte(db_session, e, conector="reclame_aqui")
    now = datetime.utcnow()
    mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # concluída logo após o início do mês (gasto garantido in-month) + erro AGORA (última)
    db_session.add(
        ColetaExecucao(
            empresa_id=e.id,
            fonte_id=f.id,
            status="concluido",
            iniciado_em=mes + timedelta(minutes=1),
            custo_apify_centavos=626,
        )
    )
    db_session.add(
        ColetaExecucao(
            empresa_id=e.id,
            fonte_id=f.id,
            status="erro",
            iniciado_em=now,
            mensagem_erro="timeout (>45min)",
        )
    )
    db_session.commit()
    body = client_loyall.get(f"/ui/fontes/{f.id}/row").get_data(as_text=True)
    assert "gasto este mês" in body  # derivado da execução concluída
    assert "última coleta falhou" in body  # da execução mais recente (erro)


# ── Monitoramento: rollup por empresa + fix do `desde` ──────────────────────


def test_falhas_por_empresa_rollup(db_session):
    """Agrupa por empresa, conta, ordena por n desc; falha fora da janela não entra."""
    ea = _emp(db_session, "EmpA")
    fa = _fonte(db_session, ea, conector="google")
    eb = _emp(db_session, "EmpB")
    fb = _fonte(db_session, eb, conector="google")
    _exe(db_session, ea, fa, "erro", dias=1, motivo="Apify falhou")
    _exe(db_session, ea, fa, "erro", dias=2)
    _exe(db_session, ea, fa, "erro", dias=3)
    _exe(db_session, eb, fb, "erro", dias=1)
    _exe(db_session, ea, fa, "erro", dias=20)  # fora dos 14d
    db_session.commit()
    lista, total = ui._falhas_por_empresa(dias=14)
    assert total == 4  # 3 de A + 1 de B (a de 20d fora)
    assert lista[0]["nome"] == "EmpA" and lista[0]["n"] == 3  # ordenado por n desc
    assert lista[1]["nome"] == "EmpB" and lista[1]["n"] == 1


def test_monitoramento_painel_render(client_loyall, db_session):
    e = _emp(db_session, "PainelX")
    f = _fonte(db_session, e, conector="google")
    _exe(db_session, e, f, "erro", dias=1, motivo="Apify falhou")
    db_session.commit()
    body = client_loyall.get("/monitoramento").get_data(as_text=True)
    assert "Coletas com falha · últimos 14 dias (1)" in body
    assert "PainelX" in body and "1 falha" in body


def test_monitoramento_painel_vazio(client_loyall, db_session):
    body = client_loyall.get("/monitoramento").get_data(as_text=True)
    assert "Nenhuma falha nos últimos 14 dias" in body


def test_monitoramento_filtro_desde_renomeado(client_loyall, db_session):
    """O campo de data virou name='desde' (a API lê ?desde) — o 'desde_data' morto saiu."""
    body = client_loyall.get("/monitoramento").get_data(as_text=True)
    assert 'name="desde"' in body
    assert 'name="desde_data"' not in body
