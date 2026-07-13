"""Seeder de respostas de pesquisa (DADO DE TESTE) — valida o fluxo ponta-a-ponta.

Gera N respondentes aleatórios para uma pesquisa pública e POSTa cada um no
endpoint real ``/p/<token>`` (NÃO chama ``registrar_respostas`` direto) — passa pela
validação server-side, pelo hash de dedup e por tudo o que um respondente real toca.

Por respondente:
  - Unidade (âncora): escolhe uma das opções ao acaso.
  - Notas: valor aleatório 1..5 em CADA pergunta de nota.
  - Comentário: ~50% de chance por pergunta (o resto vai nota-only — exercita
    exatamente o caminho que estourava 500 antes do fix do dedup 1579fd6).
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

_COMENTARIOS = [
    "Atendimento rápido e cordial.",
    "Demorou mais do que eu esperava.",
    "Equipe muito atenciosa, recomendo.",
    "Poderia melhorar a comunicação.",
    "Resolveram meu problema na hora.",
    "Fiquei satisfeito com o serviço.",
    "Tive dificuldade para ser atendido.",
    "Ambiente agradável e organizado.",
    "Preço justo pelo que oferecem.",
    "Voltarei com certeza.",
    "Faltou clareza nas informações.",
    "Superou minhas expectativas.",
]


def _carregar_pesquisa(token: str, empresa_esperada: int):
    """Lê a pesquisa pelo token, imprime empresa + título e aplica a trava. Devolve
    ``(pesquisa_id, titulo, [perguntas])`` onde cada pergunta é o dict de
    ``payload_publico`` (id/formato/opcoes)."""
    from src.models.empresa import Empresa
    from src.models.pesquisa import Pesquisa
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
        return pesq.id, pesq.titulo, payload["perguntas"]


def _monta_form(perguntas, rng: random.Random):
    """Monta o dict de form-data de UM respondente + conta (comentarios, nota_only)."""
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
            if rng.random() < 0.5:
                form[f"q_{pid}_texto"] = rng.choice(_COMENTARIOS)
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

    _pid, titulo, perguntas = _carregar_pesquisa(args.token, args.empresa)
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
        form, nc, nn = _monta_form(perguntas, rng)
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
