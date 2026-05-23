# Instruções Globais — Máquina de Dinheiro

> **Sempre ativas.** Aplicam-se a todas as conversas neste workspace.

## Contexto do Projeto

Sistema de trading algorítmico contínuo (24/7) em mercados cripto. Estratégia: **Grid Adaptativo + Market Making leve (Avellaneda-Stoikov + skew por OFI)**, operando majoritariamente com ordens Maker. Meta anualizada: Sharpe ≥ 1.5, retorno líquido 12-25% a.a., Max Drawdown ≤ 8%.

Documentação canônica em `docs/TRADING_THESIS.md` e `docs/ARCHITECTURE.md` (local-only).
Estado atual e próximos passos em `docs/SESSION_HANDOFF.md`.

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
- Trabalho atual é **local-only** (sem push). Quando houver remote, commit + push ao final de cada task.
- Mensagens de commit: padrão `<tipo>(<escopo>): <descrição>` (feat, fix, docs, refactor, test, chore).
- **`docs/` e `tests/.local/` são locais-only** — não trackear.

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

## Comunicação

- Resposta em **pt-br**.
- Concisa: 1-3 frases para perguntas simples; expandir só quando complexo.
- Sem emojis salvo solicitação explícita.
- Sem timing estimates ("vai levar X horas").
- Após operações, confirmar brevemente em vez de explicar tudo.
