# gocam-curator

A Python command-line tool that helps a bioinformatics **curator** build **GO-CAM (Gene Ontology Causal Activity Models)** for synaptic biological processes.

The curator works with domain experts (neuroscientists, cell biologists) who provide biological knowledge. This tool assists the **curator** — never the expert — with:

- Extracting biological claims from papers, slide decks, and figures
- Verifying those claims against live ontology and protein databases
- Generating structured, readable documents for expert review

> **This tool does not replace expertise.** It produces structured drafts. The curator reviews everything, consults the domain expert, and makes all final modelling decisions.

---

## Table of Contents

- [What is GO-CAM?](#what-is-go-cam)
- [Installation](#installation)
- [Configuration](#configuration)
- [The Pipeline — Step by Step](#the-pipeline--step-by-step)
- [Commands](#commands)
  - [gocam init](#gocam-init)
  - [gocam extract-all](#gocam-extract-all)
  - [gocam validate](#gocam-validate)
  - [gocam narrative](#gocam-narrative)
  - [gocam interpret](#gocam-interpret)
  - [gocam enrich](#gocam-enrich)
  - [gocam search](#gocam-search)
  - [gocam run](#gocam-run)
  - [gocam status](#gocam-status)
- [File Types Supported](#file-types-supported)
- [Naming Your Input Files](#naming-your-input-files)
- [Active Prompts Reference](#active-prompts-reference)
- [GO-CAM Rules Enforced](#go-cam-rules-enforced)
- [Project Structure](#project-structure)
- [External APIs Used](#external-apis-used)

---

## What is GO-CAM?

A **GO-CAM** (Gene Ontology Causal Activity Model) is a structured representation of a biological process. Instead of a flat list of gene annotations, a GO-CAM is a *network*:

- Each **node** is a protein performing a specific **Molecular Function** (e.g. "protein serine/threonine kinase activity")
- Each **edge** is a causal link between two activities (e.g. "protein A *directly positively regulates* protein B")
- Every node and edge is backed by **evidence**: a paper (PMID), a figure, an experimental assay, and an [ECO code](https://www.evidenceontology.org/) for the evidence type

GO-CAMs are built in [Noctua](https://noctua.geneontology.org/). This tool produces the ontology-mapped, database-verified input that makes the Noctua modelling step tractable.

**Why does this matter?**
Raw papers describe biology in natural language. GO-CAM requires precise ontology terms with verified IDs. Manually mapping "CaMKII phosphorylates GluA1" to `GO:0004674 (protein serine/threonine kinase activity)` + `ECO:0000269` + `PMID:12345678` for dozens of proteins is extremely time-consuming. This tool automates the first draft; the curator corrects and approves it.

---

## Installation

### Requirements

- Python **3.10 or newer** (required — the code uses Python 3.10+ syntax)
- An API key for **Anthropic** (Claude) or **Google Gemini** — at least one

Check your Python version first:

```bash
python3 --version
# Must print Python 3.10.x or higher
```

### Install from source

```bash
# 1. Clone the repository
git clone https://github.com/yourorg/gocam-curator.git
cd gocam-curator

# 2. Create a virtual environment (keeps dependencies isolated)
python3 -m venv .venv

# 3. Activate the environment
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 4. Install the tool and all its dependencies
pip install -e .

# 5. Verify the installation
gocam --help
```

You should see the help text listing all available commands. If you see `command not found`, make sure the virtual environment is activated.

### Optional: PDF output from narrative

To generate PDF versions of narrative documents (in addition to Markdown), install the optional PDF dependencies:

```bash
pip install -e ".[pdf]"
```

This installs `markdown` and `weasyprint`. WeasyPrint requires some system libraries — see [WeasyPrint's installation docs](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) if you run into errors.

### Dependencies installed automatically

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client |
| `google-genai` | Gemini API client |
| `click` | CLI framework |
| `pydantic>=2.0` | Data validation and type-safe models |
| `rich` | Terminal formatting (tables, spinners, colour) |
| `httpx` | HTTP client for database queries |
| `python-dotenv` | Loading `.env` configuration files |
| `python-pptx` | PowerPoint slide text and image extraction |
| `pymupdf` | PDF text and figure extraction |
| `pillow` | Image resizing before API calls |

---

## Configuration

Create a `.env` file in the project root by copying the example:

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum your API key:

```dotenv
# ── AI Provider ───────────────────────────────────────────────────────────────
# Which AI service to use: "anthropic" (Claude) or "gemini" (Google Gemini)
LLM_PROVIDER=anthropic

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-...          # required when LLM_PROVIDER=anthropic
GEMINI_API_KEY=AIza...                # required when LLM_PROVIDER=gemini

# ── Model selection (optional — sensible defaults shown) ──────────────────────
ANTHROPIC_MODEL=claude-sonnet-4-5
GEMINI_MODEL=gemini-2.5-pro

# ── Rate limiting: seconds to wait between consecutive API calls ──────────────
ANTHROPIC_API_CALL_DELAY=2
GEMINI_API_CALL_DELAY=10
```

The `.env` file is listed in `.gitignore` and will never be committed to git. Do not share it.

### Switching AI providers

Change `LLM_PROVIDER` in `.env` — no code changes needed. Both providers use the same commands and produce identical output formats.

**Anthropic (Claude)** is the default and generally gives the best extraction quality for scientific text. **Gemini** is an alternative if you prefer Google's infrastructure; PDFs are automatically split into smaller chunks because Gemini has tighter output limits.

---

## The Pipeline — Step by Step

The full workflow from raw papers to a validated, expert-readable model looks like this:

```
Input files (.pdf, .pptx, .png, .jpg, .txt)
    placed in: processes/<name>/input/
          │
          ▼
  gocam extract-all          AI reads each file and extracts structured claims:
                              nodes (protein + molecular function) and
                              edges (causal relations between proteins).
                              Output: extractions/*.json
          │
          ▼
  gocam validate             No AI. Looks up every claim in live databases:
                              proteins → UniProt
                              GO terms → QuickGO
                              ECO codes → OLS4/EBI
                              PMIDs/DOIs → PubMed / CrossRef
                              synaptic annotations → SynGO
                              Output: validation/validated_claims.json
          │
          ▼
  gocam narrative            No AI. Formats validated claims into two
                              human-readable Markdown documents for expert review:
                              - claims_nodes_v1.md  (one section per protein)
                              - claims_edges_v1.md  (one section per interaction)
          │
          ▼  [Curator reviews, discusses with domain expert, iterates]
          │
          ▼
  gocam interpret            AI reviews validated claims and suggests:
  (optional)                 - GO-term alternatives for unresolved terms
                              - Missing proteins or process steps (gap analysis)
                              - Relation type corrections for edges
                              Output: interpretation/suggestions.md
                              (read-only — never modifies validated data)
```

Or run steps 1–3 in a single command:

```bash
gocam run <process-name>
```

### What "validation" means here

`gocam validate` does not ask the AI to judge whether claims are biologically correct. It makes **REST API calls to public databases** and checks:

- Does this UniProt accession exist for this species?
- Does this GO term ID exist in QuickGO? Is it obsolete?
- Is this protein already annotated with this GO term in the database?
- Does this PMID resolve to a real paper?
- Does this ECO code exist in the Evidence and Conclusion Ontology?

This is factual database lookup, not AI inference. The AI is only used in `extract-all` (to read files) and `interpret` (to suggest improvements).

---

## Commands

### gocam init

Create a new process workspace.

```bash
gocam init ampar-endocytosis
gocam init vesicle-fusion --species "Rattus norvegicus"
gocam init ltp-signalling --complexity HIGH --expert-name "Dr. Smith" --expert-email smith@uni.edu
```

**What it does:** Creates the directory `processes/<name>/` with all required subdirectories and a `meta.json` file storing process metadata.

```
processes/ampar-endocytosis/
├── meta.json           ← process name, species, expert contact info
├── input/              ← drop your source files here
├── extractions/        ← AI extraction output (created by extract-all)
├── validation/         ← database verification results (created by validate)
├── narratives/         ← expert-readable documents (created by narrative)
├── interpretation/     ← AI suggestions (created by interpret)
└── searches/           ← gene lookup results (created by search)
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--species` | `Mus musculus` | Species used for UniProt and GO lookups |
| `--complexity` | `MID` | Process complexity: LOW / MID / HIGH |
| `--expert-name` | — | Name of the domain expert (appears in narrative documents) |
| `--expert-email` | — | Expert's email (appears in narrative documents) |

**No AI is used.** This is a local filesystem operation only.

---

### gocam extract-all

Extract GO-CAM claims from every supported file in the `input/` folder.

```bash
gocam extract-all
gocam extract-all --process ampar-endocytosis   # if not in the process directory
```

**What it does:** For each file in `input/`, the AI reads the content and extracts two types of structured claims:

- **Node claims** — a protein performing a molecular activity in a specific context. Example: "CaMKII performs protein kinase activity at the postsynaptic density."
- **Edge claims** — a causal relationship between two proteins. Example: "CaMKII directly positively regulates GluA1."

Each claim records:
- The protein name and gene symbol
- Molecular function, biological process, and cellular component (as free text at this stage — ontology IDs are assigned later by `validate`)
- An **exact quote** from the source
- Figure reference (e.g. "Fig. 3B")
- Experimental assay (e.g. "co-immunoprecipitation")
- PMID if mentioned in the text, or derived from the filename (see [Naming Your Input Files](#naming-your-input-files))
- Confidence level (HIGH / MEDIUM / LOW)

**Output:** One JSON file per input file in `extractions/`. Already-extracted files are skipped on re-runs.

**AI prompt used:** `prompts/system.md` + `prompts/extract.md`

> **Tip:** You can also run `gocam extract <single-file>` to process one file at a time, which is useful for testing.

---

### gocam validate

Verify all extracted claims against live databases. **No AI is used.**

```bash
gocam validate
gocam validate --process ampar-endocytosis
```

**What it does:** Reads all extraction JSONs and checks every claim against five databases:

| Database | What is checked |
|----------|-----------------|
| [UniProt](https://rest.uniprot.org/) | Does this protein/gene exist for this species? Returns the canonical UniProt accession. |
| [QuickGO](https://www.ebi.ac.uk/QuickGO/) | Does this GO term ID exist? Is it obsolete? Is the protein already annotated with it? |
| [OLS4/EBI](https://www.ebi.ac.uk/ols4/) | Does this ECO code exist? If the assay name is known but no ECO code is given, searches OLS4 for the best match. |
| [PubMed](https://pubmed.ncbi.nlm.nih.gov/) | Does this PMID correspond to a real paper? |
| [SynGO](https://www.syngodb.org/) | Is this protein annotated in the expert-curated SynGO synaptic database? |

For each claim, the status is recorded:

- **VERIFIED** — ID exists in the database and is current
- **CONFIRMED** — ID exists AND the protein is already annotated with it (the annotation already exists in the community database)
- **OBSOLETE** — the term exists but has been deprecated; a replacement should be found
- **NOT_FOUND** — the ID does not exist in the database; likely wrong
- **SKIPPED** — no ID was provided (not a failure — some claims genuinely lack certain annotations)

**PMID resolution priority:**

The tool tries to find a PMID for each claim in this order, stopping at the first success:
1. PMID from the **filename** (e.g. `20357116.pdf` → PMID `20357116`) — most reliable, curator-controlled
2. PMID extracted from **text content** by the AI during extraction
3. DOI found in the **PDF header** → resolved to PMID via CrossRef

**Output:** `validation/validated_claims.json` — a structured file containing all nodes and edges with their database-verified status.

---

### gocam narrative

Assemble the validated claims into expert-readable documents. **No AI is used.**

```bash
gocam narrative
gocam narrative --process ampar-endocytosis

# Focus on specific genes only:
gocam narrative --genes "BRAG2,PICK1,ARF6,AP2"

# Also generate a PDF alongside the Markdown:
gocam narrative --pdf
```

**What it does:** Reads `validation/validated_claims.json` and generates two Markdown documents:

- **`claims_nodes_v1.md`** — one section per protein/node. Shows the molecular function, biological process, cellular component, verification status, SynGO annotations, and evidence (PMID, figure, assay, ECO code).
- **`claims_edges_v1.md`** — one section per interaction/edge. Shows the causal relation, mechanism, and evidence.

Each document separates claims into **Included** (verified PMID present) and **Excluded** (missing or unverified evidence) sections, so the domain expert immediately sees which claims are well-supported.

Re-running `narrative` does not overwrite the previous version — it creates `claims_nodes_v2.md`, `claims_edges_v2.md`, and so on. This preserves the history of revisions.

**`--genes` filter:** Provide a comma-separated list of gene/protein name substrings. Only nodes and edges whose proteins match one of those substrings will appear in the output. Matching is case-insensitive and partial (e.g. `--genes "ap2"` will match AP2α, AP2β, and AP-2 complex). The output file is named after the gene list: `brag2_pick1_arf6_nodes_v1.md`.

**`--pdf` flag:** Generates a PDF version alongside the Markdown. Requires the optional `pdf` dependencies (`pip install -e ".[pdf]"`). Hyperlinks and formatting are preserved in the PDF.

**No AI prompt used.** This step is deterministic formatting — same input always produces the same output.

---

### gocam interpret

Ask the AI to review validated claims and suggest improvements.

```bash
gocam interpret ampar-endocytosis
```

**What it does:** Reads the validated claims and sends a structured summary to the AI with three tasks:

1. **GO-term alternatives** — for any node where a GO term came back NOT_FOUND or OBSOLETE, suggests 2–3 alternative term *names* to search for (not IDs — those must be verified)
2. **Gap analysis** — identifies proteins or process steps that are well-established for this biology but absent from the current model
3. **Relation type review** — flags edges where the relation type may be wrong given the evidence type (e.g. a knockout experiment rarely justifies "directly_regulates")

**Important limitations of this step:**
- The AI will **never suggest PMIDs, DOIs, or paper titles** — it hallucinates them. Finding papers is the curator's job.
- The AI will **never generate GO IDs or ECO codes** — it only suggests term *names*. IDs must be verified via `gocam validate` or `gocam search`.
- Every suggestion is explicitly prefixed with `SUGGESTION:` so it is clearly distinguished from verified data.
- This step is **read-only** — it never modifies `validated_claims.json`.

**Output:** `interpretation/suggestions.md` (always overwritten — this is advisory text, not versioned data)

**AI prompt used:** `prompts/system.md` + `prompts/interpret.md`

---

### gocam enrich

Discover additional literature via PubMed and extract claims from it.

```bash
gocam enrich ampar-endocytosis
gocam enrich ampar-endocytosis --max-papers 20
gocam enrich ampar-endocytosis --queries-only   # preview queries without fetching
```

**What it does:**

1. Builds PubMed search queries from the gene symbols in your validated claims
2. Searches PubMed via the free E-utilities API (no key required)
3. Filters out PMIDs already present anywhere in the process
4. Checks SynGO for expert-curated references associated with each gene (priority sources)
5. Downloads abstracts for new papers
6. Extracts claims from each abstract using the AI
7. Generates `ENRICHMENT_REPORT.md` labelling each finding as **CONFIRMS** (gene already in your model) or **NEW** (not seen before)

**This step is strictly separated from the main pipeline.** The original `validated_claims.json` and narrative documents are never modified. Everything goes into:

| Data | Location |
|------|---------|
| PubMed abstract text | `input/enrichment/pubmed_{PMID}.txt` |
| Extraction JSONs | `extractions/enrichment/pubmed_{PMID}.json` |
| Enrichment report | `extractions/enrichment/ENRICHMENT_REPORT.md` |

The curator manually decides which enrichment findings are worth promoting to the main pipeline (by adding the paper to `input/` and re-running `extract-all` + `validate`).

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--max-papers` | 10 | Maximum number of new abstracts to process |
| `--queries-only` | off | Print the queries that would be sent to PubMed, then exit |

**AI prompt used:** `prompts/system.md` + `prompts/extract.md` (same as standard extraction)

---

### gocam search

Look up a single gene or protein across multiple databases. **No AI used.**

```bash
gocam search PICK1
gocam search CAMK2A --species human
gocam search Gria2 --species mouse
```

**What it does:** Runs three parallel database queries and displays a consolidated report:

1. **UniProt** — protein name, alternative gene symbols, function description, existing GO annotations
2. **QuickGO** — all current GO annotations for the UniProt accession
3. **OLS4** — GO terms whose descriptions mention the gene name

This is useful **before and after** `gocam validate` — check what GO annotations already exist for a protein, or look up the correct term name to try when `validate` returns NOT_FOUND.

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--species` | `mouse` | One of: mouse, human, rat, fly, worm, zebrafish, yeast |
| `--process` | auto-detect | Save results to a specific process |

Results are saved to `processes/<name>/searches/<gene>.json` if a process can be detected.

---

### gocam run

Run the full pipeline (steps 1–3) in a single command.

```bash
gocam run ampar-endocytosis
gocam run ampar-endocytosis --skip-verify   # skip database validation (faster, for testing)
```

**What it does:** Runs `extract-all → validate → narrative` in sequence. Each step is skipped if its output already exists, making this safe to re-run if something fails partway through.

Progress is shown step by step. The final narrative documents are printed to the terminal on completion.

> Note: `gocam run` does **not** automatically run `gocam interpret` or `gocam enrich` — those are optional steps you run manually after reviewing the narrative.

---

### gocam status

Show a progress overview of all processes.

```bash
gocam status
```

Displays a table with one row per process:

```
Process                Complexity   Extracted   Validated   Narrative   Interpretation
ampar-endocytosis      MID          6 files     ✓           nodes v2    ✓
vesicle-fusion         HIGH         3 files     —           —           —
```

**No AI is used.**

---

## File Types Supported

| Extension | How it is processed |
|-----------|-------------------|
| `.txt`, `.md` | Full text sent in one API call |
| `.pdf` | Text extracted with PyMuPDF; figures extracted as images and sent separately. Reference and acknowledgement sections are detected and skipped. |
| `.png`, `.jpg`, `.jpeg` | Sent as vision input (image resized to ≤5 MB if needed) |
| `.pptx` | Each slide processed individually; speaker notes included; title, acknowledgement, and reference slides skipped |

---

## Naming Your Input Files

The filename is used to automatically assign a PMID to all claims extracted from that file. This is the most reliable way to ensure every claim gets a verified reference — the curator controls the filename.

**Convention:** include the PMID as a 7–9 digit number anywhere in the filename:

```
input/
├── 20357116.pdf                    ← PMID 20357116 assigned to all claims
├── scholz2010_20357116.pdf         ← same, more descriptive name
├── fig3_20357116.png               ← individual figure from same paper
├── review_article.pdf              ← no PMID in filename — fallback to text extraction
└── expert_slides.pptx              ← no PMID — each slide may carry its own
```

If no PMID is in the filename, the tool tries to extract one from the text content. For PDFs, it also reads the DOI from the paper header and resolves it to a PMID via CrossRef.

---

## Active Prompts Reference

All prompts live in `prompts/` and are plain Markdown files. You can edit them without touching any Python code — changes take effect immediately on the next run.

### How prompts are assembled

Every AI call receives a **system message** built from two files:

```
system message = prompts/system.md  +  prompts/<command>.md
user message   = the actual data (file content, extraction JSONs, etc.)
```

### Active prompt files

| File | Used by | What it instructs the AI to do |
|------|---------|-------------------------------|
| `prompts/system.md` | Every AI call | Establishes the curator-assistant role. Enforces the four GO-CAM rules (no binding as MF, substrate independence, CAR test, IDs unverified by default). Sets JSON output format. |
| `prompts/extract.md` | `extract-all`, `enrich` | Extract node claims (proteins + activities) and edge claims (causal relations) from scientific text, images, or slides. Returns a `claims` JSON array. |
| `prompts/interpret.md` | `interpret` | Review validated claims. Suggest GO-term alternatives, gap analysis, and relation type corrections. All suggestions prefixed with `SUGGESTION:`. Never generate IDs or references. |

> **`prompts/old_prompts/`** contains archived prompt files from an earlier version of the pipeline. They are not loaded by any command and are kept for reference only.

### Editing prompts safely

- You can add instructions, change wording, or adjust focus without touching Python.
- The JSON structure the AI must return is defined by Pydantic models in `src/gocam/models/claim.py`. If you change the output structure in `extract.md`, the corresponding model must be updated to match — otherwise parsing will fail.
- Always test prompt changes on a small file before running on a full process.

---

## GO-CAM Rules Enforced

These rules are embedded in `prompts/system.md` and `prompts/extract.md`. They reflect real constraints of the GO-CAM standard and are applied at every AI extraction step.

### 1. No "binding" as a Molecular Function

GO terms containing "binding" describe *interactions*, not *activities*. If a paper only says "Protein A binds Protein B", no Molecular Function is assigned — the binding relationship is modelled as a `has_input` *edge* from A to B.

**Wrong:** node with `molecular_function = "syntaxin binding"`
**Right:** node for protein A with `molecular_function = null` (unknown), plus an edge `A → has_input → syntaxin`

### 2. Substrate Independence

A Molecular Function term must not be named after its specific substrate. The GO term describes the *type of activity*, not the specific molecule it acts on.

**Wrong:** `"GluA1 phosphorylation activity"`
**Right:** `"protein serine/threonine kinase activity"` with a `has_input` edge pointing to GluA1

This preserves the reusability of GO terms across organisms and experimental contexts.

### 3. The CAR Test

When a knockout or knockdown experiment shows that a downstream process fails after protein A is removed, this does **not** automatically mean A directly regulates that process.

*Analogy:* Removing a car's engine makes the radio stop working. But the engine does not regulate the radio — it is a structural prerequisite. When you see "protein A knockout → downstream process B fails", ask: did A directly control B, or did removing A collapse the entire system?

Every causal claim from perturbation data is classified as:
- **directly_positively_regulates / directly_negatively_regulates** — direct enzymatic or mechanistic evidence (kinase assay, in vitro reconstitution)
- **indirectly_positively_regulates / indirectly_negatively_regulates** — real effect, but through intermediate steps
- **constitutively_upstream_of** — A is required for B to function but does not regulate it causally (structural prerequisite)
- **has_input** — A acts on B as a substrate or molecular target

### 4. All IDs Are Unverified Until Checked

AI models hallucinate ontology identifiers. A hallucinated GO ID may be syntactically valid but point to a completely unrelated term — or not exist at all. Worse, it may be a real code for the *wrong* thing (e.g. ECO:0000104 is a real, valid code, but it describes "DNA microarray evidence" — not a protein pull-down assay).

Every GO ID, ECO code, and UniProt accession produced by the AI is treated as **unverified** until `gocam validate` checks it against the live database. Only database-confirmed IDs appear as verified in the narrative.

### 5. Extraction and Interpretation Are Separate Steps

`gocam extract-all` asks: *"What does this text or image explicitly say?"* No GO terms are assigned. No interpretations are made.

`gocam validate` maps those claims to ontology terms via database lookup.

`gocam interpret` suggests improvements — but is read-only and advisory.

Combining extraction and GO mapping in a single step causes GO ID hallucination anchored to text patterns rather than actual ontology structure. Keeping them separate means errors in one step do not corrupt the other.

---

## Project Structure

```
gocam-curator/
├── .env                            ← API keys — never commit this file
├── .env.example                    ← Template: copy to .env and fill in
├── pyproject.toml                  ← Package metadata and dependencies
│
├── prompts/                        ← Editable AI prompts (plain Markdown)
│   ├── system.md                   ← Shared rules loaded for every AI call
│   ├── extract.md                  ← Extraction prompt (nodes + edges)
│   ├── interpret.md                ← Interpretation/suggestion prompt
│   └── old_prompts/                ← Archived prompts (not used by any command)
│
├── src/
│   └── gocam/
│       ├── cli.py                  ← CLI entry point (registered commands)
│       ├── config.py               ← Paths, API keys, model IDs, env settings
│       ├── commands/               ← One module per command
│       │   ├── init.py             ← gocam init
│       │   ├── extract.py          ← gocam extract (single file)
│       │   ├── extract_all.py      ← gocam extract-all (all files in input/)
│       │   ├── validate.py         ← gocam validate (database verification)
│       │   ├── narrative.py        ← gocam narrative (Markdown/PDF output)
│       │   ├── interpret.py        ← gocam interpret (AI suggestions)
│       │   ├── enrich.py           ← gocam enrich (PubMed literature discovery)
│       │   ├── search.py           ← gocam search (gene lookup)
│       │   ├── run.py              ← gocam run (full pipeline)
│       │   └── status.py           ← gocam status (progress overview)
│       ├── models/                 ← Pydantic v2 data schemas
│       │   └── claim.py            ← NodeClaim, EdgeClaim, ValidationReport, ...
│       ├── services/               ← External API clients and file processors
│       │   ├── llm.py              ← Provider-agnostic LLM client factory
│       │   ├── providers/          ← Anthropic and Gemini implementations
│       │   ├── quickgo.py          ← GO term + annotation verification (QuickGO)
│       │   ├── uniprot.py          ← Protein lookup (UniProt REST)
│       │   ├── eco.py              ← ECO code verification (OLS4/EBI)
│       │   ├── pubmed.py           ← PubMed search + abstract fetch
│       │   ├── syngo.py            ← SynGO local database queries
│       │   ├── file_processor.py   ← File type detection and dispatch
│       │   ├── pdf_reader.py       ← PDF text + figure extraction (PyMuPDF)
│       │   └── pptx_reader.py      ← Slide extraction (python-pptx)
│       └── utils/
│           ├── display.py          ← Rich console helpers
│           ├── io.py               ← JSON read/write, prompt loading
│           └── process.py          ← Process directory resolution
│
└── processes/                      ← Data directory — one folder per process
    └── <process-name>/
        ├── meta.json               ← Species, complexity, expert info
        ├── input/                  ← Drop source files here
        │   └── enrichment/         ← PubMed abstracts from gocam enrich
        ├── extractions/
        │   ├── *.json              ← Per-file extraction results
        │   └── enrichment/         ← Enrichment extractions and report
        ├── validation/
        │   └── validated_claims.json  ← Database-verified nodes and edges
        ├── narratives/
        │   ├── claims_nodes_v1.md  ← Expert validation draft (nodes)
        │   ├── claims_edges_v1.md  ← Expert validation draft (edges)
        │   └── *.pdf               ← Optional PDF versions (--pdf flag)
        ├── interpretation/
        │   └── suggestions.md      ← AI suggestions (gocam interpret)
        └── searches/
            └── <gene>.json         ← Gene lookup results (gocam search)
```

---

## External APIs Used

All external API calls use public endpoints — no paid accounts are required beyond the AI provider.

| Service | What it is used for | Auth required |
|---------|---------------------|--------------|
| [Anthropic API](https://www.anthropic.com/) | AI extraction and interpretation (Claude) | `ANTHROPIC_API_KEY` in `.env` |
| [Google Gemini API](https://ai.google.dev/) | AI extraction and interpretation (Gemini) | `GEMINI_API_KEY` in `.env` |
| [QuickGO](https://www.ebi.ac.uk/QuickGO/) | GO term existence and protein annotation lookup | None — public |
| [UniProt REST](https://rest.uniprot.org/) | Protein and gene symbol lookup | None — public |
| [OLS4/EBI](https://www.ebi.ac.uk/ols4/) | ECO code verification and assay name search | None — public |
| [PubMed E-utilities](https://eutils.ncbi.nlm.nih.gov/) | PMID verification, abstract search and download | None (≤3 req/sec limit) |
| [SynGO](https://www.syngodb.org/) | Expert-curated synaptic gene annotations | Local database file |

---

## Typical Workflow Example

```bash
# ── SETUP ──────────────────────────────────────────────────────────────────────

# 1. Create a workspace for the process you are modelling
gocam init ampar-endocytosis --species "Mus musculus" --expert-name "Dr. Smith"

# 2. Copy your source files into input/.
#    Name PDFs with their PMID for automatic evidence linking:
cp ~/papers/20357116.pdf       processes/ampar-endocytosis/input/
cp ~/papers/15385962.pdf       processes/ampar-endocytosis/input/
cp ~/slides/expert_talk.pptx   processes/ampar-endocytosis/input/
cp ~/figures/pathway_fig.png   processes/ampar-endocytosis/input/


# ── MAIN PIPELINE ──────────────────────────────────────────────────────────────

# 3. Extract claims from all input files (AI — takes a few minutes per file)
gocam extract-all --process ampar-endocytosis

# 4. Verify all claims against databases (no AI — fast)
gocam validate --process ampar-endocytosis

# 5. Generate the expert validation documents
gocam narrative --process ampar-endocytosis
#    → produces: narratives/claims_nodes_v1.md
#    → produces: narratives/claims_edges_v1.md


# ── REVIEW AND ITERATION ───────────────────────────────────────────────────────

# 6. Open the narrative documents and share with the domain expert
open processes/ampar-endocytosis/narratives/claims_nodes_v1.md

# 7. Get AI suggestions on what might be missing or wrong
gocam interpret ampar-endocytosis
#    → produces: interpretation/suggestions.md

# 8. Look up a specific protein while reviewing
gocam search PICK1 --species mouse
gocam search ARF6 --species mouse

# 9. Discover additional literature
gocam enrich ampar-endocytosis --max-papers 15
#    → review: extractions/enrichment/ENRICHMENT_REPORT.md

# 10. Generate a focused sub-narrative for specific proteins of interest
gocam narrative --genes "BRAG2,PICK1,ARF6,AP2"

# 11. Generate PDF version for sharing
gocam narrative --pdf


# ── STATUS ─────────────────────────────────────────────────────────────────────

# 12. Check progress across all your processes
gocam status
```

---

## Frequently Asked Questions

**Q: Why are some GO terms showing NOT_FOUND in the narrative?**

The AI suggests term names in plain English (e.g. "clathrin-mediated endocytosis"). `gocam validate` searches QuickGO for the closest match. NOT_FOUND means no matching current term was found — the name may be slightly wrong, too specific, or not an official GO term. Use `gocam search` or browse [QuickGO](https://www.ebi.ac.uk/QuickGO/) directly to find the correct term name, then re-run `validate`.

**Q: The narrative shows a PMID as NOT_CHECKED. Why?**

NOT_CHECKED means no PMID was found for that claim. This happens when: (a) the source file had no PMID in its filename, (b) no PMID appeared in the text, and (c) no DOI could be resolved. Fix: rename the file to include the PMID (e.g. `20357116.pdf`) and re-run `extract-all` + `validate`.

**Q: Can I edit the AI prompts?**

Yes. All prompts in `prompts/` are plain Markdown files. Edit them in any text editor. Changes take effect on the next command run. The GO-CAM rules in `prompts/system.md` are especially important — they prevent the most common errors.

**Q: gocam interpret suggests something wrong. Should I accept it?**

No. `gocam interpret` output is advisory only. Every suggestion is labelled `SUGGESTION:` and the AI is explicitly instructed not to generate IDs, references, or factual claims. Treat it as a brainstorming prompt, not ground truth.

**Q: What is the difference between VERIFIED and CONFIRMED?**

- **VERIFIED** — the GO term exists and is current, but the protein does not yet have this annotation in the community database. This is a new annotation candidate.
- **CONFIRMED** — the protein already has this exact annotation in QuickGO. The community has already validated this biology.
