"""gocam init — create a new process workspace."""

from datetime import date
from pathlib import Path

import click

from gocam.config import PROCESS_SUBDIRS, PROCESSES_DIR
from gocam.models import Expert, Paper, ProcessMeta
from gocam.utils.display import console, print_error, print_process_created
from gocam.utils.io import write_json


def _slug_to_name(slug: str) -> str:
    """Convert 'ampa-receptor-endocytosis' → 'Ampa receptor endocytosis'."""
    return slug.replace("-", " ").replace("_", " ").capitalize()


@click.command("init")
@click.argument("name")
@click.option("--species", default="Mus musculus", show_default=True, help="Species (e.g. 'Mus musculus').")
@click.option(
    "--complexity",
    type=click.Choice(["LOW", "MID", "HIGH"], case_sensitive=False),
    default="MID",
    show_default=True,
    help="Expected model complexity.",
)
@click.option("--expert-name", default=None, help="Domain expert's full name.")
@click.option("--expert-institution", default=None, help="Expert's institution.")
@click.option("--expert-email", default=None, help="Expert's e-mail address.")
@click.option("--pmid", multiple=True, help="PMID(s) to associate (can repeat: --pmid 12345 --pmid 67890).")
def init_command(
    name: str,
    species: str,
    complexity: str,
    expert_name: str | None,
    expert_institution: str | None,
    expert_email: str | None,
    pmid: tuple[str, ...],
) -> None:
    """Create a new GO-CAM process workspace at processes/NAME.

    Creates the directory structure and an initial meta.json. After running
    this command, place your source files in processes/NAME/input/ and then
    run 'gocam extract-all' (or 'gocam run NAME' for the full pipeline).

    \b
    DIRECTORY STRUCTURE CREATED
      processes/NAME/
        meta.json           Process metadata (species, expert, papers)
        input/              Place source files here (.txt, .pdf, .pptx, .png, .jpg)
        extractions/        Populated by 'gocam extract-all'
        validation/         Populated by 'gocam validate'
        narratives/         Populated by 'gocam narrative'

    \b
    EXAMPLES
      gocam init vesicle-fusion
      gocam init ampa-endocytosis --species "Rattus norvegicus" --complexity HIGH
      gocam init clathrin-pathway --expert-name "Dr. Jane Smith" --pmid 12345678
    """
    process_dir: Path = PROCESSES_DIR / name

    if process_dir.exists():
        print_error(f"Process '{name}' already exists at {process_dir}")
        raise SystemExit(1)

    # Build metadata
    expert: Expert | None = None
    if expert_name:
        expert = Expert(
            name=expert_name,
            institution=expert_institution,
            email=expert_email,
        )

    papers: list[Paper] = [Paper(pmid=p, role="primary_evidence") for p in pmid]

    meta = ProcessMeta(
        process_name=_slug_to_name(name),
        species=species,
        complexity=complexity.upper(),
        expert=expert,
        created=date.today().isoformat(),
        status="extraction",
        papers=papers,
    )

    # Create directory structure
    process_dir.mkdir(parents=True, exist_ok=False)
    for subdir in PROCESS_SUBDIRS:
        (process_dir / subdir).mkdir()

    # Write meta.json
    write_json(process_dir / "meta.json", meta)

    print_process_created(name, process_dir)
