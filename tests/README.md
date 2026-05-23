# Tests — Local-Only

Esta pasta contém os testes do projeto. Por convenção, **testes são local-only**
— ficam no repositório para o CI rodar, mas não vão para o Docker build de produção
(excluídos via `.dockerignore`).

Rodar testes:

```powershell
uv run pytest
uv run pytest -m "not integration and not live"  # apenas unitários
uv run pytest --cov=src --cov-report=term-missing
```
