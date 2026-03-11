# Phase 5 — Narrative Generation Prompt

Your task is to convert verified GO-CAM evidence records into a numbered list of expert-readable claims.

The output is sent to the domain expert for validation. Write for a cell biologist, not a bioinformatician.

---

## Output Format

Return a Markdown document:

```markdown
# Expert Validation — {process_name}
## Generated: {date} | Status: DRAFT

Dear {expert_name},

Below is a numbered list of claims derived from our model of {process_name}.
Please review each claim and indicate whether it is correct.
Respond per number: "OK", "WRONG — [correction]", or "UNCERTAIN".

---

**Claim 1:** Plain English statement of the biological claim.
- Molecular Function: term name (GO:XXXXXXX)
- Biological Process: process name (GO:XXXXXXX or plain English if unknown)
- Cellular Component: compartment name (GO:XXXXXXX or plain English if unknown)
- Relation: relation_type → target protein or process
- Evidence: experimental method, figure reference, first author + year (PMID: XXXXXXX)
- Confidence: HIGH / MEDIUM / LOW — brief reason

**Claim 2:** ...

---

## Flagged Uncertainties
- [Any claims with LOW confidence, missing verification, or warnings]
```

---

## Writing Rules

1. **Write for a biologist.** Use protein names, not gene symbols. Include GO IDs in parentheses after term names (as shown in the format above) — the expert may need them for reference — but avoid other ontology jargon.
2. **Each claim = one protein activity with its evidence.** Do not bundle multiple proteins into one claim.
3. **Include the experimental basis** — what assay, which paper, which figure. The expert needs to know where the claim comes from.
4. **Flag anything uncertain** — LOW confidence claims, unverified IDs, binding-only descriptions.
5. **Order claims logically** — upstream regulators first, then effectors, then outcomes.
6. **If a claim has a warning** (from evidence record), mention it briefly under the claim.
7. **Keep language simple** — "CaMKII adds a phosphate group to GluA1" not "CaMKII phosphorylates GRIA1."
