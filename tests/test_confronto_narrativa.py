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

    body = client_loyall.get(f"/pesquisas/{p.id}/confronto").get_data(as_text=True)
    pos = [
        body.index("Pontos cegos"),
        body.index("Descompassos"),
        body.index("Consciência compartilhada"),
        body.index("Forças confirmadas"),
        body.index("Não perguntado"),
    ]
    assert pos == sorted(pos)  # seções na ordem da história
    assert "time não consegue avaliar" in body  # ponto cego com colaborador vazio
