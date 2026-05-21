// =============================================================================
// diagnosticsProvider.ts — Validação e sublinhado de erros em tempo real
//
// O DiagnosticsProvider analisa o texto do arquivo .auditor linha por linha e
// com regex globais, detectando erros conhecidos ANTES de qualquer execução.
// Os erros são exibidos como sublinhados vermelhos no editor e aparecem no
// painel "Problemas" do VS Code.
//
// Erros detectados:
//   1. Variável de domínio desconhecida (ex: NOTA_ESTADO, ITEM_PRECO)
//   2. Variável ITEM_* em contexto NOTA (e vice-versa)
//   3. Tipo de documento inválido após ANALISAR (ex: ANALISAR XML)
//   4. Operador inválido => (confusão comum com >=)
//   5. String sem fechamento de aspas na linha
// =============================================================================

import * as vscode from 'vscode';

// Conjuntos de variáveis válidas — espelham domain_vars.py do interpretador
const VALID_NOTA_VARS = new Set([
  'NOTA_UF_EMITENTE', 'NOTA_UF_DESTINATARIO', 'NOTA_CNPJ_EMITENTE',
  'NOTA_CNPJ_DESTINATARIO', 'NOTA_VALOR_TOTAL', 'NOTA_VALOR_ICMS',
  'NOTA_NUMERO', 'NOTA_SERIE', 'NOTA_DATA_EMISSAO', 'NOTA_NATUREZA',
  'NOTA_TIPO_OPERACAO', 'NOTA_PROTOCOLO',
]);

const VALID_ITEM_VARS = new Set([
  'ITEM_CFOP', 'ITEM_NCM', 'ITEM_DESCRICAO', 'ITEM_QUANTIDADE',
  'ITEM_VALOR_UNITARIO', 'ITEM_VALOR_TOTAL', 'ITEM_ALIQUOTA_ICMS',
  'ITEM_VALOR_ICMS', 'ITEM_BASE_CALCULO_ICMS', 'ITEM_CST_ICMS',
  'ITEM_ALIQUOTA_IPI', 'ITEM_ALIQUOTA_PIS', 'ITEM_ALIQUOTA_COFINS',
]);

export class AuditorDiagnosticsProvider {

  // Coleção nomeada: permite limpar apenas os diagnósticos desta extensão
  // sem afetar diagnósticos de outros provedores (ex: TypeScript, ESLint)
  private collection = vscode.languages.createDiagnosticCollection('auditor');

  validate(document: vscode.TextDocument) {
    const diagnostics: vscode.Diagnostic[] = [];
    const text  = document.getText();
    const lines = text.split('\n');

    // ── Verificação 1: variáveis de domínio desconhecidas ─────────────────
    // Percorre linha por linha procurando tokens NOTA_* ou ITEM_* que não
    // estejam na lista de variáveis válidas do interpretador.
    const varRegex = /\b((?:NOTA|ITEM)_[A-Z0-9_]+)\b/g;
    lines.forEach((line, lineIdx) => {
      // Remove comentário da linha antes de analisar (evita falsos positivos)
      const stripped = line.replace(/#.*$/, '');
      varRegex.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = varRegex.exec(stripped)) !== null) {
        const varName = match[1];
        if (!VALID_NOTA_VARS.has(varName) && !VALID_ITEM_VARS.has(varName)) {
          const start = new vscode.Position(lineIdx, match.index);
          const end   = new vscode.Position(lineIdx, match.index + varName.length);
          diagnostics.push(new vscode.Diagnostic(
            new vscode.Range(start, end),
            `Variável desconhecida: '${varName}'. Verifique a lista de variáveis NOTA_* e ITEM_* válidas.`,
            vscode.DiagnosticSeverity.Error
          ));
        }
      }
    });

