# =============================================================================
# parser.py — Análise Sintática com PLY yacc (LALR(1))
#
# Segunda fase do pipeline. O parser recebe a sequência de tokens do lexer e
# constrói a Árvore Sintática Abstrata (AST) descrita em ast_nodes.py.
#
# Como o PLY yacc funciona:
#   - Cada função p_NOME define uma produção da gramática BNF.
#   - A docstring da função É a produção (ex: "programa : regra_list").
#   - p[0] recebe o valor semântico do lado esquerdo (não-terminal sendo reduzido).
#   - p[1], p[2], ... são os valores dos símbolos do lado direito.
#   - O PLY gera automaticamente tabelas LALR(1) em parsetab.py (salvo em /tmp).
#
# Precedência de operadores lógicos:
#   Em vez de declarar %prec, a gramática usa duas regras intermediárias:
#     condicao      → lida com OU (menor precedência)
#     condicao_and  → lida com E  (maior precedência)
#   Isso torna a gramática explicitamente não-ambígua, sem conflitos shift/reduce.
# =============================================================================

import ply.yacc as yacc
from .lexer import tokens, build_lexer, LexError  # noqa: F401  (tokens e LexError re-exportados)
from .ast_nodes import (
    ProgramNode, RuleNode, FilterNode, ValidationNode,
    BinaryOpNode, ExprNode, ActionNode,
)


# -----------------------------------------------------------------------------
# ParseError — exceção de erro sintático com número de linha
# -----------------------------------------------------------------------------
class ParseError(Exception):
    def __init__(self, msg, line):
        super().__init__(f"[Erro Sintático] Linha {line}: {msg}")


# =============================================================================
# Regras de produção — nível de programa
# =============================================================================

def p_programa(p):
    """programa : regra_list"""
    # Raiz da AST: um programa é simplesmente uma lista de regras
    p[0] = ProgramNode(rules=p[1])


def p_regra_list_multi(p):
    """regra_list : regra_list regra"""
    # Acumula regras iterativamente (regra_list cresce para a direita)
    p[0] = p[1] + [p[2]]


def p_regra_list_single(p):
    """regra_list : regra"""
    # Base da recursão: lista com exatamente uma regra
    p[0] = [p[1]]


# =============================================================================
# Regras de produção — bloco REGRA
# =============================================================================

def p_regra(p):
    """regra : REGRA STRING ANALISAR doc_tipo corpo_regra"""
    # p[2] = nome da regra (STRING)
    # p[4] = tipo de documento ("NFE" ou "CTE")
    # p[5] = tupla (filtros, validacao, acao) montada por p_corpo_regra
    filters, validation, on_fail = p[5]
    p[0] = RuleNode(name=p[2], doc_type=p[4],
                    filters=filters, validation=validation, on_fail=on_fail)


def p_doc_tipo(p):
    """doc_tipo : NFE
               | CTE"""
    # Passa o texto do token diretamente ("NFE" ou "CTE")
    p[0] = p[1]


def p_corpo_regra(p):
    """corpo_regra : filtro_list validacao acao_falha"""
    # Agrega as três partes obrigatórias do corpo em uma tupla,
    # desempacotada em p_regra logo acima
    p[0] = (p[1], p[2], p[3])


# =============================================================================
# Regras de produção — cláusula FILTRAR
# =============================================================================

def p_filtro_list_multi(p):
    """filtro_list : filtro_list filtro"""
    # Uma regra pode ter zero ou mais cláusulas FILTRAR; acumula em lista
    p[0] = p[1] + [p[2]]


def p_filtro_list_empty(p):
    """filtro_list :"""
    # Produção vazia (ε): FILTRAR é opcional — lista começa vazia
    p[0] = []


def p_filtro(p):
    """filtro : FILTRAR contexto ONDE condicao"""
    # p[2] = contexto ("NOTA" ou "ITEM")
    # p[4] = árvore de condição do filtro
    p[0] = FilterNode(context=p[2], condition=p[4])


# =============================================================================
# Regras de produção — cláusula VALIDAR
# =============================================================================

def p_validacao(p):
    """validacao : VALIDAR contexto QUE condicao"""
    # p[2] = contexto ("NOTA" ou "ITEM")
    # p[4] = árvore de condição que DEVE ser verdadeira para a regra passar
    p[0] = ValidationNode(context=p[2], condition=p[4])


# =============================================================================
# Regras de produção — cláusula AO_FALHAR
# =============================================================================

def p_acao_falha(p):
    """acao_falha : AO_FALHAR acao"""
    # Apenas desempacota a ação — o nó ActionNode já foi criado em p_acao_*
    p[0] = p[2]


def p_acao_alerta(p):
    """acao : ALERTA STRING"""
    # Ação de aviso: não bloqueia a nota, apenas registra a ocorrência
    p[0] = ActionNode(action_type='ALERTA', message=p[2])


def p_acao_rejeitar(p):
    """acao : REJEITAR STRING"""
    # Ação de rejeição: marca a nota como inválida no relatório
    p[0] = ActionNode(action_type='REJEITAR', message=p[2])


# =============================================================================
# Regras de produção — contexto (NOTA ou ITEM)
# =============================================================================

def p_contexto(p):
    """contexto : NOTA
               | ITEM"""
    # Define em qual nível a cláusula opera:
    #   NOTA → aplica sobre a nota fiscal como um todo
    #   ITEM → aplica sobre cada produto individualmente
    p[0] = p[1]


