# Auditor-DSL

> Linguagem de domínio específico para auditoria fiscal de Notas Fiscais Eletrônicas (NF-e)

---

## O que é

Auditor-DSL é uma linguagem declarativa e um interpretador desenvolvidos para automatizar
a validação de documentos fiscais eletrônicos no padrão SPED/NF-e. Com ela, auditores e
contadores podem escrever regras de validação em uma sintaxe próxima do português, sem
necessidade de conhecimento em programação.

O sistema lê arquivos XML de NF-e, aplica as regras definidas pelo usuário e gera um
relatório detalhado com alertas e rejeições — em segundos, para qualquer volume de notas.

---

## O problema que resolve

O cenário tributário brasileiro exige análise constante de grandes volumes de documentos
fiscais. Cada NF-e é um arquivo XML com dezenas de campos: emitente, destinatário,
produtos, alíquotas de ICMS, IPI, PIS, COFINS, protocolos de autorização, CFOP, NCM,
entre outros.

Validar essas informações manualmente é inviável. As soluções existentes exigem ou um
programador para cada nova regra, ou sistemas rígidos que não acompanham a velocidade
das mudanças na legislação.

A Auditor-DSL resolve isso dando ao próprio especialista fiscal a capacidade de criar,
modificar e executar regras de validação de forma autônoma.

---

## Como funciona

O usuário escreve um arquivo `.auditor` com as regras de validação:

```
REGRA "Aliquota ICMS Interestadual SP"
ANALISAR NFE
FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
E TIPO_OPERACAO == INTERESTADUAL
FILTRAR ITEM ONDE ITEM_CFOP == "6102"
VALIDAR ITEM QUE ITEM_ALIQUOTA_ICMS == 12%
OU ITEM_ALIQUOTA_ICMS == 7%
AO_FALHAR ALERTA "Aliquota interestadual incorreta para mercadoria de revenda."
```

O interpretador processa esse arquivo em quatro etapas:

1. **Análise Léxica** — o texto é dividido em tokens reconhecidos pela linguagem (palavras-chave, variáveis de domínio, operadores, valores)
2. **Análise Sintática** — os tokens são organizados em uma Árvore Sintática Abstrata (AST) seguindo a gramática da linguagem, implementada com PLY (Python Lex-Yacc)
3. **Análise Semântica** — as regras são verificadas quanto à coerência: variáveis existentes, contextos corretos, tipos compatíveis
4. **Interpretação** — a AST é executada sobre os XMLs reais, avaliando cada nota e cada item contra as condições definidas

---

## Instalação

**Requisitos:** Python 3.11 ou superior

```bash
git clone https://github.com/fho-engcomp/auditor-dsl.git
cd auditor-dsl
pip install -r requirements.txt
```

`requirements.txt`:
```
ply==3.11
colorama
pytest
```

---

## Uso

### Executar regras sobre uma pasta de XMLs

```bash
python -m auditor regras.auditor pasta/com/xmls/
```

### Executar sobre um único arquivo XML

```bash
python -m auditor regras.auditor nota_fiscal.xml
```

### Gerar relatório em JSON

```bash
python -m auditor regras.auditor pasta/xmls/ --formato json
```

### Verificar a sintaxe das regras sem processar XMLs

```bash
python -m auditor --verificar regras.auditor
```

### Ver tokens e AST gerados (modo debug)

```bash
python -m auditor regras.auditor pasta/xmls/ --verbose
```

---

## A linguagem

### Estrutura de uma regra

Toda regra segue esta estrutura:

```
REGRA "Nome descritivo"
ANALISAR NFE | CTE
FILTRAR NOTA | ITEM ONDE <condição>   (opcional, repetível)
VALIDAR NOTA | ITEM QUE <condição>
AO_FALHAR ALERTA | REJEITAR "Mensagem"
```

### Palavras-chave

