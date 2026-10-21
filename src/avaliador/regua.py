"""Régua do Avaliador — o capítulo 2 do Manual de Operação, literal, as marcas de leitura
de documento e as pistas de autor.

Fontes, sem texto paralelo:
- ``dados/manual_cap2.json``: extrato LITERAL do capítulo 2 do Manual (gerado por
  ``scripts/extrair_manual_cap2.py``; o .docx não vai para a imagem). Um teste compara o
  extrato com o .docx quando ele existe na máquina;
- ``dados/marcas.json``: extrato LITERAL do capítulo "Marcas de leitura de documento" (o
  17 no v11), gerado por ``scripts/extrair_marcas.py``, com o mesmo teste contra o .docx.
  18/10: carregado e validado, ainda sem uso na leitura;
- códigos e nomes conferidos contra ``SUBPILARES_ORDEM`` / ``NOME_SUBPILAR`` (painel.py);
- pistas = bibliotecas de frases dos autores (Alexandre e Dener), usadas como "buracos
  comuns para procurar" — o modelo não é obrigado a escolher nenhuma; o texto da resposta
  é dele, com citação conferida. Biblioteca 1 para arquivo (documento/apresentação da
  própria empresa); biblioteca 3 ("dito contra respondido") para texto colado de conversa.

Dado quebrado levanta na carga (``ReguaInvalida``), antes de qualquer chamada paga.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

from src.api.painel import NOME_SUBPILAR, PILARES_ORDEM, SUBPILARES_ORDEM

DADOS = Path(__file__).parent / "dados"
ARQUIVOS = ("manual_cap2.json", "frases_l1.json", "frases_l3.json", "marcas.json")

ORIGEM_ARQUIVO = "arquivo"
ORIGEM_TEXTO = "texto"
ORIGEM_PAGINA = "pagina"  # página pública do site: é documento, usa a biblioteca 1
BIBLIOTECA_POR_ORIGEM = {ORIGEM_ARQUIVO: "L1", ORIGEM_TEXTO: "L3", ORIGEM_PAGINA: "L1"}

# Grupos da biblioteca que viram pista de cada subpilar. No P1 a biblioteca 1 é dividida
# por parte (escopo/prazo/fora/preço); P1d_pergunta é texto de tela de outro desenho, não
# pista.
_GRUPOS_P1_L1 = ("P1a", "P1b", "P1c", "P1d", "P1d_sem_anexo")

# Grupos fora das pistas, com o motivo — (biblioteca, subpilar): motivo. Vazio desde
# 12/10/2026: o A1 das bibliotecas 1 e 3 foi reescrito pelos autores contra o Manual.
PISTAS_FORA: Dict[tuple, str] = {}


class ReguaInvalida(ValueError):
    """Os dados não fecham com o modelo do PDPA ou entre si."""


@dataclass(frozen=True)
class Subpilar:
    codigo: str
    nome: str
    pergunta: str
    texto: str  # a linha do Manual, inteira


@dataclass(frozen=True)
class Marca:
    codigo: str  # "P1.01"; "C.01" no bloco fora dos doze
    grupo: str  # o subpilar, ou GRUPO_FORA
    texto: str
    so_cliente_nomeado: bool  # só se espera em peça feita para um cliente com nome
    porque_importa: str  # vazio até os autores escreverem (decisão de 18/10)


GRUPO_FORA = "C"

# O código da marca é identidade: a leitura gravada guarda cada marca pelo código, e a tela
# busca a exceção e o "porque importa" na régua de hoje por ele. Marca que sai do Manual
# deixa buraco na numeração, e o código não volta a ser usado (Manual v13, 21/10: oito
# marcas saíram por não valerem para toda relação comercial).
MARCAS_APOSENTADAS = frozenset(
    {"P1.05", "P1.06", "P1.08", "P1.09", "P2.05", "P3.03", "Pa2.07", "Pa3.05"}
)


@dataclass(frozen=True)
class Pilar:
    codigo: str
    titulo: str
    descricao: str
    subpilares: tuple


class Regua:
    def __init__(self, manual: dict, l1: dict, l3: dict, versao: str, marcas: dict = None):
        self.versao = versao
        self.fonte: str = manual["fonte"]
        self.abertura: str = manual["abertura"]
        self.pilares: List[Pilar] = []
        for cod, p in zip(PILARES_ORDEM, manual["pilares"]):
            subs = tuple(
                Subpilar(s["codigo"], s["nome"], s["pergunta"], s["texto"]) for s in p["subpilares"]
            )
            self.pilares.append(Pilar(cod, p["titulo"], p["descricao"], subs))
        self._sub = {s.codigo: s for p in self.pilares for s in p.subpilares}
        self.bibliotecas = {"L1": l1["frases"], "L3": l3["frases"]}
        # None só em teste que monta a régua sem o capítulo das marcas
        self.marcas_cap: dict = marcas
        self.marcas: List[Marca] = [
            Marca(x["codigo"], x["grupo"], x["texto"], x["so_cliente_nomeado"], x["porque_importa"])
            for x in (marcas or {}).get("marcas", [])
        ]

    def marcas_de(self, grupo: str) -> List[Marca]:
        """As marcas de um subpilar (ou do bloco fora dos doze), na ordem do Manual."""
        return [m for m in self.marcas if m.grupo == grupo]

    def subpilar(self, codigo: str) -> Subpilar:
        return self._sub[codigo]

    def pilar_de(self, codigo: str) -> Pilar:
        return next(p for p in self.pilares if codigo in {s.codigo for s in p.subpilares})

    def _grupos(self, biblioteca: str, codigo: str) -> tuple:
        if biblioteca == "L1" and codigo == "P1":
            return _GRUPOS_P1_L1
        return (codigo,)

    def pistas(self, codigo: str, origem: str) -> List[str]:
        """Frases de autor que servem de pista para o subpilar, na biblioteca da origem.
        Vazio quando o grupo está em ``PISTAS_FORA`` — o modelo fica só com o Manual."""
        bib = BIBLIOTECA_POR_ORIGEM[origem]
        if (bib, codigo) in PISTAS_FORA:
            return []
        frases = self.bibliotecas[bib]
        return [f["texto"] for g in self._grupos(bib, codigo) for f in frases.get(g, [])]


def validar(r: Regua) -> None:
    erros: List[str] = []
    codigos = [s.codigo for p in r.pilares for s in p.subpilares]
    if codigos != SUBPILARES_ORDEM:
        erros.append(f"subpilares do Manual ≠ SUBPILARES_ORDEM: {codigos}")
    if len(r.pilares) != len(PILARES_ORDEM):
        erros.append(f"pilares do Manual: {len(r.pilares)} (esperado {len(PILARES_ORDEM)})")
    for c, s in r._sub.items():
        if NOME_SUBPILAR.get(c) != s.nome:
            erros.append(f"{c}: Manual diz {s.nome!r}, painel diz {NOME_SUBPILAR.get(c)!r}")
    for p in r.pilares:
        if not (p.descricao or "").strip():
            erros.append(f"pilar {p.codigo} sem a frase de descrição do Manual")
    vistos: set = set()
    for bib, grupos in r.bibliotecas.items():
        for g, lista in grupos.items():
            for f in lista:
                fid = f.get("id", "")
                if fid in vistos:
                    erros.append(f"id repetido: {fid}")
                vistos.add(fid)
                if not fid.startswith(f"{bib}-{g}-"):
                    erros.append(f"id {fid} fora do padrão {bib}-{g}-NN")
                if not (f.get("texto") or "").strip():
                    erros.append(f"{fid}: texto vazio")
        for c in SUBPILARES_ORDEM:
            if (bib, c) in PISTAS_FORA:
                continue
            if not any(grupos.get(g) for g in r._grupos(bib, c)):
                erros.append(f"biblioteca {bib} sem pista para {c}")
    if r.marcas_cap is not None:
        erros += _erros_das_marcas(r)
    if erros:
        raise ReguaInvalida("; ".join(erros))


def _erros_das_marcas(r: Regua) -> List[str]:
    erros: List[str] = []
    titulos = [p["titulo"] for p in r.marcas_cap["pilares"]]
    if titulos != [p.titulo for p in r.pilares]:
        erros.append(f"pilares das marcas ≠ pilares do capítulo 2: {titulos}")
    vistos: set = set()
    for m in r.marcas:
        if m.codigo in vistos:
            erros.append(f"marca repetida: {m.codigo}")
        vistos.add(m.codigo)
        if m.grupo not in SUBPILARES_ORDEM and m.grupo != GRUPO_FORA:
            erros.append(f"marca {m.codigo} em grupo fora do modelo: {m.grupo}")
        if not m.codigo.startswith(f"{m.grupo}."):
            erros.append(f"marca {m.codigo} no grupo {m.grupo}")
        if not m.texto.strip():
            erros.append(f"marca {m.codigo} sem texto")
        if m.codigo in MARCAS_APOSENTADAS:
            erros.append(f"marca {m.codigo} usa código aposentado")
    for g in SUBPILARES_ORDEM + [GRUPO_FORA]:
        codigos = [m.codigo for m in r.marcas_de(g)]
        if not codigos:
            erros.append(f"nenhuma marca em {g}")
        nums = [int(c.split(".")[1]) for c in codigos]
        if nums != sorted(set(nums)) or any(n < 1 for n in nums):
            erros.append(f"numeração das marcas de {g} fora de ordem: {codigos}")
    return erros


def _ler(nome: str) -> dict:
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def carregar_regua() -> Regua:
    """Versão = hash dos arquivos da régua: toda análise grava qual régua a produziu."""
    h = hashlib.sha256()
    for nome in ARQUIVOS:
        h.update((DADOS / nome).read_bytes())
    r = Regua(
        _ler("manual_cap2.json"),
        _ler("frases_l1.json"),
        _ler("frases_l3.json"),
        versao=f"manual+marcas+pistas:{h.hexdigest()[:12]}",
        marcas=_ler("marcas.json"),
    )
    validar(r)
    return r
