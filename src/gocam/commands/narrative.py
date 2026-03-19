"""gocam narrative — deterministic assembly of validated claims into Markdown (no AI)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from gocam.models.claim import (
    ValidatedEdgeClaim,
    ValidatedEvidence,
    ValidatedGOTerm,
    ValidatedNodeClaim,
    ValidationReport,
)
from gocam.utils.display import console, print_error, print_info, print_success, print_warning
from gocam.utils.io import read_json
from gocam.utils.process import load_meta, resolve_process

_NARRATIVES_DIR = "narratives"

_CONF_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
_STATUS_RANK = {"VERIFIED": 3, "FOUND": 3, "OBSOLETE": 2, "NOT_FOUND": 1, "SKIPPED": 0}


def _next_version_path(narratives_dir: Path, prefix: str = "claims") -> Path:
    v = 1
    while True:
        candidate = narratives_dir / f"{prefix}_v{v}.md"
        if not candidate.exists():
            return candidate
        v += 1


def _matches_genes(tokens: list[str], *fields: str | None) -> bool:
    """Return True if any gene token is a substring of any of the given fields."""
    for field in fields:
        if not field:
            continue
        field_lower = field.lower()
        if any(tok in field_lower for tok in tokens):
            return True
    return False


def _filter_by_genes(
    nodes: list[ValidatedNodeClaim],
    edges: list[ValidatedEdgeClaim],
    genes: list[str],
) -> tuple[list[ValidatedNodeClaim], list[ValidatedEdgeClaim]]:
    """Keep only nodes/edges that match at least one gene token (substring, case-insensitive)."""
    tokens = [g.lower() for g in genes]
    filtered_nodes = [
        n for n in nodes
        if _matches_genes(tokens, n.gene_symbol, n.protein_name)
    ]
    filtered_edges = [
        e for e in edges
        if _matches_genes(tokens, e.subject, e.object)
    ]
    return filtered_nodes, filtered_edges


# ---------------------------------------------------------------------------
# Link helpers
# ---------------------------------------------------------------------------

def _doi_link(doi: str | None) -> str:
    if not doi:
        return ""
    return f"[{doi}](https://doi.org/{doi})"


def _pmid_link(pmid: str) -> str:
    return f"[PMID:{pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid}/)"


def _quickgo_link(go_id: str) -> str:
    return f"[{go_id}](https://www.ebi.ac.uk/QuickGO/term/{go_id})"


def _status_icon(status: str) -> str:
    if status in ("VERIFIED", "FOUND"):
        return "✓"
    if status == "OBSOLETE":
        return "!"
    if status in ("NOT_FOUND", "INVALID"):
        return "✗"
    return "?"


# ---------------------------------------------------------------------------
# Evidence quality gate
# ---------------------------------------------------------------------------

_GOOD_PMID_STATUSES = {"VERIFIED", "RESOLVED_FROM_DOI"}


def _evidence_is_complete(ev: ValidatedEvidence | None) -> bool:
    """Return True when evidence is traceable to a real paper (verified PMID).

    Assay is desirable but not required — review articles and secondary sources
    often lack a specific experimental method.
    """
    if not ev:
        return False
    return bool(ev.pmid and ev.pmid_status in _GOOD_PMID_STATUSES)


def _missing_fields(ev: ValidatedEvidence | None) -> list[str]:
    """Return a human-readable list of what is missing from the evidence."""
    missing = []
    if not ev:
        return ["evidence"]
    if not ev.pmid:
        missing.append("PMID")
    elif ev.pmid_status not in _GOOD_PMID_STATUSES:
        missing.append(f"PMID {ev.pmid} ({ev.pmid_status})")
    return missing


# ---------------------------------------------------------------------------
# Node grouping and merging (collapse by UniProt ID)
# ---------------------------------------------------------------------------

def _collect_go_terms(terms: list[ValidatedGOTerm | None]) -> list[ValidatedGOTerm]:
    """Deduplicate GO terms by GO ID, keeping the highest-status entry."""
    best: dict[str, ValidatedGOTerm] = {}
    for t in terms:
        if t is None:
            continue
        key = t.go_id or t.term.lower()
        if key not in best or _STATUS_RANK.get(t.status, 0) > _STATUS_RANK.get(best[key].status, 0):
            best[key] = t
    return list(best.values())


def _collect_evidences(nodes: list[ValidatedNodeClaim]) -> list[ValidatedEvidence]:
    """Gather all evidence records across nodes, deduplicated by PMID."""
    seen: set[str] = set()
    result: list[ValidatedEvidence] = []
    for n in nodes:
        if not n.evidence:
            continue
        key = n.evidence.pmid or str(id(n.evidence))
        if key not in seen:
            seen.add(key)
            result.append(n.evidence)
    return result


def _group_nodes_by_uniprot(
    nodes: list[ValidatedNodeClaim],
) -> list[list[ValidatedNodeClaim]]:
    """Group nodes by UniProt ID. Nodes without a UniProt ID are not merged."""
    groups: dict[str, list[ValidatedNodeClaim]] = {}
    singletons: list[list[ValidatedNodeClaim]] = []
    for node in nodes:
        if node.uniprot_id:
            groups.setdefault(node.uniprot_id, []).append(node)
        else:
            singletons.append([node])
    return list(groups.values()) + singletons


def _group_edges(edges: list[ValidatedEdgeClaim]) -> list[list[ValidatedEdgeClaim]]:
    """Group edges with the same subject + relation + object."""
    groups: dict[tuple[str, str, str], list[ValidatedEdgeClaim]] = {}
    for edge in edges:
        key = (edge.subject.lower(), edge.relation.lower(), edge.object.lower())
        groups.setdefault(key, []).append(edge)
    return list(groups.values())


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _go_lines(label: str, terms: list[ValidatedGOTerm]) -> list[str]:
    if not terms:
        return [f"- {label}: _not specified_"]
    lines = []
    for go_term in terms:
        icon = _status_icon(go_term.status)
        go_id_str = f" ({_quickgo_link(go_term.go_id)})" if go_term.go_id else ""
        official = (
            f' [official: "{go_term.official_label}"]'
            if go_term.official_label
            and go_term.official_label.lower() != go_term.term.lower()
            else ""
        )
        annotated = " [already in QuickGO]" if go_term.already_annotated else ""
        syngo = " [SynGO confirmed]" if go_term.syngo_confirmed else ""
        lines.append(f"- {label}: {go_term.term}{go_id_str} {icon}{official}{annotated}{syngo}")
    return lines


def _evidence_block(ev: ValidatedEvidence) -> list[str]:
    """Format one evidence block: assay, figure, PMID (clickable), title, DOI."""
    lines = []
    if ev.assay:
        eco_str = f" ({ev.eco_code})" if ev.eco_code else ""
        eco_status = f" {_status_icon(ev.eco_status)}" if ev.eco_code else ""
        lines.append(f"- Assay: {ev.assay}{eco_str}{eco_status}")
    if ev.figure:
        lines.append(f"- Figure: {ev.figure}")
    if ev.pmid:
        pmid_icon = _status_icon(ev.pmid_status)
        title_str = f' "{ev.pmid_title}"' if ev.pmid_title else ""
        doi_str = f" | DOI: {_doi_link(ev.doi)}" if ev.doi else ""
        lines.append(
            f"- Reference: {_pmid_link(ev.pmid)} {pmid_icon}{title_str}{doi_str}"
        )
    return lines or ["- Evidence: _none_"]


def _render_node_group(group: list[ValidatedNodeClaim], index: int) -> list[str]:
    lines: list[str] = []

    names = list(dict.fromkeys(n.protein_name for n in group))
    genes = list(dict.fromkeys(n.gene_symbol for n in group if n.gene_symbol))
    uniprot = group[0].uniprot_id

    gene_str = f" ({', '.join(genes)})" if genes else ""
    uniprot_str = (
        f" — [{uniprot}](https://www.uniprot.org/uniprotkb/{uniprot})" if uniprot else ""
    )
    merged_str = f" \\[merged {len(group)} extractions\\]" if len(group) > 1 else ""

    lines.append(f"**Node {index}: {', '.join(names)}{gene_str}{uniprot_str}{merged_str}**")

    mf_terms = _collect_go_terms([n.molecular_function for n in group])
    bp_terms = _collect_go_terms([n.biological_process for n in group])
    cc_terms = _collect_go_terms([n.cellular_component for n in group])

    lines.extend(_go_lines("MF", mf_terms))
    lines.extend(_go_lines("BP", bp_terms))
    lines.extend(_go_lines("CC", cc_terms))

    evidences = _collect_evidences(group)
    for ev in evidences:
        lines.extend(_evidence_block(ev))
    if not evidences:
        lines.append("- Evidence: _none_")

    best_conf = max((n.confidence for n in group), key=lambda c: _CONF_RANK.get(c, 0))
    lines.append(f"- Confidence: {best_conf}")

    quotes = list(dict.fromkeys(n.quote for n in group if n.quote))
    for q in quotes:
        lines.append(f'- Quote: "{q}"')

    all_syngo = list(dict.fromkeys(ann for n in group for ann in n.syngo_annotations))
    if all_syngo:
        lines.append(f"- SynGO: {', '.join(all_syngo[:5])}")

    lines.append("")
    return lines


def _render_edge_group(group: list[ValidatedEdgeClaim], index: int) -> list[str]:
    lines: list[str] = []
    first = group[0]
    merged_str = f" \\[merged {len(group)} extractions\\]" if len(group) > 1 else ""

    lines.append(f"**Edge {index}: {first.subject} → {first.relation} → {first.object}{merged_str}**")

    mechanisms = list(dict.fromkeys(e.mechanism for e in group if e.mechanism))
    if mechanisms:
        lines.append(f"- Mechanism: {'; '.join(mechanisms)}")

    seen_pmids: set[str] = set()
    for e in group:
        if not e.evidence:
            continue
        key = e.evidence.pmid or str(id(e.evidence))
        if key not in seen_pmids:
            seen_pmids.add(key)
            lines.extend(_evidence_block(e.evidence))
    if not seen_pmids:
        lines.append("- Evidence: _none_")

    best_conf = max((e.confidence for e in group), key=lambda c: _CONF_RANK.get(c, 0))
    lines.append(f"- Confidence: {best_conf}")

    quotes = list(dict.fromkeys(e.quote for e in group if e.quote))
    for q in quotes:
        lines.append(f'- Quote: "{q}"')

    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Main assembly
# ---------------------------------------------------------------------------

def _build_narrative(report: ValidationReport, process_name: str, species: str) -> str:
    lines: list[str] = []
    lines.append(f"# GO-CAM Claims — {process_name}")
    lines.append(f"\n*Species: {species} | Generated: {date.today().isoformat()}*\n")

    # --- Filter nodes by evidence quality ---
    node_groups = _group_nodes_by_uniprot(report.nodes)
    included_node_groups: list[list[ValidatedNodeClaim]] = []
    excluded_nodes: list[tuple[list[ValidatedNodeClaim], list[str]]] = []

    for group in node_groups:
        evidences = _collect_evidences(group)
        if any(_evidence_is_complete(ev) for ev in evidences):
            included_node_groups.append(group)
        else:
            # Collect what's missing from the best available evidence
            all_missing = _missing_fields(evidences[0] if evidences else None)
            excluded_nodes.append((group, all_missing))

    # --- Filter edges by evidence quality ---
    edge_groups = _group_edges(report.edges)
    included_edge_groups: list[list[ValidatedEdgeClaim]] = []
    excluded_edges: list[tuple[list[ValidatedEdgeClaim], list[str]]] = []

    for group in edge_groups:
        evidences = [e.evidence for e in group if e.evidence]
        if any(_evidence_is_complete(ev) for ev in evidences):
            included_edge_groups.append(group)
        else:
            all_missing = _missing_fields(evidences[0] if evidences else None)
            excluded_edges.append((group, all_missing))

    n_node_merged = sum(1 for g in included_node_groups if len(g) > 1)
    n_edge_merged = sum(1 for g in included_edge_groups if len(g) > 1)

    # --- Nodes ---
    if included_node_groups:
        merge_note = (
            f" ({n_node_merged} protein(s) collapsed from duplicate extractions)"
            if n_node_merged else ""
        )
        lines.append(f"## Nodes (Molecular Activities){merge_note}\n")
        for i, group in enumerate(included_node_groups, 1):
            lines.extend(_render_node_group(group, i))

    # --- Edges ---
    if included_edge_groups:
        merge_note = (
            f" ({n_edge_merged} relation(s) collapsed from duplicate extractions)"
            if n_edge_merged else ""
        )
        lines.append(f"## Edges (Causal Relations){merge_note}\n")
        for i, group in enumerate(included_edge_groups, 1):
            lines.extend(_render_edge_group(group, i))

    # --- Validation Summary ---
    total_raw_nodes = len(report.nodes)
    total_included_nodes = sum(len(g) for g in included_node_groups)
    total_raw_edges = len(report.edges)
    total_included_edges = sum(len(g) for g in included_edge_groups)

    lines.append("## Validation Summary\n")

    go_verified = sum(
        1 for n in report.nodes
        for gt in (n.molecular_function, n.biological_process, n.cellular_component)
        if gt and gt.status == "VERIFIED"
    )
    go_total = sum(
        1 for n in report.nodes
        for gt in (n.molecular_function, n.biological_process, n.cellular_component)
        if gt
    )
    uniprot_found = sum(1 for n in report.nodes if n.uniprot_status == "FOUND")
    syngo_hits = sum(1 for n in report.nodes if n.syngo_annotations)

    lines.append(
        f"- Nodes: {total_raw_nodes} extracted → {len(included_node_groups)} included"
        + (f" ({n_node_merged} collapsed)" if n_node_merged else "")
        + (f", {len(excluded_nodes)} excluded (insufficient evidence)" if excluded_nodes else "")
    )
    lines.append(
        f"- Edges: {total_raw_edges} extracted → {len(included_edge_groups)} included"
        + (f" ({n_edge_merged} collapsed)" if n_edge_merged else "")
        + (f", {len(excluded_edges)} excluded (insufficient evidence)" if excluded_edges else "")
    )
    lines.append(f"- GO terms verified: {go_verified}/{go_total}")
    lines.append(f"- UniProt matches: {uniprot_found}/{total_raw_nodes}")
    lines.append(f"- SynGO matches: {syngo_hits}/{total_raw_nodes}")

    # --- Excluded (for transparency) ---
    if excluded_nodes or excluded_edges:
        lines.append("\n## Excluded — Insufficient Evidence\n")
        lines.append(
            "_These claims were removed from the main narrative because they lack a "
            "verified PMID. Review manually if needed._\n"
        )
        for group, missing in excluded_nodes:
            names = ", ".join(dict.fromkeys(n.protein_name for n in group))
            lines.append(f"- **Node — {names}**: missing {', '.join(missing)}")
        for group, missing in excluded_edges:
            first = group[0]
            lines.append(
                f"- **Edge — {first.subject} → {first.relation} → {first.object}**: "
                f"missing {', '.join(missing)}"
            )

    # --- Unresolved (included claims that still need attention) ---
    unresolved: list[str] = []
    for group in included_node_groups:
        for n in group:
            if not n.molecular_function or n.molecular_function.status != "VERIFIED":
                mf_desc = (
                    f'"{n.molecular_function.term}" — {n.molecular_function.status}'
                    if n.molecular_function else "not specified"
                )
                unresolved.append(f"- {n.protein_name} ({n.id}): MF {mf_desc}")

    if unresolved:
        lines.append("\n## Unresolved GO Terms\n")
        lines.extend(unresolved)

    lines.append("")
    return "\n".join(lines)


@click.command("narrative")
@click.option(
    "--process", "-p",
    default=None,
    help="Process name. Auto-detected if there is exactly one process.",
)
@click.option(
    "--genes", "-g",
    default=None,
    help=(
        "Comma-separated gene/protein names to include. Partial, case-insensitive match. "
        "e.g. --genes brag,arf6,ap2,pick"
    ),
)
def narrative_command(process: str | None, genes: str | None) -> None:
    """Generate an expert-readable document from validated claims (no AI).

    Reads validation/validated_claims.json and assembles a Markdown document.
    Claims without a verified PMID are excluded from the main narrative and
    listed separately so you can review them without wasting time chasing
    unverifiable references.

    \b
    INCLUSION CRITERIA
      - PMID verified against PubMed (VERIFIED or RESOLVED_FROM_DOI)
      - Assay is shown when available but is not required

    \b
    GENE FILTER  (--genes brag,arf6,ap2,pick)
      Limits the narrative to nodes/edges that match any of the given tokens.
      Matching is a case-insensitive substring search on gene symbol and protein
      name, so "brag" matches BRAG1, BRAG2, etc. and "ap2" matches AP2A1,
      AP2M1, AP-2, etc.  Output is saved as <genes>_v1.md instead of claims_v1.md.

    \b
    OUTPUT  narratives/claims_v1.md  (or v2, v3 ... if earlier versions exist)
      - Nodes with same UniProt ID are collapsed (all info preserved)
      - Edges with same subject/relation/object are collapsed
      - GO terms: clickable links to QuickGO
      - PMIDs: clickable links to PubMed + paper title + clickable DOI
      - Excluded claims listed at the end for manual review

    \b
    EXAMPLES
      gocam narrative
      gocam narrative --genes brag,arf6,ap2,pick
      gocam narrative -g arf6 -p vesicle-fusion
    """
    process_dir = resolve_process(process)
    meta = load_meta(process_dir)
    process_name: str = meta.get("process_name", process_dir.name)
    species: str = meta.get("species", "")

    val_path = process_dir / "validation" / "validated_claims.json"
    if not val_path.exists():
        print_error("No validated_claims.json found. Run 'gocam validate' first.")
        raise SystemExit(1)

    report = ValidationReport.model_validate(read_json(val_path))

    if not report.nodes and not report.edges:
        print_warning("No validated claims found.")
        raise SystemExit(0)

    # Apply gene filter if requested
    gene_list: list[str] = []
    if genes:
        gene_list = [g.strip() for g in genes.split(",") if g.strip()]

    nodes = report.nodes
    edges = report.edges
    if gene_list:
        nodes, edges = _filter_by_genes(nodes, edges, gene_list)
        print_info(
            f"Gene filter: {', '.join(gene_list)} → "
            f"{len(nodes)} node(s), {len(edges)} edge(s) matched"
        )
        if not nodes and not edges:
            print_warning("No claims matched the gene filter.")
            raise SystemExit(0)

    # Swap report nodes/edges for the filtered set before counting and rendering
    filtered_report = report.model_copy(update={"nodes": nodes, "edges": edges})

    # Pre-flight counts for the terminal summary
    node_groups = _group_nodes_by_uniprot(nodes)
    edge_groups = _group_edges(edges)
    n_nodes_included = sum(
        1 for g in node_groups
        if any(_evidence_is_complete(ev) for ev in _collect_evidences(g))
    )
    n_edges_included = sum(
        1 for g in edge_groups
        if any(_evidence_is_complete(e.evidence) for e in g if e.evidence)
    )
    n_nodes_excluded = len(node_groups) - n_nodes_included
    n_edges_excluded = len(edge_groups) - n_edges_included

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Nodes:[/bold] {n_nodes_included} included, {n_nodes_excluded} excluded  "
        f"[bold]Edges:[/bold] {n_edges_included} included, {n_edges_excluded} excluded"
    )
    if n_nodes_excluded or n_edges_excluded:
        print_warning(
            f"{n_nodes_excluded + n_edges_excluded} claim(s) excluded (no verified PMID) "
            "— listed at end of narrative for manual review"
        )

    narrative_md = _build_narrative(filtered_report, process_name, species)

    narratives_dir = process_dir / _NARRATIVES_DIR
    narratives_dir.mkdir(exist_ok=True)

    if gene_list:
        prefix = "_".join(gene_list)
    else:
        prefix = "claims"
    out_path = _next_version_path(narratives_dir, prefix=prefix)
    out_path.write_text(narrative_md, encoding="utf-8")

    print_success(f"Narrative saved → {out_path}")
    console.print(f"\n[dim]Open with: open {out_path}[/dim]")
