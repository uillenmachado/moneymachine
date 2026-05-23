---
mode: agent
description: "Adiciona uma entrada em docs/CHANGELOG.md ao concluir uma task."
---

# Add Changelog Entry

Você acabou de concluir uma task. Adicione entrada em `docs/CHANGELOG.md`.

## Passos

1. Leia `docs/CHANGELOG.md` (crie se não existir, com H1 "Changelog — Máquina de Dinheiro").
2. **Anteponha** entrada no topo (mais recente primeiro).
3. Formato: data (AAAA-MM-DD) + tipo + escopo + descrição + commit hash (se houver).

## Template

```markdown
## AAAA-MM-DD

### Added / Changed / Fixed / Removed

- **<escopo>:** descrição da mudança. (`<commit-hash>`)
```

## Tipos

- **Added** — funcionalidade nova.
- **Changed** — mudança em funcionalidade existente.
- **Fixed** — correção de bug.
- **Removed** — remoção de funcionalidade/arquivo.
- **Refactored** — mudança interna sem alterar comportamento externo.
- **Docs** — apenas documentação.
- **Infra** — Docker, CI, dependencies.

## Exemplo

```markdown
## 2026-04-21

### Added

- **risk-engine:** implementado `RiskGate.check_pre_trade()` com gates de drawdown, latência e inventário. Cobertura 78%. (`a3f9c12`)

### Fixed

- **markdown:** corrigido MD060 em `docs/TRADING_THESIS.md` (pipes sem espaço). (`b7e2d44`)
```

## Critérios

- Uma entrada por **commit** ou por **conjunto coeso de mudanças**.
- Linguagem objetiva: descreva o que mudou, não como foi feito.
- Referencie arquivos/escopos relevantes.
- Se for mudança breaking, adicione `**BREAKING:**` no início.
