"""CLI principal — entrypoint para operação e diagnóstico."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core._version import __version__
from core.config import get_settings
from core.logging import configure_logging

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


if __name__ == "__main__":
    app()
