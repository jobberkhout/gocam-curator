"""Shared Rich console and display helpers."""

import threading
import time
from contextlib import contextmanager
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


@contextmanager
def timed_status(message: str):
    """Spinner that shows elapsed seconds — use instead of console.status() for long LLM calls."""
    start = time.monotonic()
    stop = threading.Event()

    with console.status(message) as status:
        def _tick() -> None:
            while not stop.is_set():
                time.sleep(1)
                elapsed = int(time.monotonic() - start)
                status.update(f"{message} ({elapsed}s)")

        t = threading.Thread(target=_tick, daemon=True)
        t.start()
        try:
            yield
        finally:
            stop.set()
            t.join()


def print_success(message: str) -> None:
    console.print(f"[bold green]OK[/bold green]  {message}")


def print_error(message: str) -> None:
    console.print(f"[bold red]ERROR[/bold red]  {message}")


def print_warning(message: str) -> None:
    console.print(f"[bold yellow]WARN[/bold yellow]  {message}")


def print_info(message: str) -> None:
    console.print(f"[dim]INFO[/dim]  {message}")


def print_process_created(name: str, process_dir: Path) -> None:
    """Display a summary panel after gocam init."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("directory", str(process_dir))
    table.add_row("meta.json", str(process_dir / "meta.json"))
    table.add_row("subdirs", "input/  extractions/  evidence_records/  verification/  narratives/")

    panel = Panel(
        table,
        title=f"[bold green]Process created:[/bold green] {name}",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()
    console.print("Next steps:")
    console.print(f"  1. Drop input files into [bold]{process_dir / 'input'}[/bold]")
    console.print(f"  2. Run [bold]gocam extract <file>[/bold] for each input file")
    console.print(f"  3. Run [bold]gocam report[/bold] to synthesize all extractions")
