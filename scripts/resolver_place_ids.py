"""Resolve place_id placeholder de fontes Google via Google Places API (New).

Contexto: o v3 adota a convenção "quem cadastra fornece o place_id" (ver
``src/coletor/google.py``). Quando o cadastro entra com ``ChIJ_PLACEHOLDER`` (ex.:
import de concessionárias sem o id real), este script resolve o place_id real a
partir do **nome + endereço do Local** via Places Text Search (New).

Solução PERMANENTE — serve Carbel, Pardini e todo cliente futuro. (Doc do fluxo:
``docs/ONBOARDING_CLIENTE.md``.)

SEGURANÇA (CP-Carbel):
  - DRY-RUN é o DEFAULT. Só escreve no banco com ``--aplicar`` explícito.
  - Filtra por ``--empresa`` (obrigatório) e **recusa a empresa 4 (Confins)** —
    baseline intocável.
  - Só toca fontes ``conector_tipo='google'`` cujo ``url`` começa com o placeholder.
  - **Anti-match-errado** (Text Search erra silencioso): o dry-run mostra lado a
    lado cadastrado vs Google e MARCA:
      ⚠ DUPLICADO       — 2+ fontes resolveram pro MESMO place_id (Text Search
                          colapsou unidades diferentes → quase sempre errado).
      ⚠ NOME DIVERGENTE — o nome no Google diverge do cadastrado (achou outro lugar).
    No ``--aplicar``, suspeitos (DUPLICADO/DIVERGENTE) são **PULADOS por default**
    (use ``--incluir-suspeitos`` p/ forçar). Erro de API aborta sem escrever.

Uso (no Shell do Render, onde está o banco de prod + a key):
    export GOOGLE_MAPS_API_KEY=...          # se não estiver no env do serviço
    PYTHONPATH=. python scripts/resolver_place_ids.py --empresa=5            # dry-run
    PYTHONPATH=. python scripts/resolver_place_ids.py --empresa=5 --aplicar  # grava

Requer a **Places API (New)** habilitada + billing na key. Custo ~US$0,02/busca.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models.fonte import Fonte  # noqa: E402
from src.models.local import Local  # noqa: E402
from src.utils.db import db_session  # noqa: E402

PLACEHOLDER = "ChIJ_PLACEHOLDER"
EMPRESA_PROIBIDA = 4  # Confins — baseline validado, INTOCÁVEL
_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
DIVERG_CORTE = 0.34  # overlap de tokens abaixo disto → ⚠ NOME DIVERGENTE


def _resolver_empresa(session, empresa):
    from src.models.empresa import Empresa

    emp = None
    try:
        emp = session.get(Empresa, int(empresa))
    except (TypeError, ValueError):
        pass
    if emp is None:
        emp = session.query(Empresa).filter_by(nome=str(empresa)).first()
    if emp is None:
        raise SystemExit(f"empresa {empresa!r} não encontrada (id ou nome)")
    return emp


def _endereco_local(loc: Local) -> str:
    """String de busca: nome + endereço completo + cidade + UF (desambigua
    cidades homônimas — Uberlândia ≠ BH)."""
    partes = [loc.nome, loc.endereco, loc.cidade]
    if loc.uf:
        partes.append(loc.uf)
    return ", ".join(p for p in partes if p)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def _tokens(s: str) -> set:
    return {t for t in _norm(s).replace("-", " ").replace("/", " ").split() if len(t) > 2}


def _overlap_nome(cadastrado: str, google: str) -> float:
    """Coeficiente de sobreposição de tokens |A∩B|/min(|A|,|B|). 0 = nada em comum
    (provável lugar errado); 1 = um contém o outro (só reordenado)."""
    a, b = _tokens(cadastrado), _tokens(google)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _buscar_lugar(query: str, key: str, idioma: str, regiao: str) -> List[Dict[str, Any]]:
    """Places Text Search (New). Retorna [{place_id, nome, endereco}] (top 3).

    Erros de auth/enablement/billing (400/401/403) sobem como SystemExit — abortam
    o run inteiro (não adianta repetir 19×). 'Sem resultado' devolve lista vazia."""
    body = json.dumps(
        {"textQuery": query, "languageCode": idioma, "regionCode": regiao, "maxResultCount": 3}
    ).encode("utf-8")
    req = urllib.request.Request(
        _ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")
        if e.code in (400, 401, 403):
            raise SystemExit(
                f"\n[resolver] ERRO DE API ({e.code}) — provável key inválida, Places API "
                f"(New) não habilitada, ou billing off. Nada foi escrito. Resposta:\n{detalhe}"
            )
        print(f"[resolver]   HTTP {e.code} nessa busca: {detalhe[:200]}")
        return []
    except urllib.error.URLError as e:
        print(f"[resolver]   erro de rede: {e}")
        return []
    out = []
    for p in data.get("places", []):
        out.append(
            {
                "place_id": p.get("id", ""),
                "nome": (p.get("displayName") or {}).get("text", ""),
                "endereco": p.get("formattedAddress", ""),
            }
        )
    return out


def main(empresa, aplicar: bool, incluir_suspeitos: bool) -> int:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "[resolver] GOOGLE_MAPS_API_KEY não está no env. No Shell do Render: "
            "`export GOOGLE_MAPS_API_KEY=...` antes de rodar."
        )
    idioma, regiao = "pt-BR", "BR"

    with db_session() as s:
        emp = _resolver_empresa(s, empresa)
        if emp.id == EMPRESA_PROIBIDA:
            raise SystemExit(
                f"[resolver] RECUSADO: empresa {emp.id} (Confins) é INTOCÁVEL. "
                "Este script só roda em outras empresas."
            )
        fontes = (
            s.query(Fonte)
            .filter(
                Fonte.empresa_id == emp.id,
                Fonte.conector_tipo == "google",
                Fonte.url.like(f"{PLACEHOLDER}%"),
            )
            .order_by(Fonte.id)
            .all()
        )
        modo = "APLICAR (grava no banco)" if aplicar else "DRY-RUN (só preview, nada gravado)"
        print("═" * 76)
        print(f"[resolver] empresa={emp.id} ({emp.nome}) · modo={modo}")
        print(f"[resolver] fontes google com {PLACEHOLDER}: {len(fontes)}")
        print("═" * 76)
        if not fontes:
            print("[resolver] nada a resolver.")
            return 0

        # ── FASE 1: coleta (1 chamada/fonte) ───────────────────────────────
        regs = []
        for f in fontes:
            loc = s.get(Local, f.entidade_id) if f.entidade_tipo == "local" else None
            r = {"fonte": f, "loc": loc, "query": None, "matches": []}
            if loc is not None:
                r["query"] = _endereco_local(loc)
                r["matches"] = _buscar_lugar(r["query"], key, idioma, regiao)
                time.sleep(0.2)
            regs.append(r)

        # ── FASE 2: detecta place_id duplicado entre fontes (top match) ────
        pid_para_fontes = defaultdict(list)
        for r in regs:
            if r["matches"]:
                pid_para_fontes[r["matches"][0]["place_id"]].append(r["fonte"].id)

        # ── FASE 3: relatório lado a lado + flags ──────────────────────────
        resolvidos = pulados = sem_match = 0
        for r in regs:
            f, loc = r["fonte"], r["loc"]
            if loc is None:
                print(f"\n• fonte {f.id}: SEM local ({f.entidade_tipo}#{f.entidade_id}) — pulada")
                sem_match += 1
                continue
            print(f"\n• fonte {f.id} · local {loc.id}")
            end_cad = ", ".join(p for p in (loc.endereco, loc.cidade, loc.uf) if p)
            print(f"    cadastrado : {loc.nome}  |  {end_cad or '(sem endereço)'}")
            if not r["matches"]:
                print("    google     : (nenhum resultado)")
                print("    → ⚠ SEM MATCH — resolver manual (placeholder mantido)")
                sem_match += 1
                continue
            top = r["matches"][0]
            print(f"    google     : {top['nome']}  |  {top['endereco']}")
            flags = []
            ov = _overlap_nome(loc.nome, top["nome"])
            if ov < DIVERG_CORTE:
                flags.append(f"NOME DIVERGENTE (overlap {ov:.0%})")
            outras = [fid for fid in pid_para_fontes[top["place_id"]] if fid != f.id]
            if outras:
                flags.append(f"DUPLICADO (=fontes {outras})")
            marca = ("  ⚠ " + "  ⚠ ".join(flags)) if flags else "  ✓ ok"
            print(f"    → {top['place_id']}{marca}")
            if len(r["matches"]) > 1:
                print("    candidatos extras (se o #1 estiver errado):")
                for m in r["matches"][1:]:
                    print(f"        - {m['place_id']} · {m['nome']} · {m['endereco']}")
            r["flags"], r["top"] = flags, top

            if aplicar:
                if flags and not incluir_suspeitos:
                    print("    ⤷ PULADO (suspeito) — resolver manual ou --incluir-suspeitos")
                    pulados += 1
                    continue
                f.url = top["place_id"]
                if (loc.place_id_google or "") in ("", PLACEHOLDER):
                    loc.place_id_google = top["place_id"]
                print("    ⤷ ✓ gravado em fonte.url + local.place_id_google")
                resolvidos += 1

        # ── Resumo ─────────────────────────────────────────────────────────
        suspeitos = sum(1 for r in regs if r.get("flags"))
        print("\n" + "═" * 76)
        print(
            f"[resolver] fontes={len(regs)} · com_match={len(regs) - sem_match} · "
            f"sem_match={sem_match} · suspeitos(⚠)={suspeitos}"
        )
        if aplicar:
            print(f"[resolver] APLICADO: gravados={resolvidos} · pulados(suspeitos)={pulados}.")
        else:
            print(
                "[resolver] DRY-RUN — nada gravado. Valide os ⚠ (duplicado/divergente) e os "
                "endereços; depois rode com --aplicar."
            )
        print("═" * 76)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Resolve place_id placeholder via Places API (New).")
    ap.add_argument("--empresa", required=True, help="id ou nome da empresa (NUNCA 4/Confins)")
    ap.add_argument(
        "--aplicar", action="store_true", help="grava no banco. SEM esta flag = dry-run (default)."
    )
    ap.add_argument(
        "--incluir-suspeitos",
        action="store_true",
        help="no --aplicar, grava também os marcados ⚠ (duplicado/divergente). Default: pula.",
    )
    args = ap.parse_args()
    raise SystemExit(main(args.empresa, args.aplicar, args.incluir_suspeitos))
