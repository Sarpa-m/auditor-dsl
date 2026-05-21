// =============================================================================
// extension.ts — Ponto de entrada da extensão Auditor-DSL
//
// Esta função é chamada pelo VS Code quando um arquivo .auditor é aberto.
// Ela registra os três provedores de linguagem no contexto da extensão:
//   - CompletionProvider  → autocomplete contextual (Ctrl+Space)
//   - HoverProvider       → documentação ao passar o mouse sobre palavras
//   - DiagnosticsProvider → sublinhado de erros em tempo real
//
// Todos os registros são adicionados a context.subscriptions para que o VS Code
// os destrua automaticamente quando a extensão for desativada.
// =============================================================================

import * as vscode from 'vscode';
import { AuditorCompletionProvider } from './completionProvider';
import { AuditorHoverProvider }      from './hoverProvider';
import { AuditorDiagnosticsProvider } from './diagnosticsProvider';

export function activate(context: vscode.ExtensionContext) {
  // Seletor de linguagem: todos os provedores se aplicam apenas a arquivos .auditor
  const selector: vscode.DocumentSelector = { language: 'auditor' };

  // ── Autocomplete ────────────────────────────────────────────────────────
  // Triggers definem quando o autocomplete é acionado automaticamente sem
  // o usuário pressionar Ctrl+Space. Espaço e nova linha disparam sugestões
  // após cada token; '=' dispara após digitar o operador de comparação.
  context.subscriptions.push(
    vscode.languages.registerCompletionItemProvider(
      selector,
      new AuditorCompletionProvider(),
      ' ', '\n', '='   // caracteres que disparam o autocomplete automaticamente
    )
  );

  // ── Hover docs ──────────────────────────────────────────────────────────
  // Exibe documentação em markdown quando o usuário passa o mouse sobre
  // palavras-chave e variáveis de domínio fiscal.
  context.subscriptions.push(
    vscode.languages.registerHoverProvider(
      selector,
      new AuditorHoverProvider()
    )
  );

  // ── Diagnósticos em tempo real ──────────────────────────────────────────
  // O DiagnosticsProvider é acionado a cada mudança no documento e também
  // quando um arquivo .auditor é aberto, garantindo que erros existentes
  // sejam destacados imediatamente, sem precisar editar o arquivo primeiro.
  const diagnostics = new AuditorDiagnosticsProvider();

  context.subscriptions.push(
    // Revalida sempre que o conteúdo do documento mudar
    vscode.workspace.onDidChangeTextDocument(e => {
      if (e.document.languageId === 'auditor') {
        diagnostics.validate(e.document);
      }
    }),
    // Valida ao abrir o arquivo (cobre arquivos já existentes com erros)
    vscode.workspace.onDidOpenTextDocument(doc => {
      if (doc.languageId === 'auditor') {
        diagnostics.validate(doc);
      }
    })
  );
}

// Chamada pelo VS Code ao desativar a extensão.
// Não há recursos assíncronos para liberar — as subscriptions são limpas
// automaticamente pelo VS Code via context.subscriptions.
export function deactivate() {}
