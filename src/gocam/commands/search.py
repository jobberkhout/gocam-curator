"""gocam search — quick multi-database gene/protein lookup (no LLM)."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import click
import httpx
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gocam.config import PROCESSES_DIR
from gocam.utils.display import console, print_error, print_info, print_warning
from gocam.utils.io import write_json

# ---------------------------------------------------------------------------
# Species map
# ---------------------------------------------------------------------------

_SPECIES_MAP: dict[str, tuple[str, str]] = {
    "mouse":  ("10090", "Mus musculus"),
    "human":  ("9606",  "Homo sapiens"),
    "rat":    ("10116", "Rattus norvegicus"),
    "fly":    ("7227",  "Drosophila melanogaster"),
    "worm":   ("6239",  "Caenorhabditis elegans"),
    "zebrafish": ("7955", "Danio rerio"),
    "yeast":  ("559292", "Saccharomyces cerevisiae"),
}

_TIMEOUT = 20.0
_QUICKGO_LIMIT = 100  # max annotations per QuickGO call


# ---------------------------------------------------------------------------
# Async fetchers
# ---------------------------------------------------------------------------

async def _fetch_uniprot(
    client: httpx.AsyncClient, gene: str, taxon_id: str
) -> dict:
    """Fetch protein info + GO cross-references from UniProt."""
    try:
        r = await client.get(
            "https://rest.uniprot.org/uniprotkb/search",
            params={
                "query": f"gene:{gene} AND organism_id:{taxon_id}",
                "fields": "accession,gene_names,protein_name,cc_function,go_id",
                "format": "json",
                "size": "5",
            },
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc)}

    if not results:
        return {"status": "NOT_FOUND"}

    entry = results[0]
    uniprot_id: str = entry.get("primaryAccession", "")

    # Protein name
    protein_name = ""
    pd = entry.get("proteinDescription", {})
    rec = pd.get("recommendedName") or (pd.get("submissionNames") or [{}])[0]
    full = rec.get("fullName", {})
    protein_name = full.get("value", "")

    # Gene names
    gene_names: list[str] = []
    for g in entry.get("genes", []):
        gn = g.get("geneName", {}).get("value")
        if gn:
            gene_names.append(gn)
        for syn in g.get("synonyms", []):
            v = syn.get("value")
            if v and v not in gene_names:
                gene_names.append(v)

    # Function text
    function_text = ""
    for comment in entry.get("comments", []):
        if comment.get("commentType") == "FUNCTION":
            texts = comment.get("texts", [])
            if texts:
                function_text = texts[0].get("value", "")
                break

    # GO cross-references — aspect prefix: F: MF, P: BP, C: CC
    go_mf: list[dict] = []
    go_bp: list[dict] = []
    go_cc: list[dict] = []
    for xref in entry.get("uniProtKBCrossReferences", []):
        if xref.get("database") != "GO":
            continue
        go_id = xref.get("id", "")
        term = evidence = ""
        for prop in xref.get("properties", []):
            k, v = prop.get("key", ""), prop.get("value", "")
            if k == "GoTerm":
                term = v  # "F:kinase activity" etc.
            elif k == "GoEvidenceType":
                evidence = v
        aspect = term[:1] if term else "?"
        term_name = term[2:] if len(term) > 2 else term
        entry_dict = {"id": go_id, "term": term_name, "evidence": evidence}
        if aspect == "F":
            go_mf.append(entry_dict)
        elif aspect == "P":
            go_bp.append(entry_dict)
        elif aspect == "C":
            go_cc.append(entry_dict)

    return {
        "status": "FOUND",
        "uniprot_id": uniprot_id,
        "protein_name": protein_name,
        "gene_names": gene_names,
        "function": function_text,
        "go_mf": go_mf,
        "go_bp": go_bp,
        "go_cc": go_cc,
    }


async def _fetch_quickgo(
    client: httpx.AsyncClient, uniprot_id: str
) -> list[dict]:
    """Fetch QuickGO annotations for a UniProt accession."""
    if not uniprot_id:
        return []
    try:
        r = await client.get(
            "https://www.ebi.ac.uk/QuickGO/services/annotation/search",
            params={
                "geneProductId": f"UniProtKB:{uniprot_id}",
                "limit": str(_QUICKGO_LIMIT),
            },
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as exc:
        return [{"error": str(exc)}]

    annotations = []
    for ann in results:
        annotations.append({
            "go_id": ann.get("goId", ""),
            "go_name": ann.get("goName", ""),
            "aspect": ann.get("goAspect", ""),
            "evidence_code": ann.get("evidenceCode", ""),
            "reference": ann.get("reference", ""),
        })
    return annotations


async def _fetch_ols(client: httpx.AsyncClient, gene: str) -> list[dict]:
    """Search OLS4 for GO terms containing the gene name."""
    try:
        r = await client.get(
            "https://www.ebi.ac.uk/ols4/api/search",
            params={"q": gene, "ontology": "go", "rows": "10"},
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
    except Exception as exc:
        return [{"error": str(exc)}]

    results = []
    for doc in docs:
        results.append({
            "id": doc.get("obo_id") or doc.get("id", ""),
            "label": doc.get("label", ""),
            "description": (doc.get("description") or [""])[0],
        })
    return results


async def _fetch_all(
    gene: str, taxon_id: str
) -> tuple[dict, list[dict], list[dict]]:
    """Run UniProt + OLS4 in parallel, then QuickGO once UniProt ID is known."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        uniprot_task = asyncio.create_task(_fetch_uniprot(client, gene, taxon_id))
        ols_task = asyncio.create_task(_fetch_ols(client, gene))

        uniprot_result = await uniprot_task
        quickgo_result = await _fetch_quickgo(
            client, uniprot_result.get("uniprot_id", "")
        )
        ols_result = await ols_task

    return uniprot_result, quickgo_result, ols_result


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _display(
    gene: str,
    species_label: str,
    uniprot: dict,
    quickgo: list[dict],
    ols: list[dict],
) -> None:
    if uniprot.get("status") == "NOT_FOUND":
        print_warning(f"No UniProt entry found for gene '{gene}' in {species_label}.")
        return
    if uniprot.get("status") == "ERROR":
        print_error(f"UniProt error: {uniprot.get('error')}")
        return

    # Header panel
    uid = uniprot.get("uniprot_id", "?")
    pname = uniprot.get("protein_name", "")
    gnames = " / ".join(uniprot.get("gene_names", [gene]))
    func = uniprot.get("function", "")

    header_table = Table.grid(padding=(0, 2))
    header_table.add_column(style="dim", min_width=16)
    header_table.add_column()
    header_table.add_row("UniProt ID", f"[bold cyan]{uid}[/bold cyan]")
    header_table.add_row("Protein name", pname)
    header_table.add_row("Gene names", gnames)
    header_table.add_row("Species", species_label)
    if func:
        # Truncate long function strings for display
        display_func = func[:300] + ("…" if len(func) > 300 else "")
        header_table.add_row("Function", display_func)

    console.print(Panel(header_table, title=f"[bold]Search: {gene.upper()}[/bold]",
                        border_style="cyan", padding=(1, 2)))

    # GO annotations table
    go_mf = uniprot.get("go_mf", [])
    go_bp = uniprot.get("go_bp", [])
    go_cc = uniprot.get("go_cc", [])
    total = len(go_mf) + len(go_bp) + len(go_cc)

    if total:
        go_table = Table(show_header=True, header_style="bold", box=None,
                         pad_edge=False, padding=(0, 2))
        go_table.add_column("Aspect", style="dim", min_width=4)
        go_table.add_column("GO ID", min_width=12)
        go_table.add_column("Term")
        go_table.add_column("Evidence", style="dim")

        def _add_rows(entries: list[dict], label: str, style: str) -> None:
            for e in entries:
                go_table.add_row(
                    f"[{style}]{label}[/{style}]",
                    e.get("id", ""),
                    e.get("term", ""),
                    e.get("evidence", ""),
                )

        _add_rows(go_mf, "MF", "yellow")
        _add_rows(go_bp, "BP", "green")
        _add_rows(go_cc, "CC", "blue")

        console.print(f"\n[bold]GO Annotations from UniProt[/bold] ({total} total)")
        console.print(go_table)

    # QuickGO summary
    if quickgo and not any("error" in a for a in quickgo):
        n_qgo = len(quickgo)
        console.print(
            f"\n[bold]QuickGO Annotations[/bold] — {n_qgo} annotation(s) found for {uid}"
        )
        if n_qgo > 0:
            qgo_table = Table(show_header=True, header_style="bold dim", box=None,
                              pad_edge=False, padding=(0, 2))
            qgo_table.add_column("GO ID", min_width=12)
            qgo_table.add_column("Term")
            qgo_table.add_column("Aspect", style="dim")
            qgo_table.add_column("ECO", style="dim")
            qgo_table.add_column("Reference", style="dim")
            for ann in quickgo[:20]:
                qgo_table.add_row(
                    ann.get("go_id", ""),
                    ann.get("go_name", ""),
                    ann.get("aspect", "")[:2].upper(),
                    ann.get("evidence_code", ""),
                    ann.get("reference", ""),
                )
            console.print(qgo_table)
            if n_qgo > 20:
                console.print(f"  [dim]… and {n_qgo - 20} more (see saved JSON)[/dim]")

    # OLS4 terms
    valid_ols = [t for t in ols if "error" not in t and t.get("label")]
    if valid_ols:
        console.print(f"\n[bold]Related GO Terms from OLS4[/bold] (query: '{gene}')")
        ols_table = Table(show_header=True, header_style="bold dim", box=None,
                          pad_edge=False, padding=(0, 2))
        ols_table.add_column("GO ID", min_width=12)
        ols_table.add_column("Label")
        ols_table.add_column("Description", style="dim")
        for term in valid_ols[:10]:
            desc = term.get("description", "")
            if len(desc) > 80:
                desc = desc[:77] + "…"
            ols_table.add_row(term.get("id", ""), term.get("label", ""), desc)
        console.print(ols_table)


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

