# =============================================================================
# lexer.py — Análise Léxica (tokenização) com PLY lex
#
# Esta é a primeira fase do pipeline de compilação. O lexer lê o texto bruto
# do arquivo .auditor e o converte em uma sequência de tokens — unidades
# mínimas de significado (palavras-chave, operadores, literais).
#
# Como o PLY funciona:
#   - Cada função t_NOME ou variável t_NOME define uma regra de token.
#   - O PLY converte as docstrings/strings em expressões regulares e as
#     combina em uma única regex otimizada.
#   - Funções têm prioridade sobre variáveis simples; entre funções, a ordem
#     de definição no arquivo determina a precedência.
#   - build_lexer() instancia o lexer completo pronto para uso.
# =============================================================================

import ply.lex as lex


# -----------------------------------------------------------------------------
# LexError — exceção de erro léxico com localização de linha
# -----------------------------------------------------------------------------
class LexError(Exception):
    def __init__(self, msg, line):
        # Formata a mensagem com o número de linha para facilitar depuração
        super().__init__(f"[Erro Léxico] Linha {line}: {msg}")


# =============================================================================
# tokens — lista mestra de todos os tipos de token reconhecidos pelo lexer
#
# O PLY exige que esta tupla exista e contenha TODOS os tokens que o parser
# vai usar. O parser importa 'tokens' diretamente deste módulo.
# =============================================================================
tokens = (
    # Palavras-chave estruturais da DSL
    'REGRA',      # inicia uma definição de regra
    'ANALISAR',   # define o tipo de documento a ser auditado
    'FILTRAR',    # define um filtro de pré-seleção
    'ONDE',       # introduz a condição de um filtro
    'VALIDAR',    # define a condição que deve ser verdadeira
    'QUE',        # introduz a condição de validação
    'AO_FALHAR',  # define a ação quando a validação falha
    'ALERTA',     # ação: emite aviso sem rejeitar a nota
    'REJEITAR',   # ação: marca a nota como inválida
    'E',          # operador lógico AND (maior precedência que OU)
    'OU',         # operador lógico OR

    # Contexto de análise
    'NOTA',       # nível de nota fiscal inteira
    'ITEM',       # nível de produto/item individual

    # Tipos de documento
    'NFE',        # Nota Fiscal Eletrônica
    'CTE',        # Conhecimento de Transporte Eletrônico

    # Valores especiais para TIPO_OPERACAO
    'INTERESTADUAL',   # operação entre estados diferentes
    'INTRAESTADUAL',   # operação dentro do mesmo estado

    # Operadores de string
    'CONTEM',     # verifica se a string contém uma substring
    'INICIA_COM', # verifica se a string começa com um prefixo

    # Variável especial derivada (não lida do XML, calculada pelo xml_loader)
    'TIPO_OPERACAO',

    # Operadores de comparação
    'EQ',   # ==
    'NEQ',  # !=
    'GTE',  # >=
    'LTE',  # <=
    'GT',   # >
    'LT',   # <

    # Literais de valor
    'STRING',     # texto entre aspas duplas: "SP", "6102"
    'PERCENTUAL', # número seguido de %: 12%, 1.65%
    'NUMERO',     # número inteiro ou decimal: 100000, 12.5

    # Identificador de variável de domínio fiscal
    'VARIAVEL_DOM',  # qualquer token NOTA_* ou ITEM_* — ex: NOTA_UF_EMITENTE
)

# =============================================================================
# reserved — conjunto de palavras reservadas da DSL
#
# Usado dentro de t_WORD para distinguir uma palavra-chave (ex: REGRA) de
# uma variável de domínio (NOTA_UF_EMITENTE) ou de um identificador inválido.
# Mantido como set para busca O(1).
# =============================================================================
reserved = {
    'REGRA', 'ANALISAR', 'FILTRAR', 'ONDE', 'VALIDAR', 'QUE',
    'AO_FALHAR', 'ALERTA', 'REJEITAR', 'E', 'OU',
    'NOTA', 'ITEM', 'NFE', 'CTE',
    'INTERESTADUAL', 'INTRAESTADUAL', 'CONTEM', 'INICIA_COM',
    'TIPO_OPERACAO',
}

