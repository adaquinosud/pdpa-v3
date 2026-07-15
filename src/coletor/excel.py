"""Importador Excel/CSV de verbatins — GENÉRICO (Fase 1).

Lê a 1ª aba de qualquer planilha de pesquisa/CSAT e mapeia, por aliases, 7
campos lógicos (texto, data, rating, review_id_externo, agrupamento, local,
fonte). Cria Agrupamento/Local que não existem (resolve-or-create), depara por
``review_id_externo`` (índice único parcial) ou pelo hash, e — ao fim — dispara
o pós-coleta (force=True) pra rodar classificação→temas→detecção→diagnóstico→
sugestões→relatórios→leitura. NÃO classifica no momento do import.

Compat: ``importar_arquivo(caminho, empresa_id, local_id=, fonte_id=)`` segue
funcionando; ``local_id``/``fonte_id`` viram fallback file-level quando a linha
não traz coluna local/fonte. ``computar_hash_dedup`` (fórmula de texto) mantida.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from sqlalchemy import func

from src.models.agrupamento import Agrupamento
from src.models.fonte import Fonte
from src.models.local import Local
from src.models.pessoa import Pessoa, PessoaIdentificador
from src.models.verbatim import Verbatim
from src.utils.db import db_session

# Aliases por coluna lógica — case-insensitive (comparados em strip().lower()).
_ALIASES: Dict[str, set[str]] = {
    "texto": {
        "texto",
        "verbatim",
        "verbatins",
        "comentario",
        "comentário",
        "text",
        "review",
        "resposta",
    },
    "autor": {"autor", "author", "nome", "respondente", "cliente"},
    "data": {"data", "date", "data_publicacao", "data_publicação", "dt", "data_criacao_original"},
    "rating": {"rating", "nota", "score", "csat", "nps", "avaliacao", "avaliação"},
    "review_id": {
        "id",
        "id_chamado",
        "id chamado",
        "ticket",
        "protocolo",
        "review_id",
        "review_id_externo",
        "chamado",
    },
    "agrupamento": {"agrupamento", "fila", "categoria", "grupo", "departamento"},
    "local": {"local", "origem", "unidade", "loja", "filial"},
    "fonte": {"fonte", "source"},
}

# Colunas de IDENTIDADE — só relevantes no modo "interno identificado" (cria
# Pessoa). Aliases de FRASE INTEIRA de propósito: ``id_cliente`` NÃO usa o token
# solto "id" (que o ``review_id`` já reivindica — bare "id" engoliria "id chamado"
# /ticket). No modo interno entram ANTES dos campos-base (capturam a coluna de
# identidade); no modo normal NÃO entram (detecção idêntica à de hoje).
_ALIASES_IDENTIDADE: Dict[str, set[str]] = {
    "email": {"email", "e-mail", "mail"},
    "id_cliente": {
        "id_cliente",
        "id cliente",
        "codigo cliente",
        "código cliente",
        "cod cliente",
        "cod_cliente",
        "customer_id",
        "customer id",
    },
}


def _aliases_efetivos(interno: bool) -> Dict[str, set[str]]:
    """Mapa de aliases usado na detecção. Interno = identidade primeiro + base;
    normal = base intacta (byte-a-byte como hoje)."""
    if interno:
        return {**_ALIASES_IDENTIDADE, **_ALIASES}
    return _ALIASES


# Vocabulário PT de rating qualitativo → escala 1–5 (best-effort; só usado quando
# a célula é palavra pura, sem número). Número embutido ("5 - Ótimo") tem prioridade.
_RATING_PALAVRAS: Dict[str, int] = {
    "muito insatisfeito": 1,
    "insatisfeito": 2,
    "neutro": 3,
    "satisfeito": 4,
    "muito satisfeito": 5,
    "pessimo": 1,
    "péssimo": 1,
    "ruim": 2,
    "regular": 3,
    "bom": 4,
    "otimo": 5,
    "ótimo": 5,
    "detrator": 1,
    "promotor": 5,
}


def _detectar_colunas(columns: List[str], interno: bool = False) -> Dict[str, Optional[str]]:
    """Mapeia campo lógico → nome real da coluna (ou None se ausente).

    Casa por nome inteiro normalizado OU por TOKEN — qualquer palavra do header
    que seja alias casa o campo (ex.: 'Nota CSAT' → rating, 'ID Chamado' →
    review_id). Cada coluna é atribuída a no máximo 1 campo (1ª na ordem do mapa);
    headers ambíguos podem ser corrigidos no preview (Fase 2).

    ``interno=True`` adiciona os campos de identidade (email/id_cliente), com
    prioridade sobre os campos-base; ``interno=False`` usa só os campos de hoje."""
    aliases = _aliases_efetivos(interno)
    mapping: Dict[str, Optional[str]] = {k: None for k in aliases}
    usados: set[int] = set()
    for campo, campo_aliases in aliases.items():
        for idx, col in enumerate(columns):
            if idx in usados:
                continue
            norm = str(col).strip().lower()
            tokens = {t for t in re.split(r"[^a-z0-9]+", norm) if t}
            if norm in campo_aliases or (tokens & campo_aliases):
                mapping[campo] = col
                usados.add(idx)
                break
    return mapping


def _validar(colunas: Dict[str, Optional[str]], interno_identificado: bool = False) -> List[str]:
    """Exige ao menos uma coluna de SINAL (texto OU rating). No modo interno
    identificado, exige TAMBÉM uma coluna de identidade (email OU id_cliente)."""
    erros: List[str] = []
    if colunas.get("texto") is None and colunas.get("rating") is None:
        erros.append("Nenhuma coluna de texto nem de rating encontrada (precisa de ao menos uma).")
    if interno_identificado and colunas.get("email") is None and colunas.get("id_cliente") is None:
        erros.append("Import interno identificado exige uma coluna de email ou id_cliente.")
    return erros


def computar_hash_dedup(texto: str, fonte_id: int, autor: Optional[str]) -> str:
    """Hash de dedup para linhas de TEXTO (fórmula histórica, mantida p/ compat)."""
    base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    return hashlib.sha256(base.encode()).hexdigest()


def _hash_dedup(
    fonte_id: int,
    texto: str,
    autor: Optional[str],
    rating: Optional[int],
    data_iso: Optional[str],
    review_id: Optional[str],
) -> str:
    """Hash de dedup robusto. Texto → fórmula histórica; com review_id → por id;
    rating-only sem id → rating+data+autor (evita colisão de notas distintas)."""
    if review_id:
        base = f"{fonte_id}|rid:{review_id}"
    elif texto:
        base = f"{fonte_id}|{autor or ''}|{texto[:200]}"
    else:
        r = rating if rating is not None else ""
        base = f"{fonte_id}|{autor or ''}|rating:{r}|data:{data_iso or ''}"
    return hashlib.sha256(base.encode()).hexdigest()


def prever_arquivo(caminho: Union[str, Path], interno_identificado: bool = False) -> Dict[str, Any]:
    """Preview (read-only, sem DB): lê a 1ª aba, detecta as colunas e valida —
    para a tela mostrar o mapa de campos antes de confirmar o import.

    ``interno_identificado=True`` detecta as colunas de identidade e valida que
    exista email OU id_cliente."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    df = _ler_dataframe(caminho)
    colunas = _detectar_colunas(list(df.columns), interno=interno_identificado)
    return {
        "colunas_detectadas": colunas,
        "erros_validacao": _validar(colunas, interno_identificado),
        "total": len(df),
        "headers": [str(c) for c in df.columns],
        "interno": interno_identificado,
    }


