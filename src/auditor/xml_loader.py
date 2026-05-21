# =============================================================================
# xml_loader.py — Leitura e Mapeamento de XMLs NF-e/CT-e
#
# Quinta fase do pipeline (paralela ao interpretador). Converte arquivos XML
# de Nota Fiscal Eletrônica em dicionários Python que o interpretador pode
# avaliar contra as regras da DSL.
#
# Estrutura do dicionário retornado por load_xml():
#   {
#     'arquivo':       str,                     # nome do arquivo (sem caminho)
#     'nota':          dict[str, str|float],    # NOTA_* → valor extraído do XML
#     'itens':         list[dict[str, ...]],    # um dict por elemento <det>
#     'tipo_operacao': 'INTERESTADUAL'|'INTRAESTADUAL',  # derivado das UFs
#   }
#
# O mapeamento variável → XPath está inteiramente em domain_vars.py.
# Este módulo apenas aplica os XPaths e converte os tipos.
# =============================================================================

import xml.etree.ElementTree as ET
from pathlib import Path
from .domain_vars import NOTA_VARS, ITEM_VARS, NS


def load_xml(path: str) -> dict:
    """
    Carrega um único arquivo XML de NF-e e retorna o dicionário de domínio.
    Lança xml.etree.ElementTree.ParseError se o arquivo for inválido.
    """
    tree = ET.parse(path)
    root = tree.getroot()  # pode ser <nfeProc> ou <NFe> dependendo do envelope

    # ── Extração das variáveis de nível de nota ───────────────────────────
    # Itera sobre NOTA_VARS e aplica cada XPath na raiz do documento.
    # XPaths com './/' funcionam independentemente do envelope externo.
    nota: dict = {}
    for var, (xpath, tipo) in NOTA_VARS.items():
        el = root.find(xpath)
        if el is not None and el.text:
            # Converte para float se o tipo for numérico ou percentual;
            # mantém como string caso contrário.
            nota[var] = float(el.text) if tipo in ('num', 'pct') else el.text
        else:
            # Elemento ausente no XML → None (interpretador trata None como falso)
            nota[var] = None

    # ── Cálculo de TIPO_OPERACAO ──────────────────────────────────────────
    # TIPO_OPERACAO não existe como campo no XML — é derivado comparando as
    # UFs do emitente e do destinatário. Se forem iguais, é operação intraestadual;
    # caso contrário (inclusive se uma das UFs for None), é interestadual.
    uf_emit = nota.get('NOTA_UF_EMITENTE')
    uf_dest = nota.get('NOTA_UF_DESTINATARIO')
    tipo_op = 'INTERESTADUAL' if uf_emit != uf_dest else 'INTRAESTADUAL'

    # ── Extração dos itens (um por elemento <det>) ────────────────────────
    # A NF-e pode ter N itens/produtos, cada um dentro de <det nItem="N">.
    # Para cada <det>, aplica-se os XPaths de ITEM_VARS relativos a esse elemento.
    itens = []
    for det in root.findall(f'.//{{{NS}}}det'):
        item: dict = {}
        for var, (xpath, tipo) in ITEM_VARS.items():
            el = det.find(xpath)
            if el is not None and el.text:
                item[var] = float(el.text) if tipo in ('num', 'pct') else el.text
            else:
                item[var] = None
        itens.append(item)

    return {
        'arquivo':       Path(path).name,  # apenas o nome do arquivo, sem o caminho completo
        'nota':          nota,
        'itens':         itens,
        'tipo_operacao': tipo_op,
    }


def load_all(path: str) -> list:
    """
    Carrega um único arquivo XML ou todos os *.xml de uma pasta.
    Retorna lista de dicionários de domínio, ordenada por nome de arquivo.
    Aceita tanto um arquivo específico quanto um diretório como argumento.
    """
    p = Path(path)
    if p.is_file():
        # Caminho aponta para um arquivo único
        return [load_xml(str(p))]
    # Caminho aponta para diretório: carrega todos os .xml em ordem alfabética
    return [load_xml(str(f)) for f in sorted(p.glob('*.xml'))]
