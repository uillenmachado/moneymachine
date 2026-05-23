---
mode: agent
description: "Registra um erro encontrado e sua correção em docs/ERRORS_AND_FIXES.md (anti-regressão)."
---

# Log Error Fix

Você acabou de corrigir um erro. Registre-o em `docs/ERRORS_AND_FIXES.md` para evitar repetição em sessões futuras.

## Passos

1. Leia `docs/ERRORS_AND_FIXES.md` (se não existir, crie com H1 e introdução).
2. **Anteponha** uma nova entrada no topo (mais recente primeiro) seguindo o template abaixo.
3. Use a data atual (formato `AAAA-MM-DD`).
4. Chame `get_errors` no arquivo após editar — deve retornar "No errors found".

## Template

```markdown
## AAAA-MM-DD — <Título curto do erro>

**Contexto:** Em que arquivo / situação ocorreu.

**Sintoma:** O que apareceu (mensagem de erro literal, comportamento incorreto, warning específico).

**Causa-raiz:** Por que aconteceu. Vá além do óbvio — explique o porquê do porquê.

**Correção aplicada:** Mudança concreta (arquivo + linhas + descrição). Se houve commit, mencione o hash.

**Como prevenir:** Regra, padrão ou check automático que evita repetição. Considere:

- Adicionar regra em `.github/instructions/*.instructions.md`?
- Adicionar pre-commit hook ou teste?
- Atualizar `/memories/lessons-from-mistakes.md` (memória global do usuário)?

**Tags:** `#python` `#async` `#markdown` `#docker` `#git` `#typing` (escolha as relevantes)
```

## Critérios

- Seja específico. "Erro de typing" é ruim; "mypy reclamou de `Decimal | None` em `risk.check_pre_trade()`" é bom.
- Cite linhas, arquivos, comandos.
- Se for um erro **recorrente** (já está em ERRORS_AND_FIXES.md), apenas adicione nova ocorrência e fortaleça a prevenção.
