// =============================================================================
// completionProvider.ts — Autocomplete contextual para Auditor-DSL
//
// Estratégia: ler o texto do arquivo do início até o cursor, identificar o
// último token e o contexto (NOTA/ITEM) da cláusula atual, e devolver a lista
// de sugestões adequada para aquela posição na gramática.
//
// Fluxo de decisão principal (função provideCompletionItems):
//   início → REGRA → "nome" → ANALISAR → NFE/CTE
//   → FILTRAR/VALIDAR → NOTA/ITEM → ONDE/QUE
//   → variável → operador → valor
//   → E/OU → (nova variável ou TIPO_OPERACAO)
//   → AO_FALHAR → ALERTA/REJEITAR → "mensagem"
//   → (próximo REGRA)
// =============================================================================

import * as vscode from 'vscode';

// =============================================================================
// Dados de domínio fiscal — espelham domain_vars.py do interpretador Python
//
// Mantidos aqui como dicionários TypeScript para que o autocomplete
// funcione offline, sem chamar o interpretador Python.
// =============================================================================

/** Variáveis de nível de nota: nome DSL → descrição amigável */
const NOTA_VARS: Record<string, string> = {
  'NOTA_UF_EMITENTE':       'Estado (UF) de quem emitiu a nota. Ex: "SP", "RJ"',
  'NOTA_UF_DESTINATARIO':   'Estado (UF) de quem recebeu a nota',
  'NOTA_CNPJ_EMITENTE':     'CNPJ do emitente (somente dígitos)',
  'NOTA_CNPJ_DESTINATARIO': 'CNPJ do destinatário (somente dígitos)',
  'NOTA_VALOR_TOTAL':       'Valor total da nota em reais',
  'NOTA_VALOR_ICMS':        'Total de ICMS destacado na nota',
  'NOTA_NUMERO':            'Número da nota fiscal',
  'NOTA_SERIE':             'Série da nota fiscal',
  'NOTA_DATA_EMISSAO':      'Data e hora de emissão (ISO 8601)',
  'NOTA_NATUREZA':          'Natureza da operação (texto livre)',
  'NOTA_TIPO_OPERACAO':     'Tipo: 0=entrada, 1=saída',
  'NOTA_PROTOCOLO':         'Protocolo de autorização da SEFAZ',
};

/** Variáveis de nível de item: nome DSL → descrição amigável */
const ITEM_VARS: Record<string, string> = {
  'ITEM_CFOP':              'Código Fiscal de Operações e Prestações',
  'ITEM_NCM':               'Nomenclatura Comum do Mercosul (8 dígitos)',
  'ITEM_DESCRICAO':         'Descrição do produto ou serviço',
  'ITEM_QUANTIDADE':        'Quantidade do item',
  'ITEM_VALOR_UNITARIO':    'Valor unitário do item',
  'ITEM_VALOR_TOTAL':       'Valor total do item',
  'ITEM_ALIQUOTA_ICMS':     'Alíquota de ICMS (%). Ex: 12%, 7%',
  'ITEM_VALOR_ICMS':        'Valor monetário do ICMS',
  'ITEM_BASE_CALCULO_ICMS': 'Base de cálculo do ICMS',
  'ITEM_CST_ICMS':          'Código de Situação Tributária do ICMS',
  'ITEM_ALIQUOTA_IPI':      'Alíquota de IPI (%)',
  'ITEM_ALIQUOTA_PIS':      'Alíquota de PIS (%). Ex: 1.65%',
  'ITEM_ALIQUOTA_COFINS':   'Alíquota de COFINS (%). Ex: 7.6%',
};

/** Variáveis cujo tipo é numérico — aceitam operadores >, <, >=, <= */
const NUMERIC_VARS = new Set([
  'NOTA_VALOR_TOTAL', 'NOTA_VALOR_ICMS',
  'ITEM_QUANTIDADE', 'ITEM_VALOR_UNITARIO', 'ITEM_VALOR_TOTAL',
  'ITEM_VALOR_ICMS', 'ITEM_BASE_CALCULO_ICMS',
]);

/** Variáveis cujo tipo é percentual — aceitam operadores relacionais e valores com % */
const PCT_VARS = new Set([
  'ITEM_ALIQUOTA_ICMS', 'ITEM_ALIQUOTA_IPI',
  'ITEM_ALIQUOTA_PIS', 'ITEM_ALIQUOTA_COFINS',
]);

