# CLAUDE.md — gocam-curator

## What This Project Is

A Python CLI tool (`gocam`) that helps a bioinformatics curator build GO-CAM (Gene Ontology Causal Activity Models) for synaptic processes. The curator works with domain experts (neuroscientists) who provide biological knowledge. This tool assists the curator — never the expert — with extracting information from papers/slides/cartoons, mapping biology to ontology terms, verifying those terms against databases, and generating expert-readable validation documents.

## Domain Context (READ THIS FIRST)

GO-CAM models represent biological processes as networks of molecular activities. Each node is a **Molecular Function** (what a protein does), connected by causal edges (how activities regulate each other). The model also captures the Biological Process, Cellular Component, evidence (paper + figure), and the experimental method used (ECO code).

### Critical GO-CAM Rules (enforce these in all prompts)

1. **NO BINDING RULE**: Never use any GO term containing "binding" as a Molecular Function. Binding is an interaction (an edge), not a function (a node). If a text only says "Protein A binds Protein B", the function is unknown — do NOT invent a binding MF.

2. **SUBSTRATE INDEPENDENCE**: A Molecular Function term must NEVER be named after its specific target. Wrong: "syntaxin chaperone activity", "AMPA receptor phosphorylator". Right: "protein kinase activity" with a `has_input` edge to the specific target.

3. **THE CAR TEST**: If a knockout experiment shows a process failing, ask: did this specific process fail, or did the entire general machinery collapse? Removing a car's engine makes the radio stop, but the engine doesn't regulate the radio. Distinguish DIRECT regulation from STRUCTURAL prerequisite.

4. **ALL GO IDs ARE UNVERIFIED BY DEFAULT**: LLMs hallucinate GO IDs. Every ID suggested by Claude must be marked `"verified": false` until `gocam verify` checks it against QuickGO/UniProt/EBI.

5. **EXTRACTION ≠ INTERPRETATION**: When analyzing images/text, extract what is there. Do not infer molecular functions from arrows in cartoons. A drawn arrow means "the expert thinks A does something to B" — not "A directly positively regulates B."

## Architecture

See `gocam_tool_architecture.md` for the full technical spec with JSON examples.

### Commands

| Command | Phase | What it does |
|---------|-------|-------------|
| `gocam init <name>` | Setup | Creates a process workspace under `processes/` |
| `gocam extract <file>` | Phase 2 | Extracts entities/interactions from .txt, .png, .jpg, .pptx, .pdf |
| `gocam report` | Phase 2b | Synthesizes all extractions into one reviewable Markdown report |
| `gocam translate` | Phase 4 | Maps extracted biology → GO terms, ECO codes, evidence records |
| `gocam verify` | Phase 4b | Checks all GO/ECO/UniProt IDs against live databases (no AI) |
| `gocam narrative` | Phase 5 | Converts evidence records → numbered claims for expert review |
| `gocam status` | — | Shows overview of all processes and their progress |

### Project Structure

```
gocam-curator/
├── CLAUDE.md                       # This file
├── gocam_tool_architecture.md      # Full technical spec
├── pyproject.toml
├── .env                            # ANTHROPIC_API_KEY (gitignored)
├── prompts/                        # AI prompts as editable .md files
│   ├── system.md                   # Shared: GO-CAM rules, role, JSON output format
│   ├── extract_text.md             # Text → entities, quotes, gaps
│   ├── extract_visual.md           # Image → labels, arrows, compartments, gaps
│   ├── extract_slides.md           # PPTX-specific: skip titles, extract notes
│   ├── report.md                   # Merge all extractions → single report
│   ├── translate.md                # Biology → GO/ECO mapping (strict rules)
│   └── narrative.md                # Evidence records → expert-readable claims
├── src/
│   └── gocam/
│       ├── __init__.py
│       ├── cli.py                  # Click CLI: main entry point
│       ├── config.py               # Paths, API keys, settings
│       ├── commands/               # One module per command
│       ├── models/                 # Pydantic v2 data models
│       ├── services/               # Anthropic API, QuickGO, UniProt, EBI, file processors
│       └── utils/                  # Rich display, file I/O helpers
└── processes/                      # Data directory (one folder per biological process)
```

### Data Flow

```
Input files (.txt, .png, .pptx, .pdf)
    │
    ▼
gocam extract  ──→  extractions/*.json  (per file)
    │
    ▼
gocam report   ──→  extractions/REPORT.md  (merged, deduplicated)
    │
    ▼
[Curator reviews report, has expert meeting]
    │
    ▼
gocam translate ──→  evidence_records/records.json  (GO/ECO mapped, UNVERIFIED)
    │
    ▼
gocam verify   ──→  verification/report.json  (checked against live DBs)
    │
    ▼
gocam narrative ──→  narratives/claims_v1.md  (expert-readable)
```

