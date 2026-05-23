---
mode: agent
description: "Atualiza docs/SESSION_HANDOFF.md com o estado atual antes de encerrar a sessão."
---

# Session Handoff

Vamos encerrar a sessão. Atualize `docs/SESSION_HANDOFF.md` para que a próxima sessão (suas ou de outra IA) tenha contexto linear, sem precisar redescobrir tudo.

## Passos

1. Leia o estado atual de `docs/SESSION_HANDOFF.md` (sobrescrever, não anexar).
2. Reconstrua com base em:
   - Últimos commits locais (`git log --oneline -10`).
   - Arquivos modificados não commitados (`git status`).
   - Conversa atual: o que foi pedido, o que foi feito, o que ficou pendente.
3. Use o template abaixo.
4. `get_errors` → "No errors found".

## Template

```markdown
# Session Handoff — AAAA-MM-DD

**Último commit local:** `<hash>` — `<mensagem>`
**Branch:** `main`
**Estado:** ✅ tudo verde / ⚠️ pendências / ❌ bloqueado

## O Que Foi Feito Nesta Sessão

- Item 1 com referência a arquivo/PR/commit.
- Item 2.

## Estado Atual do Sistema

- Lint: ✅ / ❌ (`ruff check`)
- Format: ✅ / ❌ (`ruff format --check`)
- Types: ✅ / ❌ (`mypy strict`)
- Tests: ✅ X passed / ❌ Y failed (`pytest`)
- Docker: ✅ / ❌ (`docker compose config`)
- Painel Problemas: ✅ zero / ❌ N warnings

## Próximos Passos (em ordem)

1. **[PRIORIDADE]** Descrição da próxima tarefa concreta.
2. Tarefa seguinte.
3. ...

## Bloqueios Conhecidos

- Nenhum. / Lista de bloqueios com dependência externa.

## Arquivos / Áreas em Foco

- `caminho/relevante.py` — o que está pela metade.

## Notas Importantes

- Decisões pendentes do usuário.
- Pontos de atenção para a próxima sessão.
```

## Critérios

- Substitua o conteúdo inteiro (handoff é estado **atual**, não histórico — histórico vai em CHANGELOG).
- Seja honesto sobre o que está incompleto. Não declare "✅" se mentir vai causar retrabalho.
- Após escrever, leia em voz alta mentalmente: "Se eu acordasse amanhã sem memória, este arquivo me deixaria operacional em 5 minutos?"
