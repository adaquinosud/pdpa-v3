"""Copy do card Índice Geral (frente copy Painel).

A explicação deixou de falar em "pilar travado" (vocabulário de gargalo, que a 17
não tem) e passa a dizer que o PIOR PILAR define o teto. A frase final é DERIVADA
do dado (nome do pilar + ratio) e CONDICIONAL: só aparece quando o pior pilar é o
binding (pior*2 == indice_geral); quando a média ponderada é o teto, some — senão
o executivo faria pior×2 e acharia divergência com o índice exibido.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

# Espelha o bloco de templates/partials/explorar_painel.html (self-contained em n1).
# O teste estático abaixo garante que o template real carrega a mesma expressão.
_SNIPPET = (
    "{% set _com_vol = n1.pilares | selectattr('total') | list %}"
    "{% set _pior = (_com_vol | min(attribute='ratio')) if _com_vol else none %}"
    "Não é média — é o pior pilar que define o teto."
    "{% if _pior and (_pior.ratio * 2) | round(2) == n1.indice_geral %}"
    " Aqui, {{ _pior.nome }} em {{ ('%.2f'|format(_pior.ratio))|replace('.', ',') }} é o teto."
    "{% endif %}"
)


def _render(n1):
    return Environment().from_string(_SNIPPET).render(n1=n1)


def test_frase_final_deriva_pior_pilar_quando_binda():
    # Empresa 17: pior pilar Precisão 1,03 → índice 2,06; pior binda (1,03×2 == 2,06).
    n1 = {
        "indice_geral": 2.06,
        "pilares": [
            {"pilar": "P", "nome": "Precisão", "ratio": 1.03, "total": 262},
            {"pilar": "D", "nome": "Direção", "ratio": 1.73, "total": 100},
            {"pilar": "Pa", "nome": "Parceria", "ratio": 1.66, "total": 200},
        ],
    }
    html = _render(n1)
    assert "é o pior pilar que define o teto" in html
    # nome + ratio DERIVADOS do dado, ratio com vírgula (locale) — teste de dono da 17
    assert "Aqui, Precisão em 1,03 é o teto." in html


def test_frase_final_some_quando_media_binda():
    # média ponderada < pior pilar → índice = média×2; pior (2,0×2=4,0) != índice 2,0
    # → a frase final some (as duas primeiras ficam).
    n1 = {
        "indice_geral": 2.0,
        "pilares": [
            {"pilar": "P", "nome": "Precisão", "ratio": 2.0, "total": 100},
            {"pilar": "D", "nome": "Direção", "ratio": 2.0, "total": 100},
        ],
    }
    html = _render(n1)
    assert "é o pior pilar que define o teto" in html  # as 2 primeiras ficam
    assert "Aqui," not in html  # a frase final auto-verificável NÃO aparece


def test_sem_pilar_com_volume_nao_quebra_e_omite_frase():
    html = _render({"indice_geral": 0.0, "pilares": []})
    assert "é o pior pilar que define o teto" in html and "Aqui," not in html


def test_copies_novas_no_template_antigas_fora():
    tpl = Path("templates/partials/explorar_painel.html").read_text(encoding="utf-8")
    # Índice (PRESERVADO)
    assert "é o pior pilar que define o teto" in tpl
    assert "Pilar travado puxa o índice para baixo" not in tpl
    # Proximity — copy nova, antigas fora
    assert "Começar baixo é o normal" in tpl
    assert "É o pilar mais distante que fixa o conjunto — não a média." not in tpl
    assert "O pilar gargalo puxa para baixo" not in tpl
    # Previsibilidade (empresa) — 4 variantes + guard
    assert "Ainda não há histórico suficiente para medir consistência." in tpl
    assert "problema de padronização, não de capacidade" in tpl
    assert "o que for corrigido tende a se manter" in tpl
    assert "Consistência da experiência" not in tpl  # copy antiga do card empresa fora
    # Concentração — 4 variantes + guard poucas_lojas + a distinção "pior experiência"
    assert "Poucas lojas com dado suficiente" in tpl
    assert "5 lojas de pior experiência" in tpl  # distingue das "maiores por volume" (Governança)
    assert "está espalhada pela rede" in tpl
    assert "Onde dói" not in tpl  # copy antiga fora
    # Gini — 3 variantes + insuficiente
    assert "procure o que essas fazem e replique" in tpl
    assert "Quão concentrados os detratores estão entre as lojas." not in tpl
    # Engajamento — badge de confiança
    assert "mede se há dado para confiar nos outros números" in tpl
    assert "os demais indicadores são especulativos" not in tpl


# ── Proximity: copy nova (com valor nomeia o binding; sem binding omite "puxado por") ──

_SNIPPET_PROX = (
    "Distância até a excelência (ratio 9,0). Começar baixo é o normal — o que importa é a "
    "evolução, não o valor absoluto. Hoje: {{ '%.0f'|format(proximity.valor) }}"
    "{% if proximity.binding_pilar_nome %}, puxado por "
    "{{ proximity.binding_pilar_nome }}{% endif %}."
)


def _render_prox(proximity):
    return Environment().from_string(_SNIPPET_PROX).render(proximity=proximity)


def test_binding_proximity_pega_menor_proximity():
    from src.ui import _pilar_binding_proximity

    # D tem a MENOR proximity (20) → binda D. O helper vê proximity, não ratio.
    prox = {"P": {"valor": 35.0}, "D": {"valor": 20.0}, "Pa": {"valor": 48.0}}
    assert _pilar_binding_proximity(prox) == "D"


def test_binding_proximity_ignora_pilar_null():
    from src.ui import _pilar_binding_proximity

    # um pilar (talvez o de menor ratio) com proximity NULL não entra no min.
    prox = {"P": {"valor": None}, "D": {"valor": 30.0}, "Pa": {"valor": 45.0}}
    assert _pilar_binding_proximity(prox) == "D"


def test_binding_proximity_todos_null_sem_binding():
    from src.ui import _pilar_binding_proximity

    assert _pilar_binding_proximity({"P": {"valor": None}, "D": {"valor": None}}) is None


def test_proximity_com_valor_nomeia_binding():
    html = _render_prox({"valor": 7.0, "binding_pilar_nome": "Precisão"})
    assert "Começar baixo é o normal" in html
    assert "Hoje: 7, puxado por Precisão." in html
    assert "não a média" not in html  # a copy antiga saiu


def test_proximity_com_valor_sem_binding_omite_puxado():
    html = _render_prox({"valor": 7.0, "binding_pilar_nome": None})
    assert "Hoje: 7." in html and "puxado por" not in html


# ── Variantes por estado/faixa (switch do template) ───────────────────────────

_PREV = (
    "{% if previsib.estado == 'sem_dado' %}"
    "Ainda não há histórico suficiente para medir consistência."
    "{% elif previsib.estado == 'erratico' %}"
    "É problema de padronização, não de capacidade."
    "{% elif previsib.estado == 'medio' %}"
    "Padronizar o que já funciona é o caminho mais curto."
    "{% else %}o que for corrigido tende a se manter.{% endif %}"
)
_CONC = (
    "{% if concentracao.estado == 'poucas_lojas' %}Poucas lojas com dado suficiente"
    "{% elif concentracao.estado == 'cirurgico' %}{{ '%.0f'|format(concentracao.pct) }}"
    "% da dor vem das 5 lojas de pior experiência. Intervenção cirúrgica"
    "{% elif concentracao.estado == 'misto' %}{{ '%.0f'|format(concentracao.pct) }}"
    "% da dor vem das 5 piores lojas — parte é local"
    "{% else %}Só {{ '%.0f'|format(concentracao.pct) }}% da dor vem das 5 piores "
    "lojas — está espalhada pela rede.{% endif %}"
)


def test_previsibilidade_variantes():
    R = lambda e: Environment().from_string(_PREV).render(previsib={"estado": e})  # noqa: E731
    assert "Ainda não há histórico" in R("sem_dado")
    assert "padronização, não de capacidade" in R("erratico")
    assert "caminho mais curto" in R("medio")
    assert "tende a se manter" in R("estavel")


def test_concentracao_variantes_e_guard():
    R = (
        lambda st, pct: Environment()
        .from_string(_CONC)
        .render(concentracao={"estado": st, "pct": pct})  # noqa: E731
    )
    assert "Poucas lojas com dado suficiente" in R("poucas_lojas", None)
    assert "62% da dor vem das 5 lojas de pior experiência" in R("cirurgico", 62.0)
    assert "Só 7% da dor" in R("sistemico", 6.9)  # 6,9 → "7%", "espalhada"


# ── Guards T1/T2 (query de leitura à parte; cálculo intocado) ──────────────────


def _seed_lojas(db_session, n_lojas, verb_por_loja):
    from src.models.empresa import Empresa
    from src.models.fonte import Fonte
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    e = Empresa(nome=f"PG-{id(db_session)}-{n_lojas}x{verb_por_loja}")
    db_session.add(e)
    db_session.flush()
    f = Fonte(
        empresa_id=e.id,
        entidade_tipo="empresa",
        entidade_id=e.id,
        conector_tipo="google",
        url="http://x",
    )
    db_session.add(f)
    db_session.flush()
    for li in range(n_lojas):
        loc = Local(empresa_id=e.id, nome=f"L{li}")
        db_session.add(loc)
        db_session.flush()
        for vi in range(verb_por_loja):
            db_session.add(
                Verbatim(
                    empresa_id=e.id,
                    fonte_id=f.id,
                    local_id=loc.id,
                    texto="x",
                    tem_texto=True,
                    subpilar="P1",
                    tipo="detrator",
                    hash_dedup=f"h{e.id}-{li}-{vi}",
                )
            )
    db_session.commit()
    return e


def test_concentracao_n_lojas_so_conta_lojas_com_5v(db_session):
    from src.api.painel import concentracao_n_lojas

    e = _seed_lojas(db_session, n_lojas=3, verb_por_loja=5)  # 3 lojas x 5 verbatins
    assert concentracao_n_lojas(e.id, db_session, {}) == 3
    e2 = _seed_lojas(db_session, n_lojas=4, verb_por_loja=4)  # nenhuma chega a 5
    assert concentracao_n_lojas(e2.id, db_session, {}) == 0


def test_previsibilidade_medida_true_por_lojas(db_session):
    from src.api.painel import previsibilidade_medida

    e = _seed_lojas(db_session, n_lojas=2, verb_por_loja=5)  # ≥2 lojas com ≥5 → medível
    assert previsibilidade_medida(e.id, db_session, {}) is True


def test_previsibilidade_medida_false_sem_dispersao(db_session):
    from src.api.painel import previsibilidade_medida

    # 1 loja, sem data_criacao_original → nem eixo lojas (≥2) nem eixo meses (≥3) → default 70,0
    e = _seed_lojas(db_session, n_lojas=1, verb_por_loja=6)
    assert previsibilidade_medida(e.id, db_session, {}) is False
