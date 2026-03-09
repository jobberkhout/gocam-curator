"""File I/O helpers: JSON read/write and prompt loading."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from gocam.config import PROMPTS_DIR


def read_json(path: Path) -> Any:
    """Read and parse a JSON file."""
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Write data to a JSON file (pretty-printed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if isinstance(data, BaseModel):
            # model_dump_json doesn't support ensure_ascii=False directly,
            # so round-trip through json.dumps for consistent unicode output.
            json.dump(data.model_dump(), f, indent=2, ensure_ascii=False)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_prompt(name: str) -> str:
    """Load a prompt from the prompts/ directory by filename (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt() -> str:
    """Load the shared system prompt (prompts/system.md)."""
    return load_prompt("system")
