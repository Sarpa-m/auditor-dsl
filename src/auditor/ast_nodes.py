# =============================================================================
# ast_nodes.py — Nós da Árvore Sintática Abstrata (AST)
#
# Este módulo define as estruturas de dados que representam um programa
# Auditor-DSL após a análise sintática. O parser constrói uma árvore de objetos
# desses tipos; as fases seguintes (semântica, interpretador) percorrem essa
# árvore para validar e executar as regras.
#
# Todos os nós são dataclasses imutáveis — facilitam inspeção e depuração.
# =============================================================================

from dataclasses import dataclass
from typing import List, Union


# -----------------------------------------------------------------------------
# ProgramNode — raiz da AST
#
# Um arquivo .auditor pode conter uma ou mais regras. O ProgramNode agrupa
# todas elas em uma lista ordenada. É o objeto devolvido pela função parse().
# -----------------------------------------------------------------------------
@dataclass
class ProgramNode:
    rules: List['RuleNode']  # lista de regras declaradas no arquivo, em ordem


# -----------------------------------------------------------------------------
# RuleNode — representa um bloco REGRA completo
#
# Exemplo de fonte que gera este nó:
#   REGRA "Validar Aliquota"
#   ANALISAR NFE
#   FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
#   VALIDAR ITEM QUE ITEM_ALIQUOTA_ICMS == 12%
#   AO_FALHAR ALERTA "Aliquota incorreta."
# -----------------------------------------------------------------------------
@dataclass
class RuleNode:
    name:       str                  # nome da regra (STRING após REGRA)
    doc_type:   str                  # tipo de documento: "NFE" ou "CTE"
    filters:    List['FilterNode']   # lista de cláusulas FILTRAR (pode ser vazia)
    validation: 'ValidationNode'     # cláusula VALIDAR obrigatória
    on_fail:    'ActionNode'         # cláusula AO_FALHAR obrigatória


# -----------------------------------------------------------------------------
# FilterNode — representa uma cláusula FILTRAR … ONDE …
#
# O filtro seleciona quais notas ou itens serão submetidos à validação.
# Se a condição do filtro for falsa, aquela nota/item é ignorada — nenhuma
# violação é gerada e nenhuma validação é executada para ela.
#
# Exemplos:
#   FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
#   FILTRAR ITEM ONDE ITEM_CFOP == "6102"
# -----------------------------------------------------------------------------
@dataclass
class FilterNode:
    context:   str              # "NOTA" (filtra a nota inteira) ou "ITEM" (filtra por produto)
    condition: 'ConditionNode'  # expressão booleana que deve ser verdadeira para passar


# -----------------------------------------------------------------------------
# ValidationNode — representa a cláusula VALIDAR … QUE …
#
# Define a condição que DEVE ser verdadeira. Se for falsa, a regra falha
# e o AO_FALHAR é acionado para aquela nota/item.
#
# Exemplos:
#   VALIDAR NOTA QUE NOTA_VALOR_TOTAL <= 100000
#   VALIDAR ITEM QUE ITEM_ALIQUOTA_ICMS == 12% OU ITEM_ALIQUOTA_ICMS == 7%
# -----------------------------------------------------------------------------
@dataclass
class ValidationNode:
    context:   str              # "NOTA" ou "ITEM" — define o nível de aplicação
    condition: 'ConditionNode'  # condição que deve ser verdadeira; falha → AO_FALHAR


# -----------------------------------------------------------------------------
# BinaryOpNode — nó interno da árvore de condições (operador binário)
#
# As condições formam uma árvore binária em vez de uma lista plana. Isso
# garante que a precedência entre E (AND) e OU (OR) seja resolvida
# estruturalmente pelo parser, sem lógica adicional no interpretador.
#
# Precedência: E tem prioridade maior que OU.
# Exemplo: A E B OU C → BinaryOpNode(BinaryOpNode(A, 'E', B), 'OU', C)
# -----------------------------------------------------------------------------
@dataclass
class BinaryOpNode:
    left:  Union['BinaryOpNode', 'ExprNode']  # operando esquerdo (sub-árvore ou folha)
    op:    str                                 # operador lógico: "E" ou "OU"
    right: Union['BinaryOpNode', 'ExprNode']  # operando direito (sub-árvore ou folha)


# Alias de tipo para anotar qualquer nó de condição (interno ou folha)
ConditionNode = Union[BinaryOpNode, 'ExprNode']


# -----------------------------------------------------------------------------
# ExprNode — nó folha da árvore de condições (expressão atômica)
#
# Representa uma comparação simples entre uma variável de domínio e um valor
# literal. É o único tipo de nó que o interpretador avalia diretamente contra
# os dados do XML.
#
# Exemplos de expressões que geram este nó:
#   NOTA_UF_EMITENTE == "SP"          → variable="NOTA_UF_EMITENTE", op="==",  value="SP",    kind="str"
#   NOTA_VALOR_TOTAL > 100000         → variable="NOTA_VALOR_TOTAL",  op=">",   value=100000.0, kind="num"
#   ITEM_ALIQUOTA_ICMS == 12%         → variable="ITEM_ALIQUOTA_ICMS",op="==",  value=12.0,    kind="pct"
#   ITEM_DESCRICAO CONTEM "notebook"  → variable="ITEM_DESCRICAO",    op="CONTEM", value="notebook", kind="str"
#   TIPO_OPERACAO == INTERESTADUAL    → variable="TIPO_OPERACAO",      op="==",  value="INTERESTADUAL", kind="str"
# -----------------------------------------------------------------------------
@dataclass
class ExprNode:
    variable:   str               # nome da variável DSL (ex: "NOTA_UF_EMITENTE", "TIPO_OPERACAO")
    operator:   str               # operador: "==", "!=", ">", "<", ">=", "<=", "CONTEM", "INICIA_COM"
    value:      Union[str, float] # valor literal do lado direito da comparação
    value_kind: str = 'str'       # classe do valor: 'str' (texto), 'num' (número), 'pct' (percentual)
                                  # usado pela análise semântica para validar compatibilidade de tipos


# -----------------------------------------------------------------------------
# ActionNode — representa a cláusula AO_FALHAR
#
# Define o que acontece quando a validação falha para uma nota ou item.
# ALERTA emite um aviso sem marcar a nota como rejeitada.
# REJEITAR marca a nota como inválida e emite a mensagem de erro.
#
# Exemplos:
#   AO_FALHAR ALERTA "Aliquota interestadual incorreta."
#   AO_FALHAR REJEITAR "Nota acima do limite exige revisao manual."
# -----------------------------------------------------------------------------
@dataclass
class ActionNode:
    action_type: str  # "ALERTA" ou "REJEITAR"
    message:     str  # mensagem exibida no relatório quando a regra falha
