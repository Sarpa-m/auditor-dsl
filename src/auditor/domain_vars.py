# =============================================================================
# domain_vars.py — Tabela de Variáveis de Domínio Fiscal
#
# Este módulo é o único ponto do sistema que conhece a estrutura interna dos
# XMLs de NF-e/CT-e. Ele mapeia os nomes usados na DSL (ex: NOTA_UF_EMITENTE)
# para os caminhos XPath correspondentes no XML e para o tipo do valor extraído.
#
# Isolando esse mapeamento aqui, qualquer mudança no schema do XML ou na
# nomenclatura da DSL afeta apenas este arquivo — lexer, parser e interpretador
# permanecem intocados.
# =============================================================================

# Namespace XML padrão da NF-e (Nota Fiscal Eletrônica) conforme SEFAZ.
# Todos os elementos do XML são qualificados com este namespace, por isso ele
# aparece em cada XPath: {NS}emit, {NS}dest, etc.
NS = 'http://www.portalfiscal.inf.br/nfe'

# =============================================================================
# NOTA_VARS — variáveis de nível de nota fiscal (prefixo NOTA_)
#
# Cada entrada é:  'NOME_DSL': (xpath, tipo)
#   xpath — caminho relativo à raiz do ElementTree para encontrar o elemento
#   tipo  — 'str' (texto), 'num' (número monetário/quantidade), 'pct' (alíquota)
#
# XPaths com './/' buscam o elemento em qualquer nível da árvore XML,
# necessário porque a NF-e pode ter envelopes como <nfeProc> ou <NFe>.
# =============================================================================
NOTA_VARS = {
    # UF (estado) do emitente — ex: "SP", "RJ" — usado para filtros de origem
    'NOTA_UF_EMITENTE':       (f'.//{{{NS}}}emit/{{{NS}}}enderEmit/{{{NS}}}UF',    'str'),

    # UF do destinatário — comparado com UF emitente para derivar TIPO_OPERACAO
    'NOTA_UF_DESTINATARIO':   (f'.//{{{NS}}}dest/{{{NS}}}enderDest/{{{NS}}}UF',    'str'),

    # CNPJ do emitente (14 dígitos, sem formatação)
    'NOTA_CNPJ_EMITENTE':     (f'.//{{{NS}}}emit/{{{NS}}}CNPJ',                    'str'),

    # CNPJ do destinatário
    'NOTA_CNPJ_DESTINATARIO': (f'.//{{{NS}}}dest/{{{NS}}}CNPJ',                    'str'),

    # Valor total da NF-e em reais (campo vNF do totalizador ICMSTot)
    'NOTA_VALOR_TOTAL':       (f'.//{{{NS}}}total/{{{NS}}}ICMSTot/{{{NS}}}vNF',    'num'),

    # Valor total do ICMS destacado na nota
    'NOTA_VALOR_ICMS':        (f'.//{{{NS}}}total/{{{NS}}}ICMSTot/{{{NS}}}vICMS',  'num'),

    # Número da nota fiscal (ex: "1001")
    'NOTA_NUMERO':            (f'.//{{{NS}}}ide/{{{NS}}}nNF',                      'str'),

    # Série da nota (ex: "1")
    'NOTA_SERIE':             (f'.//{{{NS}}}ide/{{{NS}}}serie',                    'str'),

    # Data/hora de emissão no formato ISO 8601 (ex: "2024-01-15T10:00:00-03:00")
    'NOTA_DATA_EMISSAO':      (f'.//{{{NS}}}ide/{{{NS}}}dhEmi',                    'str'),

    # Natureza da operação (texto livre, ex: "Venda de mercadoria")
    'NOTA_NATUREZA':          (f'.//{{{NS}}}ide/{{{NS}}}natOp',                    'str'),

    # Tipo de operação da nota: "0" = entrada, "1" = saída
    # Atenção: diferente de TIPO_OPERACAO da DSL (inter/intraestadual),
    # que é derivado da comparação das UFs e não lido diretamente do XML.
    'NOTA_TIPO_OPERACAO':     (f'.//{{{NS}}}ide/{{{NS}}}tpNF',                     'str'),

    # Número do protocolo de autorização da SEFAZ
    'NOTA_PROTOCOLO':         (f'.//{{{NS}}}infProt/{{{NS}}}nProt',                'str'),
}

