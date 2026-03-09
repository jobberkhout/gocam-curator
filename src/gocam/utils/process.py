"""Utilities for resolving the active process directory."""

from __future__ import annotations

from pathlib import Path

import click

from gocam.config import PROCESSES_DIR
from gocam.utils.io import read_json


def resolve_process(name: str | None) -> Path:
    """Return the active process directory.

    Resolution order:
    1. If --process NAME is given, use processes/NAME.
    2. If the current working directory contains meta.json, use CWD.
    3. If exactly one process exists in processes/, use it.
    4. Otherwise error — user must supply --process.
    """
    if name:
        p = PROCESSES_DIR / name
        if not p.exists():
            raise click.BadParameter(
                f"Process '{name}' not found at {p}",
                param_hint="'--process'",
            )
        if not (p / "meta.json").exists():
            raise click.BadParameter(
                f"Directory '{p}' exists but has no meta.json. "
                "Was it created with 'gocam init'?",
                param_hint="'--process'",
            )
        return p

    # Check if we're inside a process directory
    cwd = Path.cwd()
    if (cwd / "meta.json").exists():
        return cwd

    # Scan processes/
    if not PROCESSES_DIR.exists():
        raise click.UsageError(
            "No processes directory found. Run 'gocam init <name>' first."
        )

    candidates = sorted(
        p for p in PROCESSES_DIR.iterdir()
        if p.is_dir() and (p / "meta.json").exists()
    )

    if not candidates:
        raise click.UsageError(
            "No processes found. Run 'gocam init <name>' first."
        )
    if len(candidates) == 1:
        return candidates[0]

    names = ", ".join(p.name for p in candidates)
    raise click.UsageError(
        f"Multiple processes found: {names}\n"
        "Use --process <name> to specify which one."
    )


def load_meta(process_dir: Path) -> dict:
    """Load meta.json for a process directory."""
    return read_json(process_dir / "meta.json")