def gerar_modelo_xlsx(interno_identificado: bool = False) -> io.BytesIO:
    """Gera um .xlsx de exemplo (contrato visual das colunas) para download.

    Normal: texto, rating, data, autor, local, agrupamento. Interno: + email,
    id_cliente. Duas linhas de exemplo + aba de instruções. Cada cabeçalho é o NOME
    CANÔNICO do detector (membro do próprio set de ``_ALIASES``), então ``_detectar_
    colunas`` casa exatamente. Inclui as colunas de GRÃO (``local``/``agrupamento``)
    que o detector já lê mas o modelo antigo não entregava — sem elas todo import
    nascia empresa-wide, sem unidade."""
    cols = ["texto", "rating", "data", "autor", "local", "agrupamento"]
    rows = [
        {
            "texto": "Atendimento rápido e cordial",
            "rating": 5,
            "data": "2026-06-01",
            "autor": "Maria Souza",
            "local": "Loja Centro",
            "agrupamento": "Vendas",
        },
        {
            "texto": "Demorou para resolver meu problema",
            "rating": 2,
            "data": "2026-06-02",
            "autor": "João Lima",
            "local": "Loja Shopping",
            "agrupamento": "Suporte",
        },
    ]
    if interno_identificado:
        cols = cols + ["email", "id_cliente"]
        rows[0].update({"email": "maria.souza@empresa.com", "id_cliente": "CRM-1001"})
        rows[1].update({"email": "joao.lima@empresa.com", "id_cliente": "CRM-1002"})

    # Aba de instruções (o import lê SEMPRE a 1ª aba — os dados; esta é a 2ª, só ajuda).
    instr = [
        ("texto", "O comentário / resposta aberta."),
        ("rating", "A nota, de 1 a 5."),
        (
            "data",
            "A data da RESPOSTA (não a do import). Sem ela o histórico colapsa no mês do upload.",
        ),
        ("autor", "Nome ou rótulo de quem respondeu (opcional)."),
        (
            "local",
            "A unidade/loja/filial — dá o GRÃO. Cria o local/agrupamento que faltar.",
        ),
        ("agrupamento", "Fila/categoria/departamento do local (opcional)."),
    ]
    if interno_identificado:
        instr += [
            ("email", "E-mail do respondente (identidade consentida) — cria a Pessoa."),
            ("id_cliente", "Código do cliente no CRM (identidade consentida) — cria a Pessoa."),
        ]

    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=cols).to_excel(writer, index=False, sheet_name="verbatins")
        pd.DataFrame(instr, columns=["coluna", "o que preencher"]).to_excel(
            writer, index=False, sheet_name="instruções"
        )
    bio.seek(0)
    return bio


