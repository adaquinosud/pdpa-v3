"""Posição sem relato: o painel mostra qual das doze posições não tem relato no escopo.

Dois estados por posição, em qualquer escopo (empresa, agrupamento ou loja):
- ``presente``: 1+ manifestação ancorada COM TEXTO na posição;
- ``sem_relato``: zero com texto. Só-nota é nota, não relato: não muda o estado (o número
  dela vai na própria linha).

Ao lado do zero, o teto: com N manifestações ancoradas com texto no escopo e zero na posição,
o limite superior de 95% da taxa real é 1 − α^(1/N), α = 0,05. Usa só o próprio escopo: nada
de outras empresas, que não são intercambiáveis (a chance de uma fala por posição depende do
setor) e cujo dado não entra na leitura de outro cliente. Sem limiar: o teto carrega a própria
força (N = 20 dá 13,9%, N = 1.219 dá 0,245%).

"Sem relato" descreve o que foi coletado. Chamar a posição de vaga é leitura, não estado, e
"posição vaga" já é do Avaliador (``src/avaliador/veredito.py``), noutro sentido.

Contagens vêm do mesmo ``agregar_subpilares`` do Confronto, no mesmo escopo: com texto +
só-nota = o volume da linha na tabela de cima, por construção.
"""

from typing import Any, Dict, Optional

ALFA_AUSENCIA = 0.05

PRESENTE, SEM_RELATO = "presente", "sem_relato"


def teto_ausencia(n: int, alfa: float = ALFA_AUSENCIA) -> Optional[float]:
    """1 − α^(1/N): limite superior da taxa real de uma posição com zero em N. ``None`` sem N."""
    if n <= 0:
        return None
    return 1 - alfa ** (1 / n)


def estado_posicoes(
    agg: Dict[str, Dict[str, Any]], agg_texto: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Estado de cada uma das doze posições + o teto. ``agg`` é o agregado com só-nota e
    ``agg_texto`` o só-texto, ambos de ``agregar_subpilares`` no escopo da tela.

    ``regua`` leva os cortes que o rodapé do bloco cita (margem do teto, cortes do selo, piso
    da distribuição do só-nota), lidos das constantes: a copy não reescreve número."""
    from src.api.engajamento import VOLUME_CONFIANCA_ALTA, VOLUME_CONFIANCA_MEDIA
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.coletor.distribuicao_simbolos import PISO_TEXTOS

    estados = {}
    for sub in SUBPILARES_ORDEM:
        n = agg_texto.get(sub, {}).get("total", 0)
        estados[sub] = {
            "estado": PRESENTE if n > 0 else SEM_RELATO,
            "n_texto": n,
            "n_so_nota": agg.get(sub, {}).get("total", 0) - n,
        }
    total = sum(e["n_texto"] for e in estados.values())
    teto = teto_ausencia(total)
    return {
        "estados": estados,
        "total": total,
        "teto": teto,
        "um_em": round(1 / teto) if teto else None,  # "1 em cada X", inteiro mais próximo
        "nomes": NOME_SUBPILAR,
        "regua": {
            "alfa": ALFA_AUSENCIA,
            "selo_alta": VOLUME_CONFIANCA_ALTA,
            "selo_media": VOLUME_CONFIANCA_MEDIA,
            "piso_textos": PISO_TEXTOS,
        },
    }
