"""Fix: subpilar inválido ('sem_lastro') travava a edição da pergunta.

- O dropdown não tinha o valor → renderizava vazio; editar re-enviava "" e
  ``atualizar_pergunta`` pulava → o subpilar nunca saía (usuário preso).
- Fix: (1) dropdown mostra opção ⚠ + aviso quando o subpilar é inválido;
  (2) ``atualizar_pergunta`` grava campos PRESENTES (troca/limpa pega);
  (3) mensagens de regra viram acionáveis (não "regra N").
"""

from __future__ import annotations

from flask import render_template

from src.models.empresa import Empresa
from src.models.pesquisa import Pesquisa, PesquisaPergunta
from src.pesquisa.persistencia import atualizar_pergunta


def _pesq(db_session, subpilar, status="rascunho", formato="mista"):
    e = Empresa(nome=f"ESub-{subpilar}")
    db_session.add(e)
    db_session.flush()
    p = Pesquisa(
        empresa_id=e.id,
        natureza="interna",
        proposito="coleta",
        titulo="S",
        status=status,
        anonima=False,
        entidade_tipo="empresa",
    )
    db_session.add(p)
    db_session.flush()
    q = PesquisaPergunta(
        pesquisa_id=p.id, ordem=1, enunciado="Como foi?", formato=formato, subpilar_alvo=subpilar
    )
    db_session.add(q)
    db_session.commit()
    return e, p, q


# ── (2) atualizar_pergunta grava campos presentes ─────────────────────────────


def test_atualizar_troca_subpilar_invalido_persiste(db_session):
    """Trocar 'sem_lastro' → 'A2' persiste (o caso que o usuário achava travado)."""
    _e, _p, q = _pesq(db_session, "sem_lastro")
    atualizar_pergunta(db_session, q.id, enunciado="Como foi?", subpilar_alvo="A2")
    db_session.refresh(q)
    assert q.subpilar_alvo == "A2"


def test_atualizar_limpa_subpilar_com_vazio(db_session):
    """subpilar_alvo presente-mas-None LIMPA (antes pulava, deixando 'sem_lastro')."""
    _e, _p, q = _pesq(db_session, "sem_lastro")
    atualizar_pergunta(db_session, q.id, enunciado="Como foi?", subpilar_alvo=None)
    db_session.refresh(q)
    assert q.subpilar_alvo is None


def test_atualizar_campo_ausente_nao_toca_subpilar(db_session):
    """Reescrita (só opcoes_json, subpilar_alvo AUSENTE) não apaga o subpilar."""
    _e, _p, q = _pesq(db_session, "A2")
    atualizar_pergunta(db_session, q.id, opcoes_json='{"tipo":"nota","pontos":5}')
    db_session.refresh(q)
    assert q.subpilar_alvo == "A2"  # preservado


def test_atualizar_nao_zera_enunciado(db_session):
    """enunciado é obrigatório — presente-mas-vazio NÃO zera (evita NOT NULL)."""
    _e, _p, q = _pesq(db_session, "A2")
    atualizar_pergunta(db_session, q.id, enunciado=None, subpilar_alvo="D1")
    db_session.refresh(q)
    assert q.enunciado == "Como foi?" and q.subpilar_alvo == "D1"


# ── (1) dropdown mostra ⚠ para subpilar inválido ─────────────────────────────


def test_revisar_subpilar_invalido_mostra_aviso(client_loyall, db_session):
    e, p, _q = _pesq(db_session, "sem_lastro")
    html = client_loyall.get(f"/empresas/{e.id}/pesquisas/{p.id}/revisar").get_data(as_text=True)
    assert "⚠ Sem pilar definido — escolha um" in html  # opção destacada no dropdown
    assert "não tem um pilar válido" in html  # aviso acima do seletor


def test_revisar_subpilar_valido_sem_aviso(client_loyall, db_session):
    e, p, _q = _pesq(db_session, "A2")
    html = client_loyall.get(f"/empresas/{e.id}/pesquisas/{p.id}/revisar").get_data(as_text=True)
    assert "não tem um pilar válido" not in html
    assert "Sem pilar definido" not in html


# ── (3) mensagem acionável (não "regra N") ───────────────────────────────────


def test_mensagem_regra_e_acionavel(app, db_session):
    """Render de _cards com um veredito R4 → frase acionável, sem 'regra 4'."""
    e, p, q = _pesq(db_session, "A2")
    from src.ui.pesquisa import _subpilares_opcoes

    perguntas = [
        {
            "id": q.id,
            "ordem": 1,
            "enunciado": "Como foi?",
            "porque": None,
            "formato": "mista",
            "subpilar_alvo": "A2",
            "gerada_por_ancora": False,
            "regras": [
                {
                    "regra": 4,
                    "severidade": "bloqueia",
                    "motivo": "escala ausente ou inválida",
                    "reescrita": None,
                }
            ],
        }
    ]
    with app.test_request_context():
        html = render_template(
            "pesquisa/_cards.html",
            perguntas=perguntas,
            pesquisa_id=p.id,
            empresa_id=e.id,
            status="rascunho",
            subpilares=_subpilares_opcoes(),
            validou=True,
            tem_bloqueio=True,
        )
    assert "Sem escala de nota — defina uma escala de 1 a 5" in html
    assert "regra 4 —" not in html  # jargão de número sumiu