# =============================================================================
# Regras de tokens simples (expressão regular como string)
#
# O PLY usa o nome da variável (sem o prefixo t_) como tipo do token.
# Operadores de dois caracteres devem vir ANTES dos de um caractere para que
# o PLY não confunda ">=" com ">" seguido de "=".
# =============================================================================
t_EQ  = r'=='   # igual
t_NEQ = r'!='   # diferente
t_GTE = r'>='   # maior ou igual — deve preceder t_GT
t_LTE = r'<='   # menor ou igual — deve preceder t_LT
t_GT  = r'>'    # maior que
t_LT  = r'<'    # menor que


# =============================================================================
# Regras de tokens complexos (funções com docstring como regex)
#
# Funções têm prioridade sobre variáveis simples no PLY.
# A docstring de cada função É a expressão regular — o PLY a extrai
# diretamente em tempo de compilação do lexer.
# =============================================================================

def t_STRING(t):
    r'"[^"]*"'
    # Remove as aspas delimitadoras: '"SP"' → 'SP'
    # [^"]* captura qualquer caractere exceto aspas, logo strings não podem
    # conter aspas internas (limitação aceita pela especificação da DSL).
    t.value = t.value[1:-1]
    return t


def t_PERCENTUAL(t):
    r'[0-9]+(\.[0-9]+)?%'
    # Converte "12%" → 12.0 e "1.65%" → 1.65 (armazena só o número, sem o %)
    # O value_kind='pct' é marcado mais tarde no parser ao montar o ExprNode.
    t.value = float(t.value[:-1])
    return t


def t_NUMERO(t):
    r'[0-9]+(\.[0-9]+)?'
    # Converte "100000" → 100000.0 e "12.5" → 12.5
    # Deve vir DEPOIS de t_PERCENTUAL no arquivo para que "12%" não seja
    # tokenizado como NUMERO("12") seguido de um caractere ilegal "%".
    # O PLY garante isso pela ordem de definição das funções.
    t.value = float(t.value)
    return t


def t_WORD(t):
    r'[A-Z][A-Z0-9_]*'
    # Regra unificada para todos os identificadores em maiúsculas.
    # A ordem de verificação é crítica:
    #   1. Prefixo NOTA_ ou ITEM_ → VARIAVEL_DOM (ex: NOTA_UF_EMITENTE)
    #   2. Palavra reservada       → o próprio nome vira o tipo (ex: REGRA → tipo 'REGRA')
    #   3. Qualquer outro caso     → erro léxico (identificador desconhecido)
    #
    # NOTA e ITEM sozinhos (sem underscore) passam pelo passo 2 e viram
    # keywords, não VARIAVEL_DOM — a verificação de prefixo vem primeiro
    # exatamente para capturar NOTA_* antes de comparar com 'NOTA'.
    if t.value.startswith('NOTA_') or t.value.startswith('ITEM_'):
        t.type = 'VARIAVEL_DOM'
    elif t.value in reserved:
        t.type = t.value   # o tipo do token é o próprio texto (ex: 'REGRA')
    else:
        raise LexError(f"Identificador desconhecido: '{t.value}'", t.lineno)
    return t


# =============================================================================
# Caracteres e sequências ignoradas
# =============================================================================

# Espaços e tabulações são descartados entre tokens (não geram token algum)
t_ignore = ' \t'


def t_COMMENT(t):
    r'\#.*'
    # Linhas de comentário começam com # e vão até o fim da linha.
    # A função não retorna nada → o PLY descarta o token completamente.
    pass


def t_newline(t):
    r'\n+'
    # Quebras de linha não geram token, mas o contador de linhas precisa ser
    # atualizado para que erros subsequentes reportem a linha correta.
    # len(t.value) conta múltiplas quebras consecutivas de uma vez.
    t.lexer.lineno += len(t.value)


def t_error(t):
    # Chamado pelo PLY quando nenhuma regra casa com o caractere atual.
    # t.value[0] é o caractere problemático; após o erro o PLY avança
    # um caractere e tenta continuar (mas aqui lançamos exceção imediatamente).
    raise LexError(f"Caractere ilegal '{t.value[0]}'", t.lineno)


# =============================================================================
# Factory
# =============================================================================

def build_lexer():
    """Constrói e retorna uma instância pronta do lexer PLY."""
    return lex.lex()
