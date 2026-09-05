"""O card da Vitrine da tese — as três camadas juntas.

A ``<tr>`` de `parecer.html` mentia por **três caminhos independentes**, e cada
conserto isolado tornaria o card mais convincente sem torná-lo verdadeiro:

a) **guard** — a linha não tinha ``{% if %}`` nenhum e afirmava SEM sondagem;
b) **copy** — *"as IAs já ecoam as cobranças"* era literal fixo que afirmava ANTES
   do dado, e o ``"—"`` era interpolado DUAS vezes (indicador + meio da frase);
c) **medição** — ``n_concorrentes = len(encaminhamentos)`` contava Procon,
   consumidor.gov.br, Reclame Aqui e o SAC do FABRICANTE como concorrente. Medido
   na exec 28: 33 destinos, boa parte não é concorrência.

⚠️ E o A5 junto, porque é a mesma mentira na prosa: ``tem_sonda`` não entrava em
``_facts_sintese`` e ``encaminhamentos`` chegava ``[]`` nos dois casos — o colapso
falsy do §6.21.0 na terceira superfície.
"""

from __future__ import annotations

from jinja2 import Environment, FileSystemLoader

from src.utils.fmt import virg as _virg

from src.models.empresa import Empresa
from src.relatorios.parecer import montar_dados

# ⚠️ O `virg` é registrado como FILTRO no app (`src/app.py:87`), e `parecer.html` o
# usa nos decimais. Um `Environment` puro não o tem, e o render quebra com
# "No filter named 'virg'" — o template tem de renderizar aqui do mesmo jeito que em
# produção. Fonte única da função: `src.utils.fmt.virg`.
_ENV = Environment(loader=FileSystemLoader("templates"))
_ENV.filters["virg"] = _virg

AFIRMACAO_ANTIGA = "as IAs já ecoam as cobranças"


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa(db_session, sfx):
    e = Empresa(nome=f"ECard-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.commit()
    return e


def _d(db_session, sfx, **over):
    d = montar_dados(_empresa(db_session, sfx).id)
    d["tese"]["vitrine"].update(over.pop("vitrine", {}))
    d.update(over)
    return d


# ── (b) a afirmação não medida morreu ──────────────────────────────────────────


def test_a_oracao_que_afirmava_antes_do_dado_SUMIU(db_session):
    """Era literal fixo: aparecia com ou sem sonda, com ou sem número."""
    for estado in ({}, {"tem_sonda": True}):
        html = _render(_d(db_session, f"afirm{len(estado)}", **estado))
        assert AFIRMACAO_ANTIGA not in html


def _linha_vitrine(html):
    """Recorta só a <tr> da vitrine — outras linhas têm '—' legítimo (o ratio sem
    base em 'A voz pública'), e asserção ampla acusaria falso."""
    i = html.find("A vitrine")
    assert i > 0, "linha da vitrine não renderizou"
    fim = html.find("</tr>", i)  # variável evita o E203 que o black cria no slice
    return html[i:fim]


def test_placeholder_nao_e_interpolado_dentro_da_frase(db_session):
    """⚠️ O '—' entrava duas vezes, e a segunda quebrava a oração ao meio:
    'encaminham o insatisfeito para — concorrentes nomeados'."""
    linha = _linha_vitrine(_render(_d(db_session, "ph")))
    assert "para — concorrente" not in linha
    assert "<strong>—</strong>" not in linha, "placeholder não entra em oração"


# ── (a) o guard ────────────────────────────────────────────────────────────────


def test_sem_sonda_o_card_DECLARA_em_vez_de_afirmar(db_session):
    d = _d(db_session, "sem")
    assert d["tem_sonda"] is False
    html = _render(d)
    assert "a vitrine não foi medida" in html
    assert "concorrente" not in html.split("A vitrine")[1][:400]


# ── (c) a medição ──────────────────────────────────────────────────────────────


def test_conta_SO_concorrentes_nao_a_lista_toda(db_session):
    """33 destinos, 4 concorrentes → o card diz 4, e diz de quantos."""
    d = _d(
        db_session,
        "conta",
        tem_sonda=True,
        vitrine={"n_concorrentes": 4, "categorizado": True, "n_destinos": 33},
    )
    html = _render(d)
    assert "4 concorrente(s)" in html
    assert "de 33 destinos citados" in html
    assert "33 concorrente" not in html, "contar a lista toda é a mentira original"


def test_zero_concorrentes_e_RESULTADO_nao_ausencia(db_session):
    """Sondou e ninguém citou rival — isso é achado, e o card diz."""
    d = _d(
        db_session,
        "zero",
        tem_sonda=True,
        vitrine={"n_concorrentes": 0, "categorizado": True, "n_destinos": 12},
    )
    html = _render(d)
    assert "não nomearam nenhum concorrente" in html
    assert "canais de reclamação e o SAC do fabricante" in html


def test_leitura_sem_categoria_DECLARA_que_nao_da_para_contar(db_session):
    """⚠️ Leitura anterior ao prompt v3: sem categoria, o card NÃO chuta para cima."""
    d = _d(
        db_session,
        "semcat",
        tem_sonda=True,
        vitrine={"n_concorrentes": None, "categorizado": False, "n_destinos": 33},
    )
    html = _render(d)
    assert "não dá para dizer quantos destinos são concorrentes" in html
    assert "33 concorrente" not in html


# ── A5 · o estado chega ao LLM ─────────────────────────────────────────────────


def test_facts_carregam_o_ESTADO_da_sonda_nao_so_a_lista(db_session):
    """⚠️ O colapso falsy: [] significava 'não sondado' E 'sondado e ninguém citado'.
    O LLM escrevia a leitura conservadora por sorte da instrução, não por saber."""
    from src.relatorios.parecer import _facts_sintese

    d = montar_dados(_empresa(db_session, "facts").id)
    f = _facts_sintese(d)
    assert f["sonda_estado"] == "nao_sondado"
    assert "concorrentes_n" in f

    d["tem_sonda"] = True
    assert _facts_sintese(d)["sonda_estado"] == "sem_encaminhamento"

    d["ato2c"]["encaminhamentos"] = ["Rival A"]
    assert _facts_sintese(d)["sonda_estado"] == "com_dado"
