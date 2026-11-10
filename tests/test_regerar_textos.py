"""Regeração forçada de textos nomeados (src/relatorios/regerar.py, llm_secoes._FORCAR/_SO_MEDIR).

O hash dos textos cobre só o pacote: depois de mudar o prompt, sem forçar, o texto velho seria
lido para sempre. Forçar regera SÓ o pedido e atualiza a linha que existe (não apaga); medir não
grava nada."""

from __future__ import annotations

from src.models.relatorio_cache import RelatorioCache
from src.relatorios import llm_secoes


def _empresa(client_loyall, nome):
    return client_loyall.post("/api/empresas/", json={"nome": nome}).get_json()["id"]


def test_forcar_regera_mesmo_com_hash_igual_e_atualiza_a_linha(client_loyall, db_session):
    eid = _empresa(client_loyall, "RegForca")
    payload = {"pilar": "A", "subs": []}
    chamadas = []

    def fake(prompt, p):
        chamadas.append(1)
        return {"raw": f"texto {len(chamadas)}", "tokens_in": 10, "tokens_out": 5}

    r1 = llm_secoes.gerar_descricao_pilar(eid, "h", "A", payload, gerar_fn=fake)
    assert r1["texto"] == "texto 1"
    id1 = (
        db_session.query(RelatorioCache.id).filter_by(empresa_id=eid, secao="desc_pilar_A").scalar()
    )
    # mesmo pacote → cache
    assert llm_secoes.gerar_descricao_pilar(eid, "h", "A", payload, gerar_fn=fake)["cached"]
    # forçado → regera, e a linha é a MESMA (atualizada, não apagada e recriada)
    llm_secoes._FORCAR = {(eid, "desc_pilar_A")}
    try:
        r3 = llm_secoes.gerar_descricao_pilar(eid, "h", "A", payload, gerar_fn=fake)
    finally:
        llm_secoes._FORCAR = set()
    assert r3["texto"] == "texto 2" and not r3["cached"]
    db_session.expire_all()
    linhas = db_session.query(RelatorioCache).filter_by(empresa_id=eid, secao="desc_pilar_A").all()
    assert len(linhas) == 1 and linhas[0].id == id1
    assert "texto 2" in linhas[0].conteudo_json
    # forçar uma seção não força outra
    assert (
        llm_secoes.gerar_descricao_pilar(eid, "h", "D", payload, gerar_fn=fake)["cached"] is False
    )


def test_medir_nao_grava(client_loyall, db_session):
    eid = _empresa(client_loyall, "RegMedir")
    llm_secoes._SO_MEDIR = True
    try:
        llm_secoes.gerar_descricao_pilar(
            eid, "h", "P", {"x": 1}, gerar_fn=lambda pr, p: {"raw": "falso", "tokens_in": 0}
        )
    finally:
        llm_secoes._SO_MEDIR = False
    assert db_session.query(RelatorioCache).filter_by(empresa_id=eid).count() == 0


def test_regra_de_numero_vai_no_system_dos_textos_do_relatorio(monkeypatch):
    from src.api.engajamento import VOLUME_CONFIANCA_ALTA

    capt = {}

    class FakeResp:
        content = []
        usage = None

    class FakeClient:
        class messages:
            @staticmethod
            def create(**kw):
                capt.update(kw)
                return FakeResp()

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: FakeClient())
    llm_secoes._chamar_sonnet("PROMPT BASE", "{}", max_tokens=10)
    s = capt["system"]
    assert s.startswith("PROMPT BASE") and "sem detrator" in s
    assert f"abaixo de {VOLUME_CONFIANCA_ALTA} manifestações" in s  # piso lido da constante


def test_comando_medir_roda_fora_de_requisicao(client_loyall, db_session, app, monkeypatch):
    """O --medir quebrava em produção: montar_dados chama painel_nivel1 (rota autenticada) e a
    linha de comando não tem requisição ('Working outside of request context'). Roda o comando
    como a CLI roda — sem request context — e confere que mede e não grava nada."""
    from itertools import count

    from src.models.verbatim import Verbatim

    seq = count()
    e = client_loyall.post("/api/empresas/", json={"nome": "RegCLI"}).get_json()
    a = client_loyall.post(f"/api/empresas/{e['id']}/agrupamentos", json={"nome": "G"}).get_json()
    loc = client_loyall.post(
        f"/api/empresas/{e['id']}/locais", json={"nome": "L", "agrupamento_id": a["id"]}
    ).get_json()
    f = client_loyall.post(
        f"/api/locais/{loc['id']}/fontes", json={"conector_tipo": "google", "url": "ChIJRegCLI"}
    ).get_json()
    for sub, tipo in [("P1", "detrator"), ("P1", "promotor"), ("A1", "promotor")] * 3:
        i = next(seq)
        db_session.add(
            Verbatim(
                empresa_id=e["id"],
                local_id=loc["id"],
                fonte_id=f["id"],
                texto=f"t{i}",
                subpilar=sub,
                tipo=tipo,
                tem_texto=True,
                hash_dedup=f"regcli{i}",
            )
        )
    db_session.commit()

    class _Contagem:
        input_tokens = 123

    class FakeClient:
        class messages:
            @staticmethod
            def count_tokens(**kw):
                return _Contagem()

            @staticmethod
            def create(**kw):  # nunca deve ser chamado no --medir
                raise AssertionError("chamada paga no --medir")

    monkeypatch.setattr("src.classifier.classifier_v3._get_client", lambda: FakeClient())
    # o cliente de teste deixa uma requisição aberta nesta thread; a CLI não tem nenhuma —
    # roda numa thread nova, sem request context, como em produção
    import threading

    from flask import has_request_context

    saida = {}

    def _rodar():
        saida["sem_request"] = not has_request_context()
        saida["r"] = app.test_cli_runner().invoke(
            args=[
                "regerar-textos",
                "--empresa-id",
                str(e["id"]),
                "--secoes",
                "desc_pilar_P",
                "--medir",
            ]
        )

    th = threading.Thread(target=_rodar)
    th.start()
    th.join()
    assert saida["sem_request"]
    r = saida["r"]
    assert r.exit_code == 0, r.output + repr(r.exception)
    assert "desc" in r.output.lower() or "_PROMPT_DESC_PILAR" in r.output
    assert "Nada foi gravado" in r.output
    assert db_session.query(RelatorioCache).filter_by(empresa_id=e["id"]).count() == 0
