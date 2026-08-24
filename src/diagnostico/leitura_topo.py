"""Leitura no topo — o cruzamento que nenhuma célula faz sozinha (Fatia 9).

Peça DETERMINÍSTICA ($0, sem LLM): monta o raciocínio que o executivo montaria célula
a célula, cruzando quatro eixos JÁ em prod — ferida (onde dói), elo travado (o que trava
primeiro), etapa da jornada (onde o volume × o que trava a montante) e reputação em IA
(o que a vitrine diz × a realidade viva). NÃO é resumo das 25 células; é o cruzamento
entre elas.

Toda degradação é DECLARADA (jornada não configurada, sonda ausente): a frase que declara
a ausência é INFORMAÇÃO — sumir com ela não é. Menos de dois eixos com sinal → não
renderiza e diz por quê.

Casa neutra de propósito: Painel e Resumo Executivo podem consumir ``montar_leitura_topo``
depois SEM 2ª cópia. Nesta fatia só a aba Perguntas liga. O núcleo de dois eixos (ferida ×
elo travado) delega a ``_eixos_leitura`` (parecer) — uma frase, um lugar.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Optional

from src.api.painel import (
    NOME_PILAR,
    NOME_SUBPILAR,
    eh_elo_travado,
    ferida_de_agg,
    gargalo_sequencial,
)
from src.diagnostico.leituras import agregar_subpilares

# Valência crua → rótulo de exibição (a sonda e o agregado falam o mesmo vocabulário).
_VAL_ROTULO = {"promotor": "positiva", "conversivel": "neutra", "detrator": "negativa"}


def _frase(texto: str, degradado: bool = False) -> SimpleNamespace:
    return SimpleNamespace(texto=texto, degradado=degradado)


def _nucleo(ferida, gargalo_cod) -> Optional[str]:
    """Núcleo de dois eixos (ferida × elo travado). Delega a ``_eixos_leitura`` (fonte única
    com o Parecer) nos casos (a) divergem e (b) coincidem. Caso (c) — sem elo travado — o
    Parecer devolve None; aqui a leitura no topo NOMEIA a ferida e declara que nada trava
    antes (a declaração é informação, não silêncio)."""
    from src.relatorios.parecer import _eixos_leitura

    if gargalo_cod:
        return _eixos_leitura(
            ferida["subpilar"],
            ferida["nome"],
            gargalo_cod,
            NOME_PILAR.get(gargalo_cod, gargalo_cod),
        )
    return (
        f"A ferida é {ferida['nome']} ({ferida['det']} detratores). Nenhum elo trava antes "
        f"dela na sequência do Lastro — o próximo passo se decide caso a caso."
    )


def _frase_jornada(s, empresa_id: int) -> SimpleNamespace:
    """Eixo etapa: onde o VOLUME de dor está × qual etapa trava mais a MONTANTE. Jornada não
    configurada (ou sem dado) → declara que a etapa não entrou (degradação declarada)."""
    from src.jornada.leitura import agregar_jornada

    j = agregar_jornada(s, empresa_id)
    if j is None:
        return _frase(
            "A etapa da jornada não entrou nesta leitura — jornada não configurada.", True
        )
    vol = getattr(j, "volume", None)
    garg = getattr(j, "gargalo", None)
    if vol is None:
        return _frase(
            "A etapa da jornada não entrou — sem volume de dor com etapa atribuída.", True
        )
    if garg is None:
        return _frase(
            f"Na jornada, o volume de dor concentra em “{vol.rotulo}”; nenhuma etapa trava "
            f"(todas no empate ou acima)."
        )
    if getattr(j, "divergem", False):
        return _frase(
            f"Na jornada, o volume de dor está em “{vol.rotulo}”, mas o que trava mais a "
            f"montante é “{garg.rotulo}” — atacar a montante evita a dor a jusante."
        )
    return _frase(
        f"Na jornada, “{vol.rotulo}” concentra o volume de dor e é também o que trava mais "
        f"a montante."
    )


def _frase_reputacao(s, empresa_id: int, ferida, agg) -> SimpleNamespace:
    """Eixo reputação: a sonda de IA RECONHECE a ferida, ou a mostra melhor do que é? Compara
    a valência que a sonda atribui ao subpilar da ferida contra a propriedade que ELEGEU a
    ferida (detrator) — um critério só. Superestima = a vitrine está melhor que a realidade.
    Determinístico (``_direcao``). Sem sonda / subpilar não avaliado → declara."""
    from src.pesquisa.confronto import _direcao
    from src.ui import _explorar_reputacao_ia

    rep = _explorar_reputacao_ia(s, empresa_id)
    snap = getattr(rep, "snapshot", None) if getattr(rep, "tem_dado", False) else None
    if snap is None:
        return _frase("A reputação em IA não entrou — sem sonda de IA para esta empresa.", True)
    fer_sub = ferida["subpilar"]
    aval = next((a for a in snap.avaliacao if a["subpilar"] == fer_sub), None)
    if aval is None or aval.get("val") is None:
        return _frase(f"A sonda de IA não avaliou {ferida['nome']} — eixo sem sinal aqui.", True)
    ia_val = aval["val"]
    d = agg[fer_sub]
    # UM critério só: a ferida foi eleita por VOLUME DE DETRATOR — é uma poça de dor por
    # construção. A comparação honesta é contra a propriedade que a elegeu, não contra a
    # valência dominante (que num subpilar com muito promotor E muito detrator diria "positivo"
    # e contradiria a própria peça — que acabou de chamar X de ferida). O eixo pergunta: a sonda
    # RECONHECE a ferida, ou mostra melhor? (subestima é impossível — detrator é o piso.)
    direcao = _direcao("detrator", ia_val)
    ia_rot = _VAL_ROTULO.get(ia_val, ia_val)
    if direcao == "superestima":  # a IA vê a ferida melhor do que ela é
        return _frase(
            f"As IAs classificam {ferida['nome']} como {ia_rot}, mas ela é a ferida "
            f"({d['det']} detratores) — a vitrine está melhor que a realidade."
        )
    return _frase(  # ia_val == detrator → a sonda reconhece a dor
        f"A sonda de IA também vê {ferida['nome']} como negativa — reconhece a ferida."
    )


def montar_leitura_topo(s, empresa_id: int) -> SimpleNamespace:
    """Constrói a leitura no topo. Retorna namespace com ``renderiza`` (bool), ``motivo`` (por
    que não, quando não renderiza), ``ferida``, ``elo_travado`` e ``frases`` (lista de
    ``SimpleNamespace(texto, degradado)``).

    Piso = o NÚCLEO (ferida × elo travado), não a contagem de eixos (que os trataria como
    intercambiáveis, e não são). A ferida ancora: sem ela (nenhum detrator) não renderiza. Com
    ferida e sem elo travado, renderiza no caso (c). Jornada e reputação entram quando houver e
    DECLARAM quando não — nunca decidem se a peça sai."""
    agg: Dict[str, Dict[str, Any]] = agregar_subpilares(s, empresa_id)
    ferida = ferida_de_agg(agg)
    if ferida is None:
        return SimpleNamespace(
            renderiza=False,
            motivo="Sem detrator no agregado — não há ferida para ancorar a leitura.",
            ferida=None,
            elo_travado=None,
            frases=[],
        )

    gargalo_cod = gargalo_sequencial(agg)
    elos = [
        SimpleNamespace(subpilar=sub, nome=NOME_SUBPILAR.get(sub, sub), ratio=agg[sub]["ratio"])
        for sub in agg
        if eh_elo_travado(sub, gargalo_cod, agg[sub]["ratio"])
    ]
    elo_travado = (
        SimpleNamespace(
            pilar=gargalo_cod, nome=NOME_PILAR.get(gargalo_cod, gargalo_cod), subpilares=elos
        )
        if gargalo_cod
        else None
    )

    frases = [
        _frase(_nucleo(ferida, gargalo_cod)),
        _frase_jornada(s, empresa_id),
        _frase_reputacao(s, empresa_id, ferida, agg),
    ]
    return SimpleNamespace(
        renderiza=True,
        motivo=None,
        ferida=ferida,
        elo_travado=elo_travado,
        frases=frases,
    )
