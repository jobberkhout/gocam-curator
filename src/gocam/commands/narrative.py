"""gocam narrative — deterministic assembly of validated claims into Markdown (no AI)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from gocam.models.claim import (
    SynGOTerm,
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

_PDF_CSS = """
body {
    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    max-width: 900px;
    margin: 30px auto;
    padding: 0 30px;
    color: #222;
}
h1 { font-size: 20pt; color: #1a3a5c; border-bottom: 2px solid #1a3a5c; padding-bottom: 6px; }
h2 { font-size: 14pt; color: #2c5f8a; border-bottom: 1px solid #aac4de; padding-bottom: 3px; margin-top: 24px; }
p  { margin: 4px 0; }
ul { margin: 2px 0 8px 0; padding-left: 20px; }
li { margin: 2px 0; }
a  { color: #1a6fa8; text-decoration: none; }
a:hover { text-decoration: underline; }
strong { color: #111; }
em { color: #555; }
code { font-family: "Courier New", monospace; font-size: 9.5pt;
       background: #f0f4f8; padding: 1px 4px; border-radius: 3px; }
hr { border: none; border-top: 1px solid #ccc; margin: 16px 0; }
"""


def _md_to_pdf(md_text: str, out_path: Path) -> None:
    """Convert a Markdown string to PDF via markdown → HTML → WeasyPrint."""
    try:
        import markdown as _md
        from weasyprint import CSS, HTML
    except ImportError:
        raise ImportError(
            "PDF output requires extra dependencies.\n"
            "Install with:  pip install 'gocam-curator[pdf]'\n"
            "  or:          pip install markdown weasyprint\n"
            "WeasyPrint also needs system libraries (Pango/Cairo):\n"
            "  macOS:  brew install weasyprint   (or: brew install pango cairo)\n"
            "  Linux:  apt install libpango-1.0-0 libpangoft2-1.0-0"
        )

    html_body = _md.markdown(
        md_text,
        extensions=["tables", "fenced_code", "nl2br"],
    )
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>GO-CAM Narrative</title>
</head>
<body>
{html_body}
</body>
</html>"""
    HTML(string=full_html).write_pdf(
        str(out_path),
        stylesheets=[CSS(string=_PDF_CSS)],
    )


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
    if status == "RESOLVED_FROM_DOI":
        return "✓~"          # verified via DOI→PMID resolution, not direct citation
    if status == "OBSOLETE":
        return "!(obsolete)"  # distinguishable from NOT_FOUND in the document
    if status in ("NOT_FOUND", "INVALID"):
        return "✗"
    if status == "ERROR":
        return "✗(error)"
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


def _separate_edge_types(
    edges: list[ValidatedEdgeClaim],
    nodes: list[ValidatedNodeClaim],
) -> tuple[
    list[ValidatedEdgeClaim],  # causal edges — connect two protein activities
    list[ValidatedEdgeClaim],  # has_input edges — substrate/target of an activity
    list[ValidatedEdgeClaim],  # node-property edges — part_of to a non-protein (BP context)
]:
    """Classify edges into three categories for appropriate rendering.

    has_input edges and part_of-to-non-protein edges are node properties in
    GO-CAM, not causal connections. They are displayed on the subject node
    instead of as separate edges.
    """
    known: set[str] = set()
    for n in nodes:
        known.add(n.protein_name.lower())
        if n.gene_symbol:
            known.add(n.gene_symbol.lower())

    causal: list[ValidatedEdgeClaim] = []
    has_input: list[ValidatedEdgeClaim] = []
    node_props: list[ValidatedEdgeClaim] = []

    for edge in edges:
        rel = edge.relation.lower()
        if rel == "has_input":
            has_input.append(edge)
        elif rel == "part_of" and edge.object.lower() not in known:
            # part_of to a biological process term, not to another protein
            node_props.append(edge)
        else:
            causal.append(edge)

    return causal, has_input, node_props


def _build_node_edge_lookups(
    has_input: list[ValidatedEdgeClaim],
    node_props: list[ValidatedEdgeClaim],
) -> tuple[dict[str, list[ValidatedEdgeClaim]], dict[str, list[ValidatedEdgeClaim]]]:
    """Build subject → edge lookups for has_input and node-property edges."""
    hi: dict[str, list[ValidatedEdgeClaim]] = {}
    np: dict[str, list[ValidatedEdgeClaim]] = {}
    for e in has_input:
        hi.setdefault(e.subject.lower(), []).append(e)
    for e in node_props:
        np.setdefault(e.subject.lower(), []).append(e)
    return hi, np


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


def _go_summary(go_term: ValidatedGOTerm | None) -> str:
    """Compact one-line summary of a GO term for excluded-claims listings."""
    if not go_term:
        return "_not specified_"
    icon = _status_icon(go_term.status)
    id_str = f" ({go_term.go_id})" if go_term.go_id else ""
    return f"{go_term.term}{id_str} {icon}"


def _eco_link(eco_code: str) -> str:
    """Clickable QuickGO link for an ECO code."""
    return f"[{eco_code}](https://www.ebi.ac.uk/QuickGO/term/{eco_code})"


def _evidence_block(ev: ValidatedEvidence) -> list[str]:
    """Format one evidence block: assay, ECO code, figure, PMID (clickable), title, DOI."""
    lines = []
    if ev.assay:
        lines.append(f"- Assay: {ev.assay}")
    if ev.eco_code:
        label_str = f" — {ev.eco_label}" if ev.eco_label else ""
        icon = _status_icon(ev.eco_status)
        lines.append(f"- ECO: {_eco_link(ev.eco_code)}{label_str} {icon}")
    if ev.figure:
        lines.append(f"- Figure: {ev.figure}")
    if ev.pmid:
        pmid_icon = _status_icon(ev.pmid_status)
        title_str = f' "{ev.pmid_title}"' if ev.pmid_title else ""
        doi_str = f" | DOI: {_doi_link(ev.doi)}" if ev.doi else ""
        lines.append(
            f"- Reference: {_pmid_link(ev.pmid)} {pmid_icon}{title_str}{doi_str}"
        )
    # Always show source file for audit trail (dimmed if PMID already covers traceability)
    if ev.source_file:
        prefix = "  _(source:" if ev.pmid else "- Source:"
        suffix = ")_" if ev.pmid else ""
        lines.append(f"{prefix} {ev.source_file}{suffix}")
    return lines or ["- Evidence: _none_"]


def _render_node_group(
    group: list[ValidatedNodeClaim],
    index: int,
    has_input_lookup: dict[str, list[ValidatedEdgeClaim]] | None = None,
    node_props_lookup: dict[str, list[ValidatedEdgeClaim]] | None = None,
) -> list[str]:
    lines: list[str] = []

    names = list(dict.fromkeys(n.protein_name for n in group))
    genes = list(dict.fromkeys(n.gene_symbol for n in group if n.gene_symbol))
    uniprot = group[0].uniprot_id
    uniprot_status = group[0].uniprot_status

    gene_str = f" ({', '.join(genes)})" if genes else ""
    if uniprot:
        uniprot_str = f" — [{uniprot}](https://www.uniprot.org/uniprotkb/{uniprot})"
    elif uniprot_status == "NOT_FOUND":
        uniprot_str = " — [UniProt: not found]"
    else:
        uniprot_str = ""
    merged_str = f" \\[merged {len(group)} extractions\\]" if len(group) > 1 else ""

    lines.append(f"**Node {index}: {', '.join(names)}{gene_str}{uniprot_str}{merged_str}**")

    mf_terms = _collect_go_terms([n.molecular_function for n in group])
    bp_terms = _collect_go_terms([n.biological_process for n in group])
    cc_terms = _collect_go_terms([n.cellular_component for n in group])

    lines.extend(_go_lines("MF", mf_terms))
    lines.extend(_go_lines("BP", bp_terms))
    lines.extend(_go_lines("CC", cc_terms))

    # Node-property edges: part_of to a biological process not in the protein set
    subject_keys = {n.protein_name.lower() for n in group} | {n.gene_symbol.lower() for n in group if n.gene_symbol}
    if node_props_lookup:
        bp_context = [e for k in subject_keys for e in node_props_lookup.get(k, [])]
        bp_context = list({id(e): e for e in bp_context}.values())  # deduplicate
        if bp_context:
            seen_obj: set[str] = set()
            for e in bp_context:
                obj_key = e.object.lower()
                if obj_key in seen_obj:
                    continue
                seen_obj.add(obj_key)
                pmid_str = (
                    f" ({_pmid_link(e.evidence.pmid)})" if e.evidence and e.evidence.pmid else ""
                )
                lines.append(f"- BP context (from edge): {e.object}{pmid_str}")

    # has_input edges: substrates/molecular targets of this protein's activity
    if has_input_lookup:
        inputs = [e for k in subject_keys for e in has_input_lookup.get(k, [])]
        inputs = list({id(e): e for e in inputs}.values())
        if inputs:
            seen_inp: set[str] = set()
            for e in inputs:
                inp_key = e.object.lower()
                if inp_key in seen_inp:
                    continue
                seen_inp.add(inp_key)
                assay_str = f" [{e.evidence.assay}]" if e.evidence and e.evidence.assay else ""
                pmid_str = (
                    f" ({_pmid_link(e.evidence.pmid)})" if e.evidence and e.evidence.pmid else ""
                )
                lines.append(f"- Substrate/Input: {e.object}{assay_str}{pmid_str}")

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

    # SynGO enrichment with clickable PMIDs, grouped by domain
    all_syngo_terms: list[SynGOTerm] = list(
        {t.go_id: t for n in group for t in n.syngo_enrichment}.values()
    )
    if all_syngo_terms:
        lines.append("- SynGO annotations:")
        for t in all_syngo_terms:
            pmid_links = ", ".join(_pmid_link(p) for p in t.pmids) if t.pmids else "no PMID"
            lines.append(f"  - [{t.domain}] {t.go_name} ({_quickgo_link(t.go_id)}) — {pmid_links}")

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
# Main assembly — one function per document
# ---------------------------------------------------------------------------

def _partition_claims(report: ValidationReport) -> tuple[
    list[list[ValidatedNodeClaim]],                    # included node groups
    list[tuple[list[ValidatedNodeClaim], list[str]]],  # excluded nodes
    list[list[ValidatedEdgeClaim]],                    # included causal edge groups
    list[tuple[list[ValidatedEdgeClaim], list[str]]],  # excluded causal edges
    dict[str, list[ValidatedEdgeClaim]],               # has_input lookup (subject → edges)
    dict[str, list[ValidatedEdgeClaim]],               # node-property lookup (subject → edges)
]:
    """Split all claims into included/excluded groups.

    has_input and part_of-to-non-protein edges are separated out before
    grouping so they are displayed on nodes rather than as standalone edges.
    """
    node_groups = _group_nodes_by_uniprot(report.nodes)
    included_node_groups: list[list[ValidatedNodeClaim]] = []
    excluded_nodes: list[tuple[list[ValidatedNodeClaim], list[str]]] = []
    for group in node_groups:
        evidences = _collect_evidences(group)
        if any(_evidence_is_complete(ev) for ev in evidences):
            included_node_groups.append(group)
        else:
            all_missing = _missing_fields(evidences[0] if evidences else None)
            excluded_nodes.append((group, all_missing))

    # Separate edge types: causal vs has_input vs node-property (part_of to BP/CC)
    causal_edges, has_input_edges, node_prop_edges = _separate_edge_types(
        report.edges, report.nodes
    )
    has_input_lookup, node_props_lookup = _build_node_edge_lookups(has_input_edges, node_prop_edges)

    edge_groups = _group_edges(causal_edges)
    included_edge_groups: list[list[ValidatedEdgeClaim]] = []
    excluded_edges: list[tuple[list[ValidatedEdgeClaim], list[str]]] = []
    for group in edge_groups:
        evidences = [e.evidence for e in group if e.evidence]
        if any(_evidence_is_complete(ev) for ev in evidences):
            included_edge_groups.append(group)
        else:
            all_missing = _missing_fields(evidences[0] if evidences else None)
            excluded_edges.append((group, all_missing))

    return (
        included_node_groups, excluded_nodes,
        included_edge_groups, excluded_edges,
        has_input_lookup, node_props_lookup,
    )


def _build_nodes_doc(
    report: ValidationReport,
    included: list[list[ValidatedNodeClaim]],
    excluded: list[tuple[list[ValidatedNodeClaim], list[str]]],
    process_name: str,
    species: str,
    has_input_lookup: dict[str, list[ValidatedEdgeClaim]] | None = None,
    node_props_lookup: dict[str, list[ValidatedEdgeClaim]] | None = None,
) -> str:
    """Nodes document: one entry per protein with all GO terms, evidence, and quotes."""
    lines: list[str] = []
    lines.append(f"# GO-CAM Nodes — {process_name}")
    lines.append(f"\n*Species: {species} | Generated: {date.today().isoformat()}*")
    lines.append("*Use this document to create entities in GO-CAM.*\n")

    n_merged = sum(1 for g in included if len(g) > 1)
    if included:
        merge_note = f" ({n_merged} protein(s) collapsed from duplicate extractions)" if n_merged else ""
        lines.append(f"## Nodes (Molecular Activities){merge_note}\n")
        for i, group in enumerate(included, 1):
            lines.extend(_render_node_group(group, i, has_input_lookup, node_props_lookup))

    # Validation summary
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

    lines.append("## Summary\n")
    lines.append(
        f"- {len(report.nodes)} extracted → {len(included)} included"
        + (f" ({n_merged} collapsed)" if n_merged else "")
        + (f", {len(excluded)} excluded" if excluded else "")
    )
    lines.append(f"- GO terms verified: {go_verified}/{go_total}")
    lines.append(f"- UniProt matches: {uniprot_found}/{len(report.nodes)}")
    lines.append(f"- SynGO matches: {syngo_hits}/{len(report.nodes)}")

    if excluded:
        lines.append("\n## Excluded — No Verified PMID\n")
        lines.append(
            "_These nodes lack a traceable paper reference. "
            "Rename the source file with a PMID (e.g. 20357116.pdf) and re-run validate._\n"
        )
        for group, missing in excluded:
            names = ", ".join(dict.fromkeys(n.protein_name for n in group))
            genes = ", ".join(dict.fromkeys(n.gene_symbol for n in group if n.gene_symbol))
            gene_str = f" ({genes})" if genes else ""
            lines.append(f"\n**{names}{gene_str}** — missing: {', '.join(missing)}")
            # Collect and show what GO terms were found, so the work isn't wasted
            mf_terms = _collect_go_terms([n.molecular_function for n in group])
            bp_terms = _collect_go_terms([n.biological_process for n in group])
            cc_terms = _collect_go_terms([n.cellular_component for n in group])
            for go_label, terms in (("MF", mf_terms), ("BP", bp_terms), ("CC", cc_terms)):
                if terms:
                    lines.append(f"- {go_label}: " + " | ".join(_go_summary(t) for t in terms))
            # Show assay and source if available
            evs = _collect_evidences(group)
            for ev in evs:
                if ev.assay:
                    lines.append(f"- Assay: {ev.assay}")
                if ev.source_file:
                    lines.append(f"- Source: {ev.source_file}")
            quotes = list(dict.fromkeys(n.quote for n in group if n.quote))
            for q in quotes[:1]:  # just first quote to keep it short
                lines.append(f'- Quote: "{q[:150]}{"…" if len(q) > 150 else ""}"')

    unresolved: list[str] = []
    for group in included:
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


def _build_edges_doc(
    included: list[list[ValidatedEdgeClaim]],
    excluded: list[tuple[list[ValidatedEdgeClaim], list[str]]],
    process_name: str,
    species: str,
) -> str:
    """Edges document: one entry per causal relation for wiring up the GO-CAM model."""
    lines: list[str] = []
    lines.append(f"# GO-CAM Edges — {process_name}")
    lines.append(f"\n*Species: {species} | Generated: {date.today().isoformat()}*")
    lines.append("*Use this document to connect entities in GO-CAM.*\n")

    n_merged = sum(1 for g in included if len(g) > 1)
    if included:
        merge_note = f" ({n_merged} relation(s) collapsed from duplicate extractions)" if n_merged else ""
        lines.append(f"## Edges (Causal Relations){merge_note}\n")
        for i, group in enumerate(included, 1):
            lines.extend(_render_edge_group(group, i))

    lines.append("## Summary\n")
    total_raw = sum(len(g) for g in included) + sum(len(g) for g, _ in excluded)
    lines.append(
        f"- {total_raw} extracted → {len(included)} included"
        + (f" ({n_merged} collapsed)" if n_merged else "")
        + (f", {len(excluded)} excluded" if excluded else "")
    )

    if excluded:
        lines.append("\n## Excluded — No Verified PMID\n")
        lines.append(
            "_These edges lack a traceable paper reference. "
            "Rename the source file with a PMID (e.g. 20357116.pdf) and re-run validate._\n"
        )
        for group, missing in excluded:
            first = group[0]
            lines.append(
                f"\n**{first.subject} → {first.relation} → {first.object}** "
                f"— missing: {', '.join(missing)}"
            )
            if first.mechanism:
                lines.append(f"- Mechanism: {first.mechanism}")
            evs = [e.evidence for e in group if e.evidence]
            for ev in evs[:1]:
                if ev.assay:
                    lines.append(f"- Assay: {ev.assay}")
                if ev.source_file:
                    lines.append(f"- Source: {ev.source_file}")
            quotes = list(dict.fromkeys(e.quote for e in group if e.quote))
            for q in quotes[:1]:
                lines.append(f'- Quote: "{q[:150]}{"…" if len(q) > 150 else ""}"')

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
@click.option(
    "--pdf",
    is_flag=True,
    default=False,
    help="Also write PDF versions alongside the Markdown files (requires: pip install markdown weasyprint).",
)
def narrative_command(process: str | None, genes: str | None, pdf: bool) -> None:
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
    OUTPUT  (two files per run, versioned independently)
      narratives/claims_nodes_v1.md   Entities — use to create GO-CAM nodes
      narratives/claims_edges_v1.md   Relations — use to wire up the model
      With --genes: brag_arf6_nodes_v1.md / brag_arf6_edges_v1.md
      With --pdf:   same names with .pdf extension, written alongside .md
      - Nodes with same UniProt ID are collapsed (all info preserved)
      - Edges with same subject/relation/object are collapsed
      - GO terms: clickable links to QuickGO
      - PMIDs: clickable links to PubMed + paper title + clickable DOI
      - Excluded claims listed at the end for manual review

    \b
    PDF DEPENDENCIES  (only needed with --pdf)
      pip install 'gocam-curator[pdf]'
      macOS system libs:  brew install pango cairo

    \b
    EXAMPLES
      gocam narrative
      gocam narrative --pdf
      gocam narrative --genes brag,arf6,ap2,pick --pdf
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

    # Partition into included/excluded groups
    inc_nodes, exc_nodes, inc_edges, exc_edges, has_input_lookup, node_props_lookup = _partition_claims(filtered_report)

    n_nodes_excluded = len(exc_nodes)
    n_edges_excluded = len(exc_edges)

    console.print(
        f"[bold]Process:[/bold] {process_name}  "
        f"[bold]Nodes:[/bold] {len(inc_nodes)} included, {n_nodes_excluded} excluded  "
        f"[bold]Edges:[/bold] {len(inc_edges)} included, {n_edges_excluded} excluded"
    )
    if n_nodes_excluded or n_edges_excluded:
        print_warning(
            f"{n_nodes_excluded + n_edges_excluded} claim(s) excluded (no verified PMID) "
            "— listed at end of narrative for manual review"
        )

    nodes_md = _build_nodes_doc(
        filtered_report, inc_nodes, exc_nodes, process_name, species,
        has_input_lookup=has_input_lookup, node_props_lookup=node_props_lookup,
    )
    edges_md = _build_edges_doc(inc_edges, exc_edges, process_name, species)

    narratives_dir = process_dir / _NARRATIVES_DIR
    narratives_dir.mkdir(exist_ok=True)

    base = "_".join(gene_list) if gene_list else "claims"
    nodes_path = _next_version_path(narratives_dir, prefix=f"{base}_nodes")
    edges_path = _next_version_path(narratives_dir, prefix=f"{base}_edges")

    nodes_path.write_text(nodes_md, encoding="utf-8")
    edges_path.write_text(edges_md, encoding="utf-8")

    print_success(f"Nodes narrative → {nodes_path}")
    print_success(f"Edges narrative → {edges_path}")

    if pdf:
        nodes_pdf = nodes_path.with_suffix(".pdf")
        edges_pdf = edges_path.with_suffix(".pdf")
        try:
            _md_to_pdf(nodes_md, nodes_pdf)
            print_success(f"Nodes PDF       → {nodes_pdf}")
            _md_to_pdf(edges_md, edges_pdf)
            print_success(f"Edges PDF       → {edges_pdf}")
        except ImportError as exc:
            print_warning(f"PDF generation skipped: {exc}")

    console.print(f"\n[dim]Open with: open {nodes_path.parent}[/dim]")
