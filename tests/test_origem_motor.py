"""Tests do motor ORIGEM (fatia 2): gerar_origem com gerar_fn fake (rede nunca no
CI), upsert, gate de essência vazia, lado determinístico (força=solidez /
problema=gravidade), e a regra de temas por agrupamento.
"""

from __future__ import annotations

from datetime import date, datetime

from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.origem import OrigemAnalise, OrigemSintese
from src.models.pesquisa import Pesquisa, PesquisaEscopo, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.temas import TemaCache
from src.models.verbatim import Verbatim
from src.pesquisa.origem import gerar_origem

_k = [0]


def _empresa(db_session, *, com_essencia=True):
    e = Empresa(
        nome=f"EOR{id(db_session)}-{_k[0]}",
        missao="Servir bem quem confia na gente" if com_essencia else None,
        visao="Ser referência" if com_essencia else None,
        valores="Cuidado" if com_essencia else None,
    )
    _k[0] += 1
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="excel_manual",
        url="u",
        autenticacao_tipo="publica",
        status="ativa",
    )
    db_session.add(f)
    db_session.flush()
    return e, f


def _pesquisa_agrup(db_session, e):
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="confronto",
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo="agrupamento",
    )
    db_session.add(p)
    db_session.flush()
    a = Agrupamento(empresa_id=e.id, nome=f"Ag{_k[0]}")
    _k[0] += 1
    db_session.add(a)
    db_session.flush()
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    db_session.flush()
    return p, a


def _verb(db_session, e, f, sub, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e.id,
                fonte_id=f.id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"h{_k[0]}",
            )
        )


def _pergunta(db_session, p, sub):
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=_k[0], enunciado="?", formato="mista", subpilar_alvo=sub
    )
    _k[0] += 1
    db_session.add(q)
    db_session.flush()
    return q


def _resp(db_session, p, q, *, sub_class=None, val=None):
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto="c",
            subpilar_classificado=sub_class,
            valencia_classificada=val,
            classificado_em=datetime.utcnow(),
        )
    )
    db_session.flush()


def _tema(db_session, e, ag_id, sub, tipo, label, vol):
    db_session.add(
        TemaCache(
            empresa_id=e.id,
            agrupamento_id=ag_id,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=vol,
            percentual=0.1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )


def _cenario_ponto_cego_e_forca(db_session, e, f, p, a):
    """P1 ponto cego (cliente detrator, time silêncio) + Pa3 força (ambos promotor)."""
    q1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e, f, "P1", "detrator")
    _resp(db_session, p, q1, sub_class="sem_lastro", val="inativo")
    _tema(db_session, e, a.id, "P1", "detrator", "demora", 10)
    q2 = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e, f, "Pa3", "promotor")
    _resp(db_session, p, q2, sub_class="Pa3", val="promotor")
    _tema(db_session, e, a.id, "Pa3", "promotor", "equipe atenciosa", 8)


def _fake_llm(captura=None):
    def _fn(system, user):
        if captura is not None:
            captura.append((system, user))
        return {
            "gaps": [
                {
                    "subpilar": "P1",
                    "nivel": "essencia",
                    "justificativa": "trai a missão de servir bem",
                },
                {
                    "subpilar": "Pa3",
                    "nivel": "significado",
                    "justificativa": "encarna o cuidado declarado",
                },
            ],
            "sintese": "A maioria rompe fundo; aja na essência.",
        }

    return _fn


def test_gate_essencia_vazia_nao_chama_llm(db_session):
    e, f = _empresa(db_session, com_essencia=False)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)
    db_session.commit()
    chamou = []
    out = gerar_origem(db_session, p.id, gerar_fn=lambda sy, u: chamou.append(1) or {})
    assert out["status"] == "essencia_indisponivel"
    assert chamou == []  # LLM NÃO foi chamado
    assert db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id).count() == 0


