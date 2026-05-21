# =============================================================================
# __main__.py — Ponto de Entrada da CLI (python -m auditor)
#
# Orquestra todas as fases do pipeline na ordem correta:
#   1. argparse  — processa os argumentos da linha de comando
#   2. parse()   — análise léxica + sintática → AST
#   3. check()   — análise semântica → valida a AST
#   4. load_all() — carrega os XMLs → lista de documentos
#   5. run()     — interpreta as regras sobre os documentos → violações
#   6. output()  — formata e imprime o relatório
#
# Erros em qualquer fase são capturados, exibidos em vermelho no stderr
# e encerram o processo com código de saída 1.
# =============================================================================

import argparse
import sys

from .parser import parse
from .semantic import SemanticAnalyzer, SemanticError
from .xml_loader import load_all
from .interpreter import Interpreter
from .reporter import Reporter, print_error


def main():
    # ── Configuração dos argumentos da linha de comando ───────────────────
    ap = argparse.ArgumentParser(
        prog='auditor',
        description='Interpretador Auditor-DSL para auditoria fiscal NF-e/CT-e',
    )

    # Argumento posicional obrigatório: arquivo .auditor com as regras
    ap.add_argument('regras', help='Arquivo .auditor com as regras')

    # Argumento posicional opcional: pasta ou arquivo XML
    # É opcional porque --verificar não precisa de XMLs
    ap.add_argument('xmls', nargs='?', help='Pasta ou arquivo XML (NF-e/CT-e)')

    # Flag de formato de saída: txt (colorido no terminal) ou json (para integração)
    ap.add_argument('--formato', choices=['txt', 'json'], default='txt',
                    help='Formato da saída (padrão: txt)')

    # Flag de validação apenas: executa léxico + sintático + semântico sem
    # processar XMLs. Útil para checar se o arquivo .auditor está correto.
    ap.add_argument('--verificar', action='store_true',
                    help='Só valida a sintaxe/semântica, sem processar XMLs')

    # Flag de depuração: imprime a AST completa antes de executar
    ap.add_argument('--verbose', action='store_true',
                    help='Mostra dump da AST')

    args = ap.parse_args()

    # ── Fase 0: leitura do arquivo .auditor ───────────────────────────────
    try:
        source = open(args.regras, encoding='utf-8').read()
    except FileNotFoundError:
        print_error(f"Arquivo não encontrado: {args.regras}")
        sys.exit(1)

    # ── Fase 1: análise léxica + sintática ───────────────────────────────
    # parse() pode lançar LexError ou ParseError com localização de linha
    try:
        ast = parse(source)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

    # ── Fase 2: análise semântica ─────────────────────────────────────────
    # check() percorre a AST e lança SemanticError se encontrar inconsistências
    try:
        SemanticAnalyzer().check(ast)
    except SemanticError as e:
        print_error(str(e))
        sys.exit(1)

    # Modo verbose: exibe a representação completa da AST (útil para depuração)
    if args.verbose:
        print(ast)

    # Modo --verificar: encerra aqui com sucesso após validar sintaxe/semântica
    if args.verificar:
        print("Sintaxe e semântica OK.")
        sys.exit(0)

    # ── Verificação de argumento XML obrigatório fora do modo --verificar ─
    if not args.xmls:
        print_error("Informe a pasta ou arquivo XML.")
        sys.exit(1)

    # ── Fase 3: carregamento dos XMLs ─────────────────────────────────────
    # load_all() aceita caminho de arquivo único ou diretório com *.xml
    try:
        docs = load_all(args.xmls)
    except Exception as e:
        print_error(f"Erro ao carregar XML: {e}")
        sys.exit(1)

    # ── Fase 4: interpretação (aplicação das regras) ──────────────────────
    # Retorna lista de AuditResult — pode ser vazia se nenhuma regra falhar
    results = Interpreter().run(ast, docs)

    # ── Fase 5: geração do relatório ──────────────────────────────────────
    Reporter(results).output(args.formato)


# Permite execução direta do arquivo além de 'python -m auditor'
if __name__ == '__main__':
    main()