def _build_markdown(
    gene: str,
    species_label: str,
    taxon_id: str,
    uniprot: dict,
    quickgo: list[dict],
    ols: list[dict],
) -> str:
    """Render search results as a human-readable Markdown document."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    uid = uniprot.get("uniprot_id", "—")
    pname = uniprot.get("protein_name", "—")
    gnames = " / ".join(uniprot.get("gene_names", [gene])) or "—"
    func = uniprot.get("function", "")

    lines: list[str] = [
        f"# Search: {gene.upper()}",
        f"",
        f"**Species:** {species_label} (taxon:{taxon_id})  ",
        f"**Date:** {ts}  ",
        f"**UniProt ID:** [{uid}](https://www.uniprot.org/uniprotkb/{uid})  ",
        f"**Protein name:** {pname}  ",
        f"**Gene names:** {gnames}",
        f"",
    ]

    if func:
        lines += ["## Function", "", func, ""]

    # GO annotations from UniProt
    go_mf = uniprot.get("go_mf", [])
    go_bp = uniprot.get("go_bp", [])
    go_cc = uniprot.get("go_cc", [])
    total_go = len(go_mf) + len(go_bp) + len(go_cc)

    if total_go:
        lines += [f"## GO Annotations from UniProt ({total_go} total)", ""]

        def _go_section(entries: list[dict], heading: str) -> None:
            if not entries:
                return
            lines.append(f"### {heading}")
            lines.append("")
            lines.append("| GO ID | Term | Evidence |")
            lines.append("|-------|------|----------|")
            for e in entries:
                go_id = e.get("id", "")
                link = f"[{go_id}](https://www.ebi.ac.uk/QuickGO/term/{go_id})"
                lines.append(f"| {link} | {e.get('term', '')} | {e.get('evidence', '')} |")
            lines.append("")

        _go_section(go_mf, "Molecular Function (MF)")
        _go_section(go_bp, "Biological Process (BP)")
        _go_section(go_cc, "Cellular Component (CC)")

    # QuickGO annotations
    valid_qgo = [a for a in quickgo if "error" not in a]
    if valid_qgo:
        lines += [f"## QuickGO Annotations ({len(valid_qgo)} total)", ""]
        lines.append("| GO ID | Term | Aspect | Evidence | Reference |")
        lines.append("|-------|------|--------|----------|-----------|")
        for ann in valid_qgo[:50]:
            go_id = ann.get("go_id", "")
            link = f"[{go_id}](https://www.ebi.ac.uk/QuickGO/term/{go_id})"
            aspect = ann.get("aspect", "")[:2].upper()
            lines.append(
                f"| {link} | {ann.get('go_name', '')} | {aspect} "
                f"| {ann.get('evidence_code', '')} | {ann.get('reference', '')} |"
            )
        if len(valid_qgo) > 50:
            lines.append(f"| … | *{len(valid_qgo) - 50} more — see {gene.lower()}.json* | | | |")
        lines.append("")

    # OLS4 terms
    valid_ols = [t for t in ols if "error" not in t and t.get("label")]
    if valid_ols:
        lines += ["## Related GO Terms from OLS4", ""]
        lines.append("| GO ID | Label | Description |")
        lines.append("|-------|-------|-------------|")
        for term in valid_ols[:10]:
            go_id = term.get("id", "")
            link = f"[{go_id}](https://www.ebi.ac.uk/QuickGO/term/{go_id})" if go_id else "—"
            desc = term.get("description", "")
            if len(desc) > 100:
                desc = desc[:97] + "…"
            lines.append(f"| {link} | {term.get('label', '')} | {desc} |")
        lines.append("")

    return "\n".join(lines)


def _save_results(
    searches_dir: Path,
    gene: str,
    taxon_id: str,
    species_label: str,
    uniprot: dict,
    quickgo: list[dict],
    ols: list[dict],
) -> None:
    """Write <gene>.md (readable) and <gene>.json (full data) to searches_dir."""
    searches_dir.mkdir(exist_ok=True)
    stem = gene.lower()

    # Human-readable Markdown
    md_out = searches_dir / f"{stem}.md"
    md_out.write_text(
        _build_markdown(gene, species_label, taxon_id, uniprot, quickgo, ols),
        encoding="utf-8",
    )

    # Full JSON for programmatic use
    json_out = searches_dir / f"{stem}.json"
    payload = {
        "gene": gene,
        "taxon_id": taxon_id,
        "species": species_label,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "uniprot": uniprot,
        "quickgo_annotations": quickgo,
        "ols4_terms": ols,
    }
    write_json(json_out, payload)

    print_info(f"Saved → {md_out.name}  {json_out.name}")


def _try_save(
    gene: str,
    taxon_id: str,
    species_label: str,
    uniprot: dict,
    quickgo: list[dict],
    ols: list[dict],
) -> None:
    """Auto-save to the active process searches/ dir when exactly one process exists."""
    if not PROCESSES_DIR.exists():
        return
    candidates = sorted(
        p for p in PROCESSES_DIR.iterdir()
        if p.is_dir() and (p / "meta.json").exists()
    )
    if len(candidates) != 1:
        return  # ambiguous or none — don't save silently

    _save_results(
        candidates[0] / "searches",
        gene, taxon_id, species_label, uniprot, quickgo, ols,
    )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@click.command("search")
@click.argument("gene")
@click.option(
    "--species", "-s",
    default="mouse",
    show_default=True,
    help="Species to search: mouse (10090), human (9606), rat (10116), fly, worm, zebrafish, yeast.",
)
@click.option(
    "--process", "-p",
    default=None,
    help="Save results under this process (overrides auto-detection).",
)
def search_command(gene: str, species: str, process: str | None) -> None:
    """Look up a gene/protein across UniProt, QuickGO, and OLS4 (no LLM).

    Queries all three databases simultaneously and displays a consolidated
    report of existing GO annotations, protein function, and related GO
    term suggestions.

    Results are saved to processes/<active>/searches/ as <gene>.md
    (human-readable) and <gene>.json (full data) when a single active
    process can be auto-detected.

    \b
    EXAMPLES
      gocam search PICK1
      gocam search CAMK2A --species human
      gocam search Gria2 --species mouse
    """
    taxon_id, species_label = _SPECIES_MAP.get(species.lower(), ("10090", "Mus musculus"))

    console.print(
        f"[dim]Querying UniProt + QuickGO + OLS4 for[/dim] "
        f"[bold]{gene.upper()}[/bold] "
        f"[dim]({species_label}, taxon:{taxon_id})…[/dim]"
    )

    try:
        uniprot, quickgo, ols = asyncio.run(_fetch_all(gene, taxon_id))
    except Exception as exc:
        print_error(f"Search failed: {exc}")
        raise SystemExit(1)

    _display(gene, species_label, uniprot, quickgo, ols)

    # Save results
    if process:
        process_dir = PROCESSES_DIR / process
        if process_dir.exists():
            _save_results(
                process_dir / "searches",
                gene, taxon_id, species_label, uniprot, quickgo, ols,
            )
    else:
        _try_save(gene, taxon_id, species_label, uniprot, quickgo, ols)
