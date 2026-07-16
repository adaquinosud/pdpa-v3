"""Seeder de respostas de pesquisa (DADO DE TESTE) — valida o fluxo ponta-a-ponta.

Gera N respondentes aleatórios para uma pesquisa pública e POSTa cada um no
endpoint real ``/p/<token>`` (NÃO chama ``registrar_respostas`` direto) — passa pela
validação server-side, pelo hash de dedup e por tudo o que um respondente real toca.

Por respondente:
  - Unidade (âncora): escolhe uma das opções ao acaso.
  - Notas: valor aleatório 1..5 em CADA pergunta de nota.
  - Comentário: ~75% de chance por pergunta (o resto vai nota-only — exercita
    exatamente o caminho que estourava 500 antes do fix do dedup 1579fd6). A frase é
    sorteada do banco DO SUBPILAR daquela pergunta (não de um banco único) — assim os
    comentários de um mesmo subpilar ficam coerentes entre si, formam cluster e viram
    tema. As NOTAS seguem aleatórias (não é ferida plantada — só tema que se agrupe).
  - Identidade: por padrão anônimo (sem ?c=/email). Com ``--pct-identificados N`` (0-100),
    N%% dos respondentes postam IDENTIFICADOS carimbando ``c=<id_cliente>`` no form (o mesmo
    mecanismo do link ?c= real → passa por ``_reconciliar_pessoa`` → vira Pessoa). Os 6 IDs
    de cruzamento fixos (CRUZA-01..05, TESTE-CRUZA) entram primeiro — os mesmos de um Excel a
    importar, pra provar o cross-fonte na tela de pessoa. Trava de reenvio do endpoint: 1
    resposta por pessoa/pesquisa (o volume extra dos CRUZA vem do Excel, não de repetir POST).

TRAVA DE SEGURANÇA: lê a pesquisa no banco, imprime empresa (id + nome) + título e
ABORTA se a empresa não for a esperada (default 18) — evita gerar lixo em empresa real.

Uso (Render Shell ou local):
    python scripts/seed_respostas_pesquisa.py --token <token> --n 20 \
        --pct-identificados 80 --base-url https://pdpa-web.onrender.com

Depois de gerar:
  (a) É preciso rodar o PÓS-COLETA — o verbatim de pesquisa-web nasce CRU (sem
      subpilar/tipo); a classificação + temização rodam no pós-coleta. A resposta
      NÃO herda o subpilar_alvo da pergunta.
  (b) Limpeza: apagar a fonte 'pesquisa_web' da empresa + seus verbatins + os
      respondentes (ver --como-limpar no rodapé do relatório).
"""

from __future__ import annotations

import argparse
import random
import sys

import requests

