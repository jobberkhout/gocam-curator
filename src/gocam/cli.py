"""GO-CAM Curator CLI — main entry point."""

import click

from gocam.commands.extract import extract_command
from gocam.commands.extract_all import extract_all_command
from gocam.commands.init import init_command
from gocam.commands.narrative import narrative_command
from gocam.commands.report import report_command
from gocam.commands.run import run_command
from gocam.commands.status import status_command
from gocam.commands.translate import translate_command
from gocam.commands.verify import verify_command


@click.group()
@click.version_option(package_name="gocam-curator")
def main() -> None:
    """GO-CAM Curator — build causal activity models for synaptic biological processes.

    \b
    QUICK START
      gocam run <process>           Run the full pipeline in one command.
      gocam run <process> --deep    Run with a second-pass extraction.

    \b
    STEP-BY-STEP PIPELINE
      1. gocam init <name>          Create a workspace at processes/<name>/.
                                    Drop your input files into processes/<name>/input/.
      2. gocam extract-all          Extract entities and interactions from all input files.
                                    Output: extractions/*.json
      3. gocam report               Synthesize all extractions into one Markdown report.
                                    Output: extractions/REPORT.md
      4. gocam translate            Map biology to GO terms and ECO codes.
                                    Output: evidence_records/records.json (all IDs unverified)
      5. gocam verify               Check all GO/ECO/UniProt IDs against live databases.
                                    Output: verification/report.json, records.json updated
      6. gocam narrative            Convert evidence records into expert-readable claims.
                                    Output: narratives/claims_v1.md

    \b
    SUPPORTED FILE TYPES
      .txt  .md    Plain-text papers, notes, methods sections
      .pdf         Scientific papers — text extracted, figures sent as images.
                   Reference sections are detected and skipped automatically.
      .pptx        Slide decks — each slide processed individually; speaker notes included.
      .png  .jpg   Pathway diagrams, cartoons, Western blot figures

    \b
    CONFIGURATION  (.env file in the project root)
      LLM_PROVIDER=anthropic|gemini    AI provider to use (default: anthropic)
      ANTHROPIC_API_KEY=...            Required when LLM_PROVIDER=anthropic
      GEMINI_API_KEY=...               Required when LLM_PROVIDER=gemini
      ANTHROPIC_MODEL=claude-...       Override the Anthropic model (default: claude-sonnet-4-5)
      GEMINI_MODEL=gemini-...          Override the Gemini model  (default: gemini-2.5-pro)
      API_CALL_DELAY=5                 Seconds between API calls (overrides both providers)
      ANTHROPIC_API_CALL_DELAY=2       Anthropic-specific delay (default: 2)
      GEMINI_API_CALL_DELAY=10         Gemini-specific delay    (default: 10)

    \b
    EXAMPLE WORKFLOW
      # 1. Create a process workspace
      gocam init vesicle-fusion --species "Rattus norvegicus" --expert-name "Dr. Smith"

      # 2. Drop papers, slides, and figures into input/, then run the full pipeline:
      gocam run vesicle-fusion --deep

      # 3. Check progress across all processes
      gocam status

      # 4. View the expert validation document
      open processes/vesicle-fusion/narratives/claims_v1.md
    """


main.add_command(init_command)
main.add_command(extract_command)
main.add_command(extract_all_command)
main.add_command(report_command)
main.add_command(translate_command)
main.add_command(verify_command)
main.add_command(narrative_command)
main.add_command(status_command)
main.add_command(run_command)