def _ler_dataframe(caminho: Path) -> pd.DataFrame:
    """Lê a 1ª aba de xlsx/xls ou um csv. ValueError em formato não suportado."""
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(caminho)
    if ext == ".csv":
        return pd.read_csv(caminho)
    raise ValueError(f"Formato não suportado: {ext}")


def _parse_data(valor: Any) -> Optional[datetime]:
    """Converte célula em datetime ou None."""
    if pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor
    if isinstance(valor, pd.Timestamp):
        return valor.to_pydatetime()
    try:
        return pd.to_datetime(valor).to_pydatetime()
    except (ValueError, TypeError):
        return None


def _parse_rating(valor: Any) -> Optional[int]:
    """Coage rating em inteiro. Numérico → int; '5 - Ótimo' → 5 (número embutido);
    'Satisfeito' → vocabulário PT 1–5; senão None."""
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, bool):  # bool é subclasse de int — ignora
        return None
    if isinstance(valor, (int, float)):
        try:
            return int(round(float(valor)))
        except (ValueError, TypeError):
            return None
    s = str(valor).strip().lower()
    if not s:
        return None
    m = re.search(r"-?\d+", s)  # número embutido tem prioridade ('5 - ótimo')
    if m:
        try:
            return int(m.group())
        except ValueError:
            return None
    return _RATING_PALAVRAS.get(s)


