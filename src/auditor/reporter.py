# =============================================================================
# reporter.py — Geração do Relatório Final de Auditoria
#
# Recebe a lista de AuditResult do interpretador e a apresenta ao usuário
# em dois formatos possíveis:
#
#   txt  (padrão) — saída colorida no terminal, uma linha por violação,
#                   seguida de um resumo com contagem de alertas e rejeições.
#
#   json          — array JSON com todos os campos de cada violação,
#                   útil para integração com outras ferramentas ou scripts.
#
# A colorização usa o colorama, que é cross-platform (funciona no Windows
# via emulação ANSI além de Linux/macOS).
# =============================================================================

import json
import sys
from colorama import Fore, Style, init as colorama_init

# autoreset=True faz o colorama resetar as cores automaticamente após cada print,
# dispensando Style.RESET_ALL explícito ao final de cada string colorida.
colorama_init(autoreset=True)

# Rótulos coloridos pré-formatados para cada tipo de resultado.
# Usando Style.RESET_ALL explicitamente aqui porque os rótulos são inseridos
# dentro de f-strings maiores, onde o autoreset não atua na posição certa.
_ICONS = {
    'ALERTA':   Fore.YELLOW + 'ALERTA'   + Style.RESET_ALL,
    'REJEITAR': Fore.RED    + 'REJEITAR' + Style.RESET_ALL,
    'OK':       Fore.GREEN  + 'OK'       + Style.RESET_ALL,
}


class Reporter:

    def __init__(self, results: list):
        # Armazena a lista de AuditResult para ser consumida pelo método output()
        self.results = results

    def output(self, formato: str = 'txt'):
        """Despacha para o método de saída correspondente ao formato solicitado."""
        if formato == 'json':
            self._output_json()
        else:
            self._output_txt()

    def _output_txt(self):
        """
        Exibe o relatório colorido no terminal.
        Cada violação ocupa duas linhas: identificação e mensagem.
        Ao final, imprime um resumo com totais de alertas e rejeições.
        """
        if not self.results:
            # Nenhuma violação → mensagem positiva em verde
            print(Fore.GREEN + 'Nenhuma violação encontrada.' + Style.RESET_ALL)
            return

        for r in self.results:
            # Obtém o rótulo colorido; fallback para o texto bruto se tipo desconhecido
            icon = _ICONS.get(r.result, r.result)

            # item_index=None → violação de nota inteira; caso contrário, item específico
            local = f'Item {r.item_index}' if r.item_index is not None else 'Nota'

            print(
                f"[{icon}] {r.xml_file} | NF {r.nota_numero} | {local} | "
                f"Regra: {r.rule_name}\n"
                f"         {r.message}"
            )

        # Resumo quantitativo ao final do relatório
        alertas   = sum(1 for r in self.results if r.result == 'ALERTA')
        rejeicoes = sum(1 for r in self.results if r.result == 'REJEITAR')
        print(
            f"\n{Fore.CYAN}Resumo:{Style.RESET_ALL} "
            f"{alertas} alerta(s), {rejeicoes} rejeição(ões)."
        )

    def _output_json(self):
        """
        Serializa os resultados como JSON e imprime no stdout.
        ensure_ascii=False preserva caracteres especiais (acentos, ç etc.)
        que são comuns nas mensagens fiscais em português.
        """
        data = [
            {
                'regra':       r.rule_name,
                'arquivo':     r.xml_file,
                'nota_numero': r.nota_numero,
                'item':        r.item_index,   # null no JSON quando violação é de nota
                'resultado':   r.result,
                'mensagem':    r.message,
            }
            for r in self.results
        ]
        print(json.dumps(data, ensure_ascii=False, indent=2))


def print_error(msg: str):
    """
    Exibe uma mensagem de erro em vermelho no stderr.
    Usado pelo __main__.py para reportar erros de compilação e execução.
    """
    print(Fore.RED + msg + Style.RESET_ALL, file=sys.stderr)
