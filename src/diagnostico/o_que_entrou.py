"""O que entrou — contagem dos relatos que ENTRARAM na base desde uma data.

Especificação: ``docs/ESPEC_O_QUE_MUDOU.md`` (v3).

Conta pela DATA DE ENTRADA (``Verbatim.data_coleta``, gravada em UTC na inserção), direto na
tabela de relatos — não usa ``ratios_mensais`` (organizada pelo mês de ESCRITA e misturando
só-nota com texto). Só leitura, $0, sem modelo.

Recusa por desenho (§7 da especificação): nenhum ratio, faixa, veredito, severidade,
comparação entre lojas nem total acumulado. Só contagens dos que entraram.

Partições — cada uma soma ``total`` (o teste trava as três identidades):
- **relógio de escrita:** escritos no período · chegaram com idade · data de escrita igual à de
  entrada (ressalva 1: a fonte não mandou a data e o coletor gravou a de entrada) · sem data de
  escrita;
- **caminho:** planilha (``import_lote_id``) · pesquisa (``respondente_id``) · coleta (o resto —
  manual e noturna não se distinguem, ressalva 3);
- **o que dizem:** por posição só COM texto (falam bem · neutros · romperam) · sem lastro · não
  lido (texto sem posição) · só-nota em linha própria, sem posição (a redistribuição noturna
  move a posição dela; contada por posição, o passado mudaria entre visitas — §5) · fora da conta
  (qualquer outra coisa: nada some calado).

Ressalva 2 (relato que entra duas vezes) não é distinguível no dado: o template declara.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

from src.utils.fuso import FUSO_EXIBICAO

JANELA_PADRAO_DIAS = 7  # §3: decidido em 11/11 (a última passada da pós-coleta não serve)
# Ressalva 1: com a data da fonte ausente, o coletor grava ``utcnow()`` nas duas colunas na
# mesma inserção — ficam a microssegundos. 1 s separa isso de qualquer data real de escrita.
_MESMO_INSTANTE = timedelta(seconds=1)
_TIPOS = {"promotor": "falam_bem", "conversivel": "neutros", "detrator": "romperam"}


def hoje_brasilia(agora: Optional[datetime] = None) -> date:
    """Data de hoje no calendário de Brasília (``agora`` em UTC sem fuso, como o app grava)."""
    agora = agora or datetime.utcnow()
    return agora.replace(tzinfo=timezone.utc).astimezone(FUSO_EXIBICAO).date()


def inicio_do_dia_utc(dia: date) -> datetime:
    """00:00 de ``dia`` em Brasília, expresso em UTC sem fuso (o formato de ``data_coleta``)."""
    local = datetime.combine(dia, time.min, tzinfo=FUSO_EXIBICAO)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def desde_padrao(agora: Optional[datetime] = None) -> date:
    return hoje_brasilia(agora) - timedelta(days=JANELA_PADRAO_DIAS)


def o_que_entrou(
    s,
    empresa_id: int,
    desde: Optional[date] = None,
    *,
    ag_id: Optional[int] = None,
    local_id: Optional[int] = None,
    agora: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Relatos que entraram desde o início de ``desde`` (dia de Brasília) até agora.

    Escopo: ``local_id`` (uma loja) > ``ag_id`` (lojas do agrupamento) > empresa inteira
    (inclui a voz da marca, ``local_id`` vazio). Período e fonte do Painel não entram.
    """
    from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM
    from src.models.empresa import Empresa
    from src.models.local import Local
    from src.models.verbatim import Verbatim

    desde_padrao_usado = desde is None
    desde = desde or desde_padrao(agora)
    corte = inicio_do_dia_utc(desde)

    q = s.query(
        Verbatim.subpilar,
        Verbatim.tipo,
        Verbatim.tem_texto,
        Verbatim.data_criacao_original,
        Verbatim.data_coleta,
        Verbatim.import_lote_id,
        Verbatim.respondente_id,
    ).filter(Verbatim.empresa_id == empresa_id, Verbatim.data_coleta >= corte)
    if local_id is not None:
        q = q.filter(Verbatim.local_id == local_id)
    elif ag_id is not None:
        q = q.filter(Verbatim.local_id.in_(s.query(Local.id).filter(Local.agrupamento_id == ag_id)))

    relogio = {"escritos_no_periodo": 0, "com_idade": 0, "escrita_igual_entrada": 0, "sem_data": 0}
    caminho = {"coleta": 0, "planilha": 0, "pesquisa": 0}
    por_sub: Dict[str, Dict[str, int]] = {}
    sem_lastro = nao_lido = so_nota = fora_da_conta = 0
    total = 0

    for sub, tipo, tem_texto, escrito, entrou, lote, respondente in q:
        total += 1
        if escrito is None:
            relogio["sem_data"] += 1
        elif entrou is not None and abs(entrou - escrito) < _MESMO_INSTANTE:
            relogio["escrita_igual_entrada"] += 1
        elif escrito < corte:
            relogio["com_idade"] += 1
        else:
            relogio["escritos_no_periodo"] += 1

        if lote is not None:
            caminho["planilha"] += 1
        elif respondente is not None:
            caminho["pesquisa"] += 1
        else:
            caminho["coleta"] += 1

        if not tem_texto:
            so_nota += 1
        elif sub in NOME_SUBPILAR and tipo in _TIPOS:
            linha = por_sub.setdefault(sub, {"falam_bem": 0, "neutros": 0, "romperam": 0})
            linha[_TIPOS[tipo]] += 1
        elif sub == "sem_lastro":
            sem_lastro += 1
        elif sub is None:
            nao_lido += 1
        else:
            fora_da_conta += 1

    posicoes = [
        {"codigo": c, "nome": NOME_SUBPILAR[c], **por_sub[c], "total": sum(por_sub[c].values())}
        for c in SUBPILARES_ORDEM
        if c in por_sub
    ]
    empresa = s.get(Empresa, empresa_id)
    return {
        "desde": desde,
        "desde_padrao": desde_padrao_usado,
        "janela_padrao_dias": JANELA_PADRAO_DIAS,
        "total": total,
        "relogio": relogio,
        "caminho": caminho,
        "posicoes": posicoes,
        "posicoes_sem_entrada": len(SUBPILARES_ORDEM) - len(posicoes),
        "sem_lastro": sem_lastro,
        "nao_lido": nao_lido,
        "so_nota": so_nota,
        "fora_da_conta": fora_da_conta,
        "coleta_noturna_ativa": bool(empresa.coleta_noturna_ativa) if empresa else False,
    }
