"""Serviço do Avaliador — ciclo de vida da análise, gate de custo, retenção.

Fluxo: ``criar_analise`` (extrai, cobra o teto, grava PENDENTE) → ``disparar`` (daemon-
thread, padrão ``_rodar_async`` do app) → ``processar``, que lê sempre nas marcas
(``marcas.py``, cinco chamadas; virada de 19/10). Os formatos 1 (forte, falta e melhorar)
e 2 (veredito) não são mais gerados; as leituras gravadas neles continuam abrindo
(``organizar`` + ``_avaliador_leitura_v1.html``; ``organizar_veredito`` +
``_avaliador_leitura_v2.html``).

Falha é visível, nunca "processando" eterno:
- erro → FALHOU com ``erro_motivo`` (tipo do erro; NUNCA texto da peça nem resposta do
  modelo — o texto não pode sobreviver à limpeza num log). ``retomar`` refaz;
- deploy mata a thread (§7) → ``housekeeping`` (watchdog, a cada 6h) marca FALHOU o que
  parou de bater o coração.

Retenção (decisão do Alexandre, 12/10): concluir apaga o texto na hora;
``AVALIADOR_DIAS_RETENCAO_TEXTO`` dias sem uso apaga sozinho. O aviso da tela lê o
MESMO valor (``dias_retencao``). As peças de medição (``PECAS_DE_MEDICAO``, 21/10) ficam
fora das duas: o texto delas não é apagado, e não se relê, conclui nem apaga.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, object_session

from src.api.painel import NOME_PILAR, SUBPILARES_ORDEM
from src.avaliador import marcas, motor, veredito
from src.avaliador.extracao import (
    Documento,
    _normalizar,
    documento_de_texto,
    extrair,
    localizar_trecho,
)
from src.avaliador.regua import (
    ORIGEM_ARQUIVO,
    ORIGEM_PAGINA,
    GRUPO_FORA,
    ORIGEM_TEXTO,
    Regua,
    carregar_regua,
)
from src.config import get_config
from src.models.avaliador import (
    STATUS_APAGADA,
    STATUS_EM_PROCESSAMENTO,
    STATUS_FALHOU,
    STATUS_LENDO,
    STATUS_PENDENTE,
    STATUS_PRONTA,
    CORRECAO_INCLUSAO,
    CORRECAO_RECUSA,
    AvaliadorAnalise,
    AvaliadorCorrecao,
    AvaliadorParecer,
)
from src.utils.db import db_session
from src.utils.fmt import virg

logger = logging.getLogger(__name__)

HEARTBEAT_LIMITE = timedelta(minutes=20)  # sem heartbeat há mais que isto = thread morta
LIMITE_DESCRICAO = 500


class AvaliacaoRecusada(ValueError):
    """Não roda: a mensagem vai para a tela como está e nomeia o que resolve."""


def dias_retencao() -> int:
    return int(get_config().AVALIADOR_DIAS_RETENCAO_TEXTO)


# ── custo ─────────────────────────────────────────────────────────────────


def gasto_do_mes(s: Session, empresa_id: int, agora: Optional[datetime] = None) -> float:
    agora = agora or datetime.utcnow()
    inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = s.scalar(
        select(func.coalesce(func.sum(AvaliadorAnalise.custo_usd), 0.0)).where(
            AvaliadorAnalise.empresa_id == empresa_id, AvaliadorAnalise.criado_em >= inicio
        )
    )
    # o rascunho do parecer (fatia 3) também é gasto da empresa, no mês em que foi pedido
    rascunhos = s.scalar(
        select(func.coalesce(func.sum(AvaliadorParecer.rascunho_custo_usd), 0.0))
        .join(AvaliadorAnalise, AvaliadorAnalise.id == AvaliadorParecer.analise_id)
        .where(AvaliadorAnalise.empresa_id == empresa_id, AvaliadorParecer.rascunho_em >= inicio)
    )
    return float(total or 0.0) + float(rascunhos or 0.0)


def checar_teto(s: Session, empresa_id: int, estimativa_usd: float) -> None:
    """Levanta ANTES da chamada paga. Teto 0 = desligado (semântica do "Cap 0 = NÃO
    COLETAR" do §7)."""
    teto = float(get_config().AVALIADOR_TETO_MENSAL_USD)
    if teto <= 0:
        raise AvaliacaoRecusada(
            "O Avaliador está desligado: o teto mensal de custo é US$ 0. "
            "Defina AVALIADOR_TETO_MENSAL_USD para ligar."
        )
    gasto = gasto_do_mes(s, empresa_id)
    if gasto + estimativa_usd > teto:
        raise AvaliacaoRecusada(
            f"Esta leitura passaria do teto mensal de custo da empresa "
            f"(gasto no mês US$ {gasto:.2f} + estimativa US$ {estimativa_usd:.2f} "
            f"> teto US$ {teto:.2f}).".replace(".", ",")
        )


def _somar_uso(a: AvaliadorAnalise, uso: motor.Uso) -> None:
    a.tokens_in += uso.tokens_in
    a.tokens_out += uso.tokens_out
    a.tokens_cache_criacao += uso.cache_criacao
    a.tokens_cache_leitura += uso.cache_leitura
    a.custo_usd += uso.custo_usd


def _pedido(regua: Regua, a_origem: str, descricao: str, doc: Documento):
    """O pedido de toda leitura: as marcas (19/10). A origem não muda mais o pedido (as
    bibliotecas de pistas por origem eram do veredito); o parâmetro fica para quem chama."""
    return marcas.montar_sistema(regua), motor.montar_usuario(descricao, doc)


def _estimativa(regua: Regua, sistema: str, usuario: str, modelo: str) -> float:
    """O que o gate cobra. É TAMBÉM o orçamento da leitura: o motor não passa dele, nem
    com nova tentativa."""
    return marcas.estimar_custo_usd(sistema, usuario, modelo, len(marcas.etapas(regua)))


# ── leitura do estado ─────────────────────────────────────────────────────

# Formato do que fica gravado em ``itens_json`` (o nome da coluna é do formato 1 e ficou,
# sem migração; decisão de 17/10). Formato 1: LISTA de itens forte/falta/melhorar.
# Formato 2 (avaliador-v20-veredito): OBJETO com "formato": 2. A tela tem um leitor
# para cada um; a leitura gravada nunca é convertida.
FORMATO_ITENS = 1
FORMATO_VEREDITO = 2
# Formato 3 (balizador de marcas, 18/10): OBJETO com "formato": 3. Cada marca do capítulo
# de marcas do Manual com "esta" e as evidências; achados e contradições como no 2. A
# tela já o lê; o motor que o grava é a fatia seguinte.
FORMATO_MARCAS = 3
# O formato que o motor grava hoje. Leitura pronta em formato diferente deste ganha o
# aviso de "formato anterior" na tela.
FORMATO_ATUAL = FORMATO_MARCAS


def formato_da_leitura(a: AvaliadorAnalise) -> Optional[int]:
    """1, 2, 3 ou None quando o gravado não é nenhum deles (a tela declara, não quebra)."""
    try:
        gravado = json.loads(a.itens_json or "[]")
    except json.JSONDecodeError:
        return None
    if isinstance(gravado, list):
        return FORMATO_ITENS
    if isinstance(gravado, dict) and gravado.get("formato") in (FORMATO_VEREDITO, FORMATO_MARCAS):
        return gravado["formato"]
    return None


# Os três tipos de item do formato 1, só para MOSTRAR leitura já gravada nesse formato.
TIPOS_ITEM_FORMATO_1 = ("forte", "falta", "melhorar")


def organizar(regua: Regua, a: AvaliadorAnalise) -> List[dict]:
    """Leitura gravada no FORMATO 1: itens por pilar → subpilar → forte/falta/melhorar, na
    ordem do Manual. Subpilar sem item aparece declarado ("sem observação"), não some.
    Item com ``descartado`` (o limite de três daquele formato) não aparece; a contagem vai
    em ``descartados``. Só leitura: o formato 1 não é mais gerado (17/10)."""
    itens = json.loads(a.itens_json or "[]")
    out = []
    for p in regua.pilares:
        subs = []
        for s in p.subpilares:
            todos = [i for i in itens if i["subpilar"] == s.codigo]
            dele = [i for i in todos if not i.get("descartado")]
            subs.append(
                {
                    "subpilar": s,
                    "por_tipo": {
                        t: [i for i in dele if i["tipo"] == t] for t in TIPOS_ITEM_FORMATO_1
                    },
                    "vazio": not dele,
                    "descartados": len(todos) - len(dele),
                }
            )
        out.append({"pilar": p, "subpilares": subs})
    return out


def organizar_veredito(regua: Regua, a: AvaliadorAnalise) -> dict:
    """O que a tela mostra de uma leitura no formato 2, na ordem do parecer (situar,
    achados, contradições, Lastro, posições vagas, placar, os doze). Placar, vagas e ponto
    de partida são RECALCULADOS dos doze pelas mesmas funções que alimentaram o pedido: a
    tela nunca lê um número que o modelo escreveu. A lista "ordem das recomendações" saiu
    da tela em 17/10: era a tabela pela terceira vez, sempre na ordem dos pilares."""
    g = json.loads(a.itens_json)
    doze = g["doze"]
    por_cod = {d["subpilar"]: d for d in doze}
    pp = veredito.ponto_de_partida(doze)
    nome_pp = NOME_PILAR[pp] if pp else None
    texto = g["lastro"].get("texto")
    pilares = [
        {
            "pilar": p,
            "linhas": [
                {
                    **por_cod[s.codigo],
                    "subpilar": s,
                    # rodada 1: a ausência que pesa aqui está contada noutro subpilar
                    "contada_em": (
                        regua.subpilar(por_cod[s.codigo]["mesma_ausencia_de"])
                        if por_cod[s.codigo].get("mesma_ausencia_de")
                        else None
                    ),
                }
                for s in p.subpilares
                if s.codigo in por_cod
            ],
        }
        for p in regua.pilares
    ]
    return {
        "situar": g["situar"],
        "cobertura": veredito.declarar_cobertura(g["cobertura"]),
        "achados": g["achados"],
        "contradicoes": g["contradicoes"],
        "lastro": {
            "texto": texto,
            "texto_falhou": g["lastro"].get("texto_falhou"),
            "ponto_de_partida": nome_pp,
            # conferência texto × cálculo (critério de medição de 17/10), visível na tela
            "texto_diverge": bool(texto and nome_pp and nome_pp.lower() not in texto.lower()),
        },
        "vagas": [
            {**por_cod[c], "subpilar": regua.subpilar(c)} for c in veredito.posicoes_vagas(doze)
        ],
        "placar": veredito.placar(doze),
        "pilares": pilares,
    }


# Estado de uma marca na tela. "esta" só com trecho achado na peça: a leitura que diz que
# está e não traz trecho conferido não vira presença (citação não conferida nunca aparece
# como citação).
MARCA_ESTA, MARCA_SEM_CONFERENCIA, MARCA_NAO_ESTA = "esta", "sem_conferencia", "nao_esta"


def _estado_marca(m: dict) -> str:
    if not m.get("esta"):
        return MARCA_NAO_ESTA
    if any(e.get("conferido") for e in m.get("evidencias", [])):
        return MARCA_ESTA
    return MARCA_SEM_CONFERENCIA


# A frase da tela sai do texto da marca, sem segundo texto à mão (decisão de 21/10): toda
# marca do Manual, e toda que saiu dele mas segue gravada em leitura antiga (a Pa2.07,
# "Vincula…"), começa com um destes verbos, e "Diz quanto custa?" vira "Diz quanto
# custa." quando está e "Não diz quanto custa." quando não está. tests/test_avaliador_marcas
# falha se o Manual trouxer marca que comece com outra palavra.
VERBOS_DE_MARCA = frozenset(
    {
        "Diz", "Traz", "Nomeia", "Cita", "Avisa", "Descreve", "Abre", "Fala", "Menciona",
        "Lista", "Oferece", "Prevê", "Entrega", "Contraria", "Ensina", "Compara", "Aponta",
        "Recomenda", "Define", "Vincula",
    }
)  # fmt: skip


def frase_da_marca(texto: str, esta: bool) -> str:
    """A pergunta da marca virada em afirmação. Marca gravada que não começa com verbo
    (texto antigo de leitura gravada) cai na forma que não depende da gramática."""
    t = texto.strip().rstrip("?").strip()
    if t.split(" ", 1)[0] not in VERBOS_DE_MARCA:
        return f"Responde: {texto.strip()}" if esta else f"Não está no texto lido: {texto.strip()}"
    return f"{t}." if esta else f"Não {t[0].lower()}{t[1:]}."


def _frase(x: dict, esta: bool) -> dict:
    return {
        "codigo": x["codigo"],
        "grupo": x["grupo"],
        "frase": frase_da_marca(x["texto"], esta),
        "porque_importa": x["porque_importa"],
        "nota": x["nota"],
        "recusadas": x.get("recusadas", []),
        "corrigida": x.get("corrigida", False),
    }


def _trechos_da_marca(x: dict) -> List[dict]:
    """Os trechos conferidos de UMA marca, cada um uma vez: trecho contido noutro da mesma
    marca junta no maior; sobreposição parcial fica como dois."""
    out: List[dict] = []
    for e in (e for e in x["evidencias"] if e.get("conferido")):
        alvo = _normalizar(e["trecho"])
        junto = next((t for t in out if alvo in t["chave"] or t["chave"] in alvo), None)
        if junto is None:
            out.append({"chave": alvo, "evidencia": e})
        elif len(alvo) > len(junto["chave"]):
            junto["chave"], junto["evidencia"] = alvo, e
    return [t["evidencia"] for t in out]


def _bloco_de_marcas(linhas: List[dict]) -> dict:
    """O que um subpilar (ou grupo) mostra, simétrico: o que a peça diz, o que não diz (uma
    frase por marca vazia) e o que ficou sem conferência. Ordem do Manual.

    No "diz", UM BLOCO POR MARCA, sem exceção: a frase uma vez e todos os trechos dela
    embaixo. Trecho que responde a duas marcas aparece nas duas. Nunca se juntam duas
    marcas num bloco, nem quando o trecho é o mesmo: na prévia da #28 (22/10), juntar por
    trecho pôs a frase de uma marca em cima do trecho de outra, e quem confere lia erro de
    leitura onde a resposta estava certa."""
    return {
        "diz": [
            {**_frase(x, True), "evidencias": _trechos_da_marca(x)}
            for x in linhas
            if x["estado"] == MARCA_ESTA
        ],
        "nao_diz": [_frase(x, False) for x in linhas if x["estado"] == MARCA_NAO_ESTA],
        "sem_conferencia": [x for x in linhas if x["estado"] == MARCA_SEM_CONFERENCIA],
    }


def _aplicar_correcoes(m: dict, correcoes: List[AvaliadorCorrecao]) -> dict:
    """O estado da marca depois das correções à mão, sem tocar no gravado. Trecho recusado
    sai das evidências e fica em ``recusadas`` (a tela mostra riscado); trecho incluído entra
    nas evidências. Marca "está" com todos os trechos recusados passa a "não está"; marca
    "não está" (ou sem conferência) com trecho incluído passa a "está". A recusa vale também
    para a citação que não foi achada na peça: é como a pessoa resolve o "sem conferência"
    (a tela não mostra o texto dela; ver o template)."""
    minhas = [c for c in correcoes if c.marca_codigo == m["codigo"]]
    recusa = {c.trecho: c for c in minhas if c.tipo == CORRECAO_RECUSA}
    ok, recusadas = [], []
    for e in m.get("evidencias", []):
        if e["trecho"] in recusa:
            recusadas.append({**e, "correcao_id": recusa[e["trecho"]].id})
        else:
            ok.append(e)
    for c in minhas:
        if c.tipo == CORRECAO_INCLUSAO:
            ok.append(
                {
                    "pagina": c.pagina,
                    "trecho": c.trecho,
                    "conferido": True,
                    "pagina_encontrada": c.pagina,
                    "incluido": True,
                    "correcao_id": c.id,
                    # a citação da leitura traz o título da seção, calculado com o texto da
                    # peça; o trecho incluído guarda só o número (o texto pode ser apagado)
                    "referencia": f"seção {c.pagina}" if c.pagina is not None else "",
                }
            )
    if not minhas:
        estado = _estado_marca(m)
    elif any(e.get("conferido") for e in ok):
        estado = MARCA_ESTA
    elif m.get("esta") and any(not e.get("conferido") for e in ok):
        estado = MARCA_SEM_CONFERENCIA  # sobrou citação não achada sem resolver
    else:
        estado = MARCA_NAO_ESTA
    return {**m, "evidencias": ok, "recusadas": recusadas, "estado": estado,
            "corrigida": bool(minhas)}  # fmt: skip


def organizar_marcas(
    regua: Regua, a: AvaliadorAnalise, correcoes: Optional[List[AvaliadorCorrecao]] = None
) -> dict:
    """O que a tela mostra de uma leitura no formato 3. Na ordem do Manual, sem contagem,
    percentual nem ordem entre subpilares (decisão de 18/10). Peça SEM cliente com nome: as
    marcas que só se esperam com cliente nomeado saem dos subpilares e vão para um grupo à
    parte, conferidas do mesmo jeito. Sem a resposta (NULL), nada é separado.

    O texto da marca é o GRAVADO na leitura (a pergunta a que ela respondeu); o "porque
    importa" e a exceção vêm da régua de hoje. Marca que saiu do Manual depois da leitura
    continua aparecendo, com o texto gravado, no grupo gravado.

    Cada subpilar (e o bloco C e o grupo à parte) leva também a forma simétrica da tela
    (21/10, ``_bloco_de_marcas``): diz, não diz e sem conferência. A tela é a superfície de
    conferência e mostra tudo; o que entra no parecer é escolha de quem o escreve.

    ``correcoes`` (as ativas da leitura, ``correcoes_de``) são aplicadas por cima do gravado,
    marca a marca (``_aplicar_correcoes``); o resultado gravado não muda."""
    g = json.loads(a.itens_json)
    correcoes = correcoes or []
    da_regua = {m.codigo: m for m in regua.marcas}
    separa = a.cliente_nomeado is False
    linhas, a_parte = [], []
    for m in g["marcas"]:
        r = da_regua.get(m["codigo"])
        linha = {
            **_aplicar_correcoes(m, correcoes),
            "porque_importa": r.porque_importa if r else "",
            # leitura anterior a uma mudança do Manual: a pergunta gravada já não é a de hoje
            "nota": (
                "marca que saiu do Manual depois desta leitura"
                if r is None
                else (
                    "pergunta reescrita no Manual depois desta leitura"
                    if r.texto != m["texto"]
                    else ""
                )
            ),
            "subpilar": regua.subpilar(m["grupo"]) if m["grupo"] in SUBPILARES_ORDEM else None,
            # a página da frente do parecer (Manual v14): o nome curto e a exceção de hoje
            "nome_curto": r.nome_curto if r else "",
            "so_cliente_nomeado": bool(r and r.so_cliente_nomeado),
        }
        (a_parte if separa and r and r.so_cliente_nomeado else linhas).append(linha)
    pergunta = {x["codigo"]: x["pergunta"] for x in (regua.marcas_cap or {}).get("pilares", [])}
    fora = [x for x in linhas if x["grupo"] == GRUPO_FORA]
    pilares = [
        {
            "pilar": p,
            "pergunta": pergunta.get(p.codigo, ""),
            "subpilares": [
                {"subpilar": s, "marcas": ms, **_bloco_de_marcas(ms)}
                for s in p.subpilares
                for ms in [[x for x in linhas if x["grupo"] == s.codigo]]
            ],
        }
        for p in regua.pilares
    ]
    return {
        "perguntas_leitor": regua.perguntas_leitor,
        "cobertura": veredito.declarar_cobertura(g["cobertura"]),
        "cliente_nomeado": a.cliente_nomeado,
        "achados": g["achados"],
        "contradicoes": g["contradicoes"],
        "pilares": pilares,
        "fora_dos_doze": {
            **(regua.marcas_cap or {}).get("fora_dos_doze", {}),
            "marcas": fora,
            **_bloco_de_marcas(fora),
        },
        "a_parte": a_parte,
        "a_parte_bloco": _bloco_de_marcas(a_parte),
    }


# ── criação e ações da pessoa ─────────────────────────────────────────────


def _descricao(descricao: str) -> str:
    d = (descricao or "").strip()
    if not d:
        raise AvaliacaoRecusada("Diga em uma linha o que é a peça e para que ela serve.")
    return d[:LIMITE_DESCRICAO]


def criar_analise(
    s: Session,
    empresa_id: int,
    usuario_id: Optional[int],
    descricao: str,
    *,
    nome: Optional[str] = None,
    dados: Optional[bytes] = None,
    texto: Optional[str] = None,
    url: Optional[str] = None,
    sessao_http=None,
    cliente_nomeado: Optional[bool] = None,
) -> AvaliadorAnalise:
    """Arquivo (``dados``), texto colado (``texto``) OU endereço de página (``url``), um
    só. Extrai (a página é buscada AGORA, na requisição, para o erro aparecer na hora),
    cobra o teto e grava PENDENTE. Levanta ``DocumentoRecusado`` (inclui
    ``PaginaRecusada``) ou ``AvaliacaoRecusada`` antes de gastar. ``cliente_nomeado`` é
    obrigatório (18/10): a peça foi feita para um cliente com nome?"""
    descricao = _descricao(descricao)
    if cliente_nomeado is None:
        raise AvaliacaoRecusada("Diga se a peça foi feita para um cliente com nome.")
    entradas = [bool(dados), bool((texto or "").strip()), bool((url or "").strip())]
    if sum(entradas) != 1:
        raise AvaliacaoRecusada(
            "Envie um arquivo, cole um texto ou informe o endereço de uma página (um só)."
        )
    modelo = get_config().AVALIADOR_MODEL
    motor.garantir_preco(modelo)
    if dados:
        doc, origem, bruto = extrair(dados), ORIGEM_ARQUIVO, dados
    elif entradas[1]:
        doc, origem, bruto = documento_de_texto(texto), ORIGEM_TEXTO, texto.encode("utf-8")
    else:
        from src.avaliador.pagina_web import ler_paginas

        # uma ou várias páginas, uma por linha; nome = os endereços que foram LIDOS
        lidos, bruto, doc = ler_paginas(url, sessao=sessao_http)
        nome, origem = "\n".join(lidos), ORIGEM_PAGINA
    regua = carregar_regua()
    versao = marcas.PROMPT_VERSAO
    sistema, usuario = _pedido(regua, origem, descricao, doc)
    checar_teto(s, empresa_id, _estimativa(regua, sistema, usuario, modelo))
    a = AvaliadorAnalise(
        empresa_id=empresa_id,
        usuario_id=usuario_id,
        origem=origem,
        descricao=descricao,
        cliente_nomeado=cliente_nomeado,
        arquivo_nome=(nome or "")[: 22000 if origem == ORIGEM_PAGINA else 200] or None,
        conteudo_hash=hashlib.sha256(bruto).hexdigest(),
        formato=doc.formato,
        n_paginas=doc.n_paginas,
        paginas_sem_texto_json=json.dumps(doc.paginas_sem_texto),
        texto_json=doc.para_json(),
        status=STATUS_PENDENTE,
        itens_json="[]",
        modelo=modelo,
        regua_versao=regua.versao,
        prompt_versao=versao,
        tokens_in=0,
        tokens_out=0,
        tokens_cache_criacao=0,
        tokens_cache_leitura=0,
        custo_usd=0.0,
    )
    s.add(a)
    s.flush()
    return a


def _exigir_texto(a: AvaliadorAnalise) -> Documento:
    if a.texto_json is None:
        raise AvaliacaoRecusada(
            "O texto desta peça já foi apagado (análise concluída ou sem uso). "
            "Para ler de novo, envie a peça outra vez."
        )
    return Documento.de_json(a.texto_json)


# Peças de medição (21/10): as leituras que sustentam o gabarito das marcas (#24, #25 e #26,
# o site da Loyall lido três vezes em 19/10) e o site da Localiza: #28 (21/10, régua de 87)
# e #31 (22/10, régua de 79, base do parecer modelo). O texto
# guardado é a entrada congelada dos testes de reescrita e o resultado gravado é a linha de
# base: reler sobrescreve a leitura, concluir e o watchdog apagam o texto, apagar some com
# tudo. Para estas, o watchdog não apaga o texto e as três ações são recusadas. São ids de
# produção; se vierem mais peças fixas, isto vira coluna.
PECAS_DE_MEDICAO = frozenset({24, 25, 26, 28, 31})


def e_peca_de_medicao(a: AvaliadorAnalise) -> bool:
    return a.id in PECAS_DE_MEDICAO


def _exigir_alteravel(a: AvaliadorAnalise) -> None:
    if e_peca_de_medicao(a):
        raise AvaliacaoRecusada(
            "Peça de medição: o texto e o resultado desta leitura são a base do gabarito "
            "das marcas, e por isso ela não pode ser relida, concluída nem apagada. Para "
            "ler a mesma peça de novo, envie-a outra vez."
        )


def _exigir_parada(a: AvaliadorAnalise) -> None:
    if a.status in STATUS_EM_PROCESSAMENTO:
        raise AvaliacaoRecusada("A leitura ainda está em andamento.")


def marcar_uso(a: AvaliadorAnalise) -> None:
    a.usado_em = datetime.utcnow()


def refazer(s: Session, a: AvaliadorAnalise, descricao: Optional[str] = None) -> None:
    """Relê a peça guardada — com nova descrição, se vier (substitui a "correção de tipo"
    do desenho anterior). Paga uma leitura nova: o gate cobra antes."""
    _exigir_alteravel(a)
    _exigir_parada(a)
    doc = _exigir_texto(a)
    if descricao is not None:
        a.descricao = _descricao(descricao)
    regua, versao = carregar_regua(), marcas.PROMPT_VERSAO
    sistema, usuario = _pedido(regua, a.origem, a.descricao, doc)
    checar_teto(s, a.empresa_id, _estimativa(regua, sistema, usuario, a.modelo))
    a.prompt_versao = versao
    a.status = STATUS_PENDENTE
    a.erro_motivo = None
    marcar_uso(a)


def apagar_texto(a: AvaliadorAnalise, motivo: str, quando: Optional[datetime] = None) -> None:
    if a.texto_json is not None:
        a.texto_json = None
        a.texto_apagado_em = quando or datetime.utcnow()
        a.texto_apagado_motivo = motivo


def concluir(a: AvaliadorAnalise) -> None:
    _exigir_alteravel(a)
    _exigir_parada(a)
    apagar_texto(a, "concluida")
    marcar_uso(a)


# ── correção à mão (fatia 1 do parecer no app, 22/10) ─────────────────────


def correcoes_de(a: AvaliadorAnalise) -> List[AvaliadorCorrecao]:
    """As correções ativas da leitura (desfeitas ficam no banco e não contam), na ordem."""
    s = object_session(a)
    if s is None or a.id is None:
        return []
    return list(
        s.scalars(
            select(AvaliadorCorrecao)
            .where(AvaliadorCorrecao.analise_id == a.id, AvaliadorCorrecao.desfeita_em.is_(None))
            .order_by(AvaliadorCorrecao.id)
        )
    )


def _exigir_corrigivel(a: AvaliadorAnalise) -> None:
    if a.status != STATUS_PRONTA or formato_da_leitura(a) != FORMATO_MARCAS:
        raise AvaliacaoRecusada("Só uma leitura pronta, no formato atual, pode ser corrigida.")


def _marca_gravada(a: AvaliadorAnalise, codigo: str) -> dict:
    m = next((m for m in json.loads(a.itens_json)["marcas"] if m["codigo"] == codigo), None)
    if m is None:
        raise AvaliacaoRecusada("Essa marca não está nesta leitura.")
    return m


def _ativa(a: AvaliadorAnalise, codigo: str, tipo: str, trecho: str):
    return next(
        (
            c
            for c in correcoes_de(a)
            if (c.marca_codigo, c.tipo, c.trecho) == (codigo, tipo, trecho)
        ),
        None,
    )


def recusar_trecho(
    s: Session, a: AvaliadorAnalise, codigo: str, trecho: str, usuario_id: Optional[int]
) -> None:
    """A pessoa diz que um trecho citado pela leitura não responde à marca. Fica gravado; o
    resultado da leitura não muda. Vale também nas peças de medição: a base fica intacta."""
    _exigir_corrigivel(a)
    m = _marca_gravada(a, codigo)
    # o navegador envia quebra de linha como \r\n: compara normalizado e grava o trecho
    # como está na leitura (é contra ele que a tela aplica a recusa)
    alvo = _normalizar(trecho)
    ev = next(
        (
            e
            for e in m.get("evidencias", [])
            if e.get("conferido") and _normalizar(e["trecho"]) == alvo
        ),
        None,
    )
    if ev is None:
        raise AvaliacaoRecusada("Esse trecho não é um dos citados para esta marca.")
    trecho = ev["trecho"]
    if _ativa(a, codigo, CORRECAO_RECUSA, trecho) is None:
        s.add(
            AvaliadorCorrecao(
                analise_id=a.id, conteudo_hash=a.conteudo_hash, marca_codigo=codigo,
                marca_texto=m["texto"], tipo=CORRECAO_RECUSA, trecho=trecho,
                pagina=ev.get("pagina_encontrada"), usuario_id=usuario_id,
            )
        )  # fmt: skip
    marcar_uso(a)


def recusar_nao_achadas(s: Session, a: AvaliadorAnalise, codigo: str, usuario_id: Optional[int]):
    """Resolve o "sem conferência": a pessoa diz que a peça não tem o que a leitura citou e não
    foi achado. Recusa cada citação não achada da marca (o texto delas, que é do modelo, fica no
    banco e nunca na tela; por isso a tela manda só o código da marca)."""
    _exigir_corrigivel(a)
    m = _marca_gravada(a, codigo)
    nao_achadas = [e for e in m.get("evidencias", []) if not e.get("conferido")]
    if not nao_achadas:
        raise AvaliacaoRecusada("Esta marca não tem citação sem conferência.")
    for e in nao_achadas:
        if _ativa(a, codigo, CORRECAO_RECUSA, e["trecho"]) is None:
            s.add(
                AvaliadorCorrecao(
                    analise_id=a.id, conteudo_hash=a.conteudo_hash, marca_codigo=codigo,
                    marca_texto=m["texto"], tipo=CORRECAO_RECUSA, trecho=e["trecho"],
                    pagina=None, usuario_id=usuario_id,
                )
            )  # fmt: skip
    marcar_uso(a)


def incluir_trecho(
    s: Session, a: AvaliadorAnalise, codigo: str, trecho: str, usuario_id: Optional[int]
) -> None:
    """A pessoa achou na peça o trecho que responde à marca. Só entra se estiver na peça,
    com a mesma conferência das citações da leitura; por isso precisa do texto guardado."""
    _exigir_corrigivel(a)
    m = _marca_gravada(a, codigo)
    if a.texto_json is None:
        raise AvaliacaoRecusada(
            "O texto desta peça já foi apagado, e sem ele não dá para conferir o trecho novo. "
            "Para incluir trecho, envie a peça outra vez."
        )
    achada, literal, _ = localizar_trecho(Documento.de_json(a.texto_json), None, trecho.strip())
    if achada is None:
        raise AvaliacaoRecusada(
            "Esse trecho não foi achado na peça. Copie o texto exatamente como está nela, com "
            "pelo menos 12 caracteres."
        )
    if _ativa(a, codigo, CORRECAO_INCLUSAO, literal) is None:
        s.add(
            AvaliadorCorrecao(
                analise_id=a.id, conteudo_hash=a.conteudo_hash, marca_codigo=codigo,
                marca_texto=m["texto"], tipo=CORRECAO_INCLUSAO, trecho=literal, pagina=achada,
                usuario_id=usuario_id,
            )
        )  # fmt: skip
    marcar_uso(a)


def desfazer_correcao(s: Session, a: AvaliadorAnalise, correcao_id: int) -> None:
    """Desfazer não apaga: marca a hora. A correção desfeita continua no banco."""
    c = s.get(AvaliadorCorrecao, correcao_id)
    if c is None or c.analise_id != a.id or c.desfeita_em is not None:
        raise AvaliacaoRecusada("Essa correção não está ativa nesta leitura.")
    c.desfeita_em = datetime.utcnow()
    marcar_uso(a)


# ── o parecer (fatia 2, 22/10) ──────────────────────────────────────────────

CAMPO_ORDEM = "ordem"
CAMPO_NOTA_C = "nota_c"
CAMPO_EMPRESA = "empresa_da_peca"
# A conta interna onde mora a leitura de prospect (decisão de 22/10, Contexto-Mestre §4.69).
# Prospect não tem conta própria; lido dentro da conta de um cliente, o custo cai no teto
# dele e a leitura vai junto se a conta for zerada.
CONTA_PROSPECTS = "Loyall: prospects"


def parecer_de(a: AvaliadorAnalise) -> Optional[AvaliadorParecer]:
    s = object_session(a)
    if s is None or a.id is None:
        return None
    return s.scalars(select(AvaliadorParecer).where(AvaliadorParecer.analise_id == a.id)).first()


def textos_do_parecer(a: AvaliadorAnalise) -> dict:
    """O que a pessoa escreveu: {"ordem", "nota_c", "achados": {subpilar: frase},
    "escolhas": {marca: trecho escolhido para o parecer}}."""
    p = parecer_de(a)
    if p is None:
        return {
            "empresa_da_peca": "", "ordem": "", "nota_c": "", "achados": {}, "escolhas": {},
            "rascunho": {},
        }  # fmt: skip
    return {
        "empresa_da_peca": p.empresa_da_peca or "",
        "ordem": p.ordem,
        "nota_c": p.nota_c,
        "achados": json.loads(p.achados_json or "{}"),
        "escolhas": json.loads(p.escolhas_json or "{}"),
        "rascunho": json.loads(p.rascunho_json or "{}"),
    }


def _parecer_ou_novo(s: Session, a: AvaliadorAnalise) -> AvaliadorParecer:
    p = parecer_de(a)
    if p is None:
        p = AvaliadorParecer(
            analise_id=a.id, empresa_da_peca="", ordem="", achados_json="{}", nota_c="",
            escolhas_json="{}",
            rascunho_json="{}", rascunho_custo_usd=0.0,
        )  # fmt: skip
        s.add(p)
    return p


def escolher_trecho(
    s: Session, a: AvaliadorAnalise, codigo: str, trecho: str, usuario_id: Optional[int]
) -> None:
    """ "Usar este no parecer": a pessoa troca o trecho que a marca leva para o parecer. Não é
    correção (não vai para avaliador_correcoes). Vale só trecho que a tela mostra como resposta
    da marca, já com as correções; se ele for recusado depois, o parecer volta ao automático."""
    _exigir_corrigivel(a)
    m = _marca_gravada(a, codigo)
    efetiva = _aplicar_correcoes(m, correcoes_de(a))
    alvo = _normalizar(trecho)
    ev = next(
        (
            e
            for e in efetiva["evidencias"]
            if e.get("conferido") and _normalizar(e["trecho"]) == alvo
        ),
        None,
    )
    if ev is None:
        raise AvaliacaoRecusada("Esse trecho não é uma resposta desta marca na tela.")
    p = _parecer_ou_novo(s, a)
    escolhas = json.loads(p.escolhas_json or "{}")
    escolhas[codigo] = ev["trecho"]
    p.escolhas_json = json.dumps(escolhas, ensure_ascii=False)
    p.usuario_id = usuario_id
    p.atualizado_em = datetime.utcnow()
    marcar_uso(a)


def salvar_parecer(
    s: Session, a: AvaliadorAnalise, campo: str, texto: str, usuario_id: Optional[int]
) -> None:
    """Um campo do parecer: a ordem, a nota do bloco C ou o achado de um subpilar (o campo é
    o código do subpilar). Escrever o parecer conta como usar a leitura."""
    _exigir_corrigivel(a)
    if campo not in (CAMPO_ORDEM, CAMPO_NOTA_C, CAMPO_EMPRESA) and campo not in SUBPILARES_ORDEM:
        raise AvaliacaoRecusada("Campo do parecer desconhecido.")
    p = _parecer_ou_novo(s, a)
    texto = (texto or "").strip()
    if campo == CAMPO_ORDEM:
        p.ordem = texto
    elif campo == CAMPO_NOTA_C:
        p.nota_c = texto
    elif campo == CAMPO_EMPRESA:
        p.empresa_da_peca = texto[:200]
    else:
        achados = json.loads(p.achados_json or "{}")
        achados[campo] = texto
        p.achados_json = json.dumps(achados, ensure_ascii=False)
    rj = json.loads(p.rascunho_json or "{}")
    if campo in rj and texto != rj[campo]["rascunho"]:
        rj[campo]["estado"] = RASCUNHO_EDITADO  # a pessoa escreveu por cima: fica guardado
        p.rascunho_json = json.dumps(rj, ensure_ascii=False)
    p.usuario_id = usuario_id
    p.atualizado_em = datetime.utcnow()
    marcar_uso(a)


# ── o rascunho do modelo (fatia 3, 22/10) ─────────────────────────────────

RASCUNHO_PENDENTE, RASCUNHO_ACEITO, RASCUNHO_EDITADO = "pendente", "aceito", "editado"


def _texto_do_campo(p: AvaliadorParecer, campo: str) -> str:
    if campo == CAMPO_ORDEM:
        return p.ordem or ""
    return json.loads(p.achados_json or "{}").get(campo, "")


def estimativa_rascunho(a: AvaliadorAnalise, tela: dict) -> float:
    """Pior caso do rascunho em US$ (a chamada e a nova tentativa): a tela declara antes."""
    from src.avaliador import rascunho as R

    texto, _ = R.entrada(tela, textos_do_parecer(a)["escolhas"], a.descricao or "")
    um = motor._pior_caso_usd(a.modelo, len(R.sistema()) + len(texto) + len(R.PEDIDO), R.MAX_TOKENS)
    return um * motor.TENTATIVAS


def rascunhar_parecer(
    s: Session, a: AvaliadorAnalise, usuario_id: Optional[int], client=None
) -> List[str]:
    """O modelo rascunha a frase da ordem e os doze achados a partir da tela corrigida. Só
    preenche campo EM BRANCO: o que a pessoa já escreveu não muda. Cada campo preenchido
    fica "pendente" até a pessoa editar ou aceitar como está; o Word não sai antes. O gasto
    fica gravado mesmo se a chamada falhar, e entra no teto mensal. Devolve os campos
    preenchidos."""
    from src.avaliador import parecer as P
    from src.avaliador import rascunho as R

    _exigir_corrigivel(a)
    regua = carregar_regua()
    tela = organizar_marcas(regua, a, correcoes_de(a))
    textos = textos_do_parecer(a)
    falta = P.montar(tela, textos, a.id, "", json.loads(a.itens_json)["cobertura"])["falta"]
    if falta["regua"]:
        raise AvaliacaoRecusada(
            "Esta leitura foi feita antes da régua de hoje: o rascunho sairia sobre marcas "
            "que mudaram. Faça uma leitura nova da peça."
        )
    if falta["conferir"]:
        raise AvaliacaoRecusada(
            "Antes do rascunho, resolva as marcas sem conferência: o modelo escreve a partir "
            "do que a tela mostra, e ela ainda não está fechada."
        )
    campos = [CAMPO_ORDEM, *SUBPILARES_ORDEM]
    escrito = {CAMPO_ORDEM: textos["ordem"], **textos["achados"]}
    vazios = [c for c in campos if not (escrito.get(c) or "").strip()]
    if not vazios:
        raise AvaliacaoRecusada(
            "A ordem e os doze achados já estão escritos: o rascunho só preenche campo em branco."
        )
    texto, base = R.entrada(tela, textos["escolhas"], a.descricao or "")
    limite = estimativa_rascunho(a, tela)
    checar_teto(s, a.empresa_id, limite)  # antes do gasto
    if client is None:
        from src.classifier.classifier_v3 import _get_client

        client = _get_client()
    p = _parecer_ou_novo(s, a)
    orc = {"total": motor.Uso(), "limite": limite}
    try:
        obj = motor._chamar(
            client, a.modelo, R.sistema(), texto, R.PEDIDO, R.MAX_TOKENS, R.validar, orc
        )
    except Exception as e:  # noqa: BLE001 — o gasto conta mesmo na falha
        p.rascunho_custo_usd = (p.rascunho_custo_usd or 0.0) + orc["total"].custo_usd
        p.rascunho_em = datetime.utcnow()
        p.rascunho_versao = R.VERSAO
        logger.warning(f"[avaliador] rascunho do parecer falhou na leitura {a.id}: {e!r}")
        raise AvaliacaoRecusada(
            f"O rascunho não saiu ({type(e).__name__}). Nada foi escrito nos campos; o gasto "
            f"desta tentativa, US$ {virg(orc['total'].custo_usd, 4)}, fica registrado."
        ) from None
    p.rascunho_custo_usd = (p.rascunho_custo_usd or 0.0) + orc["total"].custo_usd
    p.rascunho_em = datetime.utcnow()
    p.rascunho_versao = R.VERSAO
    rj = json.loads(p.rascunho_json or "{}")
    achados = json.loads(p.achados_json or "{}")
    for c in vazios:
        if c == CAMPO_ORDEM:
            p.ordem = obj[c]
        else:
            achados[c] = obj[c]
        rj[c] = {"rascunho": obj[c], "estado": RASCUNHO_PENDENTE, "base": base}
    p.achados_json = json.dumps(achados, ensure_ascii=False)
    p.rascunho_json = json.dumps(rj, ensure_ascii=False)
    p.usuario_id = usuario_id
    p.atualizado_em = datetime.utcnow()
    marcar_uso(a)
    return vazios


def aceitar_rascunho(
    s: Session, a: AvaliadorAnalise, campo: str, usuario_id: Optional[int]
) -> None:
    """ "Aceito como está": a pessoa passou pelo campo do rascunho sem mudar o texto. Vale
    sobre a tela de agora (a base passa a ser a de agora)."""
    from src.avaliador import rascunho as R

    _exigir_corrigivel(a)
    p = parecer_de(a)
    rj = json.loads((p.rascunho_json if p else None) or "{}")
    if campo not in rj:
        raise AvaliacaoRecusada("Esse campo não veio do rascunho do modelo.")
    if not _texto_do_campo(p, campo).strip():
        raise AvaliacaoRecusada("O campo está em branco: escreva o texto antes.")
    tela = organizar_marcas(carregar_regua(), a, correcoes_de(a))
    _, base = R.entrada(tela, textos_do_parecer(a)["escolhas"], a.descricao or "")
    if rj[campo]["estado"] != RASCUNHO_EDITADO:
        rj[campo]["estado"] = RASCUNHO_ACEITO
    rj[campo]["base"] = base
    p.rascunho_json = json.dumps(rj, ensure_ascii=False)
    p.usuario_id = usuario_id
    p.atualizado_em = datetime.utcnow()
    marcar_uso(a)


def apagar_leitura(a: AvaliadorAnalise) -> None:
    """Apaga o que é da peça e deixa só o gasto (ver ``src/models/avaliador.py``).
    Recusa em andamento: a leitura gravaria resumo e itens por cima. As correções à mão
    ficam, sem o trecho (que é da peça): sobra que marca foi corrigida e como. O texto do
    parecer sai."""
    _exigir_alteravel(a)
    _exigir_parada(a)
    s = object_session(a)
    if s is not None:
        for c in s.scalars(select(AvaliadorCorrecao).where(AvaliadorCorrecao.analise_id == a.id)):
            c.trecho = ""
        p = parecer_de(a)
        if p is not None:  # o parecer fala da peça: sai junto
            p.ordem, p.nota_c, p.achados_json, p.escolhas_json = "", "", "{}", "{}"
            p.empresa_da_peca = ""
            p.rascunho_json = "{}"  # o texto do modelo também fala da peça; o gasto fica
    apagar_texto(a, "leitura_apagada")
    a.descricao = ""
    a.arquivo_nome = None
    a.conteudo_hash = ""
    a.resumo = None
    a.itens_json = "[]"
    a.paginas_sem_texto_json = "[]"
    a.status = STATUS_APAGADA


# ── processamento (thread) ────────────────────────────────────────────────


def processar(analise_id: int, client=None) -> None:
    if client is None:
        from src.classifier.classifier_v3 import _get_client

        client = _get_client()
    regua = carregar_regua()
    with db_session() as s:
        a = s.get(AvaliadorAnalise, analise_id)
        if a is None:
            return
        try:
            doc = _exigir_texto(a)
            a.status = STATUS_LENDO
            a.atualizado_em = datetime.utcnow()
            s.commit()
            # toda leitura sai nas marcas de hoje; a que estava na fila numa versão
            # anterior (de qualquer formato) passa a levar a versão com que foi lida
            a.prompt_versao = marcas.PROMPT_VERSAO
            sistema, usuario = _pedido(regua, a.origem, a.descricao, doc)
            orc = _estimativa(regua, sistema, usuario, a.modelo)
            try:
                res, uso = marcas.ler(
                    client, a.modelo, regua, sistema, usuario, doc, orcamento_usd=orc
                )
            except (motor.RespostaInvalida, motor.OrcamentoEsgotado) as err:
                _somar_uso(a, getattr(err, "uso", None) or motor.Uso())
                raise
            _somar_uso(a, uso)
            a.resumo = None  # formato 3 não tem resumo: tudo vai no objeto gravado
            a.itens_json = marcas.para_gravar(res)
            a.erro_motivo = None
            a.regua_versao = regua.versao
            a.status = STATUS_PRONTA
            a.atualizado_em = datetime.utcnow()
        except Exception as e:  # noqa: BLE001 — toda falha vira estado visível
            a.status = STATUS_FALHOU
            a.erro_motivo = f"leitura: {type(e).__name__}"
            a.atualizado_em = datetime.utcnow()
            logger.warning(f"[avaliador] analise={a.id} erro={type(e).__name__}")


def disparar(analise_id: int, app=None) -> bool:
    from src.coletor.orquestrador import _rodar_async

    return _rodar_async(lambda: processar(analise_id), app=app, label=f"avaliador-{analise_id}")


# ── housekeeping (watchdog) ───────────────────────────────────────────────


def housekeeping(s: Session, agora: Optional[datetime] = None) -> Dict[str, int]:
    """(a) marca FALHOU a análise em processamento sem heartbeat há > 20 min (thread
    morta por deploy); (b) apaga o texto das análises sem uso há mais que
    ``dias_retencao()`` dias, menos as peças de medição. Só UPDATE — zero chamada paga.
    Idempotente."""
    agora = agora or datetime.utcnow()
    orfas = s.scalars(
        select(AvaliadorAnalise).where(
            AvaliadorAnalise.status.in_(STATUS_EM_PROCESSAMENTO),
            AvaliadorAnalise.atualizado_em < agora - HEARTBEAT_LIMITE,
        )
    ).all()
    for a in orfas:
        a.status = STATUS_FALHOU
        a.erro_motivo = "interrompida, provável reinício do servidor; use tentar de novo"
        a.atualizado_em = agora
    expiradas = s.scalars(
        select(AvaliadorAnalise).where(
            AvaliadorAnalise.texto_json.is_not(None),
            AvaliadorAnalise.status.not_in(STATUS_EM_PROCESSAMENTO),
            AvaliadorAnalise.usado_em < agora - timedelta(days=dias_retencao()),
            AvaliadorAnalise.id.not_in(PECAS_DE_MEDICAO),
        )
    ).all()
    for a in expiradas:
        apagar_texto(a, "expirada", agora)
    return {"orfas": len(orfas), "textos_apagados": len(expiradas)}
