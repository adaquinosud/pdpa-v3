"""CP-#2c: a saída da noturna é durável (relatorio_cache), lida do banco.

Prova:
1. O resumo da coleta vem de ``coletas_execucoes`` (DB), não de JSONL em ``data/``.
2. É gravado em ``relatorio_cache`` (secao="noturna", escopo empresa-wide).
3. Idempotência (Opção 1, última sobrescreve): rodar 2x → 1 linha, não duplica.
4. A saída não depende de ``data/`` (o módulo nem tem DATA_DIR/leitura de artefato).
"""

from __future__ import annotations

from datetime import datetime

import scripts.gen_relatorio_noturna as gen
from src.models.coleta_execucao import ColetaExecucao
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.relatorio_cache import RelatorioCache


def _setup(session, nome: str):
    emp = Empresa(nome=nome)
    session.add(emp)
    session.flush()
    f1 = Fonte(
        empresa_id=emp.id,
        entidade_tipo="local",
        entidade_id=1,
        conector_tipo="google",
        url="https://maps.example/f1",
        ativo=True,
    )
    f2 = Fonte(
        empresa_id=emp.id,
        entidade_tipo="local",
        entidade_id=2,
        conector_tipo="instagram",
        url="https://insta.example/f2",
        ativo=True,
    )
    session.add_all([f1, f2])
    session.flush()
    # f1: concluída com 10 coletados / 7 novos; f2: erro
    session.add_all(
        [
            ColetaExecucao(
                empresa_id=emp.id,
                fonte_id=f1.id,
                status="concluido",
                iniciado_em=datetime(2026, 6, 1, 2, 0, 0),
                concluido_em=datetime(2026, 6, 1, 2, 5, 0),
                coletados=10,
                novos=7,
                duplicados=3,
                erros=0,
            ),
            ColetaExecucao(
                empresa_id=emp.id,
                fonte_id=f2.id,
                status="erro",
                iniciado_em=datetime(2026, 6, 1, 2, 0, 0),
                concluido_em=datetime(2026, 6, 1, 2, 1, 0),
                coletados=0,
                novos=0,
                mensagem_erro="timeout: fonte não respondeu\nstacktrace...",
            ),
        ]
    )
    session.commit()
    return emp.id, f1.id, f2.id


def test_resumo_vem_de_coletas_execucoes(db_session):
    emp_id, f1, f2 = _setup(db_session, "Empresa Saida Duravel A")

    conteudo = gen.gerar_resumo_noturna(db_session, emp_id)

    assert conteudo is not None
    coleta = conteudo["coleta"]
    assert coleta["fontes_processadas"] == 2
    assert coleta["fontes_concluidas"] == 1
    assert coleta["fontes_erro"] == 1
    assert coleta["verbatins_coletados_total"] == 10
    assert coleta["verbatins_novos_total"] == 7
    assert coleta["verbatins_duplicados_total"] == 3
    # erro traz fonte/conector e a 1ª linha da mensagem (sem stacktrace)
    assert coleta["erros"] == [
        {"fonte_id": f2, "conector": "instagram", "erro": "timeout: fonte não respondeu"}
    ]


def test_grava_no_relatorio_cache_empresa_wide(db_session):
    emp_id, _, _ = _setup(db_session, "Empresa Saida Duravel B")

    gen.gerar_resumo_noturna(db_session, emp_id)

    rows = db_session.query(RelatorioCache).filter_by(empresa_id=emp_id, secao="noturna").all()
    assert len(rows) == 1
    assert rows[0].escopo_hash == gen._escopo_hash_empresa(emp_id)
    assert '"coleta"' in rows[0].conteudo_json  # JSON estruturado persistido


def test_idempotente_rodar_2x_nao_duplica(db_session):
    emp_id, _, _ = _setup(db_session, "Empresa Saida Duravel C")

    gen.gerar_resumo_noturna(db_session, emp_id)
    gen.gerar_resumo_noturna(db_session, emp_id)  # 2ª vez sobrescreve

    rows = db_session.query(RelatorioCache).filter_by(empresa_id=emp_id, secao="noturna").all()
    assert len(rows) == 1  # DELETE+INSERT → 1 linha, não duplica


def test_empresa_inexistente_retorna_none(db_session):
    assert gen.gerar_resumo_noturna(db_session, "não existe") is None


def test_saida_nao_depende_de_data():
    """O módulo não lê nem escreve artefatos em data/ (sem DATA_DIR nem leitores)."""
    assert not hasattr(gen, "DATA_DIR")
    assert not hasattr(gen, "_ler_jsonl")
    assert not hasattr(gen, "_ultimo_arquivo")