/** Valores comuns pré-definidos por variável — exibidos após o operador */
const VALUE_HINTS: Record<string, string[]> = {
  'NOTA_UF_EMITENTE':     ['"SP"', '"RJ"', '"MG"', '"RS"', '"PR"', '"SC"', '"BA"', '"GO"'],
  'NOTA_UF_DESTINATARIO': ['"SP"', '"RJ"', '"MG"', '"RS"', '"PR"', '"SC"', '"BA"', '"GO"'],
  'ITEM_CFOP':            ['"5102"', '"5405"', '"6102"', '"6108"', '"1102"', '"2102"'],
  'ITEM_CST_ICMS':        ['"000"', '"010"', '"020"', '"040"', '"041"', '"050"', '"060"'],
  'ITEM_ALIQUOTA_ICMS':   ['4%', '7%', '12%', '17%', '18%', '19%'],
  'ITEM_ALIQUOTA_PIS':    ['0.65%', '1.65%'],
  'ITEM_ALIQUOTA_COFINS': ['3%', '7.6%'],
};

// =============================================================================
// Análise de contexto
// =============================================================================

/**
 * Lê o texto do início do arquivo até a posição do cursor e extrai:
 *   last        — último token completo antes do cursor
 *   prev        — penúltimo token
 *   prev2       — antepenúltimo token
 *   currentCtx  — contexto NOTA/ITEM da cláusula atual (ou null)
 *   textUpToCursor — texto bruto para verificações adicionais com regex
 */
function getContext(document: vscode.TextDocument, position: vscode.Position) {
  const fullText        = document.getText();
  const offset          = document.offsetAt(position);
  const textUpToCursor  = fullText.slice(0, offset).trimEnd();

  // Tokeniza por espaços e quebras de linha, filtrando vazios
  const tokens = textUpToCursor.split(/\s+/).filter(Boolean);
  const last   = tokens[tokens.length - 1] ?? '';
  const prev   = tokens[tokens.length - 2] ?? '';
  const prev2  = tokens[tokens.length - 3] ?? '';

  // Descobre o contexto da cláusula atual procurando o FILTRAR/VALIDAR mais
  // recente seguido de NOTA ou ITEM + ONDE/QUE imediatamente antes do cursor.
  // Regex captura padrões como "FILTRAR NOTA ONDE" ou "VALIDAR ITEM QUE".
  const clauseMatch = textUpToCursor.match(
    /(?:FILTRAR|VALIDAR)\s+(NOTA|ITEM)\s+(?:ONDE|QUE)\s*$/
  );
  const currentCtx = clauseMatch ? clauseMatch[1] : null;

  return { last, prev, prev2, currentCtx, textUpToCursor };
}

/** Infere o tipo de uma variável de domínio com base em seu nome */
function inferType(varName: string): 'pct' | 'num' | 'str' {
  if (PCT_VARS.has(varName))     return 'pct';
  if (NUMERIC_VARS.has(varName)) return 'num';
  return 'str';
}

// =============================================================================
// AuditorCompletionProvider
// =============================================================================

export class AuditorCompletionProvider implements vscode.CompletionItemProvider {