| Palavra | Função |
|---|---|
| `REGRA` | Abre uma nova regra |
| `ANALISAR` | Define o tipo de documento (`NFE` ou `CTE`) |
| `FILTRAR` | Seleciona quais notas ou itens a regra analisa |
| `ONDE` | Introduz a condição do filtro |
| `VALIDAR` | Define o que deve estar correto |
| `QUE` | Introduz a condição de validação |
| `AO_FALHAR` | Define a ação quando a validação falha |
| `ALERTA` | Registra aviso no relatório sem bloquear |
| `REJEITAR` | Marca a nota como rejeitada no relatório |
| `E` | Operador lógico AND entre condições |
| `OU` | Operador lógico OR entre condições |
| `NOTA` | Contexto: nível da nota fiscal |
| `ITEM` | Contexto: nível de cada produto |
| `TIPO_OPERACAO` | Variável especial derivada automaticamente (`INTERESTADUAL` ou `INTRAESTADUAL`) |

### Variáveis de domínio disponíveis

**Nível da nota (`NOTA_*`):**

| Variável | Descrição |
|---|---|
| `NOTA_UF_EMITENTE` | Estado do emitente |
| `NOTA_UF_DESTINATARIO` | Estado do destinatário |
| `NOTA_CNPJ_EMITENTE` | CNPJ do emitente |
| `NOTA_CNPJ_DESTINATARIO` | CNPJ do destinatário |
| `NOTA_VALOR_TOTAL` | Valor total da nota em reais |
| `NOTA_VALOR_ICMS` | Total de ICMS destacado |
| `NOTA_NUMERO` | Número da nota fiscal |
| `NOTA_SERIE` | Série da nota |
| `NOTA_DATA_EMISSAO` | Data e hora de emissão |
| `NOTA_NATUREZA` | Natureza da operação |
| `NOTA_TIPO_OPERACAO` | Tipo: 0=entrada, 1=saída |
| `NOTA_PROTOCOLO` | Protocolo de autorização SEFAZ |

**Nível do item (`ITEM_*`):**

| Variável | Descrição |
|---|---|
| `ITEM_CFOP` | Código Fiscal de Operações e Prestações |
| `ITEM_NCM` | Nomenclatura Comum do Mercosul |
| `ITEM_DESCRICAO` | Descrição do produto |
| `ITEM_QUANTIDADE` | Quantidade |
| `ITEM_VALOR_UNITARIO` | Valor unitário |
| `ITEM_VALOR_TOTAL` | Valor total do item |
| `ITEM_ALIQUOTA_ICMS` | Alíquota de ICMS (%) |
| `ITEM_VALOR_ICMS` | Valor monetário do ICMS |
| `ITEM_BASE_CALCULO_ICMS` | Base de cálculo do ICMS |
| `ITEM_CST_ICMS` | Código de Situação Tributária |
| `ITEM_ALIQUOTA_IPI` | Alíquota de IPI (%) |
| `ITEM_ALIQUOTA_PIS` | Alíquota de PIS (%) |
| `ITEM_ALIQUOTA_COFINS` | Alíquota de COFINS (%) |

### Operadores

| Operador | Descrição | Tipos aceitos |
|---|---|---|
| `==` | Igual a | texto, número, alíquota |
| `!=` | Diferente de | texto, número, alíquota |
| `>` | Maior que | número, alíquota |
| `<` | Menor que | número, alíquota |
| `>=` | Maior ou igual a | número, alíquota |
| `<=` | Menor ou igual a | número, alíquota |
| `CONTEM` | Texto contém substring | texto |
| `INICIA_COM` | Texto começa com prefixo | texto |

---

## Exemplos de regras

### Validação de alíquota interestadual

```
REGRA "Aliquota ICMS Interestadual SP"
ANALISAR NFE
FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
E TIPO_OPERACAO == INTERESTADUAL
FILTRAR ITEM ONDE ITEM_CFOP == "6102"
VALIDAR ITEM QUE ITEM_ALIQUOTA_ICMS == 12%
OU ITEM_ALIQUOTA_ICMS == 7%
AO_FALHAR ALERTA "Aliquota interestadual incorreta para mercadoria de revenda."
```

### Nota de alto valor exige revisão manual

