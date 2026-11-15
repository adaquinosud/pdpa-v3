"""Nomeação por pedaço (decisão de 15/11): todos os grupos numa chamada, nome conferido em código,
segunda tentativa só para os reprovados, e destino definido para quem não volta."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.temas import rotulador as R


def _cliente(*respostas):
    """Cliente fake que devolve as respostas em ordem e guarda os pacotes enviados."""
    cli = MagicMock()
    cli.messages.create.side_effect = [
        MagicMock(content=[MagicMock(type="text", text=json.dumps(r))]) for r in respostas
    ]
    return cli


def _grupos(n):
    return [
        {"grupo": i, "tamanho": 10 + i, "representativos": [{"texto": f"comentário {i}"}]}
        for i in range(n)
    ]


def _pacote(cli, chamada):
    return json.loads(cli.messages.create.call_args_list[chamada].kwargs["messages"][0]["content"])


@pytest.mark.parametrize(
    "nome,ok",
    [
        ("atendimento", False),
        ("qualidade serviço", False),
        ("qualidade do serviço", False),
        ("Experiência do Cliente", False),
        ("atendimento oficina", True),
        ("qualidade comida", True),
        ("elogio sem detalhe", True),
        ("", False),
        (None, False),
    ],
)
def test_nome_valido_exige_palavra_fora_da_lista(nome, ok):
    assert R.nome_valido(nome) is ok


def test_uma_chamada_quando_todos_os_nomes_passam():
    cli = _cliente(
        {
            "grupos": [
                {"grupo": 0, "nome": "prazo de entrega", "junta_com": None, "motivo": None},
                {"grupo": 1, "nome": "prazo  de entrega", "junta_com": 0, "motivo": "mesmo atraso"},
                {"grupo": 2, "nome": "elogio sem detalhe", "junta_com": None, "motivo": None},
            ]
        }
    )
    with patch("src.classifier.classifier_v3._get_client", return_value=cli):
        r = R.rotular_pedaco({"subpilar": "D2", "tipo": "promotor"}, _grupos(3))
    assert r["chamadas"] == 1 and cli.messages.create.call_count == 1
    assert r["nomes"] == {0: "prazo de entrega", 1: "prazo de entrega", 2: "elogio sem detalhe"}
    assert r["juntados"] == [{"grupo": 1, "junta_com": 0, "motivo": "mesmo atraso"}]
    enviado = _pacote(cli, 0)
    assert enviado["nome_sem_detalhe"] == "elogio sem detalhe"
    assert enviado["palavras_que_nao_bastam"] == list(R.PALAVRAS_QUE_NAO_BASTAM)
    assert [g["grupo"] for g in enviado["grupos"]] == [0, 1, 2]
    kw = cli.messages.create.call_args_list[0].kwargs
    assert kw["max_tokens"] == R.MAX_TOKENS_PEDACO_BASE + 3 * R.MAX_TOKENS_POR_GRUPO


def test_reprovado_e_ausente_vao_a_segunda_tentativa_com_destino_definido():
    cli = _cliente(
        {
            "grupos": [
                {"grupo": 0, "nome": "explicação do contrato"},
                {"grupo": 1, "nome": "atendimento"},
                # grupos 2 e 3 não voltam
            ]
        },
        {
            "grupos": [
                {"grupo": 1, "nome": "qualidade do serviço"},  # reprova de novo
                {"grupo": 2, "nome": "retorno após a reclamação"},
                # grupo 3 falta de novo
            ]
        },
    )
    with patch("src.classifier.classifier_v3._get_client", return_value=cli):
        r = R.rotular_pedaco({"subpilar": "Pa1", "tipo": "detrator"}, _grupos(4))
    assert r["chamadas"] == 2
    assert r["nomes"] == {
        0: "explicação do contrato",
        1: "crítica sem detalhe",  # reprovou duas vezes → caso "sem detalhe" do tipo
        2: "retorno após a reclamação",
        3: None,  # ausente duas vezes → sem assunto
    }
    assert r["segunda_tentativa"] == [1, 2, 3]
    assert r["sem_detalhe_por_reprova"] == [1] and r["faltantes"] == [3]
    segunda = _pacote(cli, 1)
    assert [g["grupo"] for g in segunda["grupos"]] == [1, 2, 3]
    assert {x["grupo"]: x["motivo"] for x in segunda["reprovados"]} == {
        1: "só palavras que não bastam",
        2: "ausente da resposta",
        3: "ausente da resposta",
    }
    assert segunda["nomes_ja_dados"] == ["explicação do contrato"]


def test_falha_de_chamada_levanta_infra():
    cli = MagicMock()
    cli.messages.create.side_effect = RuntimeError("API fora")
    with patch("src.classifier.classifier_v3._get_client", return_value=cli):
        with pytest.raises(R.RotulagemInfraError):
            R.rotular_pedaco({"tipo": "promotor"}, _grupos(2))


def test_nome_sem_detalhe_por_tipo():
    assert R.nome_sem_detalhe("promotor") == "elogio sem detalhe"
    assert R.nome_sem_detalhe("detrator") == "crítica sem detalhe"
    assert R.nome_sem_detalhe("conversivel") == R.NOME_SEM_DETALHE_PADRAO


def test_pipeline_falha_do_pedaco_conta_cada_grupo_e_nao_grava(
    client_loyall, db_session, monkeypatch
):
    import src.temas.pipeline as P
    from src.models.temas import VerbatimTema
    from tests.test_frase_posicao import _empresa
    from tests.test_temas_pipeline import _pedaco_dois_grupos

    eid, lid, fid, _ag = _empresa(client_loyall, "FalhaPedaco")
    _pedaco_dois_grupos(db_session, eid, lid, fid, "fp")
    db_session.commit()

    def _cai(bucket, grupos, **kw):
        raise R.RotulagemInfraError("fora")

    monkeypatch.setattr(P, "rotular_pedaco", _cai)
    r = P.processar_empresa(eid)
    assert r.falhas_chamada == 2 and r.clusters_tentados == 2 and r.clusters_rotulados == 0
    assert db_session.query(VerbatimTema).count() == 0
