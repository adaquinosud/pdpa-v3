"""Tests da tela de confronto enriquecida (5b.3): cobertura (perguntado/não),
categorização narrativa, silêncio total visível, ordem das seções.
"""

from __future__ import annotations

from datetime import datetime

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.models.respondente import Respondente, Resposta
from src.models.verbatim import Verbatim
from src.pesquisa.confronto import gap_confronto

_k = [0]


def _pesquisa(db_session):
    e = Empresa(nome=f"ECN{id(db_session)}-{_k[0]}")
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
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="confronto",
        titulo="Conf",
        status="pronta",
        anonima=True,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    return e.id, f.id, p


def _verb(db_session, e_id, f_id, sub, tipo, n=3):
    for _ in range(n):
        _k[0] += 1
        db_session.add(
            Verbatim(
                empresa_id=e_id,
                fonte_id=f_id,
                texto="x",
                subpilar=sub,
                tipo=tipo,
                data_criacao_original=datetime.utcnow(),
                hash_dedup=f"h{_k[0]}",
            )
        )


def _pergunta(db_session, p, sub_alvo):
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=_k[0], enunciado="?", formato="mista", subpilar_alvo=sub_alvo
    )
    _k[0] += 1
    db_session.add(q)
    db_session.flush()
    return q


def _resp(db_session, p, q, *, sub_class=None, val=None, nota=None):
    """Cria uma Resposta. Comentário classificado (sub_class/val + classificado_em)
    e/ou nota. Comentário sem valência clara: val='inativo'."""
    r = Respondente(pesquisa_id=p.id, entidade_tipo="empresa")
    db_session.add(r)
    db_session.flush()
    tem_texto = sub_class is not None or val is not None
    db_session.add(
        Resposta(
            respondente_id=r.id,
            pergunta_id=q.id,
            valor_texto="comentario" if tem_texto else None,
            valor_nota=nota,
            subpilar_classificado=sub_class,
            valencia_classificada=val,
            classificado_em=datetime.utcnow() if tem_texto else None,
        )
    )
    db_session.flush()


def _por_sub(gap):
    return {g["subpilar"]: g for g in gap}


# ── Parte 1: cobertura + silêncio total visível ──────────────────────────────


def test_cobertura_perguntado_vs_nao(db_session):
    """subpilar com pergunta → perguntado; cliente-only sem pergunta → não perguntado."""
    e_id, f_id, p = _pesquisa(db_session)
    qd = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, qd, sub_class="D2", val="promotor")
    _verb(db_session, e_id, f_id, "A1", "detrator")  # cliente tem A1, sem pergunta
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))
    assert g["D2"]["cobertura"] == "perguntado"
    assert g["A1"]["cobertura"] == "nao_perguntado"


def test_silencio_total_aparece(db_session):
    """Perguntado, cliente sem dado, time só inativo → antes SUMIA. Agora aparece."""
    e_id, f_id, p = _pesquisa(db_session)
    q = _pergunta(db_session, p, "P3")
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo")  # sem sinal claro
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id))
    assert "P3" in g  # não some mais
    assert g["P3"]["estado"] == "sem_sinal" and g["P3"]["cobertura"] == "perguntado"


# ── Parte 2: categorização de cada caso ──────────────────────────────────────


