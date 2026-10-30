"""Uma chave para "o que fazer primeiro" (30/out): ``painel.chave_sequencia``.

A Sequência de ação dos impressos ordenava por (pilar no Lastro, ratio), duplicada inline nos
dois relatórios; o "Top por perspectiva" das sugestões saía na ordem ALFABÉTICA do código do
subpilar (A1–A3 primeiro). Agora as duas usam a mesma chave — (grupo, pilar, ratio), com
grupo 0 = travando com volume ≥ piso, 1 = travando abaixo do piso, 2 = o resto. A sequência
filtra os travados e corta em 5 (quem fica de fora é declarado); a seção ordena os 12.
O piso decide a ordem por dentro e não aparece escrito: o impresso mostra a BASE do ratio
("3 críticas em 4 manifestações") — sem selo, sem rótulo (🔴 já é N1 na mesma página).
"""

from __future__ import annotations

from datetime import datetime as _dt

import pytest

from tests.test_relatorios import _empresa, _fake_llm, _stamp_hashes  # noqa: F401


def _agg(**subs):
    return {k: {"ratio": r, "total": t} for k, (r, t) in subs.items()}


def test_base_pequena_rebaixa_mas_nao_corta():
    """O caso que motivou os grupos: P2 com 5 manifestações viria antes do D2 com 31 só por
    ser Precisão. Rebaixa para depois dos travados com base — e continua na lista."""
    from src.api.painel import sequencia_de_acao

    agg = _agg(
        P1=(1.90, 100), P2=(0.80, 5), D2=(0.11, 31), Pa2=(0.50, 12), A2=(0.33, 4), A1=(5.0, 3)
    )
    assert sequencia_de_acao(agg) == (["D2", "P2", "Pa2", "A2"], {})


def test_chave_ordena_os_12_sem_filtro():
    """Na seção não há filtro: quem não trava vai para o grupo 2, na ordem do Lastro. Era o
    buraco da chave sem grupo — o P1 em 1,90 passava na frente do D2 em 0,11."""
    from src.api.painel import chave_sequencia

    agg = _agg(P1=(1.90, 100), D2=(0.11, 31), A2=(0.33, 4), D1=(None, 0), Pa1=(3.0, 50))
    assert sorted(agg, key=lambda s: chave_sequencia(s, agg)) == ["D2", "A2", "P1", "D1", "Pa1"]


def test_corte_leva_o_grupo_1_primeiro_e_declara_quem_ficou_de_fora():
    from src.api.painel import sequencia_de_acao

    agg = _agg(
        P1=(0.2, 40),
        P2=(0.3, 40),
        P3=(0.4, 40),
        D1=(0.5, 40),
        D2=(0.6, 40),
        D3=(0.7, 40),
        Pa1=(0.1, 2),
    )
    subs, fora = sequencia_de_acao(agg)
    assert subs == ["P1", "P2", "P3", "D1", "D2"]
    assert fora == {0: 1, 1: 1}  # D3 com base, Pa1 com base pequena


def test_piso_e_o_do_gargalo():
    """O piso da chave é o do gargalo — uma constante, não duas."""
    from src.api.engajamento import VOLUME_CONFIANCA_ALTA
    from src.api.painel import grupo_sequencia

    piso = VOLUME_CONFIANCA_ALTA
    assert grupo_sequencia({"ratio": 0.5, "total": piso}) == 0
    assert grupo_sequencia({"ratio": 0.5, "total": piso - 1}) == 1
    assert grupo_sequencia({"ratio": 1.0, "total": 999}) == 2  # empate não trava
    assert grupo_sequencia(None) == 2


def _macros(client_loyall):
    return client_loyall.application.jinja_env.get_template("relatorios/_macros.html").module


def test_base_por_extenso(client_loyall):
    m = _macros(client_loyall)
    assert str(m.base(3, 4)) == "3 críticas em 4 manifestações"
    assert str(m.base(1, 1)) == "1 crítica em 1 manifestação"
    assert str(m.base(None, None)) == "0 críticas em 0 manifestações"


def test_linha_de_quem_ficou_de_fora(client_loyall):
    m = _macros(client_loyall)
    txt = " ".join(str(m.linha_fora({0: 1, 1: 2})).split())
    assert "Mais 3 subpilares travados fora da lista: 1 com base, 2 com base pequena." in txt
    assert not str(
        m.linha_fora(
            {},
        )
    ).strip()  # ninguém de fora → nenhuma linha
    assert "30" not in txt  # o piso não aparece escrito