# =============================================================================
# Regras de produção — condições booleanas (árvore de precedência)
#
# A gramática codifica precedência estruturalmente:
#   condicao      → trata OU (menor precedência, avaliado por último)
#   condicao_and  → trata E  (maior precedência, avaliado primeiro)
#
# Exemplo de derivação para "A E B OU C":
#   condicao → condicao OU condicao_and
#            → condicao_and OU condicao_and
#            → (condicao_and E expr) OU condicao_and
#            → ((expr) E (expr)) OU (expr)
# O resultado é: BinaryOpNode(BinaryOpNode(A,'E',B), 'OU', C)
# =============================================================================

def p_condicao_ou(p):
    """condicao : condicao OU condicao_and"""
    # Cria nó OU com a condicao acumulada à esquerda e a próxima condicao_and à direita
    p[0] = BinaryOpNode(left=p[1], op='OU', right=p[3])


def p_condicao_and_passthrough(p):
    """condicao : condicao_and"""
    # Quando não há OU, passa o condicao_and diretamente para cima sem envolver
    p[0] = p[1]


def p_condicao_and(p):
    """condicao_and : condicao_and E expr"""
    # Cria nó E com a condicao_and acumulada à esquerda e a próxima expr à direita
    p[0] = BinaryOpNode(left=p[1], op='E', right=p[3])


def p_condicao_and_single(p):
    """condicao_and : expr"""
    # Base da recursão: uma única expressão sem operadores lógicos
    p[0] = p[1]


# =============================================================================
# Regras de produção — expressões atômicas (folhas da árvore)
# =============================================================================

def p_expr_comparacao(p):
    """expr : VARIAVEL_DOM operador valor"""
    # Expressão de comparação genérica: NOTA_VALOR_TOTAL > 100000
    # p[3] é uma tupla (value, kind) devolvida pelas regras p_valor_*
    value, kind = p[3]
    p[0] = ExprNode(variable=p[1], operator=p[2], value=value, value_kind=kind)


def p_expr_contem(p):
    """expr : VARIAVEL_DOM CONTEM STRING"""
    # Verifica se o valor da variável contém a substring: ITEM_DESCRICAO CONTEM "notebook"
    p[0] = ExprNode(variable=p[1], operator='CONTEM', value=p[3], value_kind='str')


def p_expr_inicia_com(p):
    """expr : VARIAVEL_DOM INICIA_COM STRING"""
    # Verifica se o valor da variável começa com o prefixo: ITEM_CFOP INICIA_COM "6"
    p[0] = ExprNode(variable=p[1], operator='INICIA_COM', value=p[3], value_kind='str')


def p_expr_tipo_op_inter(p):
    """expr : TIPO_OPERACAO EQ INTERESTADUAL"""
    # Caso especial: TIPO_OPERACAO é variável derivada (não lida do XML),
    # calculada pelo xml_loader comparando UF emitente com UF destinatário.
    # INTERESTADUAL → UFs diferentes (ex: SP → RJ)
    p[0] = ExprNode(variable='TIPO_OPERACAO', operator='==',
                    value='INTERESTADUAL', value_kind='str')


def p_expr_tipo_op_intra(p):
    """expr : TIPO_OPERACAO EQ INTRAESTADUAL"""
    # INTRAESTADUAL → UFs iguais (ex: SP → SP)
    p[0] = ExprNode(variable='TIPO_OPERACAO', operator='==',
                    value='INTRAESTADUAL', value_kind='str')


# =============================================================================
# Regras de produção — operadores e valores literais
# =============================================================================

def p_operador(p):
    """operador : EQ
               | NEQ
               | GT
               | LT
               | GTE
               | LTE"""
    # Passa o texto do token diretamente ("==", "!=", ">", "<", ">=", "<=")
    p[0] = p[1]


def p_valor_string(p):
    """valor : STRING"""
    # Devolve tupla (valor, kind) para que p_expr_comparacao preencha value_kind no ExprNode
    p[0] = (p[1], 'str')


def p_valor_percentual(p):
    """valor : PERCENTUAL"""
    # Valor já convertido para float pelo lexer (ex: 12.0); kind='pct' sinaliza
    # para a análise semântica que apenas variáveis de alíquota aceitam este valor
    p[0] = (p[1], 'pct')


def p_valor_numero(p):
    """valor : NUMERO"""
    # Número genérico (monetário, quantidade etc.)
    p[0] = (p[1], 'num')


# =============================================================================
# Tratamento de erro sintático
# =============================================================================

def p_error(p):
    # Chamado pelo PLY quando encontra um token que não encaixa em nenhuma produção.
    # p=None significa fim de arquivo prematuro (regra incompleta).
    if p:
        raise ParseError(f"Token inesperado '{p.value}' ({p.type})", p.lineno)
    else:
        raise ParseError("Fim de arquivo inesperado — regra incompleta?", -1)


# =============================================================================
# Factories públicas
# =============================================================================

def build_parser(outputdir='/tmp'):
    """
    Constrói e retorna o par (parser, lexer) prontos para uso.
    outputdir='/tmp' evita que o PLY grave parsetab.py no diretório de trabalho.
    debug=False suprime o arquivo parser.out com o log de construção das tabelas.
    """
    lexer = build_lexer()
    parser = yacc.yacc(outputdir=outputdir, debug=False)
    return parser, lexer


def parse(source: str) -> ProgramNode:
    """
    Ponto de entrada público: recebe o código-fonte como string e devolve
    a AST completa (ProgramNode) pronta para análise semântica.
    Lança LexError ou ParseError em caso de erro.
    """
    parser, lexer = build_parser()
    return parser.parse(source, lexer=lexer)
