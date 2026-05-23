---
mode: agent
description: "Auditoria completa do projeto: regras R1-R5, best practices enterprise, findings priorizados."
---

# Audit — Auditoria Enterprise do Projeto

Conduza auditoria completa do estado atual do projeto. Padrão de qualidade: **enterprise-grade**.

## Escopo

Verificar conformidade com as 5 Regras de Produção definidas em `.github/copilot-instructions.md` + best practices de mercado.

## Procedimento (em ordem)

### 1. Higiene de CI/CD (R1)

Rodar e capturar resultados:

```powershell
python -m uv run ruff check .
python -m uv run ruff format --check .
python -m uv run mypy src tests
python -m uv run pytest -q -m "not live"
docker compose config --quiet
```

Chamar `get_errors` sem argumentos para painel Problemas global. Qualquer warning conta como **finding**.

### 2. Duplicidade / Verbosidade (R2)

- `git ls-files | Measure-Object -Line` — contagem de arquivos trackeados.
- Procurar duplicação: `grep_search` por blocos suspeitos repetidos.
- Procurar código morto: imports não usados (ruff já cobre), funções/classes públicas sem referência (`vscode_listCodeUsages` em símbolos suspeitos).
- Listar arquivos `.md` e questionar necessidade de cada um.

### 3. Repo mínimo (R3)

- `git ls-files` — listar todos os arquivos trackeados.
- Para cada arquivo/categoria, questionar: "este arquivo é consumido por algum processo real (runtime, CI, dev setup, deploy)?"
- Conferir `.dockerignore` exclui o que não vai pra produção (`.github/`, `tests/`, `docs/`, `*.md` exceto necessários).
- Conferir `.gitignore` cobre caches, builds, secrets, dados locais.

### 4. README atualizado (R4)

- Ler `README.md`.
- Conferir cada comando do setup é executável na versão atual.
- Conferir cada link interno aponta para arquivo existente no repo (não em local-only `docs/`).
- Conferir "Estado Atual" reflete o último commit/fase.
- Conferir tom profissional (sem hype, sem emoji decorativo, frases ativas e curtas).
- `get_errors` em `README.md`.

### 5. Backend (best practices)

- **Arquitetura:** separação clara de camadas (data/strategy/risk/oms/metrics)? Protocols definidos antes da implementação?
- **Async correctness:** `asyncio.sleep` em vez de `time.sleep`? `TaskGroup` para concorrência estruturada? sem fire-and-forget?
- **Idempotência:** operações críticas (ordens, halts) são idempotentes?
- **Observability:** structlog + Prometheus + traces? métricas-chave instrumentadas?
- **Error handling:** `except SpecificError`, nunca `except:` engolindo? boundaries validam com pydantic?
- **Secrets:** nunca em logs, nunca hardcoded, `SecretStr.get_secret_value()` só no uso?
- **Decimal:** zero `float` em código financeiro?
- **Tipagem:** mypy strict 100%? zero `Any` implícito? `Protocol` para interfaces?

### 6. Frontend (se existir)

- Acessibilidade: semantic HTML, ARIA labels, contraste WCAG AA, navegável por teclado?
- Performance: Lighthouse principles (LCP < 2.5s, CLS < 0.1, INP < 200ms), code splitting, lazy loading?
- SEO básico: meta tags, OpenGraph, sitemap, robots.txt, schema.org?
- Responsividade: mobile-first, breakpoints consistentes, sem horizontal scroll?
- Bundle size: dependencies justificadas, tree-shaking ativo?

### 7. Segurança

- OWASP Top 10: injection (SQL/command), broken auth, sensitive data exposure, XXE, broken access control, security misconfiguration, XSS, deserialization, vulnerable components, logging/monitoring.
- `python -m uv tree` — dependências; checar vulnerabilidades conhecidas.
- `git log --all --full-history -- .env` — confirmar `.env` nunca foi commitado.
- API keys com permissões mínimas (saque bloqueado obrigatório).
- Pre-commit hooks (gitleaks) ativos.

### 8. Performance

- Hot path: msgspec.Struct frozen+gc=False onde aplicável?
- DB: índices apropriados, queries N+1 detectadas?
- WebSocket: backpressure tratado? reconnect com backoff?
- Latência: instrumentação p50/p95/p99 nos pontos críticos?

### 9. DX (Developer Experience)

- Tempo de setup do zero ≤ 10min? (clone → testes rodando)
- Mensagens de erro ajudam a diagnosticar?
- Comandos do README copy-paste funcionais?
- CI dá feedback rápido (< 5min)?

## Output

Gerar `docs/audits/AAAA-MM-DD.md` (criar `docs/audits/` se não existir) com:

```markdown
# Auditoria — AAAA-MM-DD

**Commit base:** `<hash>`
**Auditor:** GitHub Copilot

## Sumário Executivo

- R1 (CI/CD limpo): ✅ / ⚠️ / ❌
- R2 (sem duplicidade): ✅ / ⚠️ / ❌
- R3 (repo mínimo): ✅ / ⚠️ / ❌
- R4 (README): ✅ / ⚠️ / ❌
- Backend: ✅ / ⚠️ / ❌
- Frontend: N/A (não existe ainda) / ✅ / ⚠️ / ❌
- Segurança: ✅ / ⚠️ / ❌
- Performance: ✅ / ⚠️ / ❌
- DX: ✅ / ⚠️ / ❌

## Findings

### P0 — Crítico (corrigir imediatamente)

- ...

### P1 — Importante (corrigir nesta sessão)

- ...

### P2 — Melhoria (backlog priorizado)

- ...

## Ações Corretivas Aplicadas Nesta Auditoria

- ...

## Backlog Gerado

- ...
```

## Critérios de Aceite

- **Todos os P0** corrigidos antes de declarar auditoria concluída.
- **Findings P1** documentados com plano de ação no `docs/SESSION_HANDOFF.md`.
- Auditoria registrada em `docs/CHANGELOG.md`.
- `get_errors` no relatório de auditoria → "No errors found".