def test_gerar_origem_persiste_analise_e_sintese(db_session):
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)
    db_session.commit()
    captura: list = []
    out = gerar_origem(db_session, p.id, gerar_fn=_fake_llm(captura))
    assert out == {"status": "ok", "analisados": 2}
    # a essência e os temas foram ao prompt
    _sys, user = captura[0]
    assert "Servir bem" in user and "demora" in user and "equipe atenciosa" in user
    por_sub = {a.subpilar: a for a in db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id)}
    assert por_sub["P1"].nivel == "essencia" and por_sub["Pa3"].nivel == "significado"
    assert db_session.get(OrigemSintese, p.id).texto == "A maioria rompe fundo; aja na essência."


def test_lado_deterministico_forca_solidez_problema_gravidade(db_session):
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)
    db_session.commit()
    gerar_origem(db_session, p.id, gerar_fn=_fake_llm())
    por_sub = {a.subpilar: a for a in db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id)}
    assert por_sub["P1"].lado == "gravidade"  # ponto cego (problema)
    assert por_sub["Pa3"].lado == "solidez"  # força


def test_upsert_re_rodar_sobrescreve(db_session):
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)
    db_session.commit()
    gerar_origem(db_session, p.id, gerar_fn=_fake_llm())

    # 2ª rodada com nível diferente → sobrescreve, sem duplicar
    def _fake2(system, user):
        return {
            "gaps": [{"subpilar": "P1", "nivel": "caminho", "justificativa": "z"}],
            "sintese": "novo",
        }

    out = gerar_origem(db_session, p.id, gerar_fn=_fake2)
    assert out == {"status": "ok", "analisados": 1}
    rows = db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id).all()
    assert len(rows) == 1 and rows[0].subpilar == "P1" and rows[0].nivel == "caminho"
    assert db_session.get(OrigemSintese, p.id).texto == "novo"


def test_nivel_invalido_do_llm_coerce(db_session):
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)
    db_session.commit()

    def _fake_lixo(system, user):
        return {"gaps": [{"subpilar": "P1", "nivel": "XPTO", "justificativa": "z"}], "sintese": "s"}

    gerar_origem(db_session, p.id, gerar_fn=_fake_lixo)
    row = db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id, subpilar="P1").one()
    assert row.nivel == "resultado"  # coerce ao domínio (CHECK do banco não aceitaria XPTO)


def test_temas_loja_sobem_pro_agrupamento_pai(db_session):
    """Pesquisa de LOJA: o ORIGEM usa os temas do agrupamento-pai da loja."""
    e, f = _empresa(db_session)
    a = Agrupamento(empresa_id=e.id, nome=f"AgPai{_k[0]}")
    _k[0] += 1
    db_session.add(a)
    db_session.flush()
    loja = Local(empresa_id=e.id, nome="Loja 1", agrupamento_id=a.id)
    db_session.add(loja)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="confronto",
        titulo="C",
        status="pronta",
        anonima=True,
        entidade_tipo="local",
    )
    db_session.add(p)
    db_session.flush()
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=loja.id))
    db_session.flush()
    q1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e, f, "P1", "detrator")
    _resp(db_session, p, q1, sub_class="sem_lastro", val="inativo")
    _tema(db_session, e, a.id, "P1", "detrator", "tema-do-pai", 10)  # tema no agrupamento-pai
    db_session.commit()
    captura: list = []
    gerar_origem(db_session, p.id, gerar_fn=_fake_llm(captura))
    _sys, user = captura[0]
    assert "tema-do-pai" in user  # subiu pro agrupamento-pai da loja


# ── v2: natureza (sistêmico/individual) + prática do Caminho, determinísticas ──


def test_natureza_e_pratica_por_pilar():
    from src.pesquisa.origem import natureza_de, pratica_de

    # P/D = sistêmico; Pa/A = individual. Prática: P→Integridade, D→Presença,
    # Pa→Conexão, A→Contribuição.
    assert natureza_de("P1") == "sistemico" and pratica_de("P2") == "integridade"
    assert natureza_de("D2") == "sistemico" and pratica_de("D3") == "presenca"
    assert natureza_de("Pa3") == "individual" and pratica_de("Pa1") == "conexao"
    assert natureza_de("A1") == "individual" and pratica_de("A2") == "contribuicao"
    # fora dos 4 pilares → None (não quebra)
    assert natureza_de("sem_lastro") is None and pratica_de("sem_lastro") is None