# Banco de comentários POR SUBPILAR (não um banco único). Linguagem genérica de relação
# empresa-cliente — serve pra qualquer setor. 4 variações por subpilar: massa pro cluster
# se formar, mas variando o suficiente pra não ser 1 frase repetida. A "dor" de cada
# subpilar é coerente entre si → o clusterer forma tema em cada um dos 12.
_COMENTARIOS_POR_SUBPILAR = {
    "P1": [  # Calibração da Promessa
        "não era o que tinham prometido",
        "o serviço veio diferente do anunciado",
        "prometeram uma coisa e entregaram outra",
        "a realidade não bateu com o que foi vendido",
    ],
    "P2": [  # Qualidade da Entrega
        "a qualidade deixou a desejar",
        "veio com defeito",
        "o resultado final ficou abaixo do esperado",
        "entregaram com problemas",
    ],
    "P3": [  # Consistência ao Longo do Tempo
        "cada vez é uma experiência diferente",
        "num dia é bom, no outro é ruim",
        "falta padrão, nunca sei o que esperar",
        "a experiência varia demais de uma vez pra outra",
    ],
    "D1": [  # Acessibilidade
        "difícil conseguir contato",
        "ninguém atende o telefone",
        "não consigo falar com alguém quando preciso",
        "os canais de contato não funcionam",
    ],
    "D2": [  # Eficácia Operacional
        "demorou demais pra resolver",
        "abri chamado e nunca voltaram",
        "o problema se arrastou por semanas",
        "ficaram de retornar e não retornaram",
    ],
    "D3": [  # Proatividade Estruturada
        "só avisaram depois do problema",
        "ninguém me antecipou nada",
        "fui pego de surpresa, poderiam ter avisado",
        "esperei o problema estourar pra alguém agir",
    ],
    "Pa1": [  # Empatia Comercial
        "trataram com descaso",
        "senti que não se importaram",
        "fui tratado com indiferença",
        "faltou empatia no atendimento",
    ],
    "Pa2": [  # Mutualidade
        "pago em dia e não recebo o mesmo em troca",
        "cobram certinho mas não entregam",
        "a relação é de mão única",
        "sou cliente fiel e não vejo reciprocidade",
    ],
    "Pa3": [  # Comprometimento Relacional
        "sumiram depois da venda",
        "só ligam quando querem vender",
        "depois que fecharam não deram mais atenção",
        "o pós-venda é inexistente",
    ],
    "A1": [  # Exemplo
        "poderiam ser referência mas decepcionam",
        "esperava mais de uma empresa desse porte",
        "não são o exemplo que dizem ser",
        "para o tamanho que têm, deixam a desejar",
    ],
    "A2": [  # Orientação
        "não me orientaram quando precisei",
        "faltou orientação técnica",
        "ninguém me explicou as opções direito",
        "precisei me virar sozinho, sem orientação",
    ],
    "A3": [  # Recomendação Proativa
        "nunca sugerem nada melhor",
        "não indicam o que seria ideal pra mim",
        "poderiam recomendar o que faz sentido e não fazem",
        "faltou uma sugestão do que seria melhor pra mim",
    ],
}

_PROB_COMENTARIO = 0.75  # ~75% das respostas com comentário (o resto nota-only)

# IDs de cruzamento FIXOS (os mesmos de um Excel a importar) — sempre que houver cota de
# identificados, estes entram PRIMEIRO e garantidos. O cross-fonte (pesquisa + Excel) da
# MESMA pessoa se prova na tela de pessoa; o volume extra deles vem do Excel (o endpoint
# real tem trava de reenvio: 1 resposta por pessoa/pesquisa).
_FIXOS_CRUZA = ["CRUZA-01", "CRUZA-02", "CRUZA-03", "CRUZA-04", "CRUZA-05", "TESTE-CRUZA"]


def _planeja_identidades(n: int, pct_identificados: int, rng: random.Random):
    """Decide, para cada um dos ``n`` respondentes, um ``id_cliente`` (identificado, carimbado
    como ``?c=`` no POST) ou ``None`` (anônimo, comportamento de hoje).

    ``n_ident = round(n * pct/100)``. Os IDs FIXOS de cruzamento entram primeiro (todos os 6
    quando a cota comporta; senão os primeiros que couberem); o resto dos identificados usa
    ``PESQ-2xx`` gerados. A lista é embaralhada (RNG semeado) pra não agrupar os identificados
    no começo. ``pct=0`` → tudo ``None`` (idêntico ao seeder original)."""
    pct = max(0, min(100, pct_identificados))
    n_ident = round(n * pct / 100)
    fixos = _FIXOS_CRUZA[:n_ident]  # todos os 6 quando n_ident >= 6
    extras = [f"PESQ-{201 + i}" for i in range(max(0, n_ident - len(fixos)))]
    codigos = fixos + extras  # len == n_ident, todos distintos
    ids = codigos + [None] * (n - n_ident)
    if n_ident:  # pct=0 → não toca o RNG (stream idêntico ao seeder original)
        rng.shuffle(ids)
    return ids