def test_categorias_de_cada_caso(db_session):
    e_id, f_id, p = _pesquisa(db_session)
    # descompasso superestima: cliente detrator, time promotor
    q_d2 = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, q_d2, sub_class="D2", val="promotor")
    # descompasso subestima: cliente promotor, time detrator
    q_d1 = _pergunta(db_session, p, "D1")
    _verb(db_session, e_id, f_id, "D1", "promotor")
    _resp(db_session, p, q_d1, sub_class="D1", val="detrator")
    # ponto cego: cliente detrator, time perguntado mas só inativo (silêncio)
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")
    # consciência compartilhada: gap alinhado, ambos detrator
    q_pa2 = _pergunta(db_session, p, "Pa2")
    _verb(db_session, e_id, f_id, "Pa2", "detrator")
    _resp(db_session, p, q_pa2, sub_class="Pa2", val="detrator")
    # força: gap alinhado, ambos promotor
    q_pa3 = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor")
    _resp(db_session, p, q_pa3, sub_class="Pa3", val="promotor")
    # não perguntado: cliente detrator A1, sem pergunta A1
    _verb(db_session, e_id, f_id, "A1", "detrator")
    # outros (só colaborador): pergunta A2, time promotor, cliente sem dado
    q_a2 = _pergunta(db_session, p, "A2")
    _resp(db_session, p, q_a2, sub_class="A2", val="promotor")
    db_session.commit()

    g = _por_sub(gap_confronto(db_session, p.id))
    assert g["D2"]["categoria"] == "descompasso" and g["D2"]["gap"]["direcao"] == "superestima"
    assert g["D1"]["categoria"] == "descompasso" and g["D1"]["gap"]["direcao"] == "subestima"
    assert g["P1"]["categoria"] == "ponto_cego" and g["P1"]["colaborador"] is None
    assert g["Pa2"]["categoria"] == "consciencia_compartilhada"
    assert g["Pa3"]["categoria"] == "forca"
    assert g["A1"]["categoria"] == "nao_perguntado"
    assert g["A2"]["categoria"] == "outros"  # só colaborador é residual


# ── Parte 3: a tela agrupa nas seções na ordem definida ──────────────────────


def test_secoes_na_ordem(client_loyall, db_session):
    e_id, f_id, p = _pesquisa(db_session)
    # um de cada: ponto cego, descompasso, consciência, força, não perguntado
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")  # ponto cego
    q_d2 = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, q_d2, sub_class="D2", val="promotor")  # descompasso
    q_pa2 = _pergunta(db_session, p, "Pa2")
    _verb(db_session, e_id, f_id, "Pa2", "detrator")
    _resp(db_session, p, q_pa2, sub_class="Pa2", val="detrator")  # consciência
    q_pa3 = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor")
    _resp(db_session, p, q_pa3, sub_class="Pa3", val="promotor")  # força
    _verb(db_session, e_id, f_id, "A1", "detrator")  # não perguntado
    db_session.commit()

    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    pos = [
        body.index("Pontos cegos"),
        body.index("Descompassos"),
        body.index("Consciência compartilhada"),
        body.index("Forças confirmadas"),
        body.index("Não perguntado"),
    ]
    assert pos == sorted(pos)  # seções na ordem da história
    assert "time não consegue avaliar" in body  # ponto cego com colaborador vazio


def test_rotulos_claros_sem_jargao(client_loyall, db_session):
    """Frente A: as direções e subtítulos usam linguagem clara, não jargão."""
    e_id, f_id, p = _pesquisa(db_session)
    q_d2 = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, q_d2, sub_class="D2", val="promotor")  # superestima
    q_d1 = _pergunta(db_session, p, "D1")
    _verb(db_session, e_id, f_id, "D1", "promotor")
    _resp(db_session, p, q_d1, sub_class="D1", val="detrator")  # subestima
    q_pa2 = _pergunta(db_session, p, "Pa2")
    _verb(db_session, e_id, f_id, "Pa2", "detrator")
    _resp(db_session, p, q_pa2, sub_class="Pa2", val="detrator")  # consciência
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "o time acha melhor do que o cliente sente" in body
    assert "o time se cobra mais do que o cliente" in body
    assert "os dois reconhecem o problema" in body
    # o jargão cru não aparece mais no texto visível
    assert "time mais crítico" not in body


# ── Frente B: temas do cliente por subpilar (5b.4) ───────────────────────────

from datetime import date  # noqa: E402

from src.models.agrupamento import Agrupamento  # noqa: E402
from src.models.pesquisa import PesquisaEscopo  # noqa: E402
from src.models.temas import TemaCache  # noqa: E402


def _agrupamento(db_session, e_id, nome="Ag"):
    a = Agrupamento(empresa_id=e_id, nome=f"{nome}{_k[0]}")
    _k[0] += 1
    db_session.add(a)
    db_session.flush()
    return a


