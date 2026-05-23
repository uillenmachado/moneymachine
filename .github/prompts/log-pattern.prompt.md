---
mode: agent
description: "Registra um padrão de código/processo bem-sucedido em docs/PATTERNS.md."
---

# Log Pattern

Você implementou algo que funcionou bem e merece ser **replicado** em situações similares. Registre em `docs/PATTERNS.md`.

## Passos

1. Leia `docs/PATTERNS.md` (crie se não existir).
2. **Anteponha** entrada no topo seguindo o template.
3. Use a data atual (`AAAA-MM-DD`).
4. Inclua snippet de código real do projeto (não pseudo-código).
5. `get_errors` no arquivo → "No errors found".

## Template

```markdown
## AAAA-MM-DD — <Nome do padrão>

**Contexto:** Quando aplicar (problema que resolve).

**Padrão:** Descrição de 1-2 frases.

**Exemplo:**

\`\`\`python
# código real do projeto, do arquivo X linhas Y-Z
\`\`\`

**Por que funciona:** Trade-offs, benefícios concretos (performance, segurança, clareza).

**Quando NÃO usar:** Anti-casos, limitações.

**Referências:** Links para arquivos do projeto, RFCs, docs externos.

**Tags:** `#async` `#typing` `#testing` `#performance` `#risk`
```

## Critérios

- Só registre padrões **testados** (não ideias). Se não passou nos testes/lint, não é padrão ainda.
- Prefira padrões reutilizáveis. Algo super-específico de um lugar não vale.
- Se já existe padrão similar, **atualize** em vez de duplicar.