def _carregar_pesquisa(token: str, empresa_esperada: int):
    """Lê a pesquisa pelo token, imprime empresa + título e aplica a trava. Devolve
    ``(pesquisa_id, titulo, [perguntas], sub_por_pergunta)`` onde cada pergunta é o dict
    de ``payload_publico`` (id/formato/opcoes) e ``sub_por_pergunta`` mapeia
    ``pergunta_id → subpilar_alvo`` (lido do banco: o payload público NÃO expõe o
    subpilar_alvo — Regra 6 — mas é ele que escolhe o banco de comentário coerente)."""
    from src.models.empresa import Empresa
    from src.models.pesquisa import Pesquisa, PesquisaPergunta
    from src.pesquisa.persistencia import payload_publico
    from src.utils.db import db_session

    with db_session() as s:
        pesq = s.query(Pesquisa).filter_by(token_publico=token).first()
        if pesq is None:
            print(f"ERRO: nenhuma pesquisa com token {token!r}.")
            sys.exit(1)
        empresa = s.get(Empresa, pesq.empresa_id)
        nome = empresa.nome if empresa else "(sem empresa)"
        print("── ALVO ──────────────────────────────────────────────")
        print(f"  pesquisa : p{pesq.id} · {pesq.titulo!r}")
        print(f"  empresa  : {pesq.empresa_id} · {nome!r}")
        print(f"  status   : {pesq.status} · propósito {pesq.proposito}")
        if pesq.empresa_id != empresa_esperada:
            print(
                f"\nABORTADO: empresa {pesq.empresa_id} != esperada "
                f"{empresa_esperada}. Nada foi enviado."
            )
            sys.exit(2)
        if pesq.status != "pronta":
            print(f"\nABORTADO: pesquisa não está 'pronta' (status={pesq.status}).")
            sys.exit(2)
        payload = payload_publico(pesq)
        sub_por_pergunta = {
            pp.id: pp.subpilar_alvo
            for pp in s.query(PesquisaPergunta).filter_by(pesquisa_id=pesq.id).all()
        }
        return pesq.id, pesq.titulo, payload["perguntas"], sub_por_pergunta


def _monta_form(perguntas, sub_por_pergunta, rng: random.Random):
    """Monta o dict de form-data de UM respondente + conta (comentarios, nota_only).

    O comentário é sorteado do banco DO SUBPILAR da pergunta (``sub_por_pergunta``) — se
    o subpilar não tiver banco (não deve acontecer com os 12), cai em nota-only em vez de
    forçar uma frase descorrelacionada."""
    form: dict = {}
    n_coment = 0
    n_nota_only = 0
    for p in perguntas:
        pid = p["id"]
        opc = p.get("opcoes") or {}
        tipo = opc.get("tipo")
        if tipo == "unidade":
            opcoes = opc.get("opcoes") or []
            if opcoes:
                o = rng.choice(opcoes)
                form[f"ancora_{pid}"] = f"{o['entidade_tipo']}:{o['entidade_id']}"
        elif tipo == "nota":
            form[f"q_{pid}_nota"] = str(rng.randint(1, 5))
            banco = _COMENTARIOS_POR_SUBPILAR.get(sub_por_pergunta.get(pid))
            if banco and rng.random() < _PROB_COMENTARIO:
                form[f"q_{pid}_texto"] = rng.choice(banco)  # coerente com o subpilar
                n_coment += 1
            else:
                form[f"q_{pid}_texto"] = ""  # nota-only (caminho do fix do dedup)
                n_nota_only += 1
        elif tipo == "multipla":
            rots = opc.get("rotulos") or []
            if rots and rng.random() < 0.5:
                form[f"q_{pid}_opcao"] = rng.choice(rots)
    return form, n_coment, n_nota_only