def _tema(db_session, e_id, ag_id, sub, tipo, label, volume):
    db_session.add(
        TemaCache(
            empresa_id=e_id,
            agrupamento_id=ag_id,
            subpilar=sub,
            tipo=tipo,
            tema_label=label,
            volume=volume,
            percentual=0.1,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 6, 1),
            hash_escopo="h",
        )
    )


def test_temas_valencia_dominante(db_session):
    """Ponto cego detrator → temas de detrator (reclamações); força promotor →
    temas de promotor (elogios). Nunca a valência errada."""
    e_id, f_id, p = _pesquisa(db_session)
    a = _agrupamento(db_session, e_id)
    p.entidade_tipo = "agrupamento"
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    db_session.flush()
    # ponto cego P1: cliente detrator, time inativo
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")
    _tema(db_session, e_id, a.id, "P1", "detrator", "demora no atendimento", 10)
    _tema(db_session, e_id, a.id, "P1", "promotor", "NÃO deve aparecer", 99)  # valência errada
    # força Pa3: cliente promotor, time promotor (gap alinhado)
    q_pa3 = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor")
    _resp(db_session, p, q_pa3, sub_class="Pa3", val="promotor")
    _tema(db_session, e_id, a.id, "Pa3", "promotor", "equipe atenciosa", 8)
    db_session.commit()

    g = _por_sub(gap_confronto(db_session, p.id, escopo=None))
    p1_temas = [t["tema_label"] for t in g["P1"]["temas_cliente"]]
    assert p1_temas == ["demora no atendimento"]  # só detrator (a valência dominante)
    assert "NÃO deve aparecer" not in p1_temas
    pa3_temas = [t["tema_label"] for t in g["Pa3"]["temas_cliente"]]
    assert pa3_temas == ["equipe atenciosa"]  # promotor = elogios


def test_temas_multi_agrupamento_soma(db_session):
    """Multi-agrupamento: mesmo tema_label soma volume via agrupamento_id IN."""
    e_id, f_id, p = _pesquisa(db_session)
    a1 = _agrupamento(db_session, e_id, "A1x")
    a2 = _agrupamento(db_session, e_id, "A2x")
    p.entidade_tipo = "agrupamento"
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a1.id))
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a2.id))
    db_session.flush()
    q = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo")
    _tema(db_session, e_id, a1.id, "D2", "detrator", "fila grande", 4)
    _tema(db_session, e_id, a2.id, "D2", "detrator", "fila grande", 6)  # mesmo tema
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id, escopo=None))
    temas = g["D2"]["temas_cliente"]
    assert temas == [{"tema_label": "fila grande", "volume": 10}]  # 4+6 somados


def test_gate_loja_sem_vazamento(db_session):
    """Escopo loja → temas_indisponiveis, temas vazios, SEM fallback empresa."""
    e_id, f_id, p = _pesquisa(db_session)
    a = _agrupamento(db_session, e_id)
    p.entidade_tipo = "local"  # pesquisa de loja
    db_session.flush()
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")
    # tema existe no agrupamento — NÃO pode vazar numa pesquisa de loja
    _tema(db_session, e_id, a.id, "P1", "detrator", "vazamento proibido", 50)
    _tema(db_session, e_id, None, "P1", "detrator", "empresa proibido", 50)  # nível empresa
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id, escopo=None))
    assert g["P1"]["temas_indisponiveis"] is True
    assert g["P1"]["temas_cliente"] == []  # nada vazou


def test_top_n_temas(db_session):
    """Limita a 3 temas por subpilar, os de maior volume."""
    e_id, f_id, p = _pesquisa(db_session)
    a = _agrupamento(db_session, e_id)
    p.entidade_tipo = "agrupamento"
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    db_session.flush()
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")
    for i, vol in enumerate([1, 5, 3, 9, 7]):
        _tema(db_session, e_id, a.id, "P1", "detrator", f"tema{i}", vol)
    db_session.commit()
    g = _por_sub(gap_confronto(db_session, p.id, escopo=None))
    temas = g["P1"]["temas_cliente"]
    assert len(temas) == 3
    assert [t["volume"] for t in temas] == [9, 7, 5]  # top-3 por volume desc


