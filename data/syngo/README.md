# SynGO Data Files

Place the three SynGO Excel files in this directory:

| File | Contents |
|------|---------|
| `genes.xlsx` | Gene info: hgnc_symbol, hgnc_synonyms, ensembl_id, entrez_id |
| `annotations.xlsx` | Curated annotations: symbol, uniprot_id, pubmed_id, go_id, go_name, go_domain, evidence fields |
| `ontologies.xlsx` | GO term hierarchy with associated genes |

## Download

1. Go to https://syngoportal.org
2. Navigate to **Download** → **Data files**
3. Download the bulk data export (Excel format)
4. Place the three files here

## Usage

Once the files are in place, SynGO features activate automatically:

- `gocam search <gene>` — shows a **SynGO Annotations** section with expert-curated BP/CC annotations and evidence
- `gocam verify` — flags **SYNGO_CONFIRMED** (exact gene+GO match) or **SYNGO_ALTERNATIVE** (gene annotated to different term)
- `gocam enrich` — checks SynGO for associated PMIDs before querying PubMed; SynGO references are added as priority sources

If the files are absent the tool continues normally without SynGO features — no errors, just a debug log message.

## Updating

Re-download from syngoportal.org and replace the files here. No code changes needed.
The files are loaded fresh on each `gocam` command invocation.