def main() -> None:
    ap = argparse.ArgumentParser(description="Seeder de respostas de pesquisa (teste).")
    ap.add_argument("--token", required=True, help="token_publico da pesquisa")
    ap.add_argument("--n", type=int, default=20, help="nº de respondentes (default 20)")
    ap.add_argument(
        "--base-url",
        default="https://pdpa-web.onrender.com",
        help="host do endpoint público (default prod)",
    )
    ap.add_argument("--empresa", type=int, default=18, help="empresa esperada (trava)")
    ap.add_argument("--seed", type=int, default=None, help="semente do RNG (reprodutível)")
    ap.add_argument(
        "--pct-identificados",
        type=int,
        default=0,
        help="0-100: %% de respondentes IDENTIFICADOS (?c=<id_cliente>). Default 0 = tudo "
        "anônimo (comportamento original). Os 6 IDs de cruzamento entram primeiro.",
    )
    args = ap.parse_args()

    _pid, titulo, perguntas, sub_por_pergunta = _carregar_pesquisa(args.token, args.empresa)
    n_nota = sum(1 for p in perguntas if (p.get("opcoes") or {}).get("tipo") == "nota")
    n_unidade = sum(1 for p in perguntas if (p.get("opcoes") or {}).get("tipo") == "unidade")
    rng = random.Random(args.seed)
    identidades = _planeja_identidades(args.n, args.pct_identificados, rng)
    n_ident_plan = sum(1 for c in identidades if c is not None)
    fixos_no_plano = [c for c in _FIXOS_CRUZA if c in identidades]
    print(f"  perguntas: {len(perguntas)} ({n_nota} de nota, {n_unidade} de unidade)")
    print(f"  vai gerar: {args.n} respondentes → {args.base_url}/p/{args.token}")
    print(f"  identidade: {n_ident_plan} identificados (?c=) · {args.n - n_ident_plan} anônimos")
    if fixos_no_plano:
        print(
            f"  IDs cruzamento: {', '.join(fixos_no_plano)} (1 resposta cada — volume vem do Excel)"
        )
    print("──────────────────────────────────────────────────────\n")

    url = f"{args.base_url.rstrip('/')}/p/{args.token}"
    ok = 0
    ok_ident = 0
    ok_anon = 0
    tot_coment = 0
    tot_nota_only = 0
    falhas = []
    for i in range(args.n):
        form, nc, nn = _monta_form(perguntas, sub_por_pergunta, rng)
        codigo = identidades[i]
        if codigo:  # carimbo ?c= no form (mesmo caminho do link carimbado real)
            form["c"] = codigo
        try:
            resp = requests.post(url, data=form, timeout=30, allow_redirects=False)
        except requests.RequestException as exc:  # rede/timeout
            falhas.append((i, f"exceção: {exc}"))
            continue
        if resp.status_code == 200:
            ok += 1
            ok_ident += 1 if codigo else 0
            ok_anon += 0 if codigo else 1
            tot_coment += nc
            tot_nota_only += nn
        else:
            falhas.append((i, f"HTTP {resp.status_code}"))

    print("── RELATÓRIO ─────────────────────────────────────────")
    print(f"  respondentes OK    : {ok}/{args.n}")
    print(f"    identificados    : {ok_ident}  (viram Pessoa via ?c=<id_cliente>)")
    print(f"    anônimos         : {ok_anon}")
    print(f"  verbatins (notas)  : {ok * n_nota}  (cada respondente = {n_nota} notas)")
    print(f"    com comentário   : {tot_coment}")
    print(f"    nota-only (vazio): {tot_nota_only}")
    if falhas:
        print(f"  FALHAS ({len(falhas)}):")
        for i, motivo in falhas[:20]:
            print(f"    respondente #{i}: {motivo}")
    else:
        print("  falhas             : nenhuma")
    print("──────────────────────────────────────────────────────")
    print(
        "\n(a) PÓS-COLETA: necessário — o verbatim de pesquisa-web nasce CRU "
        "(sem subpilar/tipo). Rode o pós-coleta da empresa p/ classificar + temizar."
    )
    print(
        "(b) LIMPEZA: apague a fonte 'pesquisa_web' da empresa "
        f"{args.empresa} + verbatins + respondentes (bloco no fim do docstring / peça o inline)."
    )


if __name__ == "__main__":
    main()
