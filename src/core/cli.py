"""CLI principal — entrypoint para operação e diagnóstico."""

from __future__ import annotations

import asyncio
import contextlib
import signal

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core._version import __version__
from core.config import get_settings
from core.logging import configure_logging
from data.binance_ws import BinanceWSClient
from data.ingestion import IngestionService
from data.storage import TimescaleStore

app = typer.Typer(
    name="mdd",
    help="Máquina de Dinheiro — sistema de trading algorítmico.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Exibe a versão do sistema."""
    console.print(f"Máquina de Dinheiro v{__version__}")


@app.command()
def info() -> None:
    """Exibe configuração efetiva (sem segredos)."""
    s = get_settings()
    table = Table(title="Configuração Efetiva", show_header=True)
    table.add_column("Chave", style="cyan")
    table.add_column("Valor", style="white")
    table.add_row("env", str(s.env))
    table.add_row("exchange", s.exchange)
    table.add_row("exchange_testnet", str(s.exchange_testnet))
    table.add_row("api_key_set", "sim" if s.api_key.get_secret_value() else "não")
    table.add_row("db_host", s.db.host)
    table.add_row("db_port", str(s.db.port))
    table.add_row("metrics_port", str(s.metrics_port))
    table.add_row("capital_usd", f"${s.capital_usd:,.2f}")
    table.add_row("max_daily_dd_pct", f"{s.risk.max_daily_drawdown_pct}%")
    table.add_row("latency_p99_limit_ms", str(s.risk.latency_p99_ms_limit))
    table.add_row("telegram_enabled", "sim" if s.telegram.enabled else "não")
    console.print(table)


@app.command()
def run() -> None:
    """Inicia o motor de trading. (Placeholder — implementado na Fase 4.)"""
    s = get_settings()
    configure_logging(level=s.log_level, json_output=s.log_json)
    console.print(
        Panel.fit(
            "[yellow]Motor de trading ainda não implementado.[/yellow]\n"
            "Estamos na [bold]Fase 0 — Fundação[/bold].\n"
            "Implementação ocorre na Fase 4 (Engenharia do Core).",
            title="MdD",
            border_style="yellow",
        )
    )


@app.command()
def ingest(
    symbol: list[str] = typer.Option(  # noqa: B008
        ["BTCUSDT"],
        "--symbol",
        "-s",
        help="Símbolos a ingerir (pode repetir).",
    ),
    testnet: bool = typer.Option(default=True, help="Usar testnet da Binance Spot."),
    batch_size: int = typer.Option(default=50, min=1, max=1000),
    flush_interval_s: float = typer.Option(default=1.0, min=0.1, max=60.0),
) -> None:
    """Conecta na Binance WS e persiste book + trades em TimescaleDB."""
    s = get_settings()
    configure_logging(level=s.log_level, json_output=s.log_json)
    console.print(
        Panel.fit(
            f"Ingestão Binance ({'testnet' if testnet else 'mainnet'})\n"
            f"Símbolos: {', '.join(symbol)}\n"
            f"Batch: {batch_size} · flush: {flush_interval_s}s",
            title="MdD ingest",
            border_style="cyan",
        )
    )
    asyncio.run(
        _run_ingest(
            symbol,
            testnet=testnet,
            batch_size=batch_size,
            flush_s=flush_interval_s,
        )
    )


async def _run_ingest(
    symbols: list[str],
    *,
    testnet: bool,
    batch_size: int,
    flush_s: float,
) -> None:
    s = get_settings()
    store = TimescaleStore(s.db.dsn)
    await store.connect()
    client = BinanceWSClient(symbols=symbols, testnet=testnet)
    service = IngestionService(
        client,
        store,
        batch_size=batch_size,
        flush_interval_s=flush_s,
    )

    loop = asyncio.get_running_loop()
    # Windows não suporta add_signal_handler — ignora silenciosamente.
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(service.stop()),
            )

    try:
        await service.run()
    finally:
        await store.close()


if __name__ == "__main__":
    app()
