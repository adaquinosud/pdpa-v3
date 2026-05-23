"""Importador Excel de CADASTRO hierárquico (Bloco 4 — CP3).

Distinto do importer de verbatins (``src/coletor/excel.py``): este lê
templates padronizados (``Template_Simples_PDPA_v3.xlsx`` ou
``Template_Completo_PDPA_v3.xlsx``) que descrevem **a estrutura**
(Empresa → Agrupamento → Local → Fonte), não conteúdo de coleta.

Detecção automática do template pela presença da aba ``02 Agrupamentos``:

- **Template simples** (3 abas: ``01 Empresa``, ``02 Locais``, ``03 Fontes``):
  locais ficam com ``agrupamento_id = NULL``.

- **Template completo** (4 abas: ``01 Empresa``, ``02 Agrupamentos``,
  ``03 Locais``, ``04 Fontes``): locais são vinculados a agrupamentos
  via coluna ``agrupamento*`` na aba de Locais.

Estratégia:

1. Lê todas as abas.
2. Valida linha por linha em uma passagem (acumula erros sem persistir).
3. Se houver QUALQUER erro de validação, retorna lista de erros e NÃO toca
   no banco (atomicidade).
4. Caso contrário, persiste tudo em uma transação ORM única (commit no fim).
5. Idempotência: re-import detecta empresa/agrupamento/local/fonte
   existentes pelo nome (Empresa.nome único; Agrupamento (empresa_id, nome)
   único; Local (empresa_id, nome); Fonte (empresa_id, conector_tipo, url)).
   Se ``sobrescrever=True``, atualiza campos descritivos; senão pula.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.api.fontes import CONECTORES_COM_SCRAPER, CONECTORES_CONHECIDOS
from src.models.agrupamento import Agrupamento
from src.models.empresa import Empresa
from src.models.fonte import Fonte
from src.models.local import Local
from src.utils.db import db_session


ABA_LEIA_ME = "00 Leia-me"  # opcional, ignorada
ABA_EMPRESA = "01 Empresa"
ABA_AGRUPAMENTOS = "02 Agrupamentos"
ABA_LOCAIS_COMPLETO = "03 Locais"
ABA_FONTES_COMPLETO = "04 Fontes"
ABA_LOCAIS_SIMPLES = "02 Locais"
ABA_FONTES_SIMPLES = "03 Fontes"


def _norm(valor: Any) -> Optional[str]:
    """Normaliza célula: NaN/None/string vazia → None; resto → str().strip()."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    s = str(valor).strip()
    return s if s else None


def _bool_pt(valor: Any) -> bool:
    """Converte 'sim'/'não'/True/1 para boolean."""
    if valor is None:
        return True
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)) and not pd.isna(valor):
        return bool(valor)
    s = str(valor).strip().lower()
    return s in {"sim", "true", "1", "ativo", "yes", "s"}


def detectar_template(path: Path) -> str:
    """Devolve 'completo' se a aba ``02 Agrupamentos`` existe, senão 'simples'."""
    xl = pd.ExcelFile(path)
    if ABA_AGRUPAMENTOS in xl.sheet_names:
        return "completo"
    return "simples"


