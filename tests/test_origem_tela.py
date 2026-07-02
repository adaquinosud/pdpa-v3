"""Tests da tela ORIGEM (fatia 3): render + ordem por profundidade, links
recíprocos, gates (essência vazia / pendentes / sem análise) e o disparo.
"""

from __future__ import annotations

from datetime import datetime

import src.ui.pesquisa as ui_pesq
from src.models.empresa import Empresa
from src.models.origem import OrigemAnalise, OrigemSintese
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta

_k = [0]


def _empresa(db_session, *, com_essencia=True):
    e = Empresa(
        nome=f"EOT{id(db_session)}-{_k[0]}",
        missao="Servir bem" if com_essencia else None,
        visao="Ser referência" if com_essencia else None,
        valores="Cuidado" if com_essencia else None,
    )
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    return e


def _pesquisa(db_session, e, proposito="confronto"):
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito=proposito,
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo="agrupamento",
    )
    db_session.add(p)
    db_session.flush()
    return p


def _analise(db_session, p, sub, nivel, lado, just="j"):
    db_session.add(
        OrigemAnalise(
            pesquisa_id=p.id,
            subpilar=sub,
            nivel=nivel,
            lado=lado,
            justificativa=just,
            gerado_em=datetime.utcnow(),
        )
    )


def _pendente(db_session, p):
    """Comentário com texto e SEM classificação → pendente."""
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=1, enunciado="?", formato="mista", subpilar_alvo="D2"
    )
    db_session.add(q)
    db_session.flush()
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto="algo",
            classificado_em=None,
        )
    )
    db_session.flush()


def test_origem_renderiza_e_ordena_por_profundidade(client_loyall, db_session):
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _analise(db_session, p, "D2", "resultado", "gravidade")  # raso
    _analise(db_session, p, "P1", "essencia", "gravidade")  # fundo
    _analise(db_session, p, "Pa1", "caminho", "solidez")  # meio
    db_session.add(OrigemSintese(pesquisa_id=p.id, texto="A maioria rompe na essência."))
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "A maioria rompe na essência." in body  # síntese no topo
    # ordem por profundidade: Essência(P1) → Caminho(Pa1) → Resultado(D2)
    assert body.index("P1 ·") < body.index("Pa1 ·") < body.index("D2 ·")
    # detalhe agrupado por elo separa problemas de forças
    assert "Essência" in body and "🔴 Problemas" in body and "🟢 Forças" in body


def test_links_reciprocos(client_loyall, db_session):
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    db_session.commit()
    conf = client_loyall.get(f"/pesquisas/{p.id}/confronto").get_data(as_text=True)
    assert "Ler a profundidade (ORIGEM)" in conf
    orig = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "← Confronto" in orig


def test_gate_essencia_vazia(client_loyall, db_session):
    e = _empresa(db_session, com_essencia=False)
    p = _pesquisa(db_session, e)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "Cadastre missão, visão e valores" in body
    assert 'id="origem-form"' not in body  # sem botão de rodar
    assert "Editar empresa" in body  # link pro modal


def test_gate_pendentes(client_loyall, db_session):
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _pendente(db_session, p)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "não classificado" in body
    assert 'id="origem-form"' not in body  # não roda sobre dado incompleto


def test_sem_analise_mostra_botao_e_explicacao(client_loyall, db_session):
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert 'id="origem-form"' in body and "Ler a profundidade (ORIGEM)" in body
    assert "profundidade" in body  # explicação do que o ORIGEM faz
    assert 'id="origem-spinner"' in body and "animate-spin" in body  # spinner no submit


def test_nao_confronto_redireciona(client_loyall, db_session):
    e = _empresa(db_session)
    p = _pesquisa(db_session, e, proposito="coleta")
    db_session.commit()
    r = client_loyall.get(f"/pesquisas/{p.id}/origem")
    assert r.status_code == 302 and f"/pesquisas/{p.id}/respostas" in r.headers["Location"]


def test_disparo_flash_e_redirect(client_loyall, db_session, monkeypatch):
    """O botão dispara gerar_origem; stats viram flash; redireciona pra tela."""
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    db_session.commit()
    monkeypatch.setattr(
        "src.pesquisa.origem.gerar_origem", lambda s, pid: {"status": "ok", "analisados": 3}
    )
    r = client_loyall.post(f"/pesquisas/{p.id}/origem/gerar")
    assert r.status_code == 302 and f"/pesquisas/{p.id}/origem" in r.headers["Location"]
    body = client_loyall.get(r.headers["Location"]).get_data(as_text=True)
    assert "3 gap(s) analisado(s)" in body