def test_prompt_recebe_natureza_e_pratica(db_session):
    """O input por gap carrega pilar + natureza + prática; o system explica as 2."""
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)  # P1 sistêmico + Pa3 individual
    db_session.commit()
    captura: list = []
    gerar_origem(db_session, p.id, gerar_fn=_fake_llm(captura))
    system, user = captura[0]
    # natureza (tipo de remédio) por gap
    assert "sistêmico" in user and "individual" in user
    # prática interna do Caminho por gap
    assert "Integridade" in user and "Conexão" in user
    assert "Precisão" in user and "Parceria" in user
    # o system prompt ensina as 2 camadas
    assert "TIPO DE REMÉDIO" in system and "PRÁTICA INTERNA do Caminho" in system


# ── Estabilização (recalibração): nível primeiro, coerência, temperatura ─────


def test_incoerente_heuristica():
    from src.pesquisa.origem import _incoerente

    # 1ª frase nomeia OUTRO elo (essência) mas o selo é resultado → incoerente
    assert _incoerente("resultado", "A ruptura mora na essência da empresa. Etc.")
    # 1ª frase nomeia o elo marcado → coerente
    assert not _incoerente("essencia", "Na essência, contradiz o que declara ser.")
    # nenhum nome de elo na 1ª frase → não sinaliza
    assert not _incoerente("caminho", "O método de atendimento não sustenta a promessa.")


def test_gerar_origem_sinaliza_incoerencia(db_session):
    """Justificativa que nomeia outro elo → 'avisos' (não bloqueia; persiste)."""
    e, f = _empresa(db_session)
    p, a = _pesquisa_agrup(db_session, e)
    _cenario_ponto_cego_e_forca(db_session, e, f, p, a)  # P1 + Pa3
    db_session.commit()

    def _fake_incoerente(system, user):
        return {
            "gaps": [
                {
                    "subpilar": "P1",
                    "nivel": "resultado",
                    "justificativa": "A ruptura está na essência.",
                },
                {
                    "subpilar": "Pa3",
                    "nivel": "significado",
                    "justificativa": "encarna o cuidado declarado",
                },
            ],
            "sintese": "s",
        }

    out = gerar_origem(db_session, p.id, gerar_fn=_fake_incoerente)
    assert out["status"] == "ok" and out["analisados"] == 2
    assert out.get("avisos") == ["P1"]  # P1: selo resultado, texto diz essência
    # mas persiste mesmo assim (não bloqueia)
    assert db_session.query(OrigemAnalise).filter_by(pesquisa_id=p.id).count() == 2


def test_prompt_nivel_primeiro_e_ancoras():
    from src.pesquisa.origem import _SYSTEM

    # nível é o passo 1 (decisão primária)
    assert "PASSO 1" in _SYSTEM and "CLASSIFIQUE O NÍVEL" in _SYSTEM
    # natureza/prática são passo 2 (vocabulário, não critério)
    assert "PASSO 2" in _SYSTEM and "NÃO decidem o nível" in _SYSTEM
    # regra de coerência texto×selo
    assert "PRIMEIRA frase" in _SYSTEM
    # 5 exemplos-âncora neutros (um por elo)
    assert "o pedido saiu trocado uma vez" in _SYSTEM  # resultado
    assert "trata cada cliente como um número" in _SYSTEM  # essência


def test_gerar_via_llm_forwarda_temperature(monkeypatch):
    """A temperatura chega ao _call_claude_with_retry (habilitação do ponto 4)."""
    import src.classifier.classifier_v3 as cls

    captura = {}

    class _Bloco:
        text = '{"ok": 1}'

    class _Resp:
        content = [_Bloco()]

    def _fake(system_blocks, user, modelo, max_tokens, temperature=None):
        captura["temp"] = temperature
        return _Resp()

    monkeypatch.setattr(cls, "_call_claude_with_retry", _fake)
    from src.pesquisa.llm import gerar_via_llm

    out = gerar_via_llm("sys", "usr", temperature=0.2)
    assert out == {"ok": 1} and captura["temp"] == 0.2
