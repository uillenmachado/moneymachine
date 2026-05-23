---
applyTo: "**/*.py"
description: "Convenções Python para o projeto Máquina de Dinheiro."
---

# Convenções Python

## Tipagem

- `from __future__ import annotations` no topo de todo arquivo.
- Anotações em **todas** as funções públicas (parâmetros e retorno).
- Use `Protocol` para interfaces, não classes abstratas (mais leve, duck-typing).
- `TYPE_CHECKING` para imports usados apenas em anotações.
- `mypy strict` é gate: zero `Any` implícito, zero `ignore` sem justificativa.

## Decimal vs Float

**Nunca use `float` em:**

- Preços, quantidades, taxas, fees.
- PnL, equity, drawdown.
- Spreads, ATR, OFI quando usados em decisão de ordem.

**Use `decimal.Decimal`** com contexto de precisão adequada. Em prints/logs, formate com `str(d)` ou `f"{d:.8f}"`, nunca `float(d)`.

`float` é aceitável apenas para:

- Indicadores estatísticos puros (Sharpe, Sortino, correlações).
- Latência em ms (não financeiro).
- Parâmetros calibrados (gamma, kappa).

## Async

- `asyncio` é o runtime padrão. `uvloop` é ativado automaticamente em Linux.
- **NUNCA chame `time.sleep()` em async.** Use `await asyncio.sleep()`.
- **NUNCA bloqueie o loop** com I/O síncrono. Banco: `asyncpg`. HTTP: `httpx`. WS: `websockets`.
- Use `asyncio.TaskGroup` (Python 3.11+) para concorrência estruturada.
- Sempre `await` ou trate como background task — nunca fire-and-forget sem rastreio.

## Hot Path (Strategy + Market Data)

- `msgspec.Struct` com `frozen=True, gc=False` para tipos imutáveis em alta frequência.
- Evite alocações no loop: pré-aloque buffers, reuse objetos.
- Numérico crítico: `numba @njit` quando profiling mostrar gargalo.
- **Não** crie `pandas.DataFrame` no hot path; use `polars` ou numpy puro.

## Estrutura

- Imports no topo (PLC0415 é erro).
- Ordem de imports: stdlib → 3rd party → projeto. Ruff `I` cuida disso.
- Um classe/função pública por arquivo quando >100 linhas.
- `__init__.py` re-exporta apenas o que faz parte da API pública.

## Logging

- `from core.logging import get_logger` → `log = get_logger(__name__)`.
- Logs estruturados: `log.info("event_name", key=value, ...)`, **não** f-string.
- Use `structlog.contextvars.bind_contextvars()` para contexto por request/trade.
- Nunca logue secrets (API keys, passwords). Use `SecretStr.get_secret_value()` apenas no momento da chamada.

## Testes

- Arquivo: `tests/test_<modulo>.py`.
- Marker obrigatório em cada teste: `@pytest.mark.unit` | `integration` | `slow` | `live`.
- Use `pytest-asyncio` (modo `auto` já configurado).
- Fixtures globais em `tests/conftest.py`.
- Property-based com `hypothesis` para funções matemáticas (Avellaneda, OFI, etc).
- **Cobertura mínima Risk Engine: 75%.** Cobertura geral: 60%.

## Segurança

- Validar inputs em boundaries (REST handler, WS handler, CLI). Usar `pydantic`.
- Nunca `eval` / `exec` / `pickle.loads` de fontes externas.
- Tratar erros explicitamente: `except SpecificError`, nunca `except:`.
- `decimal.Decimal` evita ataques de precisão.
