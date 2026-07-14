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
  - Anônimo (sem e-mail/consentimento).

TRAVA DE SEGURANÇA: lê a pesquisa no banco, imprime empresa (id + nome) + título e
ABORTA se a empresa não for a esperada (default 18) — evita gerar lixo em empresa real.

Uso (Render Shell ou local):
    python scripts/seed_respostas_pesquisa.py --token <token> --n 20 \
        --base-url https://pdpa-web.onrender.com

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
    args = ap.parse_args()

    _pid, titulo, perguntas, sub_por_pergunta = _carregar_pesquisa(args.token, args.empresa)
    n_nota = sum(1 for p in perguntas if (p.get("opcoes") or {}).get("tipo") == "nota")
    n_unidade = sum(1 for p in perguntas if (p.get("opcoes") or {}).get("tipo") == "unidade")
    print(f"  perguntas: {len(perguntas)} ({n_nota} de nota, {n_unidade} de unidade)")
    print(f"  vai gerar: {args.n} respondentes → {args.base_url}/p/{args.token}")
    print("──────────────────────────────────────────────────────\n")

    rng = random.Random(args.seed)
    url = f"{args.base_url.rstrip('/')}/p/{args.token}"
    ok = 0
    tot_coment = 0
    tot_nota_only = 0
    falhas = []
    for i in range(args.n):
        form, nc, nn = _monta_form(perguntas, sub_por_pergunta, rng)
        try:
            resp = requests.post(url, data=form, timeout=30, allow_redirects=False)
        except requests.RequestException as exc:  # rede/timeout
            falhas.append((i, f"exceção: {exc}"))
            continue
        if resp.status_code == 200:
            ok += 1
            tot_coment += nc
            tot_nota_only += nn
        else:
            falhas.append((i, f"HTTP {resp.status_code}"))

    print("── RELATÓRIO ─────────────────────────────────────────")
    print(f"  respondentes OK    : {ok}/{args.n}")
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
