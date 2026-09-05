"""O Parecer para de afirmar sobre sondagem de IA inexistente (§6.21, fatia 1).

Antes desta fatia a peça **declarava** a ausência e **concluía** sobre ela na mesma
página: o `{% else %}` que escreve "Sem sondagem de IA ainda" fica seis linhas acima
de duas colunas que afirmam o que a sonda teria dito. Ausência preenchida com
afirmação, num impresso que vai ao cliente (§9).

Duas pré-condições INDEPENDENTES governam a manchete do Ato 1:
- a **essência** vem do CADASTRO (`emp.missao/visao/valores`, `parecer.py:675`);
- a **sondagem** vem do instrumento (`rep.tem_dado`).

⚠️ ESCOPO DECLARADO — esta fatia cobre "NUNCA SONDADO", **não** cobre "sondado com
resultado vazio". O último teste deste arquivo PRENDE essa não-correção: se ele
começar a falhar, alguém consertou meia-§6.21 pela porta dos fundos.
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

MANCHETE_VITRINE = "Eis o que elas"
FRASE_DOURA = "a IA vê promotor onde os casos públicos são detratores"
FRASE_ATO1 = "Não sabem quem você é"
COPY_SEM_ESSENCIA = "não há o que confrontar com o que as IAs respondem"
COPY_SEM_SONDA = "Sem sondagem de IA nesta competência"


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa(db_session, sfx, **kw):
    e = Empresa(nome=f"ESonda-{sfx}-{id(db_session)}", **kw)
    db_session.add(e)
    db_session.flush()
    db_session.commit()
    return e


# ── Ato 2 · Vitrine ────────────────────────────────────────────────────────────


def test_sem_sonda_a_vitrine_nao_e_impressa(db_session):
    """O caso da BEXP: nunca sondada. A página inteira bloqueia (§10)."""
    e = _empresa(db_session, "novitrine")
    d = montar_dados(e.id)
    assert d["tem_sonda"] is False
    html = _render(d)
    assert MANCHETE_VITRINE not in html
    assert FRASE_DOURA not in html, "a conclusão sobre a sonda não pode sobreviver"


def test_com_sonda_a_vitrine_volta_a_ser_impressa(db_session):
    """Caminho FELIZ do guard: com sondagem, a página existe como antes.

    Sem este teste o guard poderia estar suprimindo sempre e ninguém notaria — o
    PDF só ficaria mais curto.
    """
    e = _empresa(db_session, "comvitrine")
    d = montar_dados(e.id)
    d["tem_sonda"] = True
    html = _render(d)
    assert MANCHETE_VITRINE in html
    assert FRASE_DOURA in html


# ── Ato 1 · a manchete e as duas pré-condições ─────────────────────────────────


def test_sem_essencia_declara_o_que_falta_e_o_que_resolve(db_session):
    """Sem cadastro de missão/visão/valores, a frase vira estado declarado (§9)."""
    e = _empresa(db_session, "semess")
    d = montar_dados(e.id)
    html = _render(d)
    assert FRASE_ATO1 not in html, "dedução de cadastro ausente não é achado de medição"
    assert COPY_SEM_ESSENCIA in html


def test_com_essencia_sem_sonda_declara_a_falta_da_SONDA(db_session):
    """A essência existe, mas não houve confronto — e o motivo é OUTRO.

    As duas ausências têm remédios diferentes (cadastrar × sondar), então a copy
    tem de distinguir: dizer 'falta cadastro' quando o cadastro existe seria mandar
    o cliente resolver o problema errado.
    """
    e = _empresa(db_session, "essemsonda", missao="Servir bem.", valores="Ética.")
    d = montar_dados(e.id)
    assert d["tem_sonda"] is False
    html = _render(d)
    assert FRASE_ATO1 not in html
    assert COPY_SEM_SONDA in html
    assert COPY_SEM_ESSENCIA not in html


def test_com_essencia_e_com_sonda_a_manchete_volta(db_session):
    """Caminho feliz do Ato 1: as duas pré-condições satisfeitas."""
    e = _empresa(db_session, "completo", missao="Servir bem.", visao="Ser referência.")
    d = montar_dados(e.id)
    d["tem_sonda"] = True
    html = _render(d)
    assert FRASE_ATO1 in html
    assert COPY_SEM_ESSENCIA not in html
    assert COPY_SEM_SONDA not in html


# ── ⚠️ O teste que TRAVA a não-correção ────────────────────────────────────────


def test_sondado_com_resultado_vazio_AINDA_imprime_as_frases_fixas(db_session):
    """⚠️ ESCOPO: esta fatia NÃO conserta o estado 'sondado, resultado vazio'.

    Com `tem_dado=True` e nenhum encaminhamento/defasagem, a página renderiza e as
    frases FIXAS de `ato2c.doura/ecoa` (literais em `parecer.py:978` e `:983`)
    seguem afirmando o que a sonda teria dito. É o defeito conhecido, deixado de pé
    POR DECISÃO — o código hoje nem consegue separar "não sondado" de "sondado e
    vazio" (`[]` para os dois, §6.21.0).

    **Frente dona: §6.21** (o discriminador). Quando ela chegar, este teste morre —
    e ter de removê-lo é o sinal de que ela chegou no lugar certo.
    """
    e = _empresa(db_session, "vazio")
    d = montar_dados(e.id)
    d["tem_sonda"] = True  # sondou…
    assert d["ato2c"]["encaminhamentos"] == [], "…e não trouxe nada"
    assert d["ato2c"]["doura"]["subpilares"] is None
    html = _render(d)
    assert FRASE_DOURA in html, (
        "se isto falhar, a §6.21 foi resolvida (ótimo) ou alguém fez meia-correção "
        "pela porta dos fundos (não ótimo) — confira qual antes de apagar o teste"
    )
