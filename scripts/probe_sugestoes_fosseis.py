"""Probe SÓ-LEITURA: sugestões estruturais que NÃO correspondem ao dado de hoje, na base toda.

Uso (Shell do Render):  PYTHONPATH=. python scripts/probe_sugestoes_fosseis.py      (todas)
                        PYTHONPATH=. python scripts/probe_sugestoes_fosseis.py 29   (uma)

$0: nenhuma chamada LLM, nenhuma escrita.

Por que existe: uma geração que falha (ex.: resposta truncada no teto de tokens) NÃO apaga
as linhas anteriores do subpilar — só sucesso apaga —, e até 29/out a falha não deixava log.
Essas linhas seguem no banco sem marca de velhas.

Critérios, por (escopo, subpilar) com sugestões gravadas:
  defasada  — o ``dados_hash`` gravado ≠ hash do payload de HOJE (mesma régua do gerador:
              ``montar_payload_subpilar`` + ``hash_payload``, gargalo pela régua canônica).
              Inclui o normal "o dado mudou e a próxima rodada ainda não passou".
  fóssil    — defasada E outro subpilar do MESMO escopo foi gerado DEPOIS dela: houve uma
              rodada posterior, e esta ficou para trás (falha, ou o dado dela só mudou
              depois daquela rodada). É um SINAL, não prova — nada no banco distingue.
  sem_hash  — linha sem ``dados_hash`` (pré-hash): não é comparável a nada.
  órfã      — subpilar sumiu do agg do escopo (ou loja abaixo do piso 30 no subpilar).

Escopos: empresa, cada agrupamento, cada loja com sugestões. O pós-coleta só regenera
empresa e lojas qualificadas; agrupamento só sob demanda — vai separado.
⚠️ A regra nova do gargalo (deploy de 29/out, ``f565fce``) mudou o payload de todo escopo
cujo gargalo mudou: as linhas desses escopos contam como defasadas até a próxima rodada.
Leia a data de geração.
"""

import sys
from collections import defaultdict

from sqlalchemy import func

from src.api.engajamento import VOLUME_CONFIANCA_ALTA
from src.diagnostico.leituras import _gargalo, agregar_subpilares, montar_payload_subpilar
from src.models.empresa import Empresa
from src.models.sugestao_estrutural import SugestaoEstrutural
from src.utils.db import db_session
from src.utils.hashing import hash_payload


def main():
    so = int(sys.argv[1]) if len(sys.argv) > 1 else None
    tot = defaultdict(lambda: defaultdict(int))
    linhas = []
    with db_session() as s:
        q = s.query(
            SugestaoEstrutural.empresa_id,
            SugestaoEstrutural.agrupamento_id,
            SugestaoEstrutural.local_id,
            SugestaoEstrutural.subpilar,
            SugestaoEstrutural.dados_hash,
            func.max(SugestaoEstrutural.gerado_em),
        ).group_by(
            SugestaoEstrutural.empresa_id,
            SugestaoEstrutural.agrupamento_id,
            SugestaoEstrutural.local_id,
            SugestaoEstrutural.subpilar,
            SugestaoEstrutural.dados_hash,
        )
        if so:
            q = q.filter(SugestaoEstrutural.empresa_id == so)
        por_escopo = defaultdict(list)
        for eid, ag, loc, sub, dh, ger in q.all():
            por_escopo[(eid, ag, loc)].append((sub, dh, ger))
        nomes = dict(s.query(Empresa.id, Empresa.nome).all())

        for (eid, ag, loc), subs in sorted(
            por_escopo.items(), key=lambda x: (x[0][0], str(x[0][1]), str(x[0][2]))
        ):
            tipo = "loja" if loc is not None else ("agrupamento" if ag is not None else "empresa")
            agg = agregar_subpilares(s, eid, ag, loc)
            g = _gargalo(agg)
            ultima = max((ger for _, _, ger in subs if ger), default=None)
            for sub, dh, ger in subs:
                t = tot[tipo]
                t["subpilares"] += 1
                if not dh:
                    t["sem_hash"] += 1
                    estado = "sem_hash"
                elif sub not in agg or (
                    loc is not None and agg[sub]["total"] < VOLUME_CONFIANCA_ALTA
                ):
                    t["orfa"] += 1
                    estado = "órfã"
                else:
                    h = hash_payload(
                        montar_payload_subpilar(
                            s, eid, ag if loc is None else None, sub, agg[sub], g, local_id=loc
                        )
                    )
                    if h == dh:
                        t["em_dia"] += 1
                        continue
                    t["defasada"] += 1
                    estado = "defasada"
                    if ger and ultima and ger < ultima:
                        t["fossil"] += 1
                        estado = "FÓSSIL"
                rid = loc if loc is not None else (ag or "")
                g_txt = f"{ger:%Y-%m-%d %H:%M}" if ger else "—"
                u_txt = f"{ultima:%Y-%m-%d %H:%M}" if ultima else "—"
                nome = (nomes.get(eid) or "")[:28]
                linhas.append(f"{eid}\t{tipo}\t{rid}\t{sub}\t{estado}\t{g_txt}\t{u_txt}\t{nome}")
    print("emp\tescopo\tid\tsub\testado\tgerado_em\túltima_do_escopo\tnome")
    for ln in linhas:
        print(ln)
    print()
    print("critério: ver docstring. 'fóssil' = defasada E houve geração POSTERIOR no mesmo escopo.")
    for tipo in ("empresa", "loja", "agrupamento"):
        t = tot[tipo]
        print(
            f"  {tipo:<12} subpilares com sugestão {t['subpilares']:>4} | "
            f"em dia {t['em_dia']:>4} | defasadas {t['defasada']:>4} "
            f"(fósseis {t['fossil']:>4}) | sem hash {t['sem_hash']:>3} | órfãs {t['orfa']:>3}"
        )


if __name__ == "__main__":
    main()
