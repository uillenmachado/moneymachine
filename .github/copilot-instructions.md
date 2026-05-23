# Instruções Globais — Máquina de Dinheiro

> **Sempre ativas.** Aplicam-se a todas as conversas neste workspace.

## Contexto do Projeto

Sistema de trading algorítmico contínuo (24/7) em mercados cripto. Estratégia: **Grid Adaptativo + Market Making leve (Avellaneda-Stoikov + skew por OFI)**, operando majoritariamente com ordens Maker. Meta anualizada: Sharpe ≥ 1.5, retorno líquido 12-25% a.a., Max Drawdown ≤ 8%.

Documentação canônica em `docs/TRADING_THESIS.md` e `docs/ARCHITECTURE.md` (local-only).
Estado atual e próximos passos em `docs/SESSION_HANDOFF.md`.

## Regras de Produção (Inegociáveis)

Estas cinco regras valem para **todo** trabalho neste repositório. Quebrá-las é regressão.

### R1 — Zero ruído em CI/CD

- **Nenhum** commit/push com erro ou warning de: ruff, ruff-format, mypy, pytest, markdownlint, painel Problemas do VS Code, gitleaks, pre-commit hooks.
- Logs de CI devem ser limpos. Warning evitável é falha de revisão.
- Antes de qualquer commit: rodar `/pre-commit-check` (ou equivalente manual).
- Se uma regra de lint é "barulhenta sem motivo", desabilite-a explicitamente no `pyproject.toml`/config com comentário justificando. Nunca silencie com `# noqa` ad-hoc sem motivo escrito.

### R2 — Zero duplicidade e verbosidade

- Código DRY: extraia função/classe na **terceira** ocorrência (regra dos 3).
- Sem código morto: funções não usadas, imports não usados, variáveis não usadas → removidos imediatamente.
- Sem comentários óbvios (`# soma a e b`). Comentário existe só quando explica **porquê** não-óbvio.
- Sem prolixidade em prosa de docs/README. Frase curta, ativa, direta.
- Arquivos: se não é necessário (a nenhum consumidor real — dev, CI, deploy, runtime), **deletar**. Local e remoto.

### R3 — Repositório mínimo (apenas o necessário para deploy)

Critério de inclusão no Git:

