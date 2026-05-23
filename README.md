# Máquina de Dinheiro

Sistema de trading algorítmico contínuo (24/7) em mercados de criptomoedas.

**Estratégia:** Grid Adaptativo com camada de Market Making (Avellaneda-Stoikov + skew por Order Flow Imbalance), operando majoritariamente com ordens Maker.

**Meta:** Sharpe ≥ 1.5, retorno líquido 12-25% a.a. (≈ 1-2%/mês em média, com variância mensal).

> ⚠️ Este software é um sistema de trading real. Mau uso pode resultar em perda total de capital. Nenhuma garantia de retorno é oferecida.

---

## Estado Atual

**Fases 1–6 completas.** Stack ponta-a-ponta em produção local: ingest WS Binance → TimescaleDB, Risk Engine com auto-halt por drawdown, OMS com REST Binance assinado (HMAC SHA-256), Strategy (Grid Adaptativo + Avellaneda-Stoikov MM com skew OFI), backtest event-driven e main loop `mdd run`.

**Cobertura:** 98 testes (4 deselected/live). Lint, format, mypy strict e pytest verdes. Risk Engine 94% cov.

Próximo passo é humano: abrir conta Binance, configurar `.env` com API keys (saque bloqueado) e validar em testnet.

---

## Stack

- **Linguagem:** Python 3.11+
- **Async runtime:** `asyncio` + `uvloop`
- **Serialização:** `msgspec`
- **Framework de trading:** `nautilus_trader` (base) + módulos próprios para Risk Engine
- **Backtest MM:** `hftbacktest`
- **Banco tick data:** TimescaleDB
- **Banco transacional:** PostgreSQL (mesma instância)
- **Observabilidade:** Prometheus + Grafana + Alertmanager → Telegram
- **Container:** Docker + Docker Compose
- **Gerenciador de pacotes:** [`uv`](https://docs.astral.sh/uv/)

---

## Setup de Desenvolvimento

### Pré-requisitos

- Python 3.11+
- Docker Desktop (Windows/Mac) ou Docker Engine + Compose v2 (Linux)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (`pip install uv` ou `winget install astral-sh.uv`)

### Instalação

```powershell
# 1. Clonar e entrar no diretório
cd "Maquina de Dinheiro"

# 2. Criar venv e instalar dependências
uv sync --all-extras

# 3. Ativar venv
.\.venv\Scripts\Activate.ps1

# 4. Copiar variáveis de ambiente
Copy-Item .env.example .env
# Editar .env com suas credenciais (NUNCA commitar este arquivo)

# 5. Subir stack de infraestrutura (TimescaleDB + Prometheus + Grafana)
docker compose up -d

# 6. Validar instalação
uv run pytest
uv run ruff check .
uv run mypy .
```

### Comandos comuns

```powershell
uv run pytest                        # Testes (exclui integration e live)
uv run pytest -m integration         # Testes que tocam TimescaleDB local
uv run pytest -m live                # Smoke contra Binance Testnet (rede real)
uv run pytest --cov=src              # Cobertura
uv run ruff check . --fix            # Lint + autofix
uv run ruff format .                 # Formatação
uv run mypy src tests                # Type check
docker compose logs -f app           # Logs do bot
docker compose down                  # Parar stack
docker compose down -v               # Parar + limpar volumes (CUIDADO: apaga dados)
```

### Ingestão de market data

```powershell
# 1. Subir apenas o banco
docker compose up -d timescaledb

# 2. Validar persistência com TimescaleDB real
uv run pytest -m integration -q

# 3. Iniciar ingestão WS Binance Testnet -> TimescaleDB
uv run mdd ingest --symbol BTCUSDT --testnet --batch-size 50 --flush-interval-s 1.0

# 4. Inspecionar dados gravados
docker exec -it mdd-timescaledb psql -U mdd -d mdd `
  -c "SELECT COUNT(*), MAX(ts) FROM book_snapshots WHERE symbol='BTCUSDT';" `
  -c "SELECT COUNT(*), MAX(ts) FROM trades_tape WHERE symbol='BTCUSDT';"
```

### Motor de trading

```powershell
# Testnet (padrão). Mainnet exige MDD_ENV=production.
uv run mdd run --symbol BTCUSDT --testnet
```

O runner conecta WS Binance, aplica gate do Risk Engine, gera quotes via `AdaptiveGrid`
e submete via REST assinado. `Ctrl+C` cancela tudo e fecha conexões.
Métricas Prometheus em `:9100/metrics`.

---

## Estrutura

```text
src/
  core/         # Event loop, configuração, tipos compartilhados
  data/         # Market Data Handler (WebSocket, order book L2)
  strategy/    # Strategy Engine (Grid + MM)
  risk/         # Risk Engine (processo isolado)
  oms/          # Order Management System
  backtest/     # Wrappers para hftbacktest e walk-forward
  metrics/      # Prometheus exporters
infra/
  docker/       # Dockerfiles auxiliares
  prometheus/   # Configuração Prometheus
  grafana/      # Dashboards e datasources
tests/          # Trackeado (CI roda); tests/.local/ é local-only
docs/           # LOCAL ONLY (journal de desenvolvimento)
notebooks/      # notebooks/scratch/ é local-only
```

> **Regra do projeto:** `docs/`, `tests/.local/` e `notebooks/scratch/` são **local-only**. Apenas o `README.md` da raiz é documentação canônica versionada.

---

## Pipeline de Implantação

| Fase | Status | Critério go/no-go |
| --- | --- | --- |
| 0 — Fundação | ✅ | `docker compose up` sobe stack, lint+mypy+tests verdes |
| 1 — Market data | ✅ | WS + gap detector + TimescaleDB + `mdd ingest` |
| 2 — Risk Engine | ✅ | Cobertura ≥ 75% (atual: 94%), fail-closed, auto-halt drawdown |
| 3 — OMS | ✅ | REST Binance assinado HMAC-SHA256, cancel_all, reconcile |
| 4 — Strategy | ✅ | AdaptiveGrid + Avellaneda-Stoikov MM com skew OFI |
| 5 — Backtest | ✅ | Engine event-driven com PnL realized + MtM + fees maker |
| 6 — Main loop | ✅ | `mdd run` integra WS → Risk → Strategy → OMS |
| 7 — Paper trading | ⏳ | 14d testnet, métricas ±15% do backtest, uptime ≥ 99.5% |
| 8 — Produção micro-lote | ⏳ | 30d com Sharpe rolling ≥ 1.2 antes de escalar |

---

## Regras de Produção (Inegociáveis)

1. **Zero ruído em CI/CD.** Nenhum commit ou push com erro/warning de lint, format, mypy, testes ou painel Problemas. Logs limpos sempre.
2. **Zero duplicidade / verbosidade.** Código e arquivos enxutos. Se um arquivo não agrega, ele não existe — nem local, nem no repo.
3. **Repo mínimo.** Só entram arquivos estritamente necessários ao deploy. Tudo o que não roda em produção vai para `.gitignore`/`.dockerignore`.
4. **README sempre atualizado e profissional.** Mudou comportamento, stack, comando ou estrutura? README reflete antes do merge.
5. **Auditoria sob demanda** (invocar `/audit`): valida regras 1–4, alinhamento com best practices enterprise (frontend, backend, segurança), e gera relatório com ações corretivas.

Detalhes operacionais e checklists em `.github/copilot-instructions.md`.

---

## Segurança

- API keys com permissão **apenas leitura + execução** (saque **bloqueado**).
- Risk Engine em processo isolado com kill switch externo.
- Saque programado de 20% do lucro mensal para cold wallet.
- Segredos via `.env` local + (futuramente) Doppler/SOPS em produção.

---

## Licença

Proprietário — Uillen Machado. Todos os direitos reservados.
