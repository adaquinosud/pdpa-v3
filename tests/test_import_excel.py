"""Testes do importador Excel/CSV (src/coletor/excel.py)."""

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest
from sqlalchemy.orm import Session

from src.coletor.excel import _detectar_colunas, computar_hash_dedup, importar_arquivo
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.verbatim import Verbatim


def _criar_xlsx(rows: List[Dict[str, Any]], tmp_path: Path, name: str = "test.xlsx") -> Path:
    """Cria um xlsx temporário a partir de uma lista de dicts."""
    df = pd.DataFrame(rows)
    arquivo = tmp_path / name
    df.to_excel(arquivo, index=False)
    return arquivo


def test_detectar_colunas_aliases() -> None:
    m = _detectar_colunas(["Verbatim", "Author", "Date", "Outra"])
    assert m["texto"] == "Verbatim"
    assert m["autor"] == "Author"
    assert m["data"] == "Date"

    m2 = _detectar_colunas(["comentário", "respondente", "data_publicação"])
    assert m2["texto"] == "comentário"
    assert m2["autor"] == "respondente"
    assert m2["data"] == "data_publicação"


def test_detectar_colunas_sem_match() -> None:
    m = _detectar_colunas(["foo", "bar"])
    assert m["texto"] is None
    assert m["autor"] is None
    assert m["data"] is None


def test_hash_dedup_deterministico() -> None:
    h1 = computar_hash_dedup("texto", 1, "Maria")
    h2 = computar_hash_dedup("texto", 1, "Maria")
    assert h1 == h2

    assert computar_hash_dedup("texto", 1, "João") != h1  # autor difere
    assert computar_hash_dedup("texto", 2, "Maria") != h1  # fonte difere
    assert computar_hash_dedup("outro", 1, "Maria") != h1  # texto difere

    # autor None aceito e idempotente
    assert computar_hash_dedup("t", 1, None) == computar_hash_dedup("t", 1, None)


def test_import_basico(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx(
        [
            {"texto": "Atendimento ótimo", "autor": "Maria"},
            {"texto": "Muito demorado", "autor": "João"},
            {"texto": "Recomendo", "autor": "Ana"},
        ],
        tmp_path,
    )
    empresa = Empresa(nome="TestCorp")
    db_session.add(empresa)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id)
    assert stats["importados"] == 3
    assert stats["duplicados"] == 0
    assert stats["erros"] == 0
    assert stats["total"] == 3
    assert "fonte_id" in stats


def test_import_dedup_intra_batch(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx(
        [
            {"texto": "Igual", "autor": "Maria"},
            {"texto": "Diferente", "autor": "João"},
            {"texto": "Igual", "autor": "Maria"},  # match da primeira
        ],
        tmp_path,
    )
    empresa = Empresa(nome="DupCorp")
    db_session.add(empresa)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id)
    assert stats["importados"] == 2
    assert stats["duplicados"] == 1


def test_import_dedup_reimport(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx([{"texto": "A", "autor": "X"}, {"texto": "B", "autor": "Y"}], tmp_path)
    empresa = Empresa(nome="ReCorp")
    db_session.add(empresa)
    db_session.commit()

    stats1 = importar_arquivo(arquivo, empresa_id=empresa.id)
    assert stats1["importados"] == 2

    stats2 = importar_arquivo(arquivo, empresa_id=empresa.id, fonte_id=stats1["fonte_id"])
    assert stats2["importados"] == 0
    assert stats2["duplicados"] == 2


def test_import_local_deterministico(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx([{"texto": "X"}, {"texto": "Y"}], tmp_path)

    empresa = Empresa(nome="LocaisCorp")
    db_session.add(empresa)
    db_session.commit()
    local = Local(empresa_id=empresa.id, nome="Filial 1")
    db_session.add(local)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id, local_id=local.id)
    assert stats["importados"] == 2

    verbatins = db_session.query(Verbatim).filter_by(local_id=local.id).all()
    assert len(verbatins) == 2
    # nenhum classificado (Bloco 3 fará isso)
    assert all(v.subpilar is None and v.tipo is None for v in verbatins)


def test_import_cria_fonte_excel_manual(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx([{"texto": "X"}], tmp_path)
    empresa = Empresa(nome="AutoFonteCorp")
    db_session.add(empresa)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id)
    fonte = db_session.get(Fonte, stats["fonte_id"])
    assert fonte is not None
    assert fonte.conector_tipo == "excel_manual"
    assert fonte.entidade_tipo == "empresa"  # local_id ausente
    assert fonte.entidade_id == empresa.id


def test_import_sem_coluna_texto(tmp_path: Path, db_session: Session) -> None:
    arquivo = _criar_xlsx([{"autor": "X"}], tmp_path, name="sem_texto.xlsx")
    empresa = Empresa(nome="EmptyCorp")
    db_session.add(empresa)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id)
    assert stats["importados"] == 0
    assert "erros_validacao" in stats
    assert any("texto" in e for e in stats["erros_validacao"])


def test_import_arquivo_inexistente(db_session: Session) -> None:
    empresa = Empresa(nome="NoFileCorp")
    db_session.add(empresa)
    db_session.commit()

    with pytest.raises(FileNotFoundError):
        importar_arquivo("/tmp/nao_existe_xpto.xlsx", empresa_id=empresa.id)


def test_import_extensao_nao_suportada(tmp_path: Path, db_session: Session) -> None:
    bad = tmp_path / "verbatins.txt"
    bad.write_text("texto qualquer")

    empresa = Empresa(nome="BadExtCorp")
    db_session.add(empresa)
    db_session.commit()

    with pytest.raises(ValueError):
        importar_arquivo(bad, empresa_id=empresa.id)


def test_import_csv(tmp_path: Path, db_session: Session) -> None:
    df = pd.DataFrame([{"texto": "CSV A", "autor": "M"}, {"texto": "CSV B", "autor": "N"}])
    arquivo = tmp_path / "verbatins.csv"
    df.to_csv(arquivo, index=False)

    empresa = Empresa(nome="CSVCorp")
    db_session.add(empresa)
    db_session.commit()

    stats = importar_arquivo(arquivo, empresa_id=empresa.id)
    assert stats["importados"] == 2