```
REGRA "Nota acima de 100 mil reais"
ANALISAR NFE
FILTRAR NOTA ONDE NOTA_UF_EMITENTE == "SP"
VALIDAR NOTA QUE NOTA_VALOR_TOTAL <= 100000
AO_FALHAR REJEITAR "Nota acima de R$100 mil exige revisao manual."
```

### Item de saída sem NCM informado

```
REGRA "CFOP de saida sem NCM"
ANALISAR NFE
FILTRAR ITEM ONDE ITEM_CFOP INICIA_COM "6"
VALIDAR ITEM QUE ITEM_NCM != ""
AO_FALHAR ALERTA "Item com CFOP de saida sem NCM informado."
```

### PIS não cumulativo fora do padrão

```
REGRA "Aliquota PIS nao cumulativo"
ANALISAR NFE
FILTRAR ITEM ONDE ITEM_CST_ICMS == "000"
VALIDAR ITEM QUE ITEM_ALIQUOTA_PIS == 1.65%
AO_FALHAR ALERTA "PIS diverge do padrao nao cumulativo (1,65%)."
```

---

## Relatório de saída

```
══════════════════════════════════════════════════════════════════
  AUDITOR-DSL — RELATÓRIO DE AUDITORIA
══════════════════════════════════════════════════════════════════

[ALERTA]   nfe_001.xml   Nota 000123   Item 2
           Regra: "Aliquota ICMS Interestadual SP"
           → Aliquota interestadual incorreta para mercadoria de revenda.

[REJEITAR] nfe_007.xml   Nota 000891
           Regra: "Nota acima de 100 mil reais"
           → Nota acima de R$100 mil exige revisao manual.

──────────────────────────────────────────────────────────────────
  Total: 47 notas processadas | 1 alerta | 1 rejeição | 45 OK
══════════════════════════════════════════════════════════════════
```

---

## Arquitetura do projeto

```
auditor-dsl/
├── src/auditor/
│   ├── lexer.py          # Análise léxica com PLY lex
│   ├── parser.py         # Análise sintática com PLY yacc → AST
│   ├── ast_nodes.py      # Definição dos nós da Árvore Sintática Abstrata
│   ├── semantic.py       # Verificação semântica das regras
│   ├── interpreter.py    # Motor de execução das regras sobre os XMLs
│   ├── xml_loader.py     # Leitura e mapeamento de NF-e XML → domínio
│   ├── domain_vars.py    # Tabela de variáveis válidas e XPaths correspondentes
│   ├── reporter.py       # Geração do relatório (texto e JSON)
│   └── __main__.py       # Interface de linha de comando
├── examples/             # Arquivos .auditor e XMLs de teste
```

---


---

## Erros detectados pelo sistema

| Tipo | Exemplo | Fase |
|---|---|---|
| Variável inexistente | `NOTA_ESTADO == "SP"` | Semântica |
| Variável em contexto errado | `FILTRAR NOTA ONDE ITEM_CFOP == "6102"` | Semântica |
| Tipo de documento inválido | `ANALISAR XML` | Sintática |
| Operador inválido | `NOTA_VALOR_TOTAL => 100` | Léxica |
| Ausência de `AO_FALHAR` | Regra encerra após `VALIDAR` | Sintática |
| String sem fechamento | `ALERTA "Mensagem sem fechar` | Léxica |
| Nome de regra duplicado | Dois blocos com mesmo nome | Semântica |
| Identificador em minúsculo | `nota_uf_emitente == "SP"` | Léxica |

---

## Contexto acadêmico

Este projeto foi desenvolvido como trabalho prático final da disciplina de
**Teoria da Computação e Compiladores** do curso de Engenharia de Computação da
**Fundação Hermínio Ometto (FHO)**, em Araras-SP.

O objetivo foi aplicar os conceitos de autômatos, gramáticas formais e fases de
tradução na construção de um interpretador completo para uma linguagem de domínio
específico com aplicação real na área fiscal e tributária brasileira.

---

## Autores

| Nome | RA |
|---|---|
| João Cadoni | 111923 |
| Mauricio Sarpa | 112824 |
| Pablo N Ramos | 112070 |

---