def test_disparo_essencia_indisponivel_avisa(client_loyall, db_session, monkeypatch):
    e = _empresa(db_session, com_essencia=False)
    p = _pesquisa(db_session, e)
    db_session.commit()
    monkeypatch.setattr(
        "src.pesquisa.origem.gerar_origem", lambda s, pid: {"status": "essencia_indisponivel"}
    )
    r = client_loyall.post(f"/pesquisas/{p.id}/origem/gerar")
    body = client_loyall.get(r.headers["Location"]).get_data(as_text=True)
    assert "Cadastre missão, visão e valores" in body


assert ui_pesq  # usado indiretamente (rotas registradas no blueprint)


def test_cadeia_de_elos_e_gerado_em(client_loyall, db_session):
    """A cadeia mostra os 5 elos (Essência→Resultado), a cascata do elo mais fundo
    que rompe, e o gerado_em (defasagem visível)."""
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _analise(db_session, p, "P1", "essencia", "gravidade")  # rompe fundo
    _analise(db_session, p, "D2", "resultado", "gravidade")
    _analise(db_session, p, "Pa1", "caminho", "solidez")  # força
    db_session.add(OrigemSintese(pesquisa_id=p.id, texto="Rompe na essência."))
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    # cabeçalho + os 5 elos (inclusive os vazios: Significado, Propósito)
    assert "Cadeia generativa" in body
    for elo in ("Essência", "Significado", "Propósito", "Caminho", "Resultado"):
        assert elo in body
    # cascata: o elo mais fundo com gravidade é Essência (P1)
    assert "a corrente rompe aqui" in body
    # síntese vira caption; gerado_em aparece
    assert "Síntese ·" in body and "Rompe na essência." in body
    assert "Análise gerada em" in body


def test_cadeia_sem_gravidade_nao_marca_ruptura(client_loyall, db_session):
    """Só forças (solidez) → nenhum elo 'rompe' → sem marca de cascata."""
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _analise(db_session, p, "Pa3", "essencia", "solidez")  # força funda, sem gravidade
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "Cadeia generativa" in body
    assert "a corrente rompe aqui" not in body  # nada rompe


def test_cadeia_v2_chip_nome_frase_e_detalhe_agrupado(client_loyall, db_session):
    """A) chip 'sigla · nome'; frase-síntese do elo (1ª frase da justificativa);
    detalhe agrupado por elo com problemas e forças separados."""
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _analise(
        db_session,
        p,
        "P2",
        "essencia",
        "gravidade",
        just="A ruptura mora na essência. Trai a promessa.",
    )
    _analise(
        db_session, p, "Pa3", "essencia", "solidez", just="Encarna o cuidado declarado. Sólida."
    )
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    # chip com sigla + nome
    assert "P2 · Qualidade da Entrega" in body
    # frase-síntese do elo (1ª frase, derivada da justificativa)
    assert "A ruptura mora na essência" in body
    # detalhe agrupado por elo, problemas e forças separados (mesmo elo: Essência)
    assert "🔴 Problemas" in body and "🟢 Forças" in body


def test_cadeia_svg_diagrama(client_loyall, db_session):
    """A cadeia agora é diagrama SVG: <svg>, chips-pílula coloridos (fill-emerald/
    fill-rose), spine + cascata vermelha nos elos herdeiros, marca da ruptura."""
    e = _empresa(db_session)
    p = _pesquisa(db_session, e)
    _analise(db_session, p, "P1", "essencia", "gravidade")  # rompe no topo → cascata p/ baixo
    _analise(db_session, p, "Pa1", "caminho", "solidez")  # força
    _analise(db_session, p, "D2", "resultado", "gravidade")
    db_session.commit()
    body = client_loyall.get(f"/pesquisas/{p.id}/origem").get_data(as_text=True)
    assert "<svg" in body and 'aria-label="Cadeia generativa' in body
    # chips-pílula por lado
    assert "fill-rose-100" in body and "fill-emerald-100" in body
    # chip traz sigla · nome
    assert "P1 · Calibração da Promessa" in body
    # cascata: barra lateral + spine vermelhos nos elos herdeiros
    assert "fill-rose-300" in body and "stroke-rose-400" in body
    # marca da ruptura
    assert "◀ a corrente rompe aqui" in body