def _texto_celula(valor: Any) -> str:
    """Texto limpo da célula (string vazia se NaN/None)."""
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _norm_nome(valor: Any) -> Optional[str]:
    """Nome trimado (None se vazio/NaN) — chave de resolve-or-create."""
    if valor is None or pd.isna(valor):
        return None
    s = str(valor).strip()
    return s or None


def _norm_email(valor: Any) -> Optional[str]:
    """Email normalizado (lower+trim) — chave estável da Pessoa interna."""
    if valor is None or pd.isna(valor):
        return None
    s = str(valor).strip().lower()
    return s or None


def _find_or_create_agrupamento(session, empresa_id: int, nome: str, cache: Dict[str, int]) -> int:
    key = nome.lower()
    if key in cache:
        return cache[key]
    ag = (
        session.query(Agrupamento)
        .filter(Agrupamento.empresa_id == empresa_id, func.lower(Agrupamento.nome) == key)
        .first()
    )
    if ag is None:
        ag = Agrupamento(empresa_id=empresa_id, nome=nome)
        session.add(ag)
        session.flush()
    cache[key] = ag.id
    return ag.id


def _find_or_create_local(
    session, empresa_id: int, nome: str, agrupamento_id: Optional[int], cache: Dict[str, int]
) -> int:
    key = nome.lower()
    if key in cache:
        return cache[key]
    loc = (
        session.query(Local)
        .filter(Local.empresa_id == empresa_id, func.lower(Local.nome) == key)
        .first()
    )
    if loc is None:  # cria; existente é REUSADO sem mover de agrupamento
        loc = Local(empresa_id=empresa_id, nome=nome, agrupamento_id=agrupamento_id)
        session.add(loc)
        session.flush()
    cache[key] = loc.id
    return cache[key]


def _find_or_create_fonte(
    session,
    empresa_id: int,
    nome: str,
    cache: Dict[str, int],
    conector_tipo: str = "excel_manual",
    autenticacao_tipo: str = "publica",
) -> int:
    """Find-or-create da fonte do import. ``conector_tipo``/``autenticacao_tipo``
    separam o regime: 'excel_manual'/'publica' (import normal de hoje) vs.
    'excel_interno'/'autenticada' (base interna consentida)."""
    key = nome.lower()
    if key in cache:
        return cache[key]
    f = (
        session.query(Fonte)
        .filter(
            Fonte.empresa_id == empresa_id,
            Fonte.conector_tipo == conector_tipo,
            func.lower(Fonte.url) == key,
        )
        .first()
    )
    if f is None:
        f = Fonte(
            empresa_id=empresa_id,
            entidade_tipo="empresa",
            entidade_id=empresa_id,
            conector_tipo=conector_tipo,
            url=nome,
            autenticacao_tipo=autenticacao_tipo,
            status="ativa",
        )
        session.add(f)
        session.flush()
    cache[key] = f.id
    return cache[key]


_LOG = logging.getLogger(__name__)

# Namespace das chaves de identidade da PESSOA na PESQUISA (item A): e-mail (voluntário)
# e código do CRM/ERP da empresa (o que ela já tem). Fontes distintas, mesma Pessoa.
FONTE_EMAIL = "pesquisa"
FONTE_CRM = "crm"


def _ident_opt_in(fonte: str, external_id: str, origem: str) -> "PessoaIdentificador":
    return PessoaIdentificador(
        tipo="interno_consentido",
        fonte=fonte,
        external_id=external_id,
        atributos_json=json.dumps(
            {"opt_in": True, "origem": origem, "data": datetime.utcnow().isoformat()}
        ),
    )


