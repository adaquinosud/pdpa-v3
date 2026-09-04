"""O consolidador lê a entidade e separa os TRÊS estados (§6.22, fatia 3).

Antes desta fatia ``_textos()`` devolvia ``list[str]`` sem rótulo, e o filtro
``if (r.resposta_texto or "").strip()`` **descartava as respostas vazias em
silêncio** — sem contagem, sem registro. Medido na exec 28: o GPT devolveu vazio em
6 de 8 entidades no encaminhamento e 4 de 8 na identidade, e nada disso aparecia.

⚠️ Os três estados NÃO colapsam: ``vazio`` é o modelo não devolver nada (achado de
instrumento), ``desconhece`` é a IA dizer que não conhece (achado de reputação — a
marca é invisível), e **nenhum dos dois é ausência de sondagem**. É a mesma família
do §6.21.
"""

from __future__ import annotations

from src.models.empresa import Empresa
from src.models.sonda_ia import SondaIAExecucao, SondaIALeitura, SondaIAResposta
from src.sonda_ia.classificador import (
    LEITURA_PROMPT_VER,
    classificar_estado,
    sintetizar_leitura,
)
from src.sonda_ia.defasagem import cruzar_defasagem


def _cenario(db_session, sfx, entidades=None, vazios_gpt=0):
    e = Empresa(nome=f"ECons-{sfx}-{id(db_session)}")
    db_session.add(e)
    db_session.flush()
    ex = SondaIAExecucao(empresa_id=e.id, competencia="2026-10", status="concluida")
    db_session.add(ex)
    db_session.flush()
    alvos = entidades or [None]
    n_gpt = 0  # contador PRÓPRIO do gpt: `n` global contaria os outros vendors junto
    for ent in alvos:
        for vendor in ("claude", "gpt", "gemini"):
            for tipo in ("identidade", "encaminhamento"):
                if vendor == "gpt" and n_gpt < vazios_gpt:
                    texto = ""
                    n_gpt += 1
                elif vendor == "claude" and ent == "Loja Invisível":
                    texto = "Não tenho informações específicas sobre essa unidade."
                else:
                    texto = f"{ent or e.nome} é uma concessionária."
                db_session.add(
                    SondaIAResposta(
                        execucao_id=ex.id,
                        empresa_id=e.id,
                        vendor=vendor,
                        modelo=f"{vendor}-x",
                        pergunta_tipo=tipo,
                        repeticao=1,
                        entidade=ent,
                        resposta_texto=texto,
                    )
                )
    db_session.commit()
    return e, ex


def _fake(capt):
    def _g(payload):
        capt.append(payload)
        return {"identidade_ecoada": "x", "encaminhamentos": [], "resumo_por_modelo": {}}

    return _g


# ── os três estados ────────────────────────────────────────────────────────────


def test_classificar_estado_separa_os_tres():
    assert classificar_estado("") == "vazio"
    assert classificar_estado("   ") == "vazio"
    assert classificar_estado(None) == "vazio"
    assert classificar_estado("Não tenho informações sobre essa loja.") == "desconhece"
    assert classificar_estado("NÃO CONHEÇO essa marca") == "desconhece"
    assert classificar_estado("É uma concessionária Jeep.") == "conteudo"


def test_desconhece_e_heuristica_com_falso_negativo(db_session):
    """⚠️ Declarado no código: recusa fora do conjunto de marcadores passa como
    'conteudo'. O prompt manda o LLM confiar no TEXTO quando ele contradisser o
    rótulo — o estado é SINAL, não fato."""
    assert classificar_estado("Desconheço por completo esta empresa.") == "conteudo"


def test_vazio_CHEGA_ao_consolidador_e_e_contado(db_session):
    """O achado que sumia: antes, vazio era filtrado e não existia."""
    e, ex = _cenario(db_session, "vazios", entidades=["A", "B"], vazios_gpt=2)
    capt = []
    sintetizar_leitura(ex.id, gerar_fn=_fake(capt))
    p = capt[0]
    estados = {i["estado"] for i in p["identidade"] + p["encaminhamento"]}
    assert "vazio" in estados
    tot_vazio = p["cobertura"]["identidade"]["por_estado"].get("vazio", 0) + p["cobertura"][
        "encaminhamento"
    ]["por_estado"].get("vazio", 0)
    assert tot_vazio == 2
    assert p["cobertura"]["identidade"]["vazio_por_vendor"].get("gpt", 0) >= 1