@pytest.fixture
def conta(client_loyall, db_session):
    """D2 trava com base (25 det, 5 prom = 30); A1 trava com base pequena (3 det, 1 prom);
    P1 não trava (10 prom, 2 det). Uma sugestão de cada, na mesma perspectiva."""
    from src.models.diagnostico import LeituraDiagnostico
    from src.models.sugestao_estrutural import SugestaoEstrutural
    from src.models.verbatim import Verbatim

    e = _empresa(client_loyall, "seq")
    loc = client_loyall.post(f"/api/empresas/{e['id']}/locais", json={"nome": "L"}).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJseq"}
    ).get_json()
    for sub, tipo, n in [
        ("D2", "detrator", 25),
        ("D2", "promotor", 5),
        ("A1", "detrator", 3),
        ("A1", "promotor", 1),
        ("P1", "promotor", 10),
        ("P1", "detrator", 2),
    ]:
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e["id"],
                    fonte_id=f["id"],
                    local_id=loc["id"],
                    texto=f"v{i}",
                    subpilar=sub,
                    tipo=tipo,
                    tem_texto=True,
                    data_criacao_original=_dt(2026, 5, 1),
                    hash_dedup=f"hseq{sub}{tipo}{i}-{_dt.utcnow().timestamp()}",
                )
            )
    db_session.add(
        LeituraDiagnostico(
            empresa_id=e["id"], subpilar="D2", leitura="Disponibilidade travada.", acao="SLA."
        )
    )
    for sub in ("A1", "D2", "P1"):
        db_session.add(
            SugestaoEstrutural(
                empresa_id=e["id"],
                subpilar=sub,
                perspectiva="processos",
                acao=f"SUG-{sub}",
                justificativa="j",
                ordem=0,
            )
        )
    db_session.commit()
    _stamp_hashes(db_session, e["id"])
    return e["id"]


@pytest.mark.parametrize("tipo", ["diagnostico_pontual", "resumo_executivo"])
def test_impresso_usa_a_mesma_chave_na_sequencia_e_na_secao(client_loyall, conta, tipo):
    h = client_loyall.get(f"/empresas/{conta}/relatorios/{tipo}").get_data(as_text=True)
    assert "Sequência de ação — regra de execução" in h  # um título, nos dois relatórios
    assert "Sequência de Lastro" not in h and "Sequência de ação recomendada" not in h

    seq = h.split("Sequência de ação — regra de execução", 1)[1]
    seq = seq.split("</p>", 1)[0]
    assert seq.index("<strong>D2</strong>") < seq.index("<strong>A1</strong>")
    assert "<strong>P1</strong>" not in seq  # não trava, não entra
    assert "(ratio 0,33 · 3 críticas em 4 manifestações)" in seq  # a base, não um selo
    assert "Regra: primeiro o que está travando" in h
    assert "🔴" not in seq  # 🔴 já é N1 na mesma página: nada de selo na sequência

    sec = h.split("Top por perspectiva", 1)[1]
    # Alfabeto daria A1, D2; a chave sem grupo daria P1, D2. A chave dá D2, A1.
    assert sec.index("SUG-D2") < sec.index("SUG-A1")
    assert "SUG-P1" not in sec  # terceira da frente: fora do top 2
    assert "🔴 4" not in sec


def test_travado_por_mostra_a_base(client_loyall):
    """A linha 🚩 do Mapa de Lastro mostrava ratio sem base ("em 0,11 (28 detratores)")."""
    m = _macros(client_loyall)
    p = {
        "ratio": 0.8,
        "gargalo_por": [
            {"subpilar": "D2", "nome": "Agilidade", "ratio": 0.11, "det": 28, "total": 31}
        ],
    }
    assert "D2 Agilidade em 0,11 (28 críticas em 31 manifestações)" in str(
        m.linha_abaixo_do_pilar(p)
    )


def test_gargalo_travado_por_leva_o_total():
    """Pa1 bom pela soma, Pa2 crítico com base: o pilar é travado PELO subpilar."""
    from src.api.painel import gargalo_detalhe, gargalo_travado_por

    agg = {
        "Pa1": {"ratio": 30.0, "total": 62, "det": 2, "prom": 60, "conv": 0, "faixa": "excelente"},
        "Pa2": {"ratio": 0.03, "total": 36, "det": 35, "prom": 1, "conv": 0, "faixa": "critico"},
    }
    tp = gargalo_travado_por(agg, gargalo_detalhe(agg))
    assert [(x["subpilar"], x["total"]) for x in tp] == [("Pa2", 36)]
