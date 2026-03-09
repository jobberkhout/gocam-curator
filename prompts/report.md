# Phase 2b — Extraction Report Synthesis Prompt

Your task is to synthesize multiple extraction JSON files into a single structured Markdown report.

This report is the curator's reference document before the expert meeting. It should be accurate, honest about uncertainty, and highlight conflicts and gaps.

**DO NOT MAP TO GO TERMS. DO NOT SUGGEST GO IDs. This is still Phase 2.**

---

## Output Format

Return a Markdown document following this structure exactly:

```markdown
# Extraction Report — {process_name}
## Generated: {date} | Sources: {N} files analyzed

### Sources Analyzed
| # | File | Type | Entities found | Interactions |
|---|------|------|---------------|--------------|
| 1 | filename.txt | text | N | N |
...

---

### Protein Synonym Map
| Canonical name (gene symbol) | Aliases found across sources |
|------------------------------|------------------------------|
| GRIA2 | GluA2, GluR2, AMPA receptor subunit 2 |
...
(List every protein that appears under more than one name. Use the canonical gene symbol throughout the rest of this report.)

---

### Consolidated Protein/Gene List (deduplicated)
| Protein | Gene | Sources | Described activities | Confidence |
|---------|------|---------|---------------------|------------|
| CaMKII | CAMK2A | 1, 3 | phosphorylates GluA1 at Ser831 | HIGH — direct biochemical evidence |
...

---

### Interaction Map (all sources merged)
Format per entry: `N. ProteinA → ProteinB (N sources: file1 [Fig. X, PMID:XXXXXXXX], file2 [Fig. Y] | causal_type | assay) — CONFIDENCE`

Rules:
- For each source that supports this interaction, include the figure reference and PMID if present in the extraction JSON.
- If a source has no figure or PMID, omit those brackets.
- Include the assay type for the strongest-evidence source.

Example:
1. BRAG2 → Arf6 (4 sources: scholz2010 [Fig. 2C, PMID:20530663], ampar_pdf [Fig. 1], slide05, slide09 | DIRECT | GEF activity assay) — HIGH
2. AP2 → GluA2 (2 sources: lee2002 [Fig. 3A, PMID:12007421], ampar_pdf | WARNING: only binding described, MF unknown) — LOW

---

### Cross-Source Conflicts
⚠ [Description of conflict between sources]
  → Suggested question for expert.

(Write "None identified." if no conflicts.)

---

### Gaps Identified (across all sources)
1. **Gap name:** Description of what is missing.
...

---

### Suggested Questions for Expert Meeting
1. "Question text?"
...
```

---

## Synthesis Rules

1. **Build a synonym map first.** Before writing anything else, identify all proteins that appear under different names across sources. Pick the official gene symbol as the canonical name (e.g., GRIA2, not GluA2). Use that canonical name everywhere in the report. List all aliases in the Protein Synonym Map table.
2. **Count source support** — for each interaction, list the source filenames (not numbers) that support it. Use the format: `(N sources: file1, file2, ...)`.
3. **Confidence levels based on source count AND evidence quality:**
   - 1 source → LOW
   - 2–3 sources → MEDIUM
   - 4+ sources → HIGH
   - Override upward for direct biochemical/electrophysiological evidence (kinase assay, patch-clamp)
   - Override downward for binding-only or cartoon-only evidence
4. **Flag binding-only interactions** explicitly in the Interaction Map with "WARNING: only binding described, MF unknown."
5. **Detect conflicts** — same protein shown as activator in one source and inhibitor in another, or different substrates reported. Flag every conflict with a suggested expert question.
6. **Merge gaps** — deduplicate similar gaps across sources, order by importance.
7. **Generate expert questions** — combine and deduplicate all questions_for_expert from all sources, plus questions arising from conflicts. Make them concrete and answerable.
8. **Do not hallucinate** — only include information from the provided extraction JSONs. If something is unclear, say so.
9. **Interaction Map completeness — CRITICAL RULE:** For EVERY protein in the Consolidated Protein List that has a non-empty "Described activities" column, there MUST be at least one corresponding entry in the Interaction Map. A described activity IS an interaction. Examples:
   - "Calcineurin — dephosphorylates GluA1" → MUST appear in Interaction Map as: `Calcineurin → GluA1 (dephosphorylation)`
   - "Thorase — ATPase-driven disruption of GluA2-GRIP1 complex" → MUST appear as: `Thorase → GluA2-GRIP1 complex (ATPase-driven disassembly)`
   - "PICK1 — competes with GRIP for GluA2 binding" → WARNING entry: `PICK1 → GluA2 (WARNING: binding only, MF unknown)`
   A protein with a described activity that does NOT appear in the Interaction Map is a bug in your output. Count your protein list and your interaction list. If the Interaction Map has fewer entries than proteins with described activities, you have missed interactions.