def test_tela_mostra_temas_e_aviso(client_loyall, db_session):
    """A tela lista 'Cliente reclama de:' (agrupamento) e o aviso na loja."""
    # agrupamento → mostra temas
    e_id, f_id, p = _pesquisa(db_session)
    a = _agrupamento(db_session, e_id)
    p.entidade_tipo = "agrupamento"
    db_session.add(PesquisaEscopo(pesquisa_id=p.id, entidade_id=a.id))
    db_session.flush()
    q_p1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q_p1, sub_class="sem_lastro", val="inativo")
    _tema(db_session, e_id, a.id, "P1", "detrator", "demora", 10)
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "Cliente reclama de:" in body and "demora" in body

    # loja → aviso, sem temas
    e2, f2, p2 = _pesquisa(db_session)
    p2.entidade_tipo = "local"
    db_session.flush()
    q2 = _pergunta(db_session, p2, "P1")
    _verb(db_session, e2, f2, "P1", "detrator")
    _resp(db_session, p2, q2, sub_class="sem_lastro", val="inativo")
    db_session.commit()
    body2 = client_loyall.get(f"/empresas/{p2.empresa_id}/pesquisas/{p2.id}/confronto").get_data(
        as_text=True
    )
    assert "apenas para pesquisas por agrupamento" in body2


# ── PONTO 1: a coluna Time faz o vazio falar; PONTO 2: manchete ──────────────


def test_time_nota_sem_valencia_explica(client_loyall, db_session):
    """Ponto cego: time deu nota mas comentário inativo → 'não apontou o problema'."""
    e_id, f_id, p = _pesquisa(db_session)
    q = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")  # cliente detrator
    _resp(db_session, p, q, sub_class="sem_lastro", val="inativo", nota=4)  # nota + sem valência
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "nota 4.0" in body and "não apontou o problema" in body


def test_time_valencia_sem_nota_explica(client_loyall, db_session):
    """Força: time promotor por comentário, sem nota → 'sem nota específica'."""
    e_id, f_id, p = _pesquisa(db_session)
    q = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor")  # cliente promotor
    _resp(db_session, p, q, sub_class="Pa3", val="promotor")  # valência, nota=None
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "sem nota específica" in body


def test_time_ambos_sinais(client_loyall, db_session):
    """Descompasso: time promotor + nota → 'promotor · nota X' (os dois sinais)."""
    e_id, f_id, p = _pesquisa(db_session)
    q = _pergunta(db_session, p, "D2")
    _verb(db_session, e_id, f_id, "D2", "detrator")  # cliente detrator
    _resp(db_session, p, q, sub_class="D2", val="promotor", nota=4)  # valência + nota
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "nota 4.0" in body and "promotor" in body


def test_manchete_contagem_no_topo(client_loyall, db_session):
    """PONTO 2: manchete com contagem por categoria antes da lista."""
    e_id, f_id, p = _pesquisa(db_session)
    # 1 ponto cego
    q1 = _pergunta(db_session, p, "P1")
    _verb(db_session, e_id, f_id, "P1", "detrator")
    _resp(db_session, p, q1, sub_class="sem_lastro", val="inativo")
    # 1 força
    q2 = _pergunta(db_session, p, "Pa3")
    _verb(db_session, e_id, f_id, "Pa3", "promotor")
    _resp(db_session, p, q2, sub_class="Pa3", val="promotor")
    db_session.commit()
    body = client_loyall.get(f"/empresas/{p.empresa_id}/pesquisas/{p.id}/confronto").get_data(
        as_text=True
    )
    assert "1 ponto(s) cego(s)" in body and "1 força(s)" in body
    # manchete vem ANTES do bloco de pontos cegos
    assert body.index("1 ponto(s) cego(s)") < body.index("🔴 Pontos cegos")