  provideCompletionItems(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.CompletionItem[] {

    const { last, prev, prev2, currentCtx, textUpToCursor } = getContext(document, position);

    // ── Início de arquivo ou após regra completa ─────────────────────────
    // Situação: arquivo vazio ou cursor logo após a mensagem do AO_FALHAR.
    if (!textUpToCursor.trim() ||
        textUpToCursor.match(/AO_FALHAR\s+(?:ALERTA|REJEITAR)\s+"[^"]*"\s*$/)) {
      return [this.kw('REGRA', 'Iniciar uma nova regra de auditoria')];
    }

    // ── Após REGRA → espera o nome da regra entre aspas ─────────────────
    if (last === 'REGRA') {
      return [this.hint('"Nome da regra"',
        'Digite o nome desta regra entre aspas duplas',
        vscode.CompletionItemKind.Value)];
    }

    // ── Após o nome da regra (string) → ANALISAR ─────────────────────────
    // Detecta que o último token é uma string entre aspas (nome da regra).
    if ((last.startsWith('"') || last.endsWith('"')) && prev === 'REGRA') {
      return [this.kw('ANALISAR', 'Define o tipo de documento a analisar')];
    }

    // ── Após ANALISAR → NFE ou CTE ───────────────────────────────────────
    if (last === 'ANALISAR') {
      return [
        this.kw('NFE', 'Nota Fiscal Eletrônica'),
        this.kw('CTE', 'Conhecimento de Transporte Eletrônico'),
      ];
    }

    // ── Após NFE/CTE → FILTRAR (opcional) ou VALIDAR ────────────────────
    if (last === 'NFE' || last === 'CTE') {
      return [
        this.kw('FILTRAR', 'Adicionar filtro de seleção (opcional)'),
        this.kw('VALIDAR', 'Definir a condição a ser validada'),
      ];
    }

    // ── Após FILTRAR ou VALIDAR → NOTA ou ITEM ───────────────────────────
    if (last === 'FILTRAR' || last === 'VALIDAR') {
      return [
        this.kw('NOTA', 'Contexto: nível da nota fiscal inteira'),
        this.kw('ITEM', 'Contexto: nível de cada produto/item'),
      ];
    }

    // ── Após "FILTRAR NOTA" / "FILTRAR ITEM" → ONDE ──────────────────────
    // ── Após "VALIDAR NOTA" / "VALIDAR ITEM" → QUE ───────────────────────
    if (['NOTA', 'ITEM'].includes(last) && ['FILTRAR', 'VALIDAR'].includes(prev)) {
      const keyword = prev === 'FILTRAR' ? 'ONDE' : 'QUE';
      return [this.kw(keyword, `Introduz a condição do ${prev.toLowerCase()}`)];
    }

    // ── Após ONDE ou QUE → variáveis de domínio + TIPO_OPERACAO ─────────
    // O contexto é inferido pelo token dois antes (NOTA ou ITEM).
    if (last === 'ONDE' || last === 'QUE') {
      const ctx = ['NOTA', 'ITEM'].includes(prev2) ? prev2 : currentCtx;
      return [
        ...this.varSuggestions(ctx),
        this.kw('TIPO_OPERACAO', 'Tipo de operação (calculado): INTERESTADUAL ou INTRAESTADUAL'),
      ];
    }

    // ── Após E / OU → nova variável ou TIPO_OPERACAO ─────────────────────
    if (last === 'E' || last === 'OU') {
      return [
        ...this.varSuggestions(currentCtx),
        this.kw('TIPO_OPERACAO', 'Tipo de operação: INTERESTADUAL ou INTRAESTADUAL'),
      ];
    }

    // ── Após variável de domínio → operadores de comparação ─────────────
    if (last.startsWith('NOTA_') || last.startsWith('ITEM_')) {
      const varType = inferType(last);
      return [
        ...this.operatorSuggestions(varType),
        this.kw('CONTEM',     'Verifica se o campo contém um texto'),
        this.kw('INICIA_COM', 'Verifica se o campo começa com um prefixo'),
      ];
    }

    // ── Após TIPO_OPERACAO → somente == (único operador suportado) ───────
    if (last === 'TIPO_OPERACAO') {
      return [this.op('==', 'Igual a')];
    }

    // ── Após operador de comparação → valores literais ───────────────────
    if (['==', '!=', '>', '<', '>=', '<='].includes(last)) {
      // Caso especial: TIPO_OPERACAO só aceita INTERESTADUAL ou INTRAESTADUAL
      if (prev === 'TIPO_OPERACAO') {
        return [
          this.kw('INTERESTADUAL', 'Operação entre estados diferentes (UFs distintas)'),
          this.kw('INTRAESTADUAL', 'Operação dentro do mesmo estado (mesma UF)'),
        ];
      }
      // Para demais variáveis: valores comuns ou hint genérico
      return this.valueSuggestions(inferType(prev), prev);
    }

    // ── Após CONTEM ou INICIA_COM → hint de string ───────────────────────
    if (last === 'CONTEM' || last === 'INICIA_COM') {
      return [this.hint('"texto"',
        'Digite o texto entre aspas duplas',
        vscode.CompletionItemKind.Value)];
    }

    // ── Após um valor literal (fim de expressão) → E, OU ou próxima cláusula
    // Detecta que o último token é uma string, número ou percentual.
    const isValue = last.startsWith('"') || last.endsWith('"') ||
                    /^[0-9]/.test(last) ||
                    last === 'INTERESTADUAL' || last === 'INTRAESTADUAL';

    if (isValue) {
      const items: vscode.CompletionItem[] = [
        this.kw('E',  'Adicionar condição AND (maior precedência que OU)'),
        this.kw('OU', 'Adicionar condição OR'),
      ];
      // Sugere próximas cláusulas estruturais conforme o estágio atual da regra
      if (!textUpToCursor.includes('VALIDAR')) {
        items.push(
          this.kw('FILTRAR', 'Adicionar outro filtro'),
          this.kw('VALIDAR', 'Definir a condição de validação'),
        );
      } else if (!textUpToCursor.includes('AO_FALHAR')) {
        items.push(this.kw('AO_FALHAR', 'Definir ação quando a validação falhar'));
      }
      return items;
    }

    // ── Após AO_FALHAR → ALERTA ou REJEITAR ─────────────────────────────
    if (last === 'AO_FALHAR') {
      return [
        this.action('ALERTA',   'Emite aviso — não bloqueia a nota'),
        this.action('REJEITAR', 'Marca a nota como rejeitada'),
      ];
    }

    // ── Após ALERTA ou REJEITAR → mensagem entre aspas ───────────────────
    if (last === 'ALERTA' || last === 'REJEITAR') {
      return [this.hint('"Mensagem de erro"',
        'Mensagem que aparecerá no relatório de auditoria',
        vscode.CompletionItemKind.Value)];
    }

    return [];
  }

  // ==========================================================================
  // Helpers privados — constroem CompletionItems tipados
  // ==========================================================================

  /**
   * Devolve sugestões de variáveis filtradas pelo contexto (NOTA, ITEM ou ambos).
   * Cada item exibe a descrição fiscal da variável como detalhe.
   */
  private varSuggestions(ctx: string | null): vscode.CompletionItem[] {
    const source = ctx === 'NOTA' ? NOTA_VARS
                 : ctx === 'ITEM' ? ITEM_VARS
                 : { ...NOTA_VARS, ...ITEM_VARS };

    return Object.entries(source).map(([name, desc]) => {
      const item = new vscode.CompletionItem(name, vscode.CompletionItemKind.Field);
      item.detail = desc;
      item.documentation = new vscode.MarkdownString(
        `**${name}**\n\n${desc}\n\n_Prefixo_: \`${name.startsWith('NOTA_') ? 'NOTA' : 'ITEM'}\``
      );
      return item;
    });
  }

  /**
   * Devolve operadores de comparação adequados para o tipo da variável.
   * Variáveis 'str' só aceitam == e !=; 'num' e 'pct' aceitam todos.
   */
  private operatorSuggestions(varType: string): vscode.CompletionItem[] {
    const base = [
      this.op('==', 'Igual a'),
      this.op('!=', 'Diferente de'),
    ];
    if (varType === 'num' || varType === 'pct') {
      base.push(
        this.op('>',  'Maior que'),
        this.op('<',  'Menor que'),
        this.op('>=', 'Maior ou igual a'),
        this.op('<=', 'Menor ou igual a'),
      );
    }
    return base;
  }

  /**
   * Devolve valores literais comuns para a variável, ou hints genéricos
   * quando não há lista pré-definida (fallback por tipo).
   */
  private valueSuggestions(varType: string, varName: string): vscode.CompletionItem[] {
    if (VALUE_HINTS[varName]) {
      return VALUE_HINTS[varName].map(v => {
        const item = new vscode.CompletionItem(v, vscode.CompletionItemKind.Constant);
        item.detail = `Valor comum para ${varName}`;
        return item;
      });
    }
    if (varType === 'str') {
      return [this.hint('"valor"', 'Digite um texto entre aspas', vscode.CompletionItemKind.Value)];
    }
    return [this.hint('0', 'Digite um número', vscode.CompletionItemKind.Value)];
  }

  /** Cria um item de palavra-chave */
  private kw(label: string, detail: string): vscode.CompletionItem {
    const item = new vscode.CompletionItem(label, vscode.CompletionItemKind.Keyword);
    item.detail = detail;
    return item;
  }

  /** Cria um item de operador */
  private op(label: string, detail: string): vscode.CompletionItem {
    const item = new vscode.CompletionItem(label, vscode.CompletionItemKind.Operator);
    item.detail = detail;
    return item;
  }

  /** Cria um item de ação (ALERTA/REJEITAR) */
  private action(label: string, detail: string): vscode.CompletionItem {
    const item = new vscode.CompletionItem(label, vscode.CompletionItemKind.Event);
    item.detail = detail;
    return item;
  }

  /** Cria um item de hint (valor ou placeholder) */
  private hint(label: string, detail: string, kind: vscode.CompletionItemKind): vscode.CompletionItem {
    const item = new vscode.CompletionItem(label, kind);
    item.detail = detail;
    return item;
  }
}