def _merge_pessoas(session, alvo_id: int, absorvida_id: int, *, gatilho: str, chaves: dict) -> None:
    """Funde ``absorvida_id`` em ``alvo_id`` — reassign FKs + move identificadores + apaga
    a órfã. AUDITÁVEL: grava PessoaMerge (quem, em quem, quando, ids movidos) e loga.
    Merge sem registro do que moveu é irreversível na prática (lição da fusão de temas)."""
    from src.models.pessoa import PessoaMerge
    from src.models.respondente import Respondente
    from src.models.verbatim import Verbatim

    vids = [v.id for v in session.query(Verbatim.id).filter(Verbatim.pessoa_id == absorvida_id)]
    rids = [
        r.id for r in session.query(Respondente.id).filter(Respondente.pessoa_id == absorvida_id)
    ]
    if vids:
        session.query(Verbatim).filter(Verbatim.id.in_(vids)).update(
            {Verbatim.pessoa_id: alvo_id}, synchronize_session=False
        )
    if rids:
        session.query(Respondente).filter(Respondente.id.in_(rids)).update(
            {Respondente.pessoa_id: alvo_id}, synchronize_session=False
        )
    # Move os identificadores da absorvida que o alvo ainda não tem (evita violar o UNIQUE)
    existentes = {
        (i.fonte, i.external_id)
        for i in session.query(PessoaIdentificador).filter_by(pessoa_id=alvo_id)
    }
    for ident in session.query(PessoaIdentificador).filter_by(pessoa_id=absorvida_id).all():
        if (ident.fonte, ident.external_id) in existentes:
            session.delete(ident)
        else:
            ident.pessoa_id = alvo_id
    session.query(Pessoa).filter(Pessoa.id == absorvida_id).delete(synchronize_session=False)
    session.add(
        PessoaMerge(
            pessoa_alvo_id=alvo_id,
            pessoa_absorvida_id=absorvida_id,
            gatilho=gatilho,
            chaves_json=json.dumps(chaves),
            verbatins_reassignados=len(vids),
            respondentes_reassignados=len(rids),
            ids_json=json.dumps({"verbatins": vids, "respondentes": rids}),
        )
    )
    session.flush()
    _LOG.info(
        "pessoa merge: %s→%s gatilho=%s chaves=%s verbatins=%d respondentes=%d",
        absorvida_id,
        alvo_id,
        gatilho,
        chaves,
        len(vids),
        len(rids),
    )


def _reconciliar_pessoa(
    session,
    *,
    email: Optional[str] = None,
    id_cliente: Optional[str] = None,
    nome: Optional[str] = None,
    origem: str = "pesquisa",
) -> Optional[int]:
    """Resolve UMA Pessoa a partir de e-mail e/ou código de CRM (item A). As duas chaves
    coexistem (``fonte='pesquisa'`` p/ e-mail, ``fonte='crm'`` p/ código): mesma pessoa,
    duas chaves, reconcilia por qualquer uma. Sem nenhuma chave → None (anônimo).

    - 0 Pessoa encontrada → cria + anexa as chaves.
    - 1 → reusa + anexa a chave que faltar.
    - 2 distintas → MERGE na mais antiga (menor id), auditável (``_merge_pessoas``).
    """
    chaves = []
    if email:
        chaves.append((FONTE_EMAIL, email))
    if id_cliente:
        chaves.append((FONTE_CRM, id_cliente))
    if not chaves:
        return None

    achados: Dict[str, PessoaIdentificador] = {}  # pessoa_id → ident (dedup por pessoa)
    for fonte, ext in chaves:
        ident = (
            session.query(PessoaIdentificador)
            .filter_by(tipo="interno_consentido", fonte=fonte, external_id=ext)
            .first()
        )
        if ident is not None:
            achados[ident.pessoa_id] = ident

    if not achados:
        pessoa = Pessoa(tipo="interno_consentido", nome_display=nome)
        pessoa.identificadores = [_ident_opt_in(f, e, origem) for f, e in chaves]
        session.add(pessoa)
        session.flush()
        return pessoa.id

    ids = sorted(achados)
    alvo_id = ids[0]  # a mais antiga sobrevive
    if len(ids) > 1:
        for absorvida_id in ids[1:]:
            _merge_pessoas(
                session,
                alvo_id,
                absorvida_id,
                gatilho=origem,
                chaves={f: e for f, e in chaves},
            )

    # Anexa ao alvo qualquer chave do gatilho que ainda não exista (nome se estava vazio)
    existentes = {
        (i.fonte, i.external_id)
        for i in session.query(PessoaIdentificador).filter_by(pessoa_id=alvo_id)
    }
    for fonte, ext in chaves:
        if (fonte, ext) not in existentes:
            session.add(_ident_opt_in_para(alvo_id, fonte, ext, origem))
    if nome:
        pessoa = session.get(Pessoa, alvo_id)
        if pessoa is not None and not pessoa.nome_display:
            pessoa.nome_display = nome
    session.flush()
    return alvo_id


