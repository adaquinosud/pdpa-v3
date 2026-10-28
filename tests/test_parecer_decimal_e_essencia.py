"""Uma fonte só por decimal — e a essência declarada é LITERAL.

Duas superfícies, **o mesmo defeito**: a camada de DADO decidindo o que é da
camada de EXIBIÇÃO.

⚠️ **O ratio.** ``parecer.py`` devolvia ``"0,06"`` (string já com vírgula) e o
template passou a aplicar ``| virg`` — que faz ``float("0,06")`` → ``ValueError``
→ ``"—"``. O ratio virou travessão em DUAS superfícies (card "A voz pública" e
Ato 2 · Intensidade), e a suíte inteira passou: **asserção de TEXTO aceita
placeholder.** Por isso os testes abaixo travam o **TIPO**.

⚠️ **A essência.** O template preferia ``d.sintese.essencia`` — a paráfrase do LLM —
sob o rótulo "A essência declarada". Medido na 27: a visão *"de acordo com os
nossos indicadores e das montadoras"* saiu impressa como *"reconhecido por
clientes e montadoras"*. **O LLM trocou o juiz declarado**, e num Parecer cujo Ato 3
acusa falha com o cliente isso atribui à empresa uma promessa que ela não fez.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.verbatim import Verbatim
from src.relatorios.parecer import PROMPT_SINTESE, montar_dados
from src.utils.fmt import virg

_ENV = Environment(loader=FileSystemLoader("templates"))
_ENV.filters["virg"] = virg


def _render(d):
    return _ENV.get_template("relatorios/parecer.html").render(d=d)


def _empresa(db_session, sfx, dados=(), **campos):
    """dados = [(conector, tipo, n)] no subpilar Pa2 (vira a ferida)."""
    e = Empresa(nome=f"EDec-{sfx}-{id(db_session)}", **campos)
    db_session.add(e)
    db_session.flush()
    for conector, tipo, n in dados:
        f = Fonte(
            empresa_id=e.id,
            entidade_tipo="empresa",
            entidade_id=e.id,
            conector_tipo=conector,
            url=f"u-{conector}-{tipo}",
            ativo=True,
            status="ativa",
        )
        db_session.add(f)
        db_session.flush()
        for i in range(n):
            db_session.add(
                Verbatim(
                    empresa_id=e.id,
                    fonte_id=f.id,
                    subpilar="Pa2",
                    tipo=tipo,
                    texto=f"t{i}",
                    tem_texto=True,
                )
            )
    db_session.commit()
    return e


# a 27 em miniatura: 35 detratores (26 no RA), 2 promotores → ratio 0,06
_BEXP = [
    ("reclame_aqui", "detrator", 26),
    ("google_maps", "detrator", 9),
    ("google_maps", "promotor", 2),
]


# ── o TIPO, que é o que a asserção de texto não pegou ──────────────────────────


def test_os_ratios_sao_NUMERO_nunca_string_formatada(db_session):
    """⚠️ String aqui é a bomba: o template formata, e `virg("0,06")` → "—".

    Trava o TIPO justamente porque a saída ERRADA ("—") é texto válido — foi assim
    que a regressão passou por 1964 testes."""
    d = montar_dados(_empresa(db_session, "tipo", _BEXP).id)
    for campo, valor in (
        ("tese.voz.ratio", d["tese"]["voz"]["ratio"]),
        ("ato2b.concentracao.ratio", d["ato2b"]["concentracao"]["ratio"]),
    ):
        assert not isinstance(valor, str), f"{campo} voltou a formatar na camada de dado"
        assert isinstance(valor, (int, float)), f"{campo} devia ser número, veio {type(valor)}"


def test_nota_media_e_numero_ou_None_nunca_placeholder(db_session):
    """A MESMA bomba, que estava armada e invisível: `virg("—")` devolve "—" por
    acaso (cai no except), então trocar o literal de fallback bastaria para expor."""
    nm = montar_dados(_empresa(db_session, "nota", _BEXP).id)["ato2a"]["nota_media"]
    assert nm is None or isinstance(nm, (int, float)), f"nota_media veio {type(nm)}"


def test_sem_base_o_ratio_e_None_e_nao_o_travessao(db_session):
    """Ausência é ESTADO (§9) — quem decide como ela aparece é a exibição."""
    d = montar_dados(_empresa(db_session, "vazio").id)
    assert d["tese"]["voz"]["ratio"] is None
    assert d["ato2b"]["concentracao"]["ratio"] is None


# ── o impresso, que é o que vai ao cliente ─────────────────────────────────────


def test_o_impresso_mostra_o_ratio_e_NAO_o_travessao_duplicado(db_session):
    """A regressão exata reportada: 'o ratio é — — 35 detratores, 2 promotores'."""
    d = montar_dados(_empresa(db_session, "imp", _BEXP).id)
    html = _render(d)
    esperado = virg(d["tese"]["voz"]["ratio"])
    assert f"o ratio é <strong>{esperado}</strong>" in html
    assert "o ratio é <strong>—</strong>" not in html
    assert "— —" not in html, "travessão duplicado: placeholder + o traço literal da frase"
    assert f"ratio {esperado}" in html, "Ato 2 · Intensidade também"


# ── a essência: LITERAL, sempre ────────────────────────────────────────────────

_VISAO_CADASTRO = "de acordo com os nossos indicadores e das montadoras"
_VISAO_LLM = "reconhecido por clientes e montadoras"


def test_a_essencia_impressa_e_a_do_CADASTRO(db_session):
    d = montar_dados(_empresa(db_session, "ess", visao=_VISAO_CADASTRO, missao="Missão crua.").id)
    html = _render(d)
    assert _VISAO_CADASTRO in html
    assert "Missão crua." in html


def test_a_parafrase_do_LLM_NAO_vence_o_cadastro(db_session):
    """⚠️ O caso da 27. Cache antigo ainda tem a chave `essencia`; ela é ignorada.

    Não basta ter tirado do prompt: os pareceres já cacheados continuam carregando
    a paráfrase, e é o TEMPLATE que tem de recusá-la."""
    d = montar_dados(_empresa(db_session, "stale", visao=_VISAO_CADASTRO).id)
    d["sintese"] = {"essencia": {"visao": _VISAO_LLM}, "abertura": "x"}
    html = _render(d)
    assert _VISAO_CADASTRO in html, "o literal do cadastro tem de vencer"
    assert _VISAO_LLM not in html, "a paráfrase do LLM não entra no impresso"


def test_o_prompt_nao_pede_mais_a_essencia():
    """A saída sai do prompt — senão o LLM segue pagando tokens para gerá-la."""
    txt = Path(PROMPT_SINTESE).read_text(encoding="utf-8")
    assert "Produza SETE saídas:" in txt
    assert "``essencia`` — objeto" not in txt, "o item de saída continua no prompt"
    assert '"essencia": {"missao"' not in txt, "o exemplo de JSON ainda pede o campo"
    assert "essencia_declarada" in txt, "a ENTRADA continua — `ausentes` depende dela"


# ── o ESCOPO do ratio: subpilar, nunca a empresa ───────────────────────────────
# 28/10/2026, empresa 29: o impresso dizia "No diagnóstico geral, o ratio é 0,11" e a
# síntese escreveu "ratio agregado de 0,11". Os dois números eram do subpilar-ferida;
# a razão da empresa na base inteira era 8,6. Lido por um conselho, o 0,11 sem escopo
# vira o número da empresa — a leitura oposta do mesmo cliente.


def test_o_impresso_nomeia_o_SUBPILAR_ao_dar_o_ratio(db_session):
    d = montar_dados(_empresa(db_session, "esc", _BEXP).id)
    html = _render(d)
    nome = d["tese"]["subpilar_nome"]
    assert f"só em {nome}, o ratio é <strong>" in html
    assert "diagnóstico geral" not in html


def test_os_fatos_da_sintese_carregam_o_subpilar_do_ratio(db_session):
    from src.relatorios.parecer import _facts_sintese

    d = montar_dados(_empresa(db_session, "facts", _BEXP).id)
    iv = _facts_sintese(d)["intensidade_voz_total"]
    assert iv["subpilar"] == d["tese"]["subpilar_nome"]
    assert "só deste subpilar" in iv["base"]


# ── ZERO casos RA é AUSÊNCIA DE BASE, não desempenho (§9/§10) ──────────────────
# 28/10/2026, empresa 29: o impresso dizia "responde 0%" e "0% (0 de 0)" a uma
# cooperativa que responde 100% no site do ReclameAqui — o RA dela nunca tinha sido
# coletado. O conselho leria o 0% como medição.

_SEM_RA = [("google_maps", "detrator", 9), ("google_maps", "promotor", 2)]


def test_sem_caso_RA_o_impresso_declara_e_NAO_imprime_zero(db_session):
    d = montar_dados(_empresa(db_session, "semra", _SEM_RA).id)
    assert d["ato2a"]["sem_base"] is True
    html = _render(d)
    assert "Sem base no ReclameAqui" in html
    assert "(0 de 0)" not in html
    assert "responde <strong>0%</strong>" not in html
    assert "dos 0 casos" not in html
    assert d["ato2a"]["manchete"] == {"l1": "Sem base", "l2": "no ReclameAqui."}


def test_sem_caso_RA_a_sintese_NAO_recebe_numero_do_RA(db_session):
    from src.relatorios.parecer import _facts_sintese

    f = _facts_sintese(montar_dados(_empresa(db_session, "semraf", _SEM_RA).id))
    assert f["conduta"] == {
        "sem_base": True,
        "motivo": "nenhuma reclamação do ReclameAqui coletada; conduta não medida",
    }
    assert f["concentracao_ra"]["sem_base"] is True
    assert "pct" not in f["concentracao_ra"]