# =============================================================================
# ITEM_VARS — variáveis de nível de item/produto (prefixo ITEM_)
#
# XPaths são relativos ao elemento <det> de cada item, não à raiz do XML.
# O xml_loader extrai cada <det> separadamente e aplica esses XPaths em cada um.
#
# XPaths com '//' dentro do item (ex: imposto//{NS}pICMS) buscam a alíquota
# independentemente do regime tributário (ICMS00, ICMS10, ICMS20, etc.),
# pois o campo pICMS pode estar em sub-elementos variáveis conforme o CST.
# =============================================================================
ITEM_VARS = {
    # Código Fiscal de Operações e Prestações — 4 dígitos (ex: "6102")
    'ITEM_CFOP':              (f'{{{NS}}}prod/{{{NS}}}CFOP',          'str'),

    # Nomenclatura Comum do Mercosul — código de 8 dígitos
    'ITEM_NCM':               (f'{{{NS}}}prod/{{{NS}}}NCM',           'str'),

    # Descrição do produto (campo xProd)
    'ITEM_DESCRICAO':         (f'{{{NS}}}prod/{{{NS}}}xProd',         'str'),

    # Quantidade comercializada
    'ITEM_QUANTIDADE':        (f'{{{NS}}}prod/{{{NS}}}qCom',          'num'),

    # Valor unitário de comercialização
    'ITEM_VALOR_UNITARIO':    (f'{{{NS}}}prod/{{{NS}}}vUnCom',        'num'),

    # Valor total do item (quantidade × valor unitário)
    'ITEM_VALOR_TOTAL':       (f'{{{NS}}}prod/{{{NS}}}vProd',         'num'),

    # Alíquota do ICMS em percentual (ex: 12.0 para 12%)
    # Tipo 'pct': aceita valores PERCENTUAL na DSL (ex: 12%) e operadores relacionais
    'ITEM_ALIQUOTA_ICMS':     (f'{{{NS}}}imposto//{{{NS}}}pICMS',     'pct'),

    # Valor monetário do ICMS calculado para o item
    'ITEM_VALOR_ICMS':        (f'{{{NS}}}imposto//{{{NS}}}vICMS',     'num'),

    # Base de cálculo do ICMS
    'ITEM_BASE_CALCULO_ICMS': (f'{{{NS}}}imposto//{{{NS}}}vBC',       'num'),

    # Código de Situação Tributária do ICMS (ex: "000", "010", "060")
    'ITEM_CST_ICMS':          (f'{{{NS}}}imposto//{{{NS}}}CST',       'str'),

    # Alíquota do IPI em percentual
    'ITEM_ALIQUOTA_IPI':      (f'{{{NS}}}imposto//{{{NS}}}pIPI',      'pct'),

    # Alíquota do PIS em percentual (ex: 1.65 para o regime não-cumulativo)
    'ITEM_ALIQUOTA_PIS':      (f'{{{NS}}}imposto//{{{NS}}}pPIS',      'pct'),

    # Alíquota do COFINS em percentual (ex: 7.6 para regime não-cumulativo)
    'ITEM_ALIQUOTA_COFINS':   (f'{{{NS}}}imposto//{{{NS}}}pCOFINS',   'pct'),
}

# =============================================================================
# Dicionários e conjuntos auxiliares usados pela análise semântica
# =============================================================================

# União de NOTA_VARS e ITEM_VARS — permite buscar qualquer variável pelo nome
# sem saber antecipadamente se é de nota ou de item.
ALL_VARS = {**NOTA_VARS, **ITEM_VARS}

# Tipos que representam quantidades numéricas e aceitam operadores relacionais
# (>, <, >=, <=). Variáveis do tipo 'str' só aceitam == e !=.
NUMERIC_TYPES = {'num', 'pct'}

# Conjunto dos nomes de variáveis cujo tipo é 'pct' (alíquota percentual).
# Apenas essas variáveis aceitam valores com o token PERCENTUAL na DSL
# (ex: ITEM_ALIQUOTA_ICMS == 12%). A análise semântica rejeita percentual
# em variáveis que não estejam neste conjunto.
PCT_VARS = {k for k, (_, t) in ALL_VARS.items() if t == 'pct'}
