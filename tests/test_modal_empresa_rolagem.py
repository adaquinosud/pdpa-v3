"""O modal de edição da empresa tem teto de altura e rodapé fixo (04/set).

⚠️ ESTE TESTE **NÃO VALIDA O VISUAL**. Ele é guarda de regressão sobre o markup:
pega remoção acidental das classes, e a estrutura DOM (o submit dentro do form, a
faixa rolável separada do rodapé). **Se a tela funciona é teste de dono, em janela
real** — regra de ouro visual, e esta fatia é impossível de validar por suíte.

O defeito: o card crescia sem limite e o rodapé com "Salvar" caía abaixo do corte
da viewport — a empresa ficava impossível de salvar. O campo novo da §6.22 fatia 1
REVELOU; não causou (o form já tinha 10 blocos).
"""

from __future__ import annotations

from html.parser import HTMLParser

from src.models.empresa import Empresa


class _Pilha(HTMLParser):
    """Guarda a pilha de tags de cada campo — prova DOM, não substring."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha, self.campos, self.submit_em_form = [], [], None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("input", "select", "textarea") and d.get("name"):
            self.campos.append((d["name"], "form" in self.pilha))
        if tag == "button" and d.get("type") == "submit":
            self.submit_em_form = "form" in self.pilha
        if tag not in ("input", "br", "img", "hr", "meta", "link"):
            self.pilha.append(tag)

    def handle_endtag(self, tag):
        if tag in self.pilha:
            while self.pilha and self.pilha.pop() != tag:
                pass


def _html(client_loyall, db_session):
    e = Empresa(nome=f"EModal-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    return client_loyall.get(f"/ui/empresas/{e.id}/editar-modal").get_data(as_text=True)


def test_card_tem_teto_de_altura_e_e_coluna_flex(client_loyall, db_session):
    html = _html(client_loyall, db_session)
    assert "max-h-[85vh]" in html, "sem teto o card cresce além da viewport"
    assert "flex flex-col max-h-[85vh]" in html


def test_faixa_de_campos_rola_e_pode_encolher(client_loyall, db_session):
    """⚠️ `min-h-0` junto do overflow: sem ele um filho flex não encolhe abaixo do
    conteúdo e o `overflow-y-auto` nunca ativa — o card volta a estourar."""
    html = _html(client_loyall, db_session)
    assert "overflow-y-auto min-h-0 flex-1" in html


def test_rodape_nao_rola(client_loyall, db_session):
    html = _html(client_loyall, db_session)
    assert "shrink-0" in html
    assert "border-t border-loyall-100 shrink-0" in html, "rodapé precisa ficar fixo"


def test_submit_continua_dentro_do_form(client_loyall, db_session):
    """A reestruturação não pode ter tirado o botão do form — seria salvar quebrado."""
    p = _Pilha()
    p.feed(_html(client_loyall, db_session))
    assert p.submit_em_form is True


def test_todos_os_campos_seguem_dentro_do_form(client_loyall, db_session):
    """Prova DOM: reestruturar container é onde campo escapa do form sem ninguém ver
    (e aí 'ausente mantém' engole a edição em silêncio)."""
    p = _Pilha()
    p.feed(_html(client_loyall, db_session))
    fora = [n for n, dentro in p.campos if not dentro]
    assert fora == [], f"campos fora do <form>: {fora}"
    assert "sonda_grao" in {n for n, _ in p.campos}