def _ident_opt_in_para(pessoa_id: int, fonte: str, external_id: str, origem: str):
    ident = _ident_opt_in(fonte, external_id, origem)
    ident.pessoa_id = pessoa_id
    return ident


def importar_arquivo(
    caminho: Union[str, Path],
    empresa_id: int,
    local_id: Optional[int] = None,
    fonte_id: Optional[int] = None,
    *,
    disparar_pos: bool = False,
    interno_identificado: bool = False,
    consentimento: bool = False,
) -> Dict[str, Any]:
    """Importa Excel/CSV para Verbatim crus (sem classificação). ``local_id``/
    ``fonte_id`` são fallback file-level (a coluna da linha tem prioridade).

    ``disparar_pos=True`` (a rota passa isso, dentro do app context) dispara o
    pós-coleta ao fim → classificação→temas→detecção→…→leitura. Default False:
    chamadas diretas (scripts/testes) ficam puras, sem precisar de app context.

    ``interno_identificado=True`` (exige ``consentimento=True``): base interna
    consentida — cria ``Pessoa(interno_consentido)`` por email|id_cliente, fonte
    'excel_interno'. Default (desligado): import idêntico ao de hoje, sem Pessoa."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    # Gate de consentimento: não importa base identificada sem o opt-in do lote.
    if interno_identificado and not consentimento:
        return {
            "importados": 0,
            "duplicados": 0,
            "erros": 0,
            "ignorados": 0,
            "total": 0,
            "colunas_detectadas": {},
            "erros_validacao": ["Consentimento obrigatório para o import interno identificado."],
        }

    # MESMA regra do coletor (fonte única): threshold de tem_texto + heurística de
    # rating dos sem-texto. Espelha src/coletor/pipeline.processar_verbatim_coletado.
    from src.coletor.pipeline import MIN_CHARS_PARA_PROCESSAR, RATING_PARA_CLASSIFICACAO

    df = _ler_dataframe(caminho)
    colunas = _detectar_colunas(list(df.columns), interno=interno_identificado)
    erros_validacao = _validar(colunas, interno_identificado)
    if erros_validacao:
        return {
            "importados": 0,
            "duplicados": 0,
            "erros": 0,
            "ignorados": 0,
            "total": 0,
            "colunas_detectadas": colunas,
            "erros_validacao": erros_validacao,
        }

    c_texto, c_autor, c_data = colunas["texto"], colunas["autor"], colunas["data"]
    c_rating, c_rid = colunas["rating"], colunas["review_id"]
    c_agr, c_local, c_fonte = colunas["agrupamento"], colunas["local"], colunas["fonte"]
    c_email, c_id_cliente = colunas.get("email"), colunas.get("id_cliente")
    # Regime da fonte: interno consentido vs. import normal de hoje.
    conector_f = "excel_interno" if interno_identificado else "excel_manual"
    auth_f = "autenticada" if interno_identificado else "publica"

    stats: Dict[str, Any] = {
        "importados": 0,
        "duplicados": 0,
        "erros": 0,
        "ignorados": 0,
        "total": len(df),
        "colunas_detectadas": colunas,
        "agrupamentos_criados": 0,
        "locais_criados": 0,
        "pessoas_vinculadas": 0,  # Pessoas DISTINTAS ligadas (criadas OU reusadas)
        "pessoas_merges": 0,  # linhas que fundiram 2 Pessoas pré-existentes (email+crm)
        "sem_identidade": 0,
    }

    with db_session() as session:
        from src.models.pessoa import PessoaMerge

        cache_agr: Dict[str, int] = {}
        cache_loc: Dict[str, int] = {}
        cache_fonte: Dict[str, int] = {}
        pessoas_vinc: set[int] = set()  # ids distintos vinculados (conta honesta)
        merges_antes = session.query(PessoaMerge).count()  # p/ o delta de fusões

        # Fonte padrão do arquivo (find-or-create por nome → dedup idempotente no
        # reimport). Se a rota passou um fonte_id explícito, ele é o default.
        if fonte_id:
            fonte_default_id = fonte_id
        else:
            nome_fonte_padrao = f"Excel Import — {caminho.name}"
            fonte_default_id = _find_or_create_fonte(
                session, empresa_id, nome_fonte_padrao, cache_fonte, conector_f, auth_f
            )
        stats["fonte_id"] = fonte_default_id

        # Pré-carrega chaves de dedup existentes (1 query cada) → dedup cross-import
        # e intra-arquivo via sets em memória, sem N queries.
        rids_existentes = {
            (r[0], r[1])
            for r in session.query(Verbatim.fonte_id, Verbatim.review_id_externo)
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.review_id_externo.isnot(None))
            .all()
        }
        hashes_existentes = {
            r[0]
            for r in session.query(Verbatim.hash_dedup)
            .filter(Verbatim.empresa_id == empresa_id, Verbatim.hash_dedup.isnot(None))
            .all()
        }
        for _, row in df.iterrows():
            try:
                texto = _texto_celula(row[c_texto]) if c_texto else ""
                rating = _parse_rating(row[c_rating]) if c_rating else None
                if not texto and rating is None:
                    stats["ignorados"] += 1  # linha sem texto e sem nota → nada a importar
                    continue

                # tem_texto pelo MESMO threshold do coletor (MIN_CHARS_PARA_PROCESSAR=3).
                tem_texto = len(texto) >= MIN_CHARS_PARA_PROCESSAR
                # Heurística de rating no ingest (espelha pipeline.py): sem-texto + nota
                # 1-5 → tipo (valência) + Pa1 PROVISÓRIO; o pós-coleta (redistribuir_
                # simbolos) move o subpilar pela proporção. Sem isso, fica preso NULL
                # (tipo NULL → redistribuir_simbolos pula). Sem rating válido → NULL.
                sub_h = tipo_h = conf_h = just_h = pv_h = None
                if not tem_texto and rating in RATING_PARA_CLASSIFICACAO:
                    sub_h, tipo_h, conf_h, just_h = RATING_PARA_CLASSIFICACAO[rating]
                    pv_h = "rating-heuristica-v1"

                autor = _norm_nome(row[c_autor]) if c_autor else None
                data_orig = _parse_data(row[c_data]) if c_data else None
                review_id = _norm_nome(row[c_rid]) if c_rid else None

                # Escopo por linha (coluna tem prioridade sobre o param file-level).
                agr_id = None
                if c_agr:
                    nome_agr = _norm_nome(row[c_agr])
                    if nome_agr:
                        antes = len(cache_agr)
                        agr_id = _find_or_create_agrupamento(
                            session, empresa_id, nome_agr, cache_agr
                        )
                        if len(cache_agr) > antes:
                            stats["agrupamentos_criados"] += 1
                row_local_id = local_id
                if c_local:
                    nome_loc = _norm_nome(row[c_local])
                    if nome_loc:
                        antes = len(cache_loc)
                        row_local_id = _find_or_create_local(
                            session, empresa_id, nome_loc, agr_id, cache_loc
                        )
                        if len(cache_loc) > antes:
                            stats["locais_criados"] += 1
                row_fonte_id = fonte_default_id
                if c_fonte:
                    nome_fonte = _norm_nome(row[c_fonte])
                    if nome_fonte:
                        row_fonte_id = _find_or_create_fonte(
                            session, empresa_id, nome_fonte, cache_fonte, conector_f, auth_f
                        )

                # Pessoa (só modo interno consentido): MESMO caminho da pesquisa-PDPA
                # (_reconciliar_pessoa) — email→fonte 'pesquisa', id_cliente→fonte 'crm',
                # multi-chave + merge auditável. Assim o mesmo email/id_cliente do CSAT e
                # de uma pesquisa colapsam na MESMA Pessoa (cruza fontes por pessoa). NUNCA
                # funde por nome (autor é só rótulo). Sem chave → verbatim sem Pessoa.
                pessoa_id_row = None
                if interno_identificado:
                    email_v = _norm_email(row[c_email]) if c_email else None
                    idc_v = _norm_nome(row[c_id_cliente]) if c_id_cliente else None
                    if email_v or idc_v:
                        pessoa_id_row = _reconciliar_pessoa(
                            session,
                            email=email_v,
                            id_cliente=idc_v,
                            nome=autor,
                            origem="import_excel",
                        )
                        if pessoa_id_row is not None:
                            pessoas_vinc.add(pessoa_id_row)
                    else:
                        stats["sem_identidade"] += 1

                data_iso = data_orig.isoformat() if data_orig else None
                hash_d = _hash_dedup(row_fonte_id, texto, autor, rating, data_iso, review_id)

                # Dedup: por (fonte_id, review_id) se houver; senão pelo hash. Cobre
                # os dois UNIQUE (review_id parcial + (empresa_id, hash_dedup)).
                dup = False
                if review_id and (row_fonte_id, review_id) in rids_existentes:
                    dup = True
                if not dup and hash_d in hashes_existentes:
                    dup = True
                if dup:
                    stats["duplicados"] += 1
                    continue

                session.add(
                    Verbatim(
                        empresa_id=empresa_id,
                        local_id=row_local_id,
                        fonte_id=row_fonte_id,
                        pessoa_id=pessoa_id_row,  # aditivo; None fora do modo interno
                        texto=texto,  # NOT NULL: rating-only entra com ""
                        tem_texto=tem_texto,
                        autor=autor,  # PERMANECE — load-bearing no dedup
                        data_criacao_original=data_orig,
                        rating=rating,
                        review_id_externo=review_id,
                        hash_dedup=hash_d,
                        subpilar=sub_h,  # heurística de rating (sem-texto); senão NULL
                        tipo=tipo_h,
                        confianca=conf_h,
                        justificativa=just_h,
                        prompt_versao=pv_h,
                    )
                )
                if review_id:
                    rids_existentes.add((row_fonte_id, review_id))
                hashes_existentes.add(hash_d)
                stats["importados"] += 1
            except Exception:  # noqa: BLE001 — linha problemática não derruba o lote
                stats["erros"] += 1

        # Contas de identidade (dentro do `with`, antes do commit): Pessoas DISTINTAS
        # vinculadas + delta de fusões (linhas que fundiram email+crm de 2 Pessoas
        # pré-existentes — auditoria "fundi N clientes que já existiam").
        stats["pessoas_vinculadas"] = len(pessoas_vinc)
        stats["pessoas_merges"] = session.query(PessoaMerge).count() - merges_antes

    # Gatilho pós-coleta (force=True, limiar=1) — APÓS o commit, pra a thread ver
    # os verbatins. Roda classificação→temas→detecção→…→leitura em daemon-thread.
    if disparar_pos and stats["importados"] > 0:
        from src.coletor.orquestrador import disparar_pos_coleta_async

        disparar_pos_coleta_async(empresa_id)
        stats["pos_coleta_disparado"] = True

    return stats
