---
applyTo: "**/*.md"
description: "Convenções de Markdown — zero warnings no painel Problemas."
---

# Markdown — Zero Warnings

O usuário **não admite warnings** no painel Problemas. Antes de finalizar qualquer edit em `.md`, chame `get_errors` e confirme "No errors found".

## Regras Mais Comuns

| Regra | Como cumprir |
| --- | --- |
| MD041 | Primeira linha **sempre** H1 (`# Título`) |
| MD022 | Linha em branco **antes e depois** de cada heading |
| MD032 | Linha em branco **antes e depois** de cada lista |
| MD031 | Linha em branco **antes e depois** de code fences |
| MD040 | Code fence **sempre** com linguagem: ` ```text `, ` ```python `, ` ```powershell ` |
| MD060 | Pipes de tabela **com espaço**: `\| --- \|`, **nunca** `\|---\|` |
| MD056 | `\|` dentro de células de tabela: escapar com `\\|` ou usar HTML entity `&#124;` |
| MD024 | Sem headings duplicados no mesmo arquivo |
| MD013 | Linha longa: aceitável em tabelas; quebrar prosa em ~100 chars |

## Template Mínimo

```markdown
# Título do Documento

Parágrafo introdutório opcional.

## Seção

Texto.

- Item de lista (com blank line antes)
- Outro item

Texto após lista (com blank line entre).

### Subseção

\`\`\`python
codigo()
\`\`\`

| Col A | Col B |
| --- | --- |
| valor | valor |
```

## PowerShell + UTF-8

- **NUNCA** `Get-Content`/`Set-Content` em arquivos com acentos — corrompe encoding.
- Use `[System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)` + `WriteAllBytes`.
- Prefira ferramentas de edição do editor (`replace_string_in_file`).

## Checklist Antes de Encerrar Edit

1. Primeira linha é `# Título`.
2. Blank lines antes/depois de headings, listas, code fences.
3. Pipes de tabela com espaços (` --- ` não `---`).
4. Code fences com linguagem (`text` para texto genérico, nunca vazio).
5. `get_errors` retorna "No errors found".
