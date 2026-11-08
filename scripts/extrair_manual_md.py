"""Regenera a cópia em texto do Manual de Operação (data/PDPA_Manual_Operacao_vNN.md) a partir
do .docx de mesmo nome.

O .docx é a fonte; o .md é só para leitura, e tem de ser regenerado no mesmo passo de qualquer
edição do .docx: dois manuais que discordam é pior que nenhum (decisão de 07/11/2026). Os dois
ficam fora do git, em data/.

Sem argumento, usa o .docx de MAIOR número em data/ (o sufixo do arquivo é iteração de arquivo,
não a versão do Manual, que está na capa):

    .venv/bin/python scripts/extrair_manual_md.py [data/PDPA_Manual_Operacao_v16.docx]

Formato (reproduz byte a byte o .md de 25/10/2026): um bloco por parágrafo não vazio, estilos
Heading1/2/3 viram #/##/###, tabela vira markdown com |---| depois da primeira linha, blocos
separados por linha em branco, cabeçalho com a data da extração.
"""

import re
import sys
from datetime import date
from html import unescape
from pathlib import Path
from zipfile import ZipFile

DATA = Path("data")
NIVEL = {"Heading1": "# ", "Heading2": "## ", "Heading3": "### "}
_RUN = re.compile(r"<w:t(?: [^>]*)?>([^<]*)</w:t>|(<w:tab/>)|(<w:br/>)")
_BLOCO = re.compile(r"<w:tbl>.*?</w:tbl>|<w:p[ >].*?</w:p>|<w:p/>", re.S)


def _texto(frag: str) -> str:
    return unescape(
        "".join(t if t else ("\t" if tab else "\n") for t, tab, _br in _RUN.findall(frag))
    )


def _tabela(tbl: str) -> str:
    linhas = []
    for tr in re.findall(r"<w:tr[ >].*?</w:tr>", tbl, re.S):
        cels = [_texto(tc).strip() for tc in re.findall(r"<w:tc>.*?</w:tc>", tr, re.S)]
        linhas.append("| " + " | ".join(cels) + " |")
        if len(linhas) == 1:
            linhas.append("|" + "|".join("---" for _ in cels) + "|")
    return "\n".join(linhas)


def extrair(docx: Path, hoje: date) -> str:
    """O .md inteiro, como texto."""
    xml = ZipFile(docx).read("word/document.xml").decode()
    blocos = []
    for m in _BLOCO.finditer(xml.split("<w:body>", 1)[1]):
        b = m.group(0)
        if b.startswith("<w:tbl>"):
            blocos.append(_tabela(b))
            continue
        t = _texto(b)
        if not t.strip():
            continue
        st = re.search(r'w:pStyle w:val="([^"]+)"', b)
        blocos.append(NIVEL.get(st.group(1) if st else "", "") + t)
    cab = (
        f"<!-- Texto extraído de data/{docx.name} em {hoje:%d/%m/%Y}. "
        "A fonte é o .docx; este arquivo é só para leitura. -->"
    )
    return cab + "\n\n" + "\n\n".join(blocos) + "\n"


def mais_recente(pasta: Path = DATA) -> Path:
    """O .docx de maior número (PDPA_Manual_Operacao_vNN.docx); ignora a trava do Word."""
    achados = [
        (int(m.group(1)), p)
        for p in pasta.glob("PDPA_Manual_Operacao_v*.docx")
        if (m := re.fullmatch(r"PDPA_Manual_Operacao_v(\d+)\.docx", p.name))
    ]
    if not achados:
        sys.exit(f"nenhum PDPA_Manual_Operacao_vNN.docx em {pasta}/")
    return max(achados)[1]


if __name__ == "__main__":
    docx = Path(sys.argv[1]) if len(sys.argv) > 1 else mais_recente()
    if (docx.parent / f"~${docx.name[2:]}").exists():
        sys.exit(
            f"{docx} está aberto no Word: feche antes (o que está no Word pode não estar gravado)."
        )
    saida = docx.with_suffix(".md")
    saida.write_text(extrair(docx, date.today()), encoding="utf-8")
    print(f"{saida} regenerado a partir de {docx}")
