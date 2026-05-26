# Auditor-DSL — Extensão para VS Code

Suporte completo à linguagem **Auditor-DSL** para auditoria fiscal de **NF-e** e **CT-e** diretamente no editor.

---

## Funcionalidades

- **Syntax highlighting** — palavras-chave, variáveis fiscais, operadores e strings com cores distintas
- **Autocomplete contextual** — sugestões inteligentes conforme a posição na gramática (Ctrl+Space ou automático)
- **Hover docs** — documentação fiscal ao passar o mouse sobre qualquer variável ou palavra-chave
- **Diagnósticos em tempo real** — sublinhado vermelho para erros antes de executar qualquer coisa
- **Snippets** — atalhos para criar regras completas rapidamente

---

## Pré-requisitos

| Ferramenta | Versão mínima |
|------------|--------------|
| [Node.js](https://nodejs.org) | 18+ |
| [npm](https://www.npmjs.com) | 9+ |
| [VS Code](https://code.visualstudio.com) | 1.85+ |

---

## Como compilar e instalar

### 1. Instalar as dependências

```bash
cd auditor-dsl-vscode
npm install
```

### 2. Compilar o TypeScript

```bash
npm run compile
```

O código compilado vai para a pasta `out/`. Você pode checar se deu certo: o arquivo `out/extension.js` deve existir após a compilação.

Para recompilar automaticamente a cada mudança (modo watch):

```bash
npm run watch
```

---

### 3. Rodar no VS Code (modo desenvolvimento)

1. Abra a pasta `auditor-dsl-vscode/` no VS Code:
   ```bash
   code auditor-dsl-vscode/
   ```
2. Pressione **F5** (ou vá em _Run → Start Debugging_).
3. Uma nova janela do VS Code abre com a extensão carregada — a **Extension Development Host**.
4. Nessa janela, abra ou crie um arquivo com extensão `.auditor` e as funcionalidades estarão ativas.

---

### 4. Empacotar como `.vsix` (opcional)

Para distribuir a extensão sem publicar no Marketplace:

```bash
npm install -g @vscode/vsce
vsce package
```

Isso gera um arquivo `auditor-dsl-0.1.0.vsix` na raiz do projeto.

Para instalar esse arquivo em qualquer VS Code:

```bash
code --install-extension auditor-dsl-0.1.0.vsix
```

Ou pela interface: _Extensions → ⋯ → Install from VSIX..._

---

## Estrutura do projeto

```
auditor-dsl-vscode/
├── src/
│   ├── extension.ts          # Ponto de entrada — registra os provedores
│   ├── completionProvider.ts # Autocomplete contextual
│   ├── hoverProvider.ts      # Documentação ao passar o mouse
│   └── diagnosticsProvider.ts# Sublinhado de erros em tempo real
├── syntaxes/
│   └── auditor.tmLanguage.json # Gramática TextMate (syntax highlighting)
├── snippets/
│   └── auditor.json          # Snippets de código
├── language-configuration.json # Configuração de comentários e aspas
├── package.json
└── tsconfig.json
```

---

## Snippets disponíveis

| Prefixo | O que gera |
|---------|-----------|
| `regra` | Regra completa com todos os campos |
| `regra-nota` | Regra com validação no nível da nota |
| `regra-item` | Regra com validação no nível do item |
| `regra-inter` | Regra para operações interestaduais |
| `filtrar-nota` | Cláusula `FILTRAR NOTA ONDE ...` |
| `filtrar-item` | Cláusula `FILTRAR ITEM ONDE ...` |
| `alerta` | Ação `AO_FALHAR ALERTA "..."` |
| `rejeitar` | Ação `AO_FALHAR REJEITAR "..."` |

---

## Exemplo de regra `.auditor`

```
# Valida alíquota de ICMS em operações interestaduais saindo de SP
REGRA "ICMS interestadual SP"
ANALISAR NFE
FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
E TIPO_OPERACAO == INTERESTADUAL
FILTRAR ITEM ONDE ITEM_CFOP == "6102"
VALIDAR ITEM QUE ITEM_ALIQUOTA_ICMS == 12%
OU ITEM_ALIQUOTA_ICMS == 7%
AO_FALHAR ALERTA "Alíquota interestadual incorreta para saída de SP"
```

---

## Erros detectados automaticamente

| Situação | Exemplo |
|----------|---------|
| Variável desconhecida | `NOTA_ESTADO` (não existe) |
| Variável no contexto errado | `ITEM_CFOP` dentro de `FILTRAR NOTA` |
| Tipo de documento inválido | `ANALISAR XML` |
| Operador JavaScript `=>` | Use `>=` no lugar |
| String sem fechar aspas | `"texto sem fechar` |

---

## Scripts npm

| Comando | O que faz |
|---------|-----------|
| `npm run compile` | Compila TypeScript → `out/` |
| `npm run watch` | Recompila automaticamente ao salvar |
| `npm run vscode:prepublish` | Compila antes de empacotar (usado pelo `vsce`) |
