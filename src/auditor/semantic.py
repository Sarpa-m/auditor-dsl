# =============================================================================
# semantic.py — Análise Semântica (visitor sobre a AST)
#
# Terceira fase do pipeline. Recebe a AST já construída pelo parser e verifica
# regras que a gramática sozinha não consegue expressar:
#
#   1. Nomes de regras únicos (sem duplicatas no mesmo arquivo)
#   2. Variáveis de domínio existentes na tabela (sem typos como NOTA_ESTADO)
#   3. Coerência de contexto (variável ITEM_* não pode aparecer em contexto NOTA)
#   4. Compatibilidade de tipo de operador (> < >= <= apenas para variáveis numéricas)
#   5. Valor percentual (12%) apenas para variáveis de alíquota (tipo 'pct')
#
# O padrão Visitor é implementado de forma simplificada: SemanticAnalyzer percorre
# a árvore recursivamente com métodos _check_*, descendo de ProgramNode até ExprNode.
# =============================================================================

from .ast_nodes import ProgramNode, RuleNode, BinaryOpNode, ExprNode
from .domain_vars import ALL_VARS, NOTA_VARS, ITEM_VARS, NUMERIC_TYPES, PCT_VARS


# -----------------------------------------------------------------------------
# SemanticError — exceção de erro semântico com identificação da regra afetada
# -----------------------------------------------------------------------------
class SemanticError(Exception):
    def __init__(self, msg, rule_name=''):
        # Inclui o nome da regra na mensagem para facilitar a localização do erro.
        # rule_name vazio ocorre apenas em validações globais (ex: nome duplicado).
        prefix = f"[Erro Semântico] Regra '{rule_name}': " if rule_name else "[Erro Semântico] "
        super().__init__(prefix + msg)


# -----------------------------------------------------------------------------
# SemanticAnalyzer — percorre e valida toda a AST
# -----------------------------------------------------------------------------
class SemanticAnalyzer:

    def check(self, program: ProgramNode):
        """
        Ponto de entrada: recebe o ProgramNode raiz e valida todas as regras.
        Lança SemanticError na primeira violação encontrada.
        """
        seen_names: set = set()
        for rule in program.rules:
            # Verifica nome duplicado antes de analisar o conteúdo da regra.
            # Dois blocos REGRA com o mesmo nome causariam ambiguidade nos relatórios.
            if rule.name in seen_names:
                raise SemanticError(f"Nome de regra duplicado: '{rule.name}'")
            seen_names.add(rule.name)
            self._check_rule(rule)

    def _check_rule(self, rule: RuleNode):
        """Percorre todos os filtros e a validação de uma regra."""
        # Valida cada cláusula FILTRAR com seu próprio contexto (NOTA ou ITEM)
        for f in rule.filters:
            self._check_condition(f.context, f.condition, rule.name)

        # Valida a cláusula VALIDAR com seu contexto
        self._check_condition(rule.validation.context,
                              rule.validation.condition, rule.name)

    def _check_condition(self, context: str, node, rule_name: str):
        """
        Desce recursivamente pela árvore de condições.
        BinaryOpNode (E/OU) → visita os dois filhos.
        ExprNode (folha)    → valida a expressão atômica.
        """
        if isinstance(node, BinaryOpNode):
            # Operador binário: propaga o mesmo contexto para ambos os lados
            self._check_condition(context, node.left, rule_name)
            self._check_condition(context, node.right, rule_name)
        elif isinstance(node, ExprNode):
            self._check_expr(context, node, rule_name)

    def _check_expr(self, context: str, expr: ExprNode, rule_name: str):
        """
        Valida uma expressão atômica contra as regras semânticas.
        Recebe o contexto da cláusula que contém a expressão.
        """
        var = expr.variable

        # TIPO_OPERACAO é uma variável especial calculada pelo xml_loader
        # (não está em NOTA_VARS nem ITEM_VARS) e é sempre semanticamente válida.
        if var == 'TIPO_OPERACAO':
            return

        # ── Regra 1: a variável deve existir na tabela de domínio ─────────
        # Captura typos como NOTA_ESTADO (não existe) vs NOTA_UF_EMITENTE (existe).
        if var not in ALL_VARS:
            raise SemanticError(f"Variável desconhecida: '{var}'", rule_name)

        # ── Regra 2: coerência de contexto ────────────────────────────────
        # Uma variável ITEM_* (nível de produto) não faz sentido em uma
        # cláusula de contexto NOTA (que opera sobre a nota como um todo),
        # pois uma nota tem múltiplos itens — qual deles usar?
        if context == 'NOTA' and var not in NOTA_VARS:
            raise SemanticError(
                f"Variável '{var}' (ITEM_*) usada em contexto NOTA", rule_name)

        # O inverso: uma variável NOTA_* em contexto ITEM também é incoerente.
        if context == 'ITEM' and var not in ITEM_VARS:
            raise SemanticError(
                f"Variável '{var}' (NOTA_*) usada em contexto ITEM", rule_name)

        # ── Regra 3: operadores relacionais exigem variável numérica ──────
        # Operadores >, <, >=, <= comparam magnitudes — não fazem sentido para
        # strings como NOTA_UF_EMITENTE ou ITEM_DESCRICAO.
        _, var_type = ALL_VARS[var]
        if expr.operator in ('>', '<', '>=', '<=') and var_type not in NUMERIC_TYPES:
            raise SemanticError(
                f"Operador '{expr.operator}' inválido para variável string '{var}'",
                rule_name)

        # ── Regra 4: valor percentual só para variáveis de alíquota ───────
        # "12%" tem semântica fiscal precisa: representa uma alíquota, não um
        # número genérico. Usar "12%" para comparar com NOTA_VALOR_TOTAL seria
        # um erro de modelagem — o auditor provavelmente quis escrever "12" (sem %).
        if expr.value_kind == 'pct' and var not in PCT_VARS:
            raise SemanticError(
                f"Valor percentual usado em variável não-percentual '{var}'",
                rule_name)
