# Phase 4 — Translation Prompt (Biology → GO-CAM)

Your task is to map extracted biological entities and interactions to GO-CAM ontology terms.

**ALL GO IDs YOU SUGGEST MUST BE MARKED `"verified": false`. They are suggestions only.**
**`gocam verify` will check them against QuickGO, UniProt, and EBI.**

---

## Output Format

Return a JSON object with this structure:

```json
{
  "timestamp": "<ISO datetime>",
  "records": [
    {
      "id": "ER-001",
      "protein": {
        "name": "string",
        "gene_symbol": "string",
        "uniprot_id": "UNVERIFIED",
        "species": "string"
      },
      "molecular_function": {
        "term": "string — GO MF term name",
        "go_id": "GO:XXXXXXX or UNKNOWN",
        "verified": false,
        "specificity_check": "string — confirm: not a binding term, not substrate-named"
      },
      "biological_process": {
        "term": "string — GO BP term name",
        "go_id": "GO:XXXXXXX or UNKNOWN",
        "verified": false
      },
      "cellular_component": {
        "term": "string — GO CC term name",
        "go_id": "GO:XXXXXXX or UNKNOWN",
        "verified": false
      },
      "relation_to_target": {
        "type": "has_input | directly_positively_regulates | directly_negatively_regulates | part_of",
        "target": "string — target protein or process",
        "mechanism": "string — DIRECT / INDIRECT / STRUCTURAL_PREREQUISITE"
      },
      "relation_to_process": {
        "type": "part_of",
        "target_bp": "string — the broader biological process this activity is part of"
      },
      "evidence": {
        "quote": "string — exact quote from source",
        "pmid": "string or null — MUST use the PMID from the source extraction or Interaction Map. Write null only if genuinely absent from all source data. Never write 'UNKNOWN'.",
        "figure": "string or null — MUST use the exact figure reference from the source extraction or Interaction Map (e.g. 'Fig. 3B', 'Figure 1C–E'). Write null only if no figure is cited in the source. Never invent a figure.",
        "assay": "string — exact experimental method as described in the source (e.g. 'co-immunoprecipitation', 'patch-clamp electrophysiology', 'in vitro GEF assay'). Never write 'biochemical assay' generically if the specific method is described.",
        "eco_code": "ECO:XXXXXXX or UNKNOWN",
        "eco_label": "string — ECO term name matching the assay above",
        "eco_verified": false,
        "controls_noted": "string or null"
      },
      "confidence": "HIGH | MEDIUM | LOW",
      "car_test": "string — PASS or FAIL with explanation",
      "warnings": ["string — any rule violations or concerns"],
      "de_novo_terms": ["string — terms that may not exist in GO and need to be requested"]
    }
  ]
}
```

---

## Coverage Rule — One Record Per Interaction

**You MUST create one EvidenceRecord for EVERY interaction listed in the Interaction Map, including those marked WARNING or LOW confidence.**

Do NOT filter interactions. Do NOT skip records because information is incomplete or confidence is low. Rules:

- If evidence is weak → `"confidence": "LOW"`, list concerns in `warnings[]`
- If a GO term is uncertain → `"go_id": "UNKNOWN"`, fill `"term"` with your best description
- **For binding-only interactions** (marked "WARNING: only binding described"): create the record with `"molecular_function": {"term": "UNKNOWN — only binding described", "go_id": "UNKNOWN", "verified": false}` and `"confidence": "LOW"`. Do NOT skip these.
- If the protein's role is unclear → `"molecular_function": {"term": "UNKNOWN", "go_id": "UNKNOWN", "verified": false}`

The curator decides what to keep. Your job is completeness, not curation.

**Producing fewer records than interactions in the Interaction Map is a failure.** Before returning your response, count: (1) how many interactions are in the Interaction Map, (2) how many records you produced. If (2) < (1), you have dropped interactions — go back and add the missing records.

---

## Translation Rules

Apply all rules from the system prompt. Key reminders:

1. **NO BINDING RULE**: Never use a GO MF term containing "binding". If only binding is described → no MF term, add warning.
2. **SUBSTRATE INDEPENDENCE**: MF term must not be named after the specific target. Use generic catalytic activity + has_input edge.
3. **CAR TEST**: Only use `directly_positively/negatively_regulates` for proven direct regulation. Use `part_of` for structural prerequisites.
4. **ALL IDs UNVERIFIED**: Every `go_id`, `eco_code`, and `uniprot_id` must have `"verified": false`.
5. **PMID — pull from source, never invent:**
   - If the Interaction Map entry lists a PMID (e.g. `[PMID:20530663]`), use it.
   - If the raw extraction JSON for that source contains a `pmid` field on the interaction, use it.
   - If the source filename encodes an author-year (e.g. `scholz2010`), that is a hint — look for the PMID in the extracted text from that source.
   - Write `null` if the PMID is truly absent from all source data. Never write `"UNKNOWN"` — that string is reserved for GO/ECO IDs only.
6. **Figure — pull exact reference from source, never invent:**
   - If the Interaction Map entry includes a figure (e.g. `[Fig. 2C, PMID:...]`), copy it verbatim.
   - If the raw extraction JSON interaction has a non-null `figure` field, use it verbatim.
   - If the supporting quote mentions a figure ("...as shown in Fig. 3B..."), extract it.
   - Write `null` only if no figure is cited anywhere in the source for this interaction.
7. **Assay — be specific, not generic:**
   - Copy the `assay_described` value from the extraction JSON if present.
   - Match the exact method name: "co-immunoprecipitation" not "binding assay"; "patch-clamp electrophysiology" not "electrophysiology"; "in vitro GEF assay" not "biochemical assay".
   - The assay name drives the ECO code — a wrong assay name causes a wrong ECO code.
5. **ECO codes** — match the EXACT assay described. Common mappings:
   - `co-immunoprecipitation` → ECO:0000226
   - `pull-down assay` → ECO:0000226
   - `yeast two-hybrid` → ECO:0000018
   - `patch-clamp / electrophysiology` → ECO:0005660
   - `gene knockout` → ECO:0001091
   - `shRNA / siRNA knockdown` → ECO:0007796
   - `immunofluorescence / imaging` → ECO:0007695
   - `western blot` → ECO:0000269
   - `kinase assay / biochemical activity assay` → ECO:0005581
   - `genetic interaction` → ECO:0001225
   - `protein overexpression` → ECO:0000120
   - If you do not know the exact ECO code for the described assay → write `"eco_code": "UNKNOWN"` and fill `eco_label` with the assay name verbatim.