def test_desconhece_chega_rotulado(db_session):
    e, ex = _cenario(db_session, "desc", entidades=["Loja Invisível"])
    capt = []
    sintetizar_leitura(ex.id, gerar_fn=_fake(capt))
    itens = capt[0]["identidade"]
    assert any(i["estado"] == "desconhece" and i["entidade"] == "Loja Invisível" for i in itens)


# ── a entidade chega, e o grão empresa não regride ─────────────────────────────


def test_grao_entidade_manda_o_nome_da_entidade(db_session):
    e, ex = _cenario(db_session, "ent", entidades=["Audi Alphaville", "Jeep Morumbi"])
    capt = []
    sintetizar_leitura(ex.id, gerar_fn=_fake(capt))
    p = capt[0]
    assert p["grao"] == "entidade"
    assert set(p["cobertura"]["entidades"]) == {"Audi Alphaville", "Jeep Morumbi"}
    assert {i["entidade"] for i in p["identidade"]} == {"Audi Alphaville", "Jeep Morumbi"}


def test_NAO_REGRESSAO_grao_empresa_rotula_com_o_nome_da_empresa(db_session):
    """As 24 empresas de hoje: entidade NULL → o rótulo é a razão social."""
    e, ex = _cenario(db_session, "emp")
    capt = []
    sintetizar_leitura(ex.id, gerar_fn=_fake(capt))
    p = capt[0]
    assert p["grao"] == "empresa"
    assert {i["entidade"] for i in p["identidade"]} == {e.nome}


def test_por_modelo_sai_no_grao_entidade_e_fica_no_grao_empresa(db_session):
    """⚠️ `por_modelo` agrupa só por vendor. Com N entidades, "os modelos divergem"
    pode ser "as entidades divergem" — dois eixos colapsados num."""
    _, ex_ent = _cenario(db_session, "pm-ent", entidades=["A", "B"])
    capt = []
    sintetizar_leitura(ex_ent.id, gerar_fn=_fake(capt))
    assert "por_modelo" not in capt[0]

    _, ex_emp = _cenario(db_session, "pm-emp")
    capt2 = []
    sintetizar_leitura(ex_emp.id, gerar_fn=_fake(capt2))
    assert "por_modelo" in capt2[0]


# ── versão do prompt ───────────────────────────────────────────────────────────


def test_grava_a_versao_e_pula_na_mesma_versao(db_session):
    _, ex = _cenario(db_session, "ver")
    sintetizar_leitura(ex.id, gerar_fn=_fake([]))
    db_session.expire_all()
    lt = db_session.query(SondaIALeitura).filter_by(execucao_id=ex.id).one()
    assert lt.prompt_versao == LEITURA_PROMPT_VER
    r = sintetizar_leitura(ex.id, gerar_fn=_fake([]))
    assert r["pulado"] is True and "versão do prompt" in r["motivo"]


def test_versao_diferente_NAO_re_sintetiza_sozinha(db_session):
    """⚠️ Run pago não dispara sozinho (§13). Versão velha → pula declarando; quem
    re-sintetiza é o comando explícito."""
    _, ex = _cenario(db_session, "vercai")
    sintetizar_leitura(ex.id, gerar_fn=_fake([]))
    db_session.expire_all()
    db_session.query(SondaIALeitura).filter_by(execucao_id=ex.id).one().prompt_versao = "v1"
    db_session.commit()
    r = sintetizar_leitura(ex.id, gerar_fn=_fake([]))
    assert r["pulado"] is True
    assert "v1" in r["motivo"]


# ── defasagem ──────────────────────────────────────────────────────────────────


def test_defasagem_NAO_roda_no_grao_entidade(db_session):
    """Sem 'avaliacao' no grão entidade, o lado-IA é vazio e `_defasagem(None, x)`
    devolveria 'exclusiva_verbatim' — que SIGNIFICA "o cliente falou e a IA não",
    quando a verdade é "não perguntamos". Medição fabricada, indo ao impresso."""
    _, ex = _cenario(db_session, "def-ent", entidades=["A"])
    r = cruzar_defasagem(ex.id)
    assert r["subpilares"] == []
    assert r.get("nao_medida") == "grao_entidade"
    db_session.expire_all()
    lt = db_session.query(SondaIALeitura).filter_by(execucao_id=ex.id).first()
    assert lt is None or lt.defasagem_json is None, "não pode gravar defasagem fabricada"


def test_defasagem_roda_no_grao_empresa(db_session):
    _, ex = _cenario(db_session, "def-emp")
    r = cruzar_defasagem(ex.id)
    assert "nao_medida" not in r
