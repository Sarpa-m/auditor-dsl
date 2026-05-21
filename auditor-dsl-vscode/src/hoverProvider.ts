// =============================================================================
// hoverProvider.ts — Documentação em hover para Auditor-DSL
//
// Quando o usuário passa o mouse sobre uma palavra reconhecida, o VS Code
// chama provideHover(). O provider extrai a palavra sob o cursor, procura
// a documentação correspondente em HOVER_DOCS e devolve um Hover com Markdown.
//
// O padrão de word range usado ([A-Z][A-Z0-9_]*) reconhece exatamente os
// identificadores válidos da DSL (tudo maiúsculo), ignorando o restante.
// =============================================================================

import * as vscode from 'vscode';

// =============================================================================
// HOVER_DOCS — documentação fiscal de cada variável e palavra-chave
//
// O conteúdo usa Markdown: **negrito**, `código`, listas com \n- etc.
// O VS Code renderiza esse Markdown na tooltip de hover.
// =============================================================================
const HOVER_DOCS: Record<string, string> = {

  // ── Variáveis de nível de nota ─────────────────────────────────────────

  'NOTA_UF_EMITENTE':
    '**UF do Emitente**\n\n' +
    'Estado de onde a nota foi emitida.\n\n' +
    'Exemplo: `"SP"`, `"MG"`, `"RJ"`\n\n' +
    '_Tipo_: texto — aceita `==` e `!=`',

  'NOTA_UF_DESTINATARIO':
    '**UF do Destinatário**\n\n' +
    'Estado para onde a mercadoria foi enviada.\n\n' +
    '_Dica_: compare com `NOTA_UF_EMITENTE` para detectar operações interestaduais. ' +
    'Para isso, use a variável derivada `TIPO_OPERACAO`.',

  'NOTA_CNPJ_EMITENTE':
    '**CNPJ do Emitente**\n\n' +
    'CNPJ de quem emitiu a nota, somente dígitos (14 caracteres).\n\n' +
    'Exemplo: `"12345678000195"`',

  'NOTA_CNPJ_DESTINATARIO':
    '**CNPJ do Destinatário**\n\n' +
    'CNPJ de quem recebeu a nota, somente dígitos.',

  'NOTA_VALOR_TOTAL':
    '**Valor Total da Nota**\n\n' +
    'Soma de todos os valores da nota em reais, incluindo tributos.\n\n' +
    '_Tipo_: número — aceita `>`, `<`, `>=`, `<=`, `==`, `!=`\n\n' +
    'Exemplo: `NOTA_VALOR_TOTAL > 100000`',

  'NOTA_VALOR_ICMS':
    '**Valor Total de ICMS**\n\n' +
    'Soma do ICMS de todos os itens da nota (campo `vICMS` do `ICMSTot`).\n\n' +
    '_Tipo_: número\n\n' +
    '_Dica_: use `NOTA_VALOR_ICMS > 0` para verificar se há ICMS destacado.',

  'NOTA_NUMERO':
    '**Número da NF-e**\n\n' +
    'Número sequencial da nota fiscal (campo `nNF`).\n\n' +
    '_Tipo_: texto',

  'NOTA_SERIE':
    '**Série da NF-e**\n\n' +
    'Número de série da nota fiscal.\n\n' +
    '_Tipo_: texto — geralmente `"1"` para NF-e padrão',

  'NOTA_DATA_EMISSAO':
    '**Data de Emissão**\n\n' +
    'Data e hora de emissão no formato ISO 8601.\n\n' +
    'Exemplo: `"2024-01-15T10:00:00-03:00"`\n\n' +
    '_Tipo_: texto',

  'NOTA_NATUREZA':
    '**Natureza da Operação**\n\n' +
    'Descrição textual da operação comercial (campo `natOp`).\n\n' +
    'Exemplo: `"Venda de mercadoria"`, `"Remessa para industrialização"`\n\n' +
    '_Tipo_: texto — use `CONTEM` para busca parcial',

  'NOTA_TIPO_OPERACAO':
    '**Tipo de Operação da Nota**\n\n' +
    'Indica se a nota é de entrada ou saída (campo `tpNF`).\n\n' +
    '- `"0"` = Entrada\n' +
    '- `"1"` = Saída\n\n' +
    '⚠️ _Diferente de `TIPO_OPERACAO`_ (inter/intraestadual).',

  'NOTA_PROTOCOLO':
    '**Protocolo de Autorização SEFAZ**\n\n' +
    'Número do protocolo que comprova a autorização de uso da NF-e.\n\n' +
    '_Dica_: uma nota sem protocolo não tem validade jurídica.',

  // ── Variáveis de nível de item ──────────────────────────────────────────

  'ITEM_CFOP':
    '**CFOP do Item**\n\n' +
    'Código Fiscal de Operações e Prestações (4 dígitos).\n\n' +
    'Estrutura do primeiro dígito:\n' +
    '- `1xxx` / `2xxx` / `3xxx` = Entradas\n' +
    '- `5xxx` / `6xxx` / `7xxx` = Saídas\n\n' +
    '_Dica_: use `INICIA_COM "6"` para filtrar saídas interestaduais.',

  'ITEM_NCM':
    '**NCM do Item**\n\n' +
    'Nomenclatura Comum do Mercosul — código de 8 dígitos que classifica o produto.\n\n' +
    'Exemplo: `"84713012"` (computadores portáteis)',

  'ITEM_DESCRICAO':
    '**Descrição do Produto**\n\n' +
    'Texto livre descrevendo o produto ou serviço (campo `xProd`).\n\n' +
    '_Dica_: use `CONTEM` para filtrar por palavra:\n' +
    '`ITEM_DESCRICAO CONTEM "notebook"`',

  'ITEM_QUANTIDADE':
    '**Quantidade**\n\n' +
    'Quantidade comercializada (campo `qCom`).\n\n' +
    '_Tipo_: número',

  'ITEM_VALOR_UNITARIO':
    '**Valor Unitário**\n\n' +
    'Valor unitário de comercialização (campo `vUnCom`).\n\n' +
    '_Tipo_: número',

  'ITEM_VALOR_TOTAL':
    '**Valor Total do Item**\n\n' +
    'Valor total do item: quantidade × valor unitário (campo `vProd`).\n\n' +
    '_Tipo_: número',

  'ITEM_ALIQUOTA_ICMS':
    '**Alíquota de ICMS**\n\n' +
    'Percentual de ICMS aplicado ao item.\n\n' +
    'Alíquotas comuns:\n' +
    '- `4%`  — interestadual para importados\n' +
    '- `7%`  — interestadual para estados do N/NE/CO\n' +
    '- `12%` — interestadual para estados do S/SE\n' +
    '- `17%`–`19%` — alíquotas internas (variam por estado)\n\n' +
    '_Tipo_: percentual — use `12%` (com o símbolo `%`)',

  'ITEM_VALOR_ICMS':
    '**Valor do ICMS do Item**\n\n' +
    'Valor monetário de ICMS calculado para este item.\n\n' +
    '_Tipo_: número',

  'ITEM_BASE_CALCULO_ICMS':
    '**Base de Cálculo do ICMS**\n\n' +
    'Valor sobre o qual a alíquota de ICMS é aplicada.\n\n' +
    '_Tipo_: número',

  'ITEM_CST_ICMS':
    '**CST do ICMS**\n\n' +
    'Código de Situação Tributária do ICMS.\n\n' +
    'Valores comuns:\n' +
    '- `"000"` = Tributada integralmente\n' +
    '- `"010"` = Tributada com ICMS por ST\n' +
    '- `"020"` = Com redução de BC\n' +
    '- `"040"` = Isenta\n' +
    '- `"041"` = Não tributada\n' +
    '- `"060"` = Cobrada anteriormente por ST',

  'ITEM_ALIQUOTA_IPI':
    '**Alíquota de IPI**\n\n' +
    'Percentual de IPI aplicado ao item.\n\n' +
    '_Tipo_: percentual — use `5%` (com o símbolo `%`)',

  'ITEM_ALIQUOTA_PIS':
    '**Alíquota de PIS**\n\n' +
    'Percentual de PIS aplicado ao item.\n\n' +
    'Valores padrão:\n' +
    '- `0.65%` = Regime cumulativo (Lucro Presumido)\n' +
    '- `1.65%` = Regime não cumulativo (Lucro Real)\n\n' +
    '_Tipo_: percentual',

  'ITEM_ALIQUOTA_COFINS':
    '**Alíquota de COFINS**\n\n' +
    'Percentual de COFINS aplicado ao item.\n\n' +
    'Valores padrão:\n' +
    '- `3%`   = Regime cumulativo\n' +
    '- `7.6%` = Regime não cumulativo\n\n' +
    '_Tipo_: percentual',

  // ── Variáveis e palavras-chave especiais ───────────────────────────────

  'TIPO_OPERACAO':
    '**TIPO_OPERACAO (calculado)**\n\n' +
    'Variável derivada automaticamente — **não existe no XML**.\n\n' +
    'O sistema compara a UF emitente com a UF destinatária:\n' +
    '- `INTERESTADUAL` → UFs diferentes (ex: SP → RJ)\n' +
    '- `INTRAESTADUAL` → mesma UF (ex: SP → SP)\n\n' +
    'Uso: `TIPO_OPERACAO == INTERESTADUAL`',

  'INTERESTADUAL':
    '**INTERESTADUAL**\n\n' +
    'Literal especial para `TIPO_OPERACAO`.\n\n' +
    'Representa uma operação entre empresas de **estados diferentes**.\n\n' +
    'Alíquotas de ICMS aplicáveis: `4%`, `7%` ou `12%` conforme o destino.',

  'INTRAESTADUAL':
    '**INTRAESTADUAL**\n\n' +
    'Literal especial para `TIPO_OPERACAO`.\n\n' +
    'Representa uma operação entre empresas do **mesmo estado**.\n\n' +
    'Alíquota de ICMS: alíquota interna do estado (geralmente `17%`–`19%`).',

  // ── Palavras-chave estruturais ──────────────────────────────────────────

  'REGRA':
    '**REGRA**\n\nInicia a definição de uma regra de auditoria.\n\n' +
    'Sintaxe: `REGRA "Nome da regra"`',

  'ANALISAR':
    '**ANALISAR**\n\nDefine o tipo de documento a ser auditado.\n\n' +
    'Valores: `NFE` (Nota Fiscal Eletrônica) ou `CTE` (Conhecimento de Transporte)',

  'FILTRAR':
    '**FILTRAR**\n\n' +
    'Define quais notas ou itens serão submetidos à validação.\n\n' +
    'Notas/itens que **não passam** no filtro são ignorados — nenhuma violação é gerada.\n\n' +
    'Sintaxe: `FILTRAR NOTA ONDE <condição>` ou `FILTRAR ITEM ONDE <condição>`',

  'VALIDAR':
    '**VALIDAR**\n\n' +
    'Define a condição que **deve ser verdadeira**.\n\n' +
    'Se a condição for falsa, a ação `AO_FALHAR` é executada.\n\n' +
    'Sintaxe: `VALIDAR NOTA QUE <condição>` ou `VALIDAR ITEM QUE <condição>`',

  'AO_FALHAR':
    '**AO_FALHAR**\n\nDefine o que acontece quando a validação falha.\n\n' +
    '- `ALERTA "mensagem"` → aviso no relatório, nota não é bloqueada\n' +
    '- `REJEITAR "mensagem"` → nota marcada como rejeitada',

  'ALERTA':
    '**ALERTA**\n\n' +
    'Ação que emite um aviso no relatório **sem bloquear** a nota.\n\n' +
    'Use para situações que merecem revisão mas não são necessariamente incorretas.',

  'REJEITAR':
    '**REJEITAR**\n\n' +
    'Ação que **marca a nota como rejeitada** no relatório.\n\n' +
    'Use para violações que impedem o processamento da nota.',

  'CONTEM':
    '**CONTEM**\n\n' +
    'Operador de substring: verifica se o campo **contém** o texto.\n\n' +
    'Exemplo: `ITEM_DESCRICAO CONTEM "notebook"` → verdadeiro para `"Notebook Pro 15"`',

  'INICIA_COM':
    '**INICIA_COM**\n\n' +
    'Operador de prefixo: verifica se o campo **começa com** o texto.\n\n' +
    'Exemplo: `ITEM_CFOP INICIA_COM "6"` → verdadeiro para `"6102"`, `"6108"`, etc.',
};

// =============================================================================
// AuditorHoverProvider
// =============================================================================

export class AuditorHoverProvider implements vscode.HoverProvider {

  provideHover(
    document: vscode.TextDocument,
    position: vscode.Position
  ): vscode.Hover | null {

    // Extrai a palavra sob o cursor usando o padrão de identificadores da DSL.
    // Captura apenas sequências de letras maiúsculas, dígitos e underscore
    // iniciadas por letra maiúscula — exatamente o padrão da linguagem.
    const range = document.getWordRangeAtPosition(position, /[A-Z][A-Z0-9_]*/);
    if (!range) return null;

    const word = document.getText(range);
    const doc  = HOVER_DOCS[word];
    if (!doc) return null;

    // Devolve o hover com Markdown renderizável e o range da palavra encontrada
    return new vscode.Hover(new vscode.MarkdownString(doc), range);
  }
}