## Tech Stack

- **Python 3.10+**
- **Click** for CLI
- **Pydantic v2** for data models and validation
- **Anthropic SDK** for Claude API (text + vision)
- **httpx** for async HTTP to QuickGO/UniProt/EBI
- **Rich** for terminal output (tables, progress bars, colored status)
- **python-pptx** for extracting slides and speaker notes
- **PyMuPDF (fitz)** for PDF text and image extraction
- **Pillow** for image resizing before API calls
- **python-dotenv** for .env loading

## Build Order

Follow this order. Build and test each step before moving to the next.

1. **Project scaffolding**: pyproject.toml, directory structure, `__init__.py` files, .gitignore, .env.example
2. **Pydantic models** (`models/`): Entity, Interaction, Evidence, Process — these are the schema everything else depends on
3. **Config** (`config.py`): paths, API key loading, process directory resolution
4. **`gocam init`**: create process workspace with meta.json + subdirectories
5. **File processors** (`services/file_processor.py`, `pptx_reader.py`, `pdf_reader.py`): detect file type, extract text/images
6. **Anthropic service** (`services/anthropic.py`): wrapper for Claude API with text and vision support, prompt loading from `prompts/` directory
7. **`gocam extract`**: orchestrate file processing → prompt selection → API call → save extraction JSON
8. **`gocam report`**: load all extractions, merge, deduplicate, generate REPORT.md
9. **`gocam translate`**: load extractions + report, run translation prompt, save evidence records
10. **`gocam verify`** (`services/quickgo.py`, `uniprot.py`, `eco.py`): pure API calls, no AI — verify every GO/ECO/UniProt ID
11. **`gocam narrative`**: load verified evidence records, generate expert-readable claims
12. **`gocam status`**: scan all process directories, show Rich table with progress
13. **Polish**: error handling, retries, progress bars, edge cases

## Key Design Principles

- **Prompts are files, not hardcoded strings.** Load from `prompts/` at runtime so the curator can edit GO-CAM rules without touching code.
- **Every AI command loads `system.md` first**, then the command-specific prompt, then the user data. The system prompt contains the domain rules that must always be enforced.
- **JSON as intermediate format.** All data between steps is JSON. Parseable, diffable, git-friendly.
- **One folder per process.** The file system is the database. No external DB needed.
- **Extraction and translation are separate steps.** Phase 2 asks "what does the text/image say?" Phase 4 asks "what GO terms fit?" Combining them causes GO ID hallucination.
- **`gocam verify` uses NO AI.** It's pure REST API calls to QuickGO, UniProt, and EBI/OLS. This is the truth layer.

## External APIs

```
# QuickGO — GO term verification
GET https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{GO_ID}

# UniProt — protein lookup
GET https://rest.uniprot.org/uniprotkb/search?query=gene:{SYMBOL}+organism_id:{TAXON}&fields=accession,gene_names,go_id

# OLS/EBI — ECO code verification
GET https://www.ebi.ac.uk/ols4/api/ontologies/eco/terms?iri=http://purl.obolibrary.org/obo/{ECO_ID}
```

## Coding Conventions

- Use `click` for all CLI commands with `@click.command()` decorators
- Use `rich.console.Console` for all terminal output — no bare `print()`
- Use `pydantic.BaseModel` for all data structures — validate on load
- Use `pathlib.Path` everywhere, no string path manipulation
- Use `httpx.AsyncClient` for external API calls with proper timeouts and retries
- All JSON output should be pretty-printed with indent=2
- Type hints on all functions
- Docstrings on all public functions and classes

## Testing

- Test each command manually after building: `gocam init test-process`, then inspect the output
- For `gocam extract`, use a short sample text first before processing full papers
- For `gocam verify`, test with known-good GO IDs (GO:0004674 = protein serine/threonine kinase activity) and known-bad IDs
- For vision: test with a simple diagram PNG before processing full slide decks

## What NOT To Do

- Do NOT hardcode GO terms or ECO codes anywhere in the source code
- Do NOT combine extraction and translation into one step
- Do NOT trust any GO ID from an LLM without verification
- Do NOT use `print()` — use Rich
- Do NOT put prompts inside Python strings — keep them in `prompts/*.md`
- Do NOT build a web UI — this is a CLI tool
- Do NOT use a database — the file system is the database
