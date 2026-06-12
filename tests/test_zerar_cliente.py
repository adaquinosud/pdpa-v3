"""Testes do script scripts/zerar_cliente.py.

Unit (sem DB): guardas de segurança, ordem FK-safe do PLANO, confirmação.
Integração (db_session :memory:): RECUSA empresa 4, dry-run não apaga, --aplicar
apaga só a empresa-alvo (estrutura + outras empresas intactas).
"""

from __future__ import annotations

import builtins

import pytest
from sqlalchemy import text

from scripts import zerar_cliente as zc
from src.utils.db import db_session as prod_db_session

# ── Unit: guardas e invariantes do plano (sem DB) ────────────────────────────


def test_empresa_proibida_e_confins():
    assert zc.EMPRESA_PROIBIDA == 4


def test_plano_nao_toca_estrutura():
    """Nenhuma tabela de estrutura (MANTIDAS) pode aparecer no PLANO de deleção."""
    tabelas_plano = {t for _, t, _ in zc.PLANO}
    assert tabelas_plano.isdisjoint(set(zc.MANTIDAS))
    # sanidade: estrutura essencial está mesmo na lista de mantidas
    for t in ("empresas", "locais", "fontes", "agrupamentos", "usuarios"):
        assert t in zc.MANTIDAS


def test_plano_ordem_fk_safe():
    """Filhos antes dos pais: verbatins por último; temas depois dos seus filhos."""
    ordem = [t for _, t, _ in zc.PLANO]
    # verbatins é o ÚLTIMO (seus filhos via subquery saem antes)
    assert ordem[-1] == "verbatins"
    # filhos de verbatins vêm antes de verbatins
    for filho in ("verbatim_embeddings", "verbatins_reclassificacoes", "verbatim_temas"):
        assert ordem.index(filho) < ordem.index("verbatins")
    # temas depois de seus filhos (verbatim_temas, temas_merges)
    assert ordem.index("verbatim_temas") < ordem.index("temas")
    assert ordem.index("temas_merges") < ordem.index("temas")
    # acoes_venda antes de temas_cruzamentos (FK cruzamento_id)
    assert ordem.index("acoes_venda") < ordem.index("temas_cruzamentos")


def test_plano_filhos_usam_subquery_de_verbatins():
    """As 3 tabelas sem empresa_id filtram por verbatim_id ∈ verbatins da empresa."""
    where = {t: w for _, t, w in zc.PLANO}
    for filho in ("verbatim_embeddings", "verbatins_reclassificacoes", "verbatim_temas"):
        assert "verbatim_id IN (SELECT id FROM verbatins WHERE empresa_id = :eid)" in where[filho]


def test_confirmar_interativo_aceita_id_e_sim(monkeypatch):
    emp = type("E", (), {"id": 6, "nome": "Pardini"})()
    for resp in ("6", "SIM", "sim", " 6 "):
        monkeypatch.setattr(builtins, "input", lambda _: resp)
        zc._confirmar_interativo(emp)  # não levanta


def test_confirmar_interativo_recusa_errado(monkeypatch):
    emp = type("E", (), {"id": 6, "nome": "Pardini"})()
    for resp in ("7", "nao", "", "n"):
        monkeypatch.setattr(builtins, "input", lambda _: resp)
        with pytest.raises(SystemExit):
            zc._confirmar_interativo(emp)


def test_confirmar_interativo_sem_tty_aborta(monkeypatch):
    emp = type("E", (), {"id": 6, "nome": "Pardini"})()

    def _raise(_):
        raise EOFError

    monkeypatch.setattr(builtins, "input", _raise)
    with pytest.raises(SystemExit):
        zc._confirmar_interativo(emp)


# ── Integração: seed + main() contra o :memory: do db_session fixture ────────


def _seed_empresa(eid: int, nome: str, com_dados: bool = True) -> None:
    """Cria empresa + fonte (+ opcional verbatim e relatorio_cache derivados)."""
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.relatorio_cache import RelatorioCache
    from src.models.verbatim import Verbatim

    with prod_db_session() as s:
        s.add(Empresa(id=eid, nome=nome, setor="saude"))
        s.flush()
        f = Fonte(
            empresa_id=eid,
            entidade_tipo="empresa",
            entidade_id=eid,
            conector_tipo="google",
            url=f"ChIJ_{eid}",
        )
        s.add(f)
        s.flush()
        if com_dados:
            s.add(
                Verbatim(
                    empresa_id=eid,
                    fonte_id=f.id,
                    texto="atendimento bom",
                    tem_texto=True,
                    hash_dedup=f"h{eid}",
                )
            )
            s.add(RelatorioCache(empresa_id=eid, escopo_hash="e", secao="s", conteudo_json="{}"))


def _count(table: str, where: str, eid: int) -> int:
    with prod_db_session() as s:
        return int(
            s.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"), {"eid": eid}).scalar()
            or 0
        )


def test_recusa_empresa_confins(db_session):
    _seed_empresa(4, "Confins", com_dados=True)
    with pytest.raises(SystemExit, match="INTOCÁVEL"):
        zc.main("4", aplicar=False)
    # nada apagado
    assert _count("verbatins", zc._DIRETO, 4) == 1


def test_dry_run_nao_apaga(db_session):
    _seed_empresa(6, "Pardini", com_dados=True)
    rc = zc.main("6", aplicar=False)
    assert rc == 0
    assert _count("verbatins", zc._DIRETO, 6) == 1
    assert _count("relatorio_cache", zc._DIRETO, 6) == 1


def test_aplicar_apaga_alvo_mantem_estrutura_e_outras(db_session, monkeypatch):
    _seed_empresa(6, "Pardini", com_dados=True)
    _seed_empresa(5, "Carbel", com_dados=True)  # NÃO pode ser tocada
    monkeypatch.setattr(builtins, "input", lambda _: "6")

    rc = zc.main("6", aplicar=True)
    assert rc == 0

    # alvo: derivados zerados
    assert _count("verbatins", zc._DIRETO, 6) == 0
    assert _count("relatorio_cache", zc._DIRETO, 6) == 0
    # alvo: estrutura preservada
    assert _count("empresas", "id = :eid", 6) == 1
    assert _count("fontes", zc._DIRETO, 6) == 1
    # empresa 5 (Carbel): TUDO intacto
    assert _count("verbatins", zc._DIRETO, 5) == 1
    assert _count("relatorio_cache", zc._DIRETO, 5) == 1
    assert _count("fontes", zc._DIRETO, 5) == 1