def _ler_aba(path: Path, sheet: str) -> pd.DataFrame:
    """Lê uma aba e remove colunas/linhas totalmente vazias."""
    df = pd.read_excel(path, sheet_name=sheet)
    df = df.dropna(how="all", axis=0).dropna(how="all", axis=1)
    # Limpa nomes de colunas (strip)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _validar_e_extrair(path: Path) -> Tuple[Dict[str, Any], List[str]]:
    """Lê o xlsx, valida e devolve (dados_extraidos, erros)."""
    erros: List[str] = []
    template = detectar_template(path)
    xl = pd.ExcelFile(path)

    # ── Aba Empresa (obrigatória em ambos templates) ────────────────────
    if ABA_EMPRESA not in xl.sheet_names:
        erros.append(f"Aba '{ABA_EMPRESA}' não encontrada")
        return {}, erros

    df_emp = _ler_aba(path, ABA_EMPRESA)
    if len(df_emp) != 1:
        erros.append(f"Aba '{ABA_EMPRESA}' deve ter EXATAMENTE 1 linha (achou {len(df_emp)})")
        return {}, erros

    row_emp = df_emp.iloc[0]
    nome_empresa = _norm(row_emp.get("nome*") or row_emp.get("nome"))
    setor = _norm(row_emp.get("setor*") or row_emp.get("setor"))
    if not nome_empresa:
        erros.append(f"Aba '{ABA_EMPRESA}': coluna 'nome*' vazia")
    if not setor:
        erros.append(f"Aba '{ABA_EMPRESA}': coluna 'setor*' vazia")

    empresa = {
        "nome": nome_empresa,
        "setor": setor,
        "cnpj": _norm(row_emp.get("cnpj")),
        "site": _norm(row_emp.get("site")),
        "observacao": _norm(row_emp.get("observacao") or row_emp.get("observação")),
    }

    # ── Aba Agrupamentos (só no template completo) ──────────────────────
    agrupamentos: List[Dict[str, Any]] = []
    if template == "completo":
        df_ag = _ler_aba(path, ABA_AGRUPAMENTOS)
        for i, row in df_ag.iterrows():
            nome = _norm(row.get("nome*") or row.get("nome"))
            if not nome:
                erros.append(f"Aba '{ABA_AGRUPAMENTOS}' linha {i + 2}: 'nome*' vazio")
                continue
            agrupamentos.append(
                {
                    "nome": nome,
                    "descricao": _norm(row.get("descricao") or row.get("descrição")),
                    "ativo": _bool_pt(row.get("ativo*", row.get("ativo", True))),
                }
            )
        nomes_ag = [a["nome"] for a in agrupamentos]
        if len(set(nomes_ag)) != len(nomes_ag):
            erros.append(f"Aba '{ABA_AGRUPAMENTOS}': nomes duplicados")

    # ── Aba Locais ──────────────────────────────────────────────────────
    aba_locais = ABA_LOCAIS_COMPLETO if template == "completo" else ABA_LOCAIS_SIMPLES
    if aba_locais not in xl.sheet_names:
        erros.append(f"Aba '{aba_locais}' não encontrada")
        return {}, erros

    df_loc = _ler_aba(path, aba_locais)
    locais: List[Dict[str, Any]] = []
    nomes_agrup_validos = {a["nome"] for a in agrupamentos}
    for i, row in df_loc.iterrows():
        nome_loc = _norm(row.get("nome*") or row.get("nome"))
        if not nome_loc:
            erros.append(f"Aba '{aba_locais}' linha {i + 2}: 'nome*' vazio")
            continue
        agrup_nome = None
        if template == "completo":
            agrup_nome = _norm(row.get("agrupamento*") or row.get("agrupamento"))
            if not agrup_nome:
                erros.append(
                    f"Aba '{aba_locais}' linha {i + 2}: 'agrupamento*' vazio "
                    f"(local '{nome_loc}')"
                )
            elif agrup_nome not in nomes_agrup_validos:
                erros.append(
                    f"Aba '{aba_locais}' linha {i + 2}: agrupamento "
                    f"'{agrup_nome}' não está em '{ABA_AGRUPAMENTOS}'"
                )
        locais.append(
            {
                "nome": nome_loc,
                "agrupamento_nome": agrup_nome,
                "endereco": _norm(row.get("endereco") or row.get("endereço")),
                "observacao": _norm(row.get("observacao") or row.get("observação")),
            }
        )
    nomes_loc = [loc["nome"] for loc in locais]
    if len(set(nomes_loc)) != len(nomes_loc):
        erros.append(f"Aba '{aba_locais}': nomes de local duplicados")

    # ── Aba Fontes ──────────────────────────────────────────────────────
    aba_fontes = ABA_FONTES_COMPLETO if template == "completo" else ABA_FONTES_SIMPLES
    if aba_fontes not in xl.sheet_names:
        erros.append(f"Aba '{aba_fontes}' não encontrada")
        return {}, erros

    df_f = _ler_aba(path, aba_fontes)
    fontes: List[Dict[str, Any]] = []
    nomes_locais_validos = {loc["nome"] for loc in locais}
    for i, row in df_f.iterrows():
        local_nome = _norm(row.get("local*") or row.get("local"))
        conector = _norm(row.get("conector_tipo*") or row.get("conector_tipo"))
        url = _norm(
            row.get("url_ou_identificador*") or row.get("url_ou_identificador") or row.get("url")
        )
        ativo = _bool_pt(row.get("ativo*", row.get("ativo", True)))

        if not local_nome:
            erros.append(f"Aba '{aba_fontes}' linha {i + 2}: 'local*' vazio")
            continue
        if local_nome not in nomes_locais_validos:
            erros.append(
                f"Aba '{aba_fontes}' linha {i + 2}: local '{local_nome}' "
                f"não está em '{aba_locais}'"
            )
            continue
        if not conector:
            erros.append(f"Aba '{aba_fontes}' linha {i + 2}: 'conector_tipo*' vazio")
            continue
        if conector not in CONECTORES_CONHECIDOS:
            erros.append(
                f"Aba '{aba_fontes}' linha {i + 2}: conector_tipo "
                f"'{conector}' desconhecido (aceitos: "
                f"{sorted(CONECTORES_CONHECIDOS)})"
            )
            continue
        if conector not in CONECTORES_COM_SCRAPER and ativo:
            erros.append(
                f"Aba '{aba_fontes}' linha {i + 2}: conector '{conector}' "
                f"não tem scraper Apify — cadastre com 'ativo=não' "
                f"(catalogação) ou use conector com scraper"
            )
            continue
        if not url:
            erros.append(f"Aba '{aba_fontes}' linha {i + 2}: 'url_ou_identificador*' vazio")
            continue

        fontes.append(
            {
                "local_nome": local_nome,
                "conector_tipo": conector,
                "url": url,
                "ativo": ativo,
                "observacao": _norm(row.get("observacao") or row.get("observação")),
            }
        )

    return (
        {
            "template": template,
            "empresa": empresa,
            "agrupamentos": agrupamentos,
            "locais": locais,
            "fontes": fontes,
        },
        erros,
    )


