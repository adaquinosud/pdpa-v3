"""Posição vaga: o painel afirma que uma das doze posições está vazia numa empresa.

O piso de confiança (30, ``VOLUME_CONFIANCA_ALTA``) responde "dá para ler?". Este módulo
responde outra pergunta, "está vazia?", com outro piso: o de ausência.

Três estados por posição, no escopo da EMPRESA:
- ``presente``: 1+ manifestação ancorada COM TEXTO na posição (o volume segue no selo);
- ``vaga``: zero, e o total ancorado com texto da empresa >= piso de ausência;
- ``indeterminada``: zero, e o total < piso, ou não existe piso (p = 0).

Piso de ausência: N = ln(α) ÷ ln(1 − p), arredondado para cima, α = 0,05, p = taxa da
posição mais rara na REFERÊNCIA. É o volume a partir do qual, se a posição tivesse ao menos
a taxa da mais rara, a chance de ver zero fica abaixo de 5%. Calculado na hora: depende da
distribuição do corpus, que muda a cada coleta.

Referência = a base menos a própria empresa (usar a própria seria circular) e menos
``EMPRESAS_FORA_DA_REFERENCIA``. Denominador = manifestação ancorada COM TEXTO, na empresa e
na referência: a só-nota recebe o subpilar dominante de um pilar por proporção
(``distribuicao_simbolos``), nunca cai numa posição rara, e só inflaria o total.

"Vaga" quer dizer vaga NO QUE FOI COLETADO: a referência mistura fontes, e uma empresa
coletada numa fonte só pode zerar uma posição que a fonte não produz.
"""

import math
from typing import Any, Dict, Optional

ALFA_AUSENCIA = 0.05

# Fora da referência, declarado na tela. 4 = conta sob veto (não se roda nada nela);
# 15, 18, 20 = contas de teste.
EMPRESAS_FORA_DA_REFERENCIA = {4: "conta sob veto", 15: "teste", 18: "teste", 20: "teste"}

PRESENTE, VAGA, INDETERMINADA = "presente", "vaga", "indeterminada"


def piso_ausencia(p: float, alfa: float = ALFA_AUSENCIA) -> Optional[int]:
    """N = ln(α) ÷ ln(1 − p), para cima. ``None`` quando não existe piso (p fora de (0, 1))."""
    if not 0 < p < 1:
        return None
    return math.ceil(math.log(alfa) / math.log(1 - p))


def estado_posicoes(s, empresa_id: int, fora: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """Estado de cada uma das doze posições da empresa + o cálculo que o sustenta."""
    from sqlalchemy import func

    from src.api.painel import SUBPILARES_ORDEM
    from src.models.verbatim import Verbatim as V

    fora = EMPRESAS_FORA_DA_REFERENCIA if fora is None else fora
    excluidas = set(fora) | {empresa_id}
    base = s.query(V.subpilar, func.count(V.id)).filter(
        V.subpilar.in_(SUBPILARES_ORDEM), V.tem_texto.is_(True)
    )
    proprio = dict(base.filter(V.empresa_id == empresa_id).group_by(V.subpilar).all())
    ref = dict(base.filter(V.empresa_id.notin_(excluidas)).group_by(V.subpilar).all())
    so_nota = dict(
        s.query(V.subpilar, func.count(V.id))
        .filter(
            V.empresa_id == empresa_id,
            V.subpilar.in_(SUBPILARES_ORDEM),
            V.tem_texto.is_(False),
        )
        .group_by(V.subpilar)
        .all()
    )

    ref_total = sum(ref.values())
    mais_rara = min(SUBPILARES_ORDEM, key=lambda x: ref.get(x, 0))
    p = ref.get(mais_rara, 0) / ref_total if ref_total else 0.0
    piso = piso_ausencia(p)
    total = sum(proprio.values())

    estados = {}
    for sub in SUBPILARES_ORDEM:
        n = proprio.get(sub, 0)
        if n > 0:
            estado = PRESENTE
        elif piso is not None and total >= piso:
            estado = VAGA
        else:
            estado = INDETERMINADA
        estados[sub] = {"estado": estado, "n_texto": n, "n_so_nota": so_nota.get(sub, 0)}

    return {
        "estados": estados,
        "total_empresa": total,
        "referencia_total": ref_total,
        "mais_rara": mais_rara,
        "n_mais_rara": ref.get(mais_rara, 0),
        "p": p,
        "piso": piso,
        "fora": {eid: motivo for eid, motivo in sorted(fora.items()) if eid != empresa_id},
    }
