"""``Empresa.sonda_grao`` — a configuração do grão da sonda (§6.22, fatia 1).

⚠️ A coluna é **DORMENTE por desenho**: nenhum consumidor a lê nesta fatia. Quem
passa a ler é a fatia 2 (o termo do prompt). Por isso o default é ``'empresa'`` — o
comportamento de hoje —, para a migração ser neutra em comportamento **e em custo**
(§13): outro default faria o próximo cron gastar N× sem ninguém pedir.

Contexto medido (§6.22.4, 03/set): "Grupo BEXP" volta artefato dos três modelos
(fintech, mineração, BMW/MINI) enquanto "Porsche Center São Paulo Oeste" é
reconhecido pelos três com detalhe correto — num grupo multimarca, o grão em que a
sonda pergunta hoje é o único sem capital relacional.

⚠️ ``htmx_salvar_empresa`` não tinha teste nenhum antes desta fatia (grep em
``tests/`` por ele voltava vazio): o de persistência aqui é o primeiro a cobri-lo.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from src.models.empresa import Empresa

VALIDOS = ("empresa", "agrupamento", "loja")


def _empresa(db_session, sfx, **kw):
    e = Empresa(nome=f"EGrao-{sfx}-{id(db_session)}", **kw)
    db_session.add(e)
    db_session.flush()
    return e


# ── default ────────────────────────────────────────────────────────────────────


def test_empresa_nasce_no_grao_empresa(db_session):
    """Neutralidade da migração: quem já existe segue no comportamento de hoje."""
    e = _empresa(db_session, "default")
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).sonda_grao == "empresa"


@pytest.mark.parametrize("grao", VALIDOS)
def test_os_tres_valores_persistem(db_session, grao):
    e = _empresa(db_session, f"v-{grao}", sonda_grao=grao)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).sonda_grao == grao


# ── constraint ─────────────────────────────────────────────────────────────────


def test_valor_fora_do_check_e_rejeitado(db_session):
    """O CHECK é a trava de última instância — o handler valida antes, mas o banco
    não confia nele (carga fora do ORM existe: foi o §4.59 defeito 4)."""
    db_session.add(Empresa(nome=f"EGrao-mau-{id(db_session)}", sonda_grao="marca"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ── persistência pela TELA ─────────────────────────────────────────────────────


def _put(client_loyall, empresa_id, **campos):
    data = {"nome": f"EGrao-tela-{empresa_id}", **campos}
    return client_loyall.put(f"/ui/empresas/{empresa_id}", data=data)


def test_tela_persiste_o_grao_escolhido(client_loyall, db_session):
    e = _empresa(db_session, "tela")
    db_session.commit()
    r = _put(client_loyall, e.id, sonda_grao="loja")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).sonda_grao == "loja"


def test_tela_com_valor_invalido_MANTEM_o_atual(db_session, client_loyall):
    """Inválido não cai para default — mantém. É o padrão do ``_ra_modo_do_form``.

    Cair para 'empresa' seria rebaixar em silêncio uma escolha já feita.
    """
    e = _empresa(db_session, "invalido", sonda_grao="loja")
    db_session.commit()
    r = _put(client_loyall, e.id, sonda_grao="galaxia")
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).sonda_grao == "loja"


def test_tela_sem_o_campo_MANTEM_o_atual(db_session, client_loyall):
    """Form antigo/parcial (sem o campo) não pode rebaixar a escolha."""
    e = _empresa(db_session, "ausente", sonda_grao="agrupamento")
    db_session.commit()
    r = _put(client_loyall, e.id)
    assert r.status_code == 200
    db_session.expire_all()
    assert db_session.get(Empresa, e.id).sonda_grao == "agrupamento"


# ── render: rótulos de produto, e o aviso de dormência ─────────────────────────


def test_modal_mostra_rotulos_de_produto_e_o_aviso(client_loyall, db_session):
    """⚠️ O aviso é obrigatório (§9): a coluna não faz nada nesta fatia, e sem ele o
    operador escolhe "por loja", salva, e acredita que mudou alguma coisa.
    """
    e = _empresa(db_session, "modal", sonda_grao="loja")
    db_session.commit()
    html = client_loyall.get(f"/ui/empresas/{e.id}/editar-modal").get_data(as_text=True)
    assert "A empresa toda (razão social)" in html
    assert "Por marca / agrupamento" in html
    assert "Por loja / unidade" in html
    assert "Ainda não tem efeito" in html
    # Asserção ESTRITA: a opção salva vem marcada. Um `or "selected" in html`
    # passaria com qualquer <option> marcada — cobertura aparente.
    assert '<option value="loja" selected>' in html
    assert '<option value="empresa" selected>' not in html