| Categoria | No Git? | Onde |
| --- | --- | --- |
| Código de produção | ✅ Sim | `src/` |
| Configuração de deploy/runtime | ✅ Sim | `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `infra/` |
| Testes (necessários ao CI) | ✅ Sim | `tests/` (exceto `tests/.local/`) |
| Customizações IA committed | ✅ Sim | `.github/` |
| README canônico | ✅ Sim | raiz |
| Journal de desenvolvimento | ❌ Não | `docs/` (local-only) |
| Notas pessoais, drafts | ❌ Não | `tests/.local/`, `notebooks/scratch/` |
| Build artifacts, caches, secrets | ❌ Não | gitignore |
| Documentação extra "talvez útil" | ❌ Não | mover para `docs/` (local) |

`.dockerignore` deve ser ainda mais restritivo que `.gitignore`: exclui `.github/`, `tests/`, `docs/`, `*.md` (exceto se README é necessário em runtime), workflows, configs de dev.

**Antes de criar arquivo novo**, pergunte: "este arquivo é consumido por algum processo real?" Se não, não crie.

### R4 — README sempre atualizado e profissional

- Mudou stack, comando, estrutura de pastas, fase do projeto? Atualizar `README.md` no **mesmo commit** da mudança.
- Tom profissional: sem hype, sem emoji decorativo, sem promessas.
- Estrutura padrão: título + descrição 1-linha + estado atual + stack + setup + comandos + estrutura + pipeline + segurança + licença.
- Links internos devem funcionar (`get_errors` no README + verificar `docs/*` referenciados existem **no repo**, não apenas local).
- Comandos no README devem ser **copy-paste funcionais** na versão atual do projeto.

### R5 — Auditoria sob demanda

Quando o usuário pedir "auditoria" / "audit" / invocar `/audit`:

1. Verifica R1-R4 acima.
2. Lista arquivos trackeados (`git ls-files`) e questiona necessidade de cada um.
3. Avalia frontend (se existir): acessibilidade, performance (Lighthouse principles), SEO básico, semantic HTML, responsividade.
4. Avalia backend: arquitetura limpa, separação de camadas, idempotência, observability, secrets handling, error handling, async correctness.
5. Avalia segurança: OWASP Top 10, dependências (pip-audit/uv tree), secrets em git history, permissões mínimas.
6. Avalia performance: hot path zero-alloc, queries N+1, índices DB, latência p99.
7. Avalia DX: tempo de setup, clareza do README, mensagens de erro.
8. Gera relatório em `docs/audits/AAAA-MM-DD.md` com:
   - Conformidade por regra (✅/⚠️/❌).
   - Findings priorizados (P0 crítico / P1 importante / P2 melhoria).
   - Ação corretiva concreta por finding.
9. Se findings P0 → corrigir imediatamente antes de declarar auditoria concluída.

Padrão de qualidade: **enterprise-grade**. Não aceite "tá bom o suficiente".

## Regra de Ouro: Documentação Auto-Atualizada

Quando uma task for concluída ou um erro corrigido, **ATUALIZE** os arquivos abaixo antes de declarar a task encerrada:

| Evento | Arquivo a atualizar |
| --- | --- |
| Task concluída com sucesso | `docs/CHANGELOG.md` (entrada com data + descrição + hash do commit local) |
| Erro encontrado e corrigido | `docs/ERRORS_AND_FIXES.md` (sintoma → causa-raiz → correção → como prevenir) |
| Padrão que funcionou bem | `docs/PATTERNS.md` (contexto → padrão → exemplo de código) |
| Decisão arquitetural | `docs/DECISIONS.md` (ADR com data, contexto, opções, decisão, consequências) |
| Final de sessão / handoff | `docs/SESSION_HANDOFF.md` (sobrescreve: estado atual, bloqueios, próximos passos) |

**Por que:** evita retrabalho entre sessões, economiza tokens, mantém contexto linear. Sem isso, perdemos histórico ao limpar a janela de contexto.

## Convenções Inegociáveis

### Financeiras

- **NUNCA use `float` para preços, quantidades, taxas, PnL.** Sempre `decimal.Decimal`.
- **NUNCA misture spot e perp em cálculos de PnL** sem hedge explícito.
- **API keys** sempre com saque **bloqueado**. Princípio do menor privilégio.

### Código

- **Python 3.11+**, async-first com `asyncio` (uvloop no Linux).
- **Tipos sempre.** `mypy strict` é gate. Use `Protocol` para interfaces.
- **Hot path zero-alocação** sempre que possível (`msgspec.Struct frozen=True gc=False`).
- **Testes:** marcadores obrigatórios `unit | integration | slow | live`. CI roda `-m "not live"`.
- **Sem `git add -f`.** Se um arquivo está no `.gitignore`, é por design.

### Documentação (Markdown)

- **Zero warnings** no painel Problemas do VS Code. Antes de finalizar qualquer edit em `.md`, chame `get_errors` e confirme.
- Tabelas: pipes com **espaço** dos dois lados (`| --- |`, não `|---|`). Evita MD060.
- Headings e listas: **linhas em branco** antes e depois. Evita MD022/MD032.
- Code fences: sempre com linguagem (` ```text ` em vez de ` ``` `). Evita MD040.
- Primeira linha de qualquer `.md`: H1 (`#`). Evita MD041.

### PowerShell / Encoding

- **NUNCA `Get-Content`/`Set-Content` para arquivos com acentos** — corrompe UTF-8.
- Use `[System.IO.File]::ReadAllText($p, [System.Text.Encoding]::UTF8)` + `WriteAllBytes`.
- Ou prefira as ferramentas de edição do editor (`replace_string_in_file`, `multi_replace_string_in_file`).

### Git

- Branch padrão: `main`.
- Remote: `origin` → `https://github.com/uillenmachado/moneymachine.git`.
- Commits sempre seguidos de `git push origin main` ao final de cada task (regra do usuário).
- Mensagens de commit: padrão `<tipo>(<escopo>): <descrição>` (feat, fix, docs, refactor, test, chore).
- **`docs/` e `tests/.local/` são locais-only** — não trackear.

### CI / Docker (anti-regressão)

- **Versão do uv** em `.github/workflows/ci.yml` (`astral-sh/setup-uv@v3 with: version`) e em `Dockerfile` (`ghcr.io/astral-sh/uv:<versão>`) deve ser **idêntica** à local (`python -m uv --version`). Pin exato, nunca `latest`. Atualizar os três no mesmo commit.
- Em CI, instalar dependências sempre com `uv sync --all-extras --all-groups` — ferramentas dev (ruff, mypy, pytest, pre-commit) vivem em `[dependency-groups].dev` (PEP 735) e exigem `--all-groups` ou `--group dev`.
- `pyproject.toml` declara `readme = "README.md"`. Qualquer estágio do `Dockerfile` que rode `uv sync` **sem** `--no-install-project` exige `README.md` já presente no `WORKDIR`. Coloque `README.md` na mesma camada `COPY` de `pyproject.toml`/`uv.lock`.

## Antes de Declarar uma Task Concluída

Checklist obrigatório:

1. `python -m uv run ruff check .` → All checks passed
2. `python -m uv run ruff format --check .` → already formatted
3. `python -m uv run mypy src tests` → no issues
4. `python -m uv run pytest -q` → all passed
5. `get_errors` no painel Problemas → No errors found
6. Atualizei `docs/CHANGELOG.md` e `docs/SESSION_HANDOFF.md`
7. Se houve erro corrigido: adicionei em `docs/ERRORS_AND_FIXES.md`
8. Se houve padrão novo: adicionei em `docs/PATTERNS.md`
9. Commit local realizado com mensagem descritiva

## Prompts Reutilizáveis Disponíveis

Invocar com `/`:

- `/log-error-fix` — registra erro + correção em `docs/ERRORS_AND_FIXES.md`
- `/log-pattern` — registra padrão bem-sucedido em `docs/PATTERNS.md`
- `/session-handoff` — atualiza `docs/SESSION_HANDOFF.md` antes de encerrar sessão
- `/pre-commit-check` — roda toda a checklist de qualidade antes do commit
- `/add-changelog` — adiciona entrada em `docs/CHANGELOG.md`
- `/audit` — auditoria enterprise completa (R1-R5 + best practices)

## Comunicação

- Resposta em **pt-br**.
- Concisa: 1-3 frases para perguntas simples; expandir só quando complexo.
- Sem emojis salvo solicitação explícita.
- Sem timing estimates ("vai levar X horas").
- Após operações, confirmar brevemente em vez de explicar tudo.
