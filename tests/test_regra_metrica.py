"""Regra 4 (Alexandre, 10/11/2026): texto do modelo lido pelo cliente não cita nem recomenda
métrica de outra metodologia (NPS, CSAT, índice de satisfação…). Fonte única:
``painel.regra_metrica_para_prompt``, anexada ao system de cada gerador. Citar para contrastar é
permitido. Aqui se confere que a regra chega ao system de cada gerador."""

from __future__ import annotations

import inspect

from src.api.painel import regra_metrica_para_prompt

REGRA = regra_metrica_para_prompt()


def test_regra_proibe_medida_e_permite_contraste():
    assert "NPS" in REGRA and "CSAT" in REGRA and "índice de" in REGRA
    assert "CONTRASTAR" in REGRA and "nunca para recomendá-la" in REGRA


class _Resp:
    def __init__(self, texto):
        self.content = [type("B", (), {"type": "text", "text": texto})()]
        self.usage = type("U", (), {"input_tokens": 1, "output_tokens": 1})()
        self.stop_reason = "end_turn"


def _cliente(capt, texto):
    class C:
        class messages:
            @staticmethod
            def create(**kw):
                capt.append(kw)
                return _Resp(texto)

    return C()


def _sys(kw):
    s = kw["system"]
    return s if isinstance(s, str) else "".join(b["text"] for b in s)


def test_frase_do_painel(monkeypatch):
    from src.api.painel_leitura import gerar_leitura_sequencial

    capt = []
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client", lambda: _cliente(capt, '{"leitura": "x"}')
    )
    gerar_leitura_sequencial(
        {
            "total_verbatins": 10,
            "pilares": [
                {
                    "pilar": "P",
                    "ratio": 1.0,
                    "total": 10,
                    "promotor": 5,
                    "conversivel": 0,
                    "detrator": 5,
                }
            ],
        }
    )
    assert REGRA in _sys(capt[0])


def test_acao_de_venda(monkeypatch):
    from src.temas.acao import _gerar_acao_llm

    capt = []
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client",
        lambda: _cliente(capt, '{"acao": "a", "impacto_qualitativo": "alto"}'),
    )
    _gerar_acao_llm({"label": "x"})
    assert REGRA in _sys(capt[0])


def test_editorial_anexa_regra_extra(monkeypatch):
    from src.anomalias import editorial

    capt = []
    monkeypatch.setattr(
        "src.classifier.classifier_v3._get_client", lambda: _cliente(capt, '{"o_que": "x"}')
    )
    editorial._chamar_sonnet({"a": 1}, regra_extra=REGRA)
    assert _sys(capt[0]).endswith(REGRA)
    # classificadores que reusam a função não recebem nada a mais
    editorial._chamar_sonnet({"a": 1})
    assert REGRA not in _sys(capt[1])


def test_quem_escreve_ao_cliente_pelo_editorial_passa_a_regra():
    """Leitura diagnóstica, síntese do Parecer e leitura de anomalia chamam o editorial com a
    regra; a verificação é no código-fonte porque o caminho real exige o pacote inteiro do banco."""
    from src.anomalias import editorial
    from src.diagnostico import leituras
    from src.relatorios import parecer

    for fn in (leituras.gerar_e_persistir_diagnostico, parecer, editorial.gerar_leitura):
        src = inspect.getsource(fn)
        assert "regra_extra=regra_metrica_para_prompt()" in src, fn


def test_chat(client_loyall, db_session):
    from src.ia.chat import responder

    e = client_loyall.post("/api/empresas/", json={"nome": "RegraChat"}).get_json()
    vistos = []

    def fake(system_prompt, contexto, pergunta):
        vistos.append(system_prompt)
        return {"resposta": "r", "tokens_in": 1, "tokens_out": 1}

    responder(db_session, e["id"], "Qual o gargalo?", gerar_fn=fake, usar_cache=False)
    assert vistos and vistos[0].endswith(REGRA)


def test_frase_de_posicao_monta_o_sistema_com_a_regra():
    from src.diagnostico import frase_posicao

    assert "+ regra_metrica_para_prompt()" in inspect.getsource(frase_posicao.gerar_frases)