def importar_cadastro(
    path: Path,
    sobrescrever: bool = False,
) -> Dict[str, Any]:
    """Importa uma planilha de cadastro (template simples ou completo).

    Args:
        path: Caminho do arquivo ``.xlsx``.
        sobrescrever: Se ``True``, atualiza campos descritivos de entidades
            já existentes (não cria duplicatas). Se ``False`` (padrão),
            pula entidades que já existem pelo nome e devolve a contagem
            de "puladas" no resultado.

    Returns:
        Dict com:
            - ``empresa_id`` (int, obrigatório se sucesso)
            - ``template``: 'simples' | 'completo'
            - ``agrupamentos_criados``, ``agrupamentos_pulados`` (int)
            - ``locais_criados``, ``locais_pulados`` (int)
            - ``fontes_criadas``, ``fontes_puladas`` (int)
            - ``erros``: lista de strings (vazia se sucesso)

    Em caso de QUALQUER erro de validação, a função NÃO escreve nada no
    banco — devolve apenas ``{"erros": [...]}`` e o caller decide.
    """
    dados, erros = _validar_e_extrair(path)
    if erros:
        return {"erros": erros}

    resultado: Dict[str, Any] = {
        "template": dados["template"],
        "empresa_id": None,
        "agrupamentos_criados": 0,
        "agrupamentos_pulados": 0,
        "locais_criados": 0,
        "locais_pulados": 0,
        "fontes_criadas": 0,
        "fontes_puladas": 0,
        "erros": [],
    }

    with db_session() as session:
        # ── Empresa ───────────────────────────────────────────────────
        emp_data = dados["empresa"]
        empresa = session.query(Empresa).filter_by(nome=emp_data["nome"]).first()
        if empresa is None:
            empresa = Empresa(
                nome=emp_data["nome"],
                setor=emp_data["setor"],
                cnpj=emp_data["cnpj"],
                site=emp_data["site"],
                observacao=emp_data["observacao"],
            )
            session.add(empresa)
            session.flush()
        elif sobrescrever:
            for campo in ("setor", "cnpj", "site", "observacao"):
                if emp_data.get(campo) is not None:
                    setattr(empresa, campo, emp_data[campo])
            session.flush()
        resultado["empresa_id"] = empresa.id

        # ── Agrupamentos ──────────────────────────────────────────────
        agrupamento_map: Dict[str, int] = {}  # nome → id
        for ag_data in dados["agrupamentos"]:
            existe = (
                session.query(Agrupamento)
                .filter_by(empresa_id=empresa.id, nome=ag_data["nome"])
                .first()
            )
            if existe is None:
                ag = Agrupamento(
                    empresa_id=empresa.id,
                    nome=ag_data["nome"],
                    descricao=ag_data["descricao"],
                    ativo=ag_data["ativo"],
                )
                session.add(ag)
                session.flush()
                agrupamento_map[ag_data["nome"]] = ag.id
                resultado["agrupamentos_criados"] += 1
            else:
                if sobrescrever:
                    existe.descricao = ag_data["descricao"]
                    existe.ativo = ag_data["ativo"]
                agrupamento_map[ag_data["nome"]] = existe.id
                resultado["agrupamentos_pulados"] += 1

        # ── Locais ────────────────────────────────────────────────────
        local_map: Dict[str, int] = {}
        for loc_data in dados["locais"]:
            existe = (
                session.query(Local).filter_by(empresa_id=empresa.id, nome=loc_data["nome"]).first()
            )
            ag_id = (
                agrupamento_map.get(loc_data["agrupamento_nome"])
                if loc_data.get("agrupamento_nome")
                else None
            )
            if existe is None:
                local = Local(
                    empresa_id=empresa.id,
                    agrupamento_id=ag_id,
                    nome=loc_data["nome"],
                    endereco=loc_data["endereco"],
                    observacao=loc_data["observacao"],
                )
                session.add(local)
                session.flush()
                local_map[loc_data["nome"]] = local.id
                resultado["locais_criados"] += 1
            else:
                if sobrescrever:
                    existe.agrupamento_id = ag_id
                    existe.endereco = loc_data["endereco"]
                    existe.observacao = loc_data["observacao"]
                local_map[loc_data["nome"]] = existe.id
                resultado["locais_pulados"] += 1

        # ── Fontes ────────────────────────────────────────────────────
        for f_data in dados["fontes"]:
            local_id = local_map[f_data["local_nome"]]
            existe = (
                session.query(Fonte)
                .filter_by(
                    empresa_id=empresa.id,
                    entidade_tipo="local",
                    entidade_id=local_id,
                    conector_tipo=f_data["conector_tipo"],
                    url=f_data["url"],
                )
                .first()
            )
            if existe is None:
                fonte = Fonte(
                    empresa_id=empresa.id,
                    entidade_tipo="local",
                    entidade_id=local_id,
                    conector_tipo=f_data["conector_tipo"],
                    url=f_data["url"],
                    ativo=f_data["ativo"],
                    observacao=f_data["observacao"],
                )
                session.add(fonte)
                resultado["fontes_criadas"] += 1
            else:
                if sobrescrever:
                    existe.ativo = f_data["ativo"]
                    existe.observacao = f_data["observacao"]
                resultado["fontes_puladas"] += 1

        session.flush()

    return resultado
