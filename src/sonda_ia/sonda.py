"""Sonda de Reputação em IA — pergunta às IAs sobre a empresa e grava as respostas
raw (``sonda_ia_respostas``).

Foco na EMPRESA (não em categoria). N repetições por pergunta/modelo (as respostas
variam — G0 mostrou consistência 0,07–0,26) e por VENDOR (a divergência entre
modelos é sinal — G0: similaridade 0,03–0,08). NÃO toca a base do cliente: escreve
só nas tabelas ``sonda_ia_*``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from src.models.sonda_ia import SondaIAExecucao, SondaIAResposta
from src.sonda_ia.adapters import ADAPTERS, PRECO
from src.utils.db import db_session

# As 3 sondas com foco na empresa (a 4ª — defasagem — é análise, vem no G4).
PERGUNTAS = {
    "identidade": "O que é a empresa {empresa}? Descreva-a em um parágrafo.",
    "avaliacao": (
        "Quais são os pontos fortes e os pontos fracos da empresa {empresa} "
        "como escolha para um cliente?"
    ),
    "encaminhamento": (
        "Estou insatisfeito com a empresa {empresa}. Que alternativas você recomenda?"
    ),
}
MODELOS_PADRAO = ("claude", "gpt", "gemini")


def _custo(modelo: str, tin: int, tout: int) -> float:
    pin, pout = PRECO.get(modelo, (0.0, 0.0))
    return tin / 1e6 * pin + tout / 1e6 * pout


def _nome_empresa(s, empresa_id: int) -> str:
    from src.models.empresa import Empresa

    e = s.get(Empresa, empresa_id)
    return e.nome if e else f"empresa {empresa_id}"


def sondar_empresa(
    empresa_id: int,
    competencia: str,
    *,
    modelos=MODELOS_PADRAO,
    n: int = 3,
    callers: Optional[Dict[str, Callable[[str], Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Roda a sonda de UMA empresa numa ``competencia`` (YYYY-MM): modelos ×
    perguntas × N repetições → ``sonda_ia_respostas`` + a ``SondaIAExecucao``.

    Idempotente: execução já ``concluida`` na competência → skip (o cron mensal não
    re-cobra). ``callers`` injetável (default = adapters reais; testes passam fakes).
    Tolerante: erro de um modelo/call não derruba o lote."""
    callers = callers or ADAPTERS
    stats = {"respostas": 0, "erros": 0, "custo_usd": 0.0, "pulado": False, "execucao_id": None}

    with db_session() as s:
        emp_nome = _nome_empresa(s, empresa_id)
        execucao = (
            s.query(SondaIAExecucao)
            .filter_by(empresa_id=empresa_id, competencia=competencia)
            .first()
        )
        if execucao is not None and execucao.status == "concluida":
            stats["execucao_id"] = execucao.id
            stats["pulado"] = True
            return stats
        if execucao is None:
            execucao = SondaIAExecucao(
                empresa_id=empresa_id,
                competencia=competencia,
                status="rodando",
                modelos_json=json.dumps(list(modelos)),
                repeticoes=n,
            )
            s.add(execucao)
            s.flush()
        else:
            # retry de execução pendente/falhou: limpa respostas anteriores.
            execucao.status = "rodando"
            s.query(SondaIAResposta).filter_by(execucao_id=execucao.id).delete()

        exec_id = execucao.id
        stats["execucao_id"] = exec_id
        custo = 0.0
        for vendor in modelos:
            caller = callers.get(vendor)
            if caller is None:
                continue
            for pergunta_tipo, tpl in PERGUNTAS.items():
                prompt = tpl.format(empresa=emp_nome)
                for rep in range(1, n + 1):
                    try:
                        r = caller(prompt)
                    except Exception as exc:
                        stats["erros"] += 1
                        print(
                            f"[sonda_ia] {vendor}/{pergunta_tipo}#{rep}: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        continue
                    tin, tout = int(r.get("tokens_in", 0)), int(r.get("tokens_out", 0))
                    custo += _custo(r.get("modelo", ""), tin, tout)
                    s.add(
                        SondaIAResposta(
                            execucao_id=exec_id,
                            empresa_id=empresa_id,
                            vendor=r.get("vendor", vendor),
                            modelo=r.get("modelo", ""),
                            pergunta_tipo=pergunta_tipo,
                            repeticao=rep,
                            resposta_texto=r.get("texto", ""),
                            tokens_in=tin,
                            tokens_out=tout,
                        )
                    )
                    stats["respostas"] += 1

        # Sem NENHUMA resposta = falha (as IAs não retornaram — chaves/rede/modelo).
        # NÃO marca 'concluida': senão a idempotência pularia o retry e a UI mostraria
        # uma sondagem "vazia" (0 modelos) em vez de sinalizar a falha.
        execucao.status = "concluida" if stats["respostas"] > 0 else "falhou"
        execucao.custo_usd = round(custo, 4)
        execucao.concluido_em = datetime.utcnow()
        stats["custo_usd"] = round(custo, 4)
    return stats


def _empresas_alvo():
    """Empresas alvo da sonda mensal: as que têm ≥1 verbatim (clientes reais) —
    evita sondar empresas vazias/teste."""
    from src.models.verbatim import Verbatim

    with db_session() as s:
        return [
            r[0]
            for r in s.query(Verbatim.empresa_id).distinct().order_by(Verbatim.empresa_id).all()
        ]


def rodar_sonda_mensal(
    competencia: Optional[str] = None,
    *,
    empresa_ids=None,
    n: int = 3,
    callers=None,
    gerar_avaliacao=None,
    gerar_leitura=None,
) -> Dict[str, Any]:
    """Cron MENSAL: p/ cada empresa alvo, ``sondar_empresa`` → ``processar_sonda``
    (classifica avaliações + sintetiza leitura + cruza a defasagem). Idempotente por
    competência (sonda pulada se já concluída; o processamento é retomável). Erro de
    uma empresa não derruba as outras. ``competencia`` default = mês atual (YYYY-MM);
    ``callers``/``gerar_*`` injetáveis (testes)."""
    from datetime import date

    from src.sonda_ia.classificador import processar_sonda

    competencia = competencia or date.today().strftime("%Y-%m")
    alvo = empresa_ids if empresa_ids is not None else _empresas_alvo()
    stats = {
        "competencia": competencia,
        "empresas": 0,
        "sondadas": 0,
        "puladas": 0,
        "respostas": 0,
        "custo_usd": 0.0,
        "erros": 0,
    }
    for eid in alvo:
        stats["empresas"] += 1
        try:
            r = sondar_empresa(eid, competencia, n=n, callers=callers)
            if r["pulado"]:
                stats["puladas"] += 1
            else:
                stats["sondadas"] += 1
                stats["respostas"] += r["respostas"]
                stats["custo_usd"] += r["custo_usd"]
            # Encadeia G3 (classificar + sintetizar) + G4 (defasagem). Idempotente:
            # roda mesmo em 'pulado' p/ completar processamento de tentativa anterior.
            if r.get("execucao_id"):
                processar_sonda(
                    r["execucao_id"], gerar_avaliacao=gerar_avaliacao, gerar_leitura=gerar_leitura
                )
        except Exception as exc:
            stats["erros"] += 1
            print(f"[sonda_ia] empresa {eid}: {type(exc).__name__}: {exc}")
    stats["custo_usd"] = round(stats["custo_usd"], 4)
    return stats
