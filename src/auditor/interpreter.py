# =============================================================================
# interpreter.py — Execução das Regras sobre os Documentos XML
#
# Última fase de processamento. O interpretador recebe:
#   - A AST validada (ProgramNode) vinda do parser + analisador semântico
#   - A lista de documentos carregados (dicts) vinda do xml_loader
#
# Para cada par (documento, regra), aplica os filtros e depois a validação.
# Cada falha de validação gera um AuditResult que compõe o relatório final.
#
# Fluxo por documento × regra:
#   1. Avaliar filtros de NOTA → se algum falhar, pular o documento inteiro
#   2a. Se validação é de NOTA → avaliar condição; falha → 1 AuditResult
#   2b. Se validação é de ITEM → para cada item:
#         - Avaliar filtros de ITEM → se falhar, pular o item
#         - Avaliar condição de validação; falha → 1 AuditResult por item
# =============================================================================

from dataclasses import dataclass
from typing import Optional
from .ast_nodes import ProgramNode, RuleNode, BinaryOpNode, ExprNode


# -----------------------------------------------------------------------------
# AuditResult — registro de uma violação de regra detectada
# -----------------------------------------------------------------------------
@dataclass
class AuditResult:
    rule_name:   str           # nome da regra que gerou a violação
    xml_file:    str           # nome do arquivo XML auditado
    nota_numero: str           # número da nota fiscal (NOTA_NUMERO do XML)
    item_index:  Optional[int] # índice do item (1-based) ou None se for violação de NOTA
    result:      str           # "ALERTA" ou "REJEITAR" conforme a cláusula AO_FALHAR
    message:     str           # mensagem de erro da cláusula AO_FALHAR


# -----------------------------------------------------------------------------
# Interpreter — motor de avaliação das regras
# -----------------------------------------------------------------------------
class Interpreter:

    def run(self, program: ProgramNode, documents: list) -> list:
        """
        Ponto de entrada público. Itera sobre todos os documentos e todas as
        regras, acumulando os resultados de violação em uma lista plana.
        """
        results = []
        for doc in documents:
            for rule in program.rules:
                # _apply_rule retorna lista vazia se não houver violação
                results.extend(self._apply_rule(rule, doc))
        return results

    def _apply_rule(self, rule: RuleNode, doc: dict) -> list:
        """
        Aplica uma regra a um documento e retorna a lista de violações
        encontradas (pode ser vazia se a nota não passar nos filtros ou
        se a validação for satisfeita).
        """
        # Separa filtros por contexto — são avaliados em momentos diferentes
        nota_filters = [f for f in rule.filters if f.context == 'NOTA']
        item_filters  = [f for f in rule.filters if f.context == 'ITEM']

        # Contexto de nota: todos os campos NOTA_* mais TIPO_OPERACAO derivado
        nota_ctx = {**doc['nota'], 'TIPO_OPERACAO': doc['tipo_operacao']}

        # ── Etapa 1: filtros de NOTA ──────────────────────────────────────
        # Se qualquer filtro de nota falhar, toda a nota é ignorada.
        # Não há violação nesse caso — a regra simplesmente não se aplica.
        for f in nota_filters:
            if not self._eval(f.condition, nota_ctx):
                return []  # nota excluída pelo filtro → sem violações

        results = []
        val = rule.validation

        if val.context == 'NOTA':
            # ── Etapa 2a: validação no nível de nota ─────────────────────
            # Avalia a condição uma única vez sobre o contexto da nota.
            # Se for falsa → gera um AuditResult sem item_index.
            if not self._eval(val.condition, nota_ctx):
                results.append(AuditResult(
                    rule_name=rule.name,
                    xml_file=doc['arquivo'],
                    nota_numero=str(doc['nota'].get('NOTA_NUMERO') or '?'),
                    item_index=None,  # violação é da nota, não de item específico
                    result=rule.on_fail.action_type,
                    message=rule.on_fail.message,
                ))
        else:
            # ── Etapa 2b: validação no nível de item ─────────────────────
            # Itera sobre cada produto (<det>) do documento.
            for idx, item in enumerate(doc['itens']):
                # Contexto de item: campos ITEM_* + TIPO_OPERACAO da nota
                item_ctx = {**item, 'TIPO_OPERACAO': doc['tipo_operacao']}

                # Aplica filtros de ITEM: se o item não passar, ele é ignorado
                # (não conta como violação — apenas não está no escopo da regra)
                if not all(self._eval(f.condition, item_ctx) for f in item_filters):
                    continue

                # Avalia a condição de validação para este item específico
                if not self._eval(val.condition, item_ctx):
                    results.append(AuditResult(
                        rule_name=rule.name,
                        xml_file=doc['arquivo'],
                        nota_numero=str(doc['nota'].get('NOTA_NUMERO') or '?'),
                        item_index=idx + 1,  # 1-based para exibição ao usuário
                        result=rule.on_fail.action_type,
                        message=rule.on_fail.message,
                    ))
        return results

    def _eval(self, node, ctx: dict) -> bool:
        """
        Avalia recursivamente um nó da árvore de condições contra um contexto.
        O contexto é um dict {nome_variavel: valor} com os dados do documento.
        """
        if isinstance(node, BinaryOpNode):
            if node.op == 'E':
                # Curto-circuito: se o lado esquerdo for falso, não avalia o direito
                return self._eval(node.left, ctx) and self._eval(node.right, ctx)
            # OU também usa curto-circuito do Python: se esquerdo for verdadeiro,
            # não avalia o direito
            return self._eval(node.left, ctx) or self._eval(node.right, ctx)
        if isinstance(node, ExprNode):
            return self._eval_expr(node, ctx)
        return False

    def _eval_expr(self, expr: ExprNode, ctx: dict) -> bool:
        """
        Avalia uma expressão atômica (folha da árvore) contra o contexto.
        Retorna False se a variável não estiver presente no contexto (campo
        ausente no XML) — tratamento conservador que não gera falsos positivos.
        """
        val = ctx.get(expr.variable)  # valor atual da variável no documento
        rhs = expr.value              # valor literal da expressão na regra
        op  = expr.operator

        # Campo ausente no XML → condição falsa (não gera violação em validações,
        # e não passa filtros — comportamento conservador e seguro)
        if val is None:
            return False

        # Comparações de igualdade e diferença funcionam para str e float
        if op == '==':  return val == rhs
        if op == '!=':  return val != rhs

        # Comparações de ordem exigem conversão explícita para float.
        # A análise semântica já garante que apenas variáveis numéricas
        # chegam até aqui com esses operadores.
        if op == '>':   return float(val) >  float(rhs)
        if op == '<':   return float(val) <  float(rhs)
        if op == '>=':  return float(val) >= float(rhs)
        if op == '<=':  return float(val) <= float(rhs)

        # CONTEM: verifica se rhs é substring de val
        # Exemplo: ITEM_DESCRICAO CONTEM "notebook" → "notebook" in "Notebook Pro"
        if op == 'CONTEM':     return str(rhs) in str(val)

        # INICIA_COM: verifica prefixo de string
        # Exemplo: ITEM_CFOP INICIA_COM "6" → "6102".startswith("6")
        if op == 'INICIA_COM': return str(val).startswith(str(rhs))

        return False  # operador desconhecido não deve ocorrer após análise semântica
