"""GO-CAM Curator CLI — main entry point."""

import click

from gocam.commands.enrich import enrich_command
from gocam.commands.extract import extract_command
from gocam.commands.extract_all import extract_all_command
from gocam.commands.init import init_command
from gocam.commands.narrative import narrative_command
from gocam.commands.run import run_command
from gocam.commands.search import search_command
from gocam.commands.status import status_command
from gocam.commands.validate import validate_command


@click.group()
@click.version_option(package_name="gocam-curator")
def main() -> None:
    """GO-CAM Curator — build causal activity models for synaptic biological processes.

    \b
    QUICK START
      gocam run <process>           Run the full pipeline in one command.

    \b
    STEP-BY-STEP PIPELINE
      1. gocam init <name>          Create a workspace at processes/<name>/.
                                    Drop your input files into processes/<name>/input/.
      2. gocam extract-all          Extract GO-CAM claims from all input files (AI).
                                    Produces nodes (molecular activities) and edges
                                    (causal relations) with evidence.
                                    Output: extractions/*.json
      3. gocam validate             Verify all claims against live databases (no AI).
                                    Looks up proteins (UniProt), GO terms (QuickGO),
                                    ECO codes (OLS4), PMIDs (PubMed), DOIs (CrossRef),
                                    and synaptic annotations (SynGO).
                                    Output: validation/validated_claims.json
      4. gocam narrative            Assemble an expert-readable validation document
                                    (no AI). Each claim shows verified IDs, database
                                    status, and clickable DOI links.
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
      LLM_PROVIDER=anthropic|gemini|vertex  AI provider (default: anthropic)
      ANTHROPIC_API_KEY=...            Required when LLM_PROVIDER=anthropic
      GEMINI_API_KEY=...               Required when LLM_PROVIDER=gemini
      GOOGLE_CLOUD_PROJECT=...         Required when LLM_PROVIDER=vertex
      VERTEX_LOCATION=us-central1      Vertex AI region (default: us-central1)
      ANTHROPIC_MODEL=claude-...       Override the Anthropic model (default: claude-sonnet-4-5)
      GEMINI_MODEL=gemini-...          Override the Gemini model  (default: gemini-2.5-pro)
      API_CALL_DELAY=5                 Seconds between API calls (overrides all providers)
      ANTHROPIC_API_CALL_DELAY=2       Anthropic-specific delay (default: 2)
      GEMINI_API_CALL_DELAY=10         Gemini-specific delay    (default: 10)
      VERTEX_API_CALL_DELAY=2          Vertex-specific delay    (default: 2)

    \b
    UTILITIES
      gocam search <gene>           Look up a gene across UniProt, QuickGO, and OLS4.
                                    No LLM — fast, pure database queries.
      gocam enrich <process>        Discover new literature via PubMed and extract
                                    from it. Kept strictly separate from the main pipeline.

    \b
    EXAMPLE WORKFLOW
      # 1. Create a process workspace
      gocam init vesicle-fusion --species "Rattus norvegicus" --expert-name "Dr. Smith"

      # 2. Drop papers, slides, and figures into input/, then run the full pipeline:
      gocam run vesicle-fusion

      # 3. Check progress across all processes
      gocam status

      # 4. View the expert validation document
      open processes/vesicle-fusion/narratives/claims_v1.md

      # 5. Discover additional literature
      gocam enrich vesicle-fusion --max-papers 15
    """


main.add_command(init_command)
main.add_command(extract_command)
main.add_command(extract_all_command)
main.add_command(validate_command)
main.add_command(narrative_command)
main.add_command(status_command)
main.add_command(run_command)
main.add_command(search_command)
main.add_command(enrich_command)
