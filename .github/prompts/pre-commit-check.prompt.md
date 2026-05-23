---
mode: agent
description: "Roda toda a checklist de qualidade antes de declarar uma task concluída ou fazer commit."
---

# Pre-Commit Check

Antes de declarar uma task concluída ou fazer commit, execute esta checklist **integralmente**. Pare na primeira falha e corrija antes de prosseguir.

## Comandos (na ordem)

1. **Lint:**

   ```powershell
   python -m uv run ruff check .
   ```

   Esperado: `All checks passed!`

2. **Format:**

   ```powershell
   python -m uv run ruff format --check .
   ```

   Esperado: `N files already formatted`.

3. **Types:**

   ```powershell
   python -m uv run mypy src tests
   ```

   Esperado: `Success: no issues found in N source files`.

4. **Tests:**

   ```powershell
   python -m uv run pytest -q -m "not live"
   ```

   Esperado: `N passed`.

5. **Docker (se houver mudança em infra):**

   ```powershell
   docker compose config --quiet
   ```

   Esperado: sem output (silêncio = ok).

6. **Painel Problemas:** chame `get_errors` sem argumentos. Esperado: nenhum erro/warning.

## Documentação (obrigatório se task afetou código)

7. Atualizei `docs/CHANGELOG.md` com nova entrada (data + descrição + escopo).
8. Atualizei `docs/SESSION_HANDOFF.md` com novo estado.
9. Se corrigi erro: adicionei em `docs/ERRORS_AND_FIXES.md`.
10. Se criei padrão novo: adicionei em `docs/PATTERNS.md`.
11. Se decisão arquitetural: adicionei ADR em `docs/DECISIONS.md`.

## Git (local-only por enquanto)

12. `git status` mostra apenas arquivos esperados (nada espúrio em `docs/`).
13. **NUNCA** `git add -f`. Se arquivo está ignorado, é por design.
14. Commit com mensagem convencional: `<tipo>(<escopo>): <descrição>`.

## Em Caso de Falha

- **Lint/format:** rodar `ruff check . --fix` e `ruff format .`, depois revalidar.
- **Mypy:** ler o erro literal, corrigir tipos. **Não** use `# type: ignore` sem justificativa em comentário.
- **Pytest:** rodar `pytest -xvs <test_path>` para ver detalhes.
- **Markdownlint:** consulte `.github/instructions/markdown.instructions.md`.

## Sucesso

Reporte ao usuário:

```text
✓ ruff check: ok
✓ ruff format: ok
✓ mypy: ok (N files)
✓ pytest: N passed
✓ painel: zero issues
✓ docs atualizados: CHANGELOG, SESSION_HANDOFF[, ERRORS_AND_FIXES, PATTERNS]
✓ commit local: <hash> — <mensagem>
```
