"""A biblioteca de frases do parecer: o "por que custa" ao lado de um subpilar vazio (23/10).

Escrita pelo Alexandre em 11/10, podada e ligada às marcas em 23/10; o extrato é
``dados/biblioteca_frases.json`` (``scripts/extrair_biblioteca.py``). Não é régua: o modelo
nunca lê estas frases (nem a leitura nem o rascunho, decisão de 23/10: o achado tem de dizer
o que as listas não dizem, e com as frases à vista o modelo as repetiria). Por isso o arquivo
fica fora do hash da régua (``regua.ARQUIVOS``).

Regra do Word, decidida em 23/10:
- só em subpilar VAZIO: nenhuma marca "está" na tela já corrigida. Frase que pressupõe que a
  peça diga algo ("há canal, não há horário") é estado "tela" e nunca vai ao Word;
- até ``MAX_FRASES`` por subpilar, sorteadas entre as que valem ali: estado "word", ou
  "cliente_nomeado" quando a peça é para cliente com nome; e, se a frase tem lista de marcas,
  ao menos uma delas ausente no bloco (a marca que só se espera com cliente nomeado sai do
  bloco quando a peça não tem cliente nomeado, e a frase dela sai junto);
- o sorteio é função do número da leitura e do subpilar: a mesma leitura dá sempre as mesmas
  frases, na tela e no Word, sem nada gravado; leituras diferentes dão sorteios diferentes.
  Consequência aceita pelo Alexandre (23/10, calcular e não congelar): editar o TEXTO de uma
  frase muda o Word de toda leitura que a sorteou, inclusive antiga (o sorteio é pelo
  código, então a escolha não muda; só o texto). Já incluir ou tirar frase de um subpilar
  muda o sorteio de todas as leituras naquele subpilar.
  Nenhuma frase se repete na peça: cada frase é de um subpilar só e o sorteio é sem reposição.
- código de marca, de subpilar e nome de pilar nunca estão no texto (conferido ao carregar).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from src.api.painel import SUBPILARES_ORDEM

ARQUIVO = Path(__file__).parent / "dados" / "biblioteca_frases.json"
MAX_FRASES = 3
WORD, TELA, CLIENTE_NOMEADO = "word", "tela", "cliente_nomeado"
# não pode aparecer no texto que vai ao cliente: código de marca ou de subpilar
_CODIGO = re.compile(r"\b(?:P|D|Pa|A|C)\d(?:\.\d+)?\b")


@lru_cache(maxsize=1)
def carregar() -> List[dict]:
    frases = json.loads(ARQUIVO.read_text(encoding="utf-8"))["frases"]
    erros = validar(frases)
    if erros:
        raise ValueError("biblioteca de frases inválida: " + "; ".join(erros))
    return frases


def validar(frases: List[dict]) -> List[str]:
    """Contra o Manual de hoje (marcas.json): toda marca do "serve a" existe no subpilar da
    frase, e todo subpilar tem frases que bastam para ``MAX_FRASES`` numa peça SEM cliente
    nomeado com o bloco inteiro vazio. Nome curto renomeado no Manual quebra aqui, não em
    silêncio no Word."""
    from src.avaliador.regua import carregar_regua

    regua = carregar_regua()
    nomes = {}
    for m in regua.marcas:
        nomes.setdefault(m.grupo, {})[m.nome_curto] = m.so_cliente_nomeado
    erros, textos = [], set()
    for f in frases:
        if f["subpilar"] not in SUBPILARES_ORDEM:
            erros.append(f"{f['codigo']}: subpilar {f['subpilar']} não existe")
            continue
        for nome in f["serve_a"] or []:
            if nome not in nomes.get(f["subpilar"], {}):
                erros.append(f"{f['codigo']}: marca {nome!r} não existe em {f['subpilar']}")
        if _CODIGO.search(f["texto"]):
            erros.append(f"{f['codigo']}: o texto traz um código")
        if "—" in f["texto"]:
            erros.append(f"{f['codigo']}: travessão no texto")
        if f["texto"] in textos:
            erros.append(f"{f['codigo']}: texto repetido")
        textos.add(f["texto"])
    for sub in SUBPILARES_ORDEM:
        sem_cliente = {n for n, so in nomes.get(sub, {}).items() if not so}
        if len(_valem(frases, sub, sem_cliente, False)) < MAX_FRASES:
            erros.append(f"{sub}: menos de {MAX_FRASES} frases para o Word sem cliente nomeado")
    return erros


def _valem(frases: List[dict], sub: str, ausentes: set, cliente_nomeado) -> List[dict]:
    estados = {WORD, CLIENTE_NOMEADO} if cliente_nomeado is True else {WORD}
    return [
        f
        for f in frases
        if f["subpilar"] == sub
        and f["estado"] in estados
        and (f["serve_a"] is None or ausentes & set(f["serve_a"]))
    ]


def sorteio(numero: int, sub: str, marcas: List[dict], cliente_nomeado) -> List[str]:
    """As frases do subpilar ``sub`` no parecer da leitura ``numero``. ``marcas``: as do bloco
    na tela já corrigida. Bloco com alguma marca "está" não leva frase: devolve []."""
    from src.avaliador.servico import MARCA_ESTA, MARCA_NAO_ESTA

    if not marcas or any(x["estado"] == MARCA_ESTA for x in marcas):
        return []
    ausentes = {x.get("nome_curto") for x in marcas if x["estado"] == MARCA_NAO_ESTA}
    valem = _valem(carregar(), sub, ausentes, cliente_nomeado)
    semente = int(hashlib.sha256(f"{numero}:{sub}".encode()).hexdigest()[:16], 16)
    escolhidas = random.Random(semente).sample(valem, min(MAX_FRASES, len(valem)))
    ordem = {f["codigo"]: i for i, f in enumerate(valem)}  # na ordem da biblioteca
    return [f["texto"] for f in sorted(escolhidas, key=lambda f: ordem[f["codigo"]])]


def codigos_do_sorteio(numero: int, sub: str, marcas: List[dict], cliente_nomeado) -> List[str]:
    """O mesmo sorteio, pelos códigos das frases (para teste e conferência)."""
    por_texto = {f["texto"]: f["codigo"] for f in carregar()}
    return [por_texto[t] for t in sorteio(numero, sub, marcas, cliente_nomeado)]


def frase(codigo: str) -> Optional[dict]:
    return next((f for f in carregar() if f["codigo"] == codigo), None)
