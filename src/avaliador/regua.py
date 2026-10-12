"""Régua do Avaliador — carrega e valida os dados de autor (src/avaliador/dados/).

Fontes de verdade, sem cópia:
- códigos e ordem dos subpilares: ``SUBPILARES_ORDEM`` (src/api/painel.py);
- nome oficial do subpilar: ``NOME_SUBPILAR`` (idem), lido em tempo de execução;
- perguntas, regras de rigor, tipos e frases: os JSON de autor (Alexandre e Dener).
  Copiar, não reescrever: o código só LÊ estes arquivos.

Dado quebrado levanta na carga (``ReguaInvalida``), antes de qualquer chamada paga.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.api.painel import NOME_SUBPILAR, SUBPILARES_ORDEM

DADOS = Path(__file__).parent / "dados"

VEREDITOS = ("respondida", "em_parte", "sem_resposta")

# Parte interna do P1 → grupo de frases "sem resposta" da biblioteca 1. As partes não
# aparecem na tela (lá é uma pergunta só); elas só escolhem a frase.
GRUPO_PARTE_P1 = {"escopo": "P1a", "prazo": "P1b", "fora": "P1c", "preco": "P1d"}
GRUPO_PRECO_PERGUNTA = "P1d_pergunta"  # o que a tela pergunta quando não há seção comercial
GRUPO_PRECO_SEM_ANEXO = "P1d_sem_anexo"  # o que ela diz depois de "não há anexo"


class ReguaInvalida(ValueError):
    """Os dados de autor não fecham com o modelo do PDPA ou entre si."""


@dataclass(frozen=True)
class Pergunta:
    codigo: str
    bloco: str
    pergunta: str
    aberta_quando: str
    verificavel_sozinho: bool
    partes: Tuple[dict, ...]

    @property
    def nome(self) -> str:
        """Nome oficial do subpilar — de NOME_SUBPILAR, nunca do JSON."""
        return NOME_SUBPILAR[self.codigo]


@dataclass(frozen=True)
class Tipo:
    codigo: str
    nome: str
    definicao: str
    nao_valem: Tuple[str, ...]
    condicionais: Dict[str, str]


class Regua:
    def __init__(self, regua: dict, l1: dict, ep: dict):
        self.versao: str = regua["versao"]
        self.blocos: Dict[str, dict] = {b["codigo"]: b for b in regua["blocos"]}
        self.regras: List[dict] = regua["regras_de_rigor"]
        por_codigo = {
            p["codigo"]: Pergunta(
                codigo=p["codigo"],
                bloco=p["bloco"],
                pergunta=p["pergunta"],
                aberta_quando=p["aberta_quando"],
                verificavel_sozinho=bool(p["verificavel_sozinho"]),
                partes=tuple(p.get("partes", [])),
            )
            for p in regua["perguntas"]
        }
        self._por_codigo = por_codigo
        self.tipos: Dict[str, Tipo] = {
            t["codigo"]: Tipo(
                codigo=t["codigo"],
                nome=t["nome"],
                definicao=t["definicao"],
                nao_valem=tuple(t.get("nao_valem", [])),
                condicionais=dict(t.get("condicionais", {})),
            )
            for t in regua["tipos"]
        }
        self.frases_l1: Dict[str, List[dict]] = l1["frases"]
        self.frases_ep: Dict[str, List[dict]] = ep["frases"]
        self._texto: Dict[str, str] = {}
        for grupos in (self.frases_l1, self.frases_ep):
            for lista in grupos.values():
                for f in lista:
                    self._texto[f["id"]] = f["texto"]

    # ── perguntas ────────────────────────────────────────────────────────
    @property
    def perguntas(self) -> List[Pergunta]:
        """As doze, na ordem canônica do PDPA (SUBPILARES_ORDEM)."""
        return [self._por_codigo[c] for c in SUBPILARES_ORDEM]

    def pergunta(self, codigo: str) -> Pergunta:
        return self._por_codigo[codigo]

    def perguntas_que_valem(self, tipo: str, discute_preco: bool) -> List[str]:
        """Códigos cobrados neste tipo de documento, na ordem canônica.

        ``nao_valem`` do tipo sai; condicional ("Pa2 só vale se o documento discutir
        preço") é decidida pela marca ``discute_preco`` da etapa 1. Hoje a única
        condicional da régua é essa; outra condicional desconhecida LEVANTA em vez de
        ser ignorada em silêncio.
        """
        t = self.tipos[tipo]
        codigos = [c for c in SUBPILARES_ORDEM if c not in t.nao_valem]
        for cod in t.condicionais:
            if cod != "Pa2":
                raise ReguaInvalida(f"condicional sem regra no código: {tipo}/{cod}")
            if not discute_preco and cod in codigos:
                codigos.remove(cod)
        return codigos

    # ── frases ───────────────────────────────────────────────────────────
    def ids_sem_resposta(self, codigo: str, parte: Optional[str] = None) -> List[str]:
        """Ids válidos para o veredito "sem resposta". No P1, por parte interna."""
        if codigo == "P1":
            if parte is None:
                raise ValueError("P1 exige a parte (escopo/prazo/fora/preco)")
            grupo = GRUPO_PARTE_P1[parte]
        else:
            grupo = codigo
        return [f["id"] for f in self.frases_l1[grupo]]

    def ids_em_parte(self, codigo: str) -> List[str]:
        return [f["id"] for f in self.frases_ep[codigo]]

    def ids_grupo(self, grupo: str) -> List[str]:
        return [f["id"] for f in self.frases_l1[grupo]]

    def texto_frase(self, frase_id: str) -> str:
        return self._texto[frase_id]


def validar(r: Regua) -> None:
    """Confere os dados de autor contra o modelo do PDPA e entre si. Levanta com a
    lista completa de problemas (não para no primeiro)."""
    erros: List[str] = []
    codigos_json = set(r._por_codigo)
    canon = set(SUBPILARES_ORDEM)
    if codigos_json != canon:
        erros.append(
            f"códigos da régua ≠ SUBPILARES_ORDEM: sobra {sorted(codigos_json - canon)}"
            f", falta {sorted(canon - codigos_json)}"
        )
    for p in r._por_codigo.values():
        if p.bloco not in r.blocos:
            erros.append(f"{p.codigo}: bloco desconhecido {p.bloco}")
    for t in r.tipos.values():
        for c in list(t.nao_valem) + list(t.condicionais):
            if c not in SUBPILARES_ORDEM:
                erros.append(f"tipo {t.codigo}: código desconhecido {c}")
    # frases: todo grupo esperado existe e não está vazio; ids únicos e com prefixo do grupo
    esperados_l1 = [c for c in SUBPILARES_ORDEM if c != "P1"] + list(GRUPO_PARTE_P1.values())
    esperados_l1 += [GRUPO_PRECO_PERGUNTA, GRUPO_PRECO_SEM_ANEXO]
    for g in esperados_l1:
        if not r.frases_l1.get(g):
            erros.append(f"biblioteca 1 sem o grupo {g}")
    for c in SUBPILARES_ORDEM:
        if not r.frases_ep.get(c):
            erros.append(f"'em parte' sem o grupo {c}")
    vistos: set = set()
    for prefixo, grupos in (("L1", r.frases_l1), ("EP", r.frases_ep)):
        for g, lista in grupos.items():
            for f in lista:
                fid = f.get("id", "")
                if fid in vistos:
                    erros.append(f"id repetido: {fid}")
                vistos.add(fid)
                if not fid.startswith(f"{prefixo}-{g}-"):
                    erros.append(f"id {fid} fora do padrão {prefixo}-{g}-NN")
                if not (f.get("texto") or "").strip():
                    erros.append(f"{fid}: texto vazio")
    if erros:
        raise ReguaInvalida("; ".join(erros))


def _ler(nome: str) -> dict:
    return json.loads((DADOS / nome).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def carregar_regua() -> Regua:
    r = Regua(_ler("regua.json"), _ler("frases_l1.json"), _ler("frases_ep.json"))
    validar(r)
    return r
