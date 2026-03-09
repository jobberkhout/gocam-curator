# gocam-curator

A Python CLI tool that helps a bioinformatics curator build **GO-CAM (Gene Ontology Causal Activity Models)** for synaptic biological processes.

The curator works with domain experts (neuroscientists, cell biologists) who provide biological knowledge. This tool assists the **curator** — never the expert — with extracting information from papers, slides, and figures; mapping biology to ontology terms; verifying those terms against live databases; and generating expert-readable validation documents.

> **Not a replacement for expertise.** The tool produces structured drafts. The curator reviews everything, consults the domain expert, and makes all final decisions about the model.

---

## Table of Contents

- [What is GO-CAM?](#what-is-go-cam)
- [Installation](#installation)
- [Configuration](#configuration)
- [Pipeline Overview](#pipeline-overview)
- [Commands](#commands)
  - [gocam init](#gocam-init)
  - [gocam extract](#gocam-extract)
  - [gocam extract-all](#gocam-extract-all)
  - [gocam report](#gocam-report)
  - [gocam translate](#gocam-translate)
  - [gocam verify](#gocam-verify)
  - [gocam narrative](#gocam-narrative)
  - [gocam run](#gocam-run)
  - [gocam search](#gocam-search)
  - [gocam enrich](#gocam-enrich)
  - [gocam status](#gocam-status)
- [LLM Prompts Reference](#llm-prompts-reference)
- [Project Structure](#project-structure)
- [Domain Rules Enforced](#domain-rules-enforced)

---

## What is GO-CAM?

GO-CAMs (Gene Ontology Causal Activity Models) represent biological processes as networks of molecular activities. Each node is a **Molecular Function** (what a protein does, e.g. "protein kinase activity"), connected by causal edges (e.g. "directly positively regulates"). Every node is also annotated with:

- **Biological Process** — the larger process the activity is part of
- **Cellular Component** — where it happens
- **Evidence** — paper (PMID), figure, experimental assay, and ECO code

GO-CAMs are built in [Noctua](https://noctua.geneontology.org/). This tool produces the structured, ontology-mapped, evidence-backed input that makes the Noctua modelling step tractable.

---

## Installation

### Requirements

- Python 3.10 or newer
- An API key for Anthropic or Google Gemini (at least one)

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourorg/gocam-curator.git
cd gocam-curator

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package and all dependencies
pip install -e .
```

After installation the `gocam` command is available globally in the environment:

```bash
gocam --help
```

### Dependencies installed automatically

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client |
| `google-genai` | Gemini API client |
| `click` | CLI framework |
| `pydantic>=2.0` | Data validation and schemas |
| `rich` | Terminal formatting (tables, spinners, colour) |
| `httpx` | Async HTTP for database queries |
| `python-dotenv` | `.env` file loading |
| `python-pptx` | PowerPoint slide text and image extraction |
| `pymupdf` | PDF text and figure extraction |
| `pillow` | Image resizing before API calls |

---

## Configuration

Create a `.env` file in the project root (copy from `.env.example`):

```bash
cp .env.example .env
```

Then edit `.env`:

```dotenv
# ── LLM Provider ──────────────────────────────────────────────────────────────
# Choose which AI provider to use: "anthropic" or "gemini"
LLM_PROVIDER=anthropic

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...          # required when LLM_PROVIDER=anthropic
GEMINI_API_KEY=AIza...                # required when LLM_PROVIDER=gemini

# ── Model selection (optional — sensible defaults shown) ──────────────────────
ANTHROPIC_MODEL=claude-sonnet-4-5
GEMINI_MODEL=gemini-2.5-pro

# ── Rate limiting between consecutive API calls (seconds) ─────────────────────
# API_CALL_DELAY sets both providers. Provider-specific vars override it.
API_CALL_DELAY=          # leave blank to use per-provider defaults
ANTHROPIC_API_CALL_DELAY=2
GEMINI_API_CALL_DELAY=10
```

### Switching between providers

```bash
# Use Anthropic Claude (default)
LLM_PROVIDER=anthropic

# Use Google Gemini
LLM_PROVIDER=gemini
```

No code changes are needed — the CLI reads the provider from `.env` at runtime.

### PDF chunking (Gemini only)

Gemini has tighter output limits than Claude. When `LLM_PROVIDER=gemini`, PDFs are automatically split into 2-page chunks per API call. Claude sends the full document in one call. This is configured automatically and requires no user action.

---

## Pipeline Overview

```
Input files (.txt, .pdf, .pptx, .png, .jpg)
        │
        ▼
gocam extract-all ──→  extractions/*.json         (what does each source say?)
        │
        ▼
gocam report      ──→  extractions/REPORT.md      (merged, deduplicated overview)
        │
        ▼  [curator reviews report, has expert meeting]
        │
        ▼
gocam translate   ──→  evidence_records/records.json   (GO terms + ECO codes, UNVERIFIED)
        │
        ▼
gocam verify      ──→  verification/report.json        (checked against live databases)
        │
        ▼
gocam narrative   ──→  narratives/claims_v1.md         (expert-readable validation draft)
```

Or run the whole pipeline in one command:

```bash
gocam run <process-name>
gocam run <process-name> --deep   # with second-pass extraction
```

---

## Commands

### gocam init

Create a new process workspace.

```bash
gocam init ampar-endocytosis
gocam init vesicle-fusion --species "Rattus norvegicus"
gocam init ltp-signalling --complexity HIGH --expert-name "Dr. Smith" --expert-email smith@uni.edu
```

**What it does:**
Creates `processes/<name>/` with subdirectories and a `meta.json` file:

```
processes/ampar-endocytosis/
├── meta.json           # process metadata (species, complexity, expert info)
├── input/              # drop your source files here
├── extractions/        # LLM extraction output per file
├── evidence_records/   # GO-mapped records
├── verification/       # database verification results
└── narratives/         # expert-readable claim drafts
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--species` | `Mus musculus` | Species for UniProt/GO lookups |
| `--complexity` | `MID` | Process complexity: LOW / MID / HIGH |
| `--expert-name` | — | Domain expert name |
| `--expert-email` | — | Domain expert email |

**No LLM is called.** This is a local filesystem operation only.

---

### gocam extract

Extract entities and interactions from a single input file.

```bash
gocam extract path/to/paper.pdf
gocam extract path/to/diagram.png
gocam extract path/to/slides.pptx
gocam extract path/to/notes.txt
```

**Supported file types:**

| Extension | How it is processed |
|-----------|-------------------|
| `.txt`, `.md` | Full text sent as a single API call |
| `.pdf` | Text extracted with PyMuPDF; figures extracted as images; reference sections detected and skipped |
| `.png`, `.jpg`, `.jpeg` | Sent as vision input (image resized if >5 MB) |
| `.pptx` | Each slide processed individually; speaker notes included; title/acknowledgment slides skipped |

**Output:** `extractions/<stem>.json` (one per file; PDFs and PPTX may produce multiple)

**LLM calls made:**
- Text files → `system.md` + `extract_text.md`
- Images → `system.md` + `extract_visual.md` (vision)
- PPTX slides → `system.md` + `extract_slides.md` (vision per slide)
- PDFs → `system.md` + `extract_text.md` for text; `system.md` + `extract_visual.md` for figures

---

### gocam extract-all

Extract from every supported file in `input/` at once.

```bash
gocam extract-all
gocam extract-all --process ampar-endocytosis
gocam extract-all --deep    # second-pass after running gocam report
```

Files already extracted are skipped automatically. Use `--deep` after running `gocam report` to perform a second pass that focuses specifically on content missed in the first extraction (indirect regulators, scaffolding proteins, negative regulators, upstream signals).

**LLM calls made:**
- Standard: same as `gocam extract` per file type
- Deep pass: `system.md` + `extract_deep.md` per file, with the existing REPORT.md injected as context

---

### gocam report

Synthesize all extraction JSONs into a single Markdown report.

```bash
gocam report
gocam report --process ampar-endocytosis
```

**What it does:**
Reads all `extractions/*.json` files and asks the LLM to merge them into a structured reference document. The report includes:

- Table of sources analysed
- Consolidated protein list with activities described per source
- Interaction Map (numbered list: `ProteinA → ProteinB [Fig. X, PMID:XXXXXXXX] | causal type | assay — CONFIDENCE`)
- Conflicts between sources
- Gaps and unanswered questions
- Suggested questions for the expert meeting

**Output:** `extractions/REPORT.md`

**LLM calls made:** `system.md` + `report.md`, with all extraction JSONs concatenated as user message.

> **Curator review point.** Read REPORT.md before running `gocam translate`. This is your chance to catch extraction errors and prepare for the expert meeting.

---

### gocam translate

Map extracted biology to GO terms and ECO codes.

```bash
gocam translate
gocam translate --process ampar-endocytosis
```

**What it does:**
Reads `REPORT.md` and the raw extraction JSONs, then asks the LLM to produce an `EvidenceRecordsFile` — one record per interaction, each containing:

- **Molecular Function** — GO MF term and ID (e.g. `GO:0004674 protein serine/threonine kinase activity`)
- **Biological Process** — GO BP term and ID
- **Cellular Component** — GO CC term and ID
- **Evidence** — exact quote, PMID, figure, assay name, ECO code
- **CAR test result** — DIRECT / STRUCTURAL_PREREQUISITE / INDIRECT
- **Confidence** — HIGH / MEDIUM / LOW
- **Warnings** — rule violations, binding-only interactions, weak evidence

All GO IDs and ECO codes are marked `verified: false`. Run `gocam verify` to check them.

If the report contains more than 25 interactions, the call is automatically split into batches of 5 to avoid output truncation. If the first pass produces fewer records than interactions in the report, a second retry is fired automatically.

**Output:** `evidence_records/records.json`

**LLM calls made:** `system.md` + `translate.md`, with REPORT.md + raw extraction JSONs + PMID table as user message (batched if >25 interactions).

---

### gocam verify

Check all GO, ECO, and UniProt IDs against live databases. **No LLM is used.**

```bash
gocam verify
gocam verify --process ampar-endocytosis
```

**What it does:**
Makes REST API calls to three databases:

| Database | URL | What is checked |
|----------|-----|-----------------|
| [QuickGO](https://www.ebi.ac.uk/QuickGO/) | `GET /services/ontology/go/terms/{GO_ID}` | GO term exists; protein already annotated with it |
| [UniProt](https://rest.uniprot.org/) | `GET /uniprotkb/search?query=gene:{SYMBOL}+organism_id:{TAXON}` | Protein exists; retrieve canonical UniProt accession |
| [OLS4/EBI](https://www.ebi.ac.uk/ols4/) | `GET /api/ontologies/eco/terms?iri=...{ECO_ID}` | ECO code exists; if unknown, search by assay name |

For each record, the command prints:

- **CONFIRMED** — GO term verified AND protein already has this annotation in QuickGO
- **VERIFIED** — GO term exists in QuickGO but protein not yet annotated (new candidate)
- **NOT FOUND** — ID does not exist in the database
- **ECO suggestions** — if eco_code is UNKNOWN, searches OLS4 by assay name and lists candidates

**Output:** `verification/report.json` + in-place updates to `evidence_records/records.json` (sets `verified: true` on confirmed IDs)

---

### gocam narrative

Convert evidence records into a numbered expert-readable validation document.

```bash
gocam narrative
gocam narrative --process ampar-endocytosis
```

**What it does:**
Reads the verified `evidence_records/records.json` and generates a Markdown document addressed to the domain expert. Each numbered claim states:

- What protein does what activity
- The biological process it is part of
- The cellular compartment
- The relationship to its target (direct regulation, structural prerequisite, etc.)
- The supporting evidence (paper, figure, assay)
- ECO code and confidence

The expert reads this document, marks which claims are correct, and flags any errors. This feeds back into the next modelling iteration.

**Output:** `narratives/claims_v1.md` (increments version number on re-runs: v2, v3, …)

**LLM calls made:** `system.md` + `narrative.md`, with records.json as user message.

---

### gocam run

Run the full pipeline in one command.

```bash
gocam run ampar-endocytosis
gocam run ampar-endocytosis --deep
gocam run ampar-endocytosis --skip-verify   # skip database verification
```

**What it does:**
Sequentially runs: `extract-all` → `report` → `translate` → `verify` → `narrative`.
With `--deep`: runs `extract-all` → `report` → `extract-all --deep` → `report` (second pass) → `translate` → `verify` → `narrative`.

Each step is skipped if its output already exists (resume-safe). Progress is shown step by step.

---

### gocam search

Look up a gene or protein across UniProt, QuickGO, and OLS4 simultaneously. **No LLM used.**

```bash
gocam search PICK1
gocam search CAMK2A --species human
gocam search Gria2 --species mouse
```

**What it does:**
Queries three databases in parallel and displays a consolidated Rich terminal report:

1. **UniProt** — protein name, gene synonyms, function description, existing GO annotations (MF/BP/CC)
2. **QuickGO** — all existing GO annotations for the UniProt accession
3. **OLS4** — GO terms containing the gene name in their description

Useful before `gocam translate` to see what GO annotations already exist for a protein of interest.

If a single active process can be auto-detected, results are saved to `processes/<name>/searches/<gene>.json`.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--species` | `mouse` | mouse, human, rat, fly, worm, zebrafish, yeast |
| `--process` | auto-detect | Save to this process explicitly |

**No LLM is called.** Pure REST API queries (httpx async).

---

### gocam enrich

Discover additional literature via PubMed and extract from it.

```bash
gocam enrich ampar-endocytosis
gocam enrich ampar-endocytosis --max-papers 20
gocam enrich ampar-endocytosis --queries-only   # print queries without fetching
```

**What it does:**

1. **Builds PubMed queries** from evidence records: `{gene_symbol} AND {target} AND {biological_process}`
2. **Searches PubMed** via E-utilities (free, no key required, rate-limited to ≤3 req/sec)
3. **Filters** PMIDs already present anywhere in the process (records + extraction JSONs)
4. **Fetches abstracts** for new papers
5. **Extracts** interactions from each abstract using the LLM
6. **Generates** `ENRICHMENT_REPORT.md` labelling each finding as **NEW** or **CONFIRMS** (matched against existing records)

**Strict separation from the main pipeline — originals are never modified:**

| Data | Saved to |
|------|---------|
| PubMed abstract text | `input/enrichment/pubmed_{PMID}.txt` |
| Extraction JSONs | `extractions/enrichment/pubmed_{PMID}.json` |
| Enrichment report | `extractions/enrichment/ENRICHMENT_REPORT.md` |

The curator decides manually which enrichment findings to promote to the main pipeline.

**LLM calls made:** `system.md` + `extract_text.md` per abstract (same as standard text extraction).

---

### gocam status

Show a progress overview of all processes.

```bash
gocam status
```

Displays a Rich table with one row per process:

```
Process                     Complexity  Extracted  Report  Translated   Verified   Narrative  Enrichment
ampar-endocytosis           MID         4 files    ✓       5 records    4/5 ✓      v2 draft   12p/8i
vesicle-fusion              HIGH        8 files    ✓       —            —          —          —
```

The **Enrichment** column shows `{papers}p/{interactions}i` when enrichment has been run.

**No LLM is called.**

---

## LLM Prompts Reference

All prompts live in `prompts/` and are loaded at runtime — the curator can edit them without touching Python code.

### How prompts are assembled

Every LLM call is built from two parts concatenated as the **system message**:

1. `prompts/system.md` — shared rules (always loaded first)
2. A command-specific prompt file (loaded second)

The **user message** contains the actual data (file content, extraction JSONs, REPORT.md).

### `prompts/system.md` — shared rules

Loaded for **every** LLM call. Establishes the curator assistant role and enforces the four non-negotiable GO-CAM rules:

- **No Binding Rule** — never use a GO term containing "binding" as a Molecular Function
- **Substrate Independence Rule** — MF terms must not be named after their specific target
- **CAR Test** — knockout phenotypes must be classified as DIRECT / STRUCTURAL_PREREQUISITE / INDIRECT / UNKNOWN
- **ID verification policy** — all GO IDs, ECO codes, and UniProt IDs must be marked `verified: false`

Also establishes output format (always JSON, with `verified: false` on all IDs, exact quotes, PMID + figure in evidence).

### `prompts/extract_text.md`

**Used by:** `gocam extract` and `gocam extract-all` for `.txt`, `.md`, and PDF text content.

**What it asks the LLM to do:**
Extract entities (proteins/genes) and interactions (directed relationships) from scientific text. For each interaction, capture:
- Source and target entities
- Described action (verbatim, close to the source)
- Exact supporting quote
- PMID (from paper header/footer)
- Figure reference (exact, e.g. "Fig. 3B")
- Assay described
- Causal type (DIRECT / STRUCTURAL_PREREQUISITE / INDIRECT / UNKNOWN)

Instructs the model to extract only what is explicitly stated — no inference, no GO IDs at this stage.

### `prompts/extract_visual.md`

**Used by:** `gocam extract` and `gocam extract-all` for `.png`, `.jpg` images and PDF figures.

**What it asks the LLM to do:**
Analyze a biological diagram or figure. Outputs a `visual_description`, entities with their positions and implied roles, and `connections_shown` (arrows between entities with arrow type and implied relation). Explicitly instructs the model not to interpret arrows as proven causal relationships — they represent "the expert thinks A does something to B."

### `prompts/extract_slides.md`

**Used by:** `gocam extract` and `gocam extract-all` for `.pptx` files.

**What it asks the LLM to do:**
Classify each slide as SKIP (title, acknowledgements, references, methods) or EXTRACT. For relevant slides, uses the same format as `extract_visual.md` but with additional guidance about reading speaker notes and extracting citations/PMIDs visible on slides.

### `prompts/extract_deep.md`

**Used by:** `gocam extract-all --deep` (second-pass extraction).

**What it asks the LLM to do:**
Given the existing REPORT.md as context ("what has already been captured"), re-read the source and return **only content that was missed in the first pass**. Specifically prompts for: indirect regulators, scaffolding and adaptor proteins, phosphatases and deubiquitinases, upstream signals, negative regulators, and proteins mentioned only in passing. Returns an empty extraction if nothing new is found.

### `prompts/report.md`

**Used by:** `gocam report`.

**What it asks the LLM to do:**
Merge N extraction JSONs into a structured Markdown report. Must produce:
- A table of all sources
- A consolidated protein list (activities described per source, conflicts flagged)
- An **Interaction Map** — one numbered entry per interaction, with source files, figure+PMID, causal type, assay, and confidence
- Conflicts section (when sources contradict each other)
- Gaps section (what is not yet known or described)
- Suggested expert questions

Key rule enforced in the prompt: every protein with described activities must appear in the Interaction Map. Produces a self-check count before returning.

### `prompts/translate.md`

**Used by:** `gocam translate`.

**What it asks the LLM to do:**
Map every interaction in the Interaction Map to a GO-CAM evidence record. For each interaction:

- Assign a Molecular Function GO term (no binding terms, no substrate-named terms)
- Assign a Biological Process GO term
- Assign a Cellular Component GO term
- Fill in the `relation_to_target` (type + mechanism)
- Fill in evidence (quote, PMID, figure, assay, ECO code)
- Classify with CAR test
- Rate confidence

Enforces the Coverage Rule: must produce **exactly one record per interaction** in the Interaction Map, even for low-confidence or binding-only cases. Performs a count self-check before returning.

Also instructs: pull PMID from source data or from filename hints (e.g. `scholz2010`), never write `"UNKNOWN"` as a PMID string.

### `prompts/narrative.md`

**Used by:** `gocam narrative`.

**What it asks the LLM to do:**
Convert evidence records into numbered claims written for a cell biologist, not a bioinformatician. Each claim states the protein's activity, what it regulates and how, the broader process, the cellular location, and the supporting evidence — all in plain language. Addressed to the named domain expert for their review and sign-off.

---

## Project Structure

```
gocam-curator/
├── .env                            # API keys — never commit this
├── .env.example                    # Template
├── pyproject.toml                  # Package metadata and dependencies
├── prompts/                        # Editable AI prompts (one file per command)
│   ├── system.md                   # Shared: GO-CAM rules, role, output format
│   ├── extract_text.md             # Text → entities, interactions, quotes
│   ├── extract_visual.md           # Image → labels, arrows, compartments
│   ├── extract_slides.md           # PPTX: skip non-content slides, extract notes
│   ├── extract_deep.md             # Second-pass: find what was missed
│   ├── report.md                   # Merge extractions → single report
│   ├── translate.md                # Biology → GO/ECO mapping (strict rules)
│   └── narrative.md                # Evidence records → expert-readable claims
├── src/
│   └── gocam/
│       ├── cli.py                  # Click CLI entry point
│       ├── config.py               # Paths, API keys, model IDs
│       ├── commands/               # One module per command
│       │   ├── init.py
│       │   ├── extract.py
│       │   ├── extract_all.py
│       │   ├── report.py
│       │   ├── translate.py
│       │   ├── verify.py
│       │   ├── narrative.py
│       │   ├── run.py
│       │   ├── search.py
│       │   ├── enrich.py
│       │   └── status.py
│       ├── models/                 # Pydantic v2 data schemas
│       │   ├── entity.py           # Entity (protein/gene)
│       │   ├── interaction.py      # Interaction, Connection
│       │   ├── evidence.py         # GOTerm, ECOEvidence, EvidenceRecord
│       │   └── process.py          # ProcessMeta, Extraction
│       ├── services/               # External API clients
│       │   ├── llm.py              # Provider-agnostic LLM client factory
│       │   ├── providers/          # Anthropic and Gemini implementations
│       │   ├── quickgo.py          # GO term + annotation verification
│       │   ├── uniprot.py          # UniProt protein lookup
│       │   ├── eco.py              # ECO code verification via OLS4
│       │   ├── pubmed.py           # PubMed E-utilities (search + fetch)
│       │   ├── file_processor.py   # File type detection and dispatch
│       │   ├── pdf_reader.py       # PyMuPDF PDF extraction
│       │   └── pptx_reader.py      # python-pptx slide extraction
│       └── utils/
│           ├── display.py          # Rich console helpers, timed_status spinner
│           ├── io.py               # JSON read/write helpers
│           └── process.py          # Process directory resolution
└── processes/                      # Data directory — one folder per process
    └── <process-name>/
        ├── meta.json
        ├── input/                  # Source files go here
        │   └── enrichment/         # PubMed abstracts from gocam enrich
        ├── extractions/
        │   ├── *.json              # Per-file extraction results
        │   ├── REPORT.md           # Synthesized overview
        │   └── enrichment/         # Enrichment extractions and report
        ├── evidence_records/
        │   └── records.json        # GO-mapped evidence records
        ├── verification/
        │   └── report.json         # Database verification results
        ├── narratives/
        │   └── claims_v1.md        # Expert validation draft
        └── searches/
            └── <gene>.json         # gocam search results
```

---

## Domain Rules Enforced

These rules are encoded in `prompts/system.md` and `prompts/translate.md` and applied to every LLM call. They reflect real constraints of the GO-CAM standard:

### 1. No Binding as Molecular Function

GO terms containing "binding" describe interactions (edges in the graph), not activities (nodes). If a text only says "Protein A binds Protein B", no Molecular Function is assigned — binding is represented as a `has_input` or `interacts_with` edge.

### 2. Substrate Independence

A Molecular Function term must not be named after its specific substrate. `"syntaxin kinase activity"` is wrong — the correct term is `"protein serine/threonine kinase activity"` with a `has_input` edge pointing to syntaxin. This preserves the reusability of GO terms across organisms and contexts.

### 3. The CAR Test

When a knockout experiment shows that downstream process B fails after protein A is removed, this does NOT automatically mean A regulates B. The analogy: removing a car's engine makes the radio stop working — but the engine doesn't regulate the radio. Every causal claim derived from perturbation data must be explicitly classified:

- **DIRECT** — enzymatic or mechanistic evidence (kinase assay, in vitro reconstitution)
- **STRUCTURAL_PREREQUISITE** — removal breaks the structure, downstream effects are secondary
- **INDIRECT** — real effect, but goes through intermediate steps
- **UNKNOWN** — insufficient evidence to classify

### 4. All IDs Are Unverified Until Verified

LLMs hallucinate ontology identifiers. Every GO ID, ECO code, and UniProt accession suggested by the LLM is marked `"verified": false` in the data model. The Pydantic schemas enforce this. Only `gocam verify` (which makes live REST API calls to QuickGO, UniProt, and OLS4) can set `"verified": true`.

### 5. Extraction and Translation Are Separate Steps

Phase 2 (`gocam extract`) asks: "What does this text or image say?" No GO terms are assigned.
Phase 4 (`gocam translate`) asks: "What GO terms fit the biology?" No new facts are invented.
Combining these steps causes GO ID hallucination anchored to extracted text rather than actual ontology structure.

---

## External APIs Used

| Service | Purpose | Authentication |
|---------|---------|---------------|
| [Anthropic API](https://www.anthropic.com/) | LLM calls (Claude) | `ANTHROPIC_API_KEY` |
| [Google Gemini API](https://ai.google.dev/) | LLM calls (Gemini) | `GEMINI_API_KEY` |
| [QuickGO](https://www.ebi.ac.uk/QuickGO/) | GO term + annotation verification | None (public) |
| [UniProt REST](https://rest.uniprot.org/) | Protein lookup | None (public) |
| [OLS4/EBI](https://www.ebi.ac.uk/ols4/) | ECO code verification | None (public) |
| [PubMed E-utilities](https://eutils.ncbi.nlm.nih.gov/) | Literature enrichment | None (≤3 req/sec) |

---

## Typical Workflow Example

```bash
# 1. Create a workspace for a new biological process
gocam init ampar-endocytosis --species "Mus musculus" --expert-name "Dr. Smith"

# 2. Copy your source files into input/
cp ~/papers/scholz2010.pdf processes/ampar-endocytosis/input/
cp ~/slides/presentation.pptx processes/ampar-endocytosis/input/
cp ~/figures/pathway_cartoon.png processes/ampar-endocytosis/input/

# 3. Run the full pipeline (or use gocam run)
gocam extract-all --process ampar-endocytosis
gocam report --process ampar-endocytosis

# 4. [Read REPORT.md. Have expert meeting. Come back.]

# 5. Run second-pass extraction to catch what was missed
gocam extract-all --process ampar-endocytosis --deep
gocam report --process ampar-endocytosis

# 6. Map biology to GO terms
gocam translate --process ampar-endocytosis

# 7. Verify all IDs against live databases (no LLM — fast)
gocam verify --process ampar-endocytosis

# 8. Generate the expert validation document
gocam narrative --process ampar-endocytosis

# 9. Look up a specific protein while reviewing
gocam search PICK1 --species mouse

# 10. Discover additional literature
gocam enrich ampar-endocytosis --max-papers 15

# 11. Check status across all processes
gocam status
```

---

## Editing Prompts

All prompts in `prompts/*.md` can be edited without touching Python code. Changes take effect immediately on the next command run. This allows the curator to:

- Add new GO-CAM rules as the project evolves
- Tune extraction focus (e.g. add "pay extra attention to phosphorylation sites")
- Adjust narrative tone for a specific expert
- Change the output format of any step

The only constraint: the JSON schema the LLM must output is defined by the Pydantic models in `src/gocam/models/`. If you change the output structure in a prompt, update the corresponding model to match.