    // ── Verificação 2: variável de contexto errado (ITEM em NOTA e vice-versa)
    // Procura cláusulas FILTRAR/VALIDAR e verifica se as variáveis usadas
    // correspondem ao contexto declarado (NOTA ou ITEM).
    //
    // Estratégia: encontra cada ocorrência de "FILTRAR/VALIDAR NOTA/ITEM ONDE/QUE"
    // e verifica se na sequência há variáveis do prefixo oposto.
    const clauseRegex = /\b(FILTRAR|VALIDAR)\s+(NOTA|ITEM)\s+(?:ONDE|QUE)(.*)/g;
    clauseRegex.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = clauseRegex.exec(text)) !== null) {
      const context     = match[2];   // "NOTA" ou "ITEM"
      const rest        = match[3];   // texto após ONDE/QUE
      const wrongPrefix = context === 'NOTA' ? 'ITEM_' : 'NOTA_';

      // Procura a primeira variável do prefixo errado na sequência da cláusula
      const wrongVarRegex = new RegExp(`\\b(${wrongPrefix}[A-Z0-9_]+)\\b`);
      const wrongMatch    = wrongVarRegex.exec(rest);
      if (wrongMatch) {
        // Determina a linha e coluna exatas para posicionar o sublinhado corretamente
        const lineIdx = document.positionAt(match.index).line;
        const line    = document.lineAt(lineIdx).text;
        const col     = line.indexOf(wrongMatch[1]);
        if (col >= 0) {
          const start = new vscode.Position(lineIdx, col);
          const end   = new vscode.Position(lineIdx, col + wrongMatch[1].length);
          diagnostics.push(new vscode.Diagnostic(
            new vscode.Range(start, end),
            `Variável '${wrongMatch[1]}' (${wrongPrefix.slice(0, -1)}_*) usada em contexto ${context}. ` +
            `Use uma variável ${context}_* neste contexto.`,
            vscode.DiagnosticSeverity.Error
          ));
        }
      }
    }

    // ── Verificação 3: tipo de documento inválido após ANALISAR ───────────
    // Aceita apenas NFE e CTE; qualquer outro token é sublinhado.
    const analisarRegex = /\bANALISAR\s+(\w+)/g;
    analisarRegex.lastIndex = 0;
    while ((match = analisarRegex.exec(text)) !== null) {
      const docType = match[1];
      if (docType !== 'NFE' && docType !== 'CTE') {
        const startOffset = match.index + match[0].indexOf(docType);
        const pos   = document.positionAt(startOffset);
        const start = pos;
        const end   = new vscode.Position(pos.line, pos.character + docType.length);
        diagnostics.push(new vscode.Diagnostic(
          new vscode.Range(start, end),
          `Tipo de documento inválido: '${docType}'. Use NFE (Nota Fiscal Eletrônica) ou CTE (Conhecimento de Transporte).`,
          vscode.DiagnosticSeverity.Error
        ));
      }
    }

    // ── Verificação 4: operador inválido => ──────────────────────────────
    // Confusão comum: o auditor escreve => (JavaScript) em vez de >= (matemático).
    const badOpRegex = /=>/g;
    badOpRegex.lastIndex = 0;
    while ((match = badOpRegex.exec(text)) !== null) {
      const pos   = document.positionAt(match.index);
      const start = pos;
      const end   = new vscode.Position(pos.line, pos.character + 2);
      diagnostics.push(new vscode.Diagnostic(
        new vscode.Range(start, end),
        `Operador inválido '=>'. Para "maior ou igual", use '>=' (ordem invertida).`,
        vscode.DiagnosticSeverity.Error
      ));
    }

    // ── Verificação 5: string sem fechamento de aspas ─────────────────────
    // Conta as aspas duplas em cada linha (excluindo comentários).
    // Um número ímpar de aspas indica que uma string não foi fechada.
    lines.forEach((line, lineIdx) => {
      const stripped  = line.replace(/#.*$/, '');  // remove comentário
      const quoteCount = (stripped.match(/"/g) || []).length;
      if (quoteCount % 2 !== 0) {
        const col = stripped.indexOf('"');  // posição da primeira aspas problemática
        diagnostics.push(new vscode.Diagnostic(
          new vscode.Range(lineIdx, col, lineIdx, stripped.length),
          'String sem fechamento de aspas. Verifique se a aspas de fechamento está na mesma linha.',
          vscode.DiagnosticSeverity.Error
        ));
      }
    });

    // Publica os diagnósticos — o VS Code atualiza o editor imediatamente
    this.collection.set(document.uri, diagnostics);
  }
}
