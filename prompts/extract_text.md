# Phase 2 — Text Extraction Prompt

Your task is to extract biological entities and interactions from the provided scientific text.

**THIS IS PHASE 2 EXTRACTION. DO NOT MAP TO GO TERMS. DO NOT SUGGEST GO IDs.**

Extract only what the text explicitly states. Do not infer, speculate, or add information that is not present in the source material.

---

## Output Format

Return a single valid JSON object with this exact structure:

```json
{
  "source": "<filename as provided>",
  "source_type": "text",
  "timestamp": "<ISO datetime>",
  "entities": [
    {
      "name": "string — common name used in text (e.g. CaMKII)",
      "gene_symbol": "string or null — standard gene symbol if clearly identifiable",
      "mentioned_activities": ["exact activities described in the text — quote-level precision"],
      "context": "string or null — cellular context, species, experimental condition"
    }
  ],
  "interactions": [
    {
      "source_entity": "string — the acting protein/gene",
      "target_entity": "string — the protein/gene being acted upon",
      "described_action": "string — what A does to B, as described in text",
      "quote": "string — exact sentence or phrase from the text that supports this interaction",
      "pmid": "string or null — PubMed ID of this paper if visible in header/footer (digits only, e.g. '20530663')",
      "figure": "string or null — EXACT figure/table reference as printed (e.g. 'Fig. 3B', 'Figure 1C–E', 'Table 2'). null only if no figure is cited.",
      "assay_described": "string or null — experimental method used (e.g. 'in vitro kinase assay', 'co-immunoprecipitation', 'patch-clamp electrophysiology')",
      "causal_type": "DIRECT | STRUCTURAL_PREREQUISITE | INDIRECT | UNKNOWN",
      "confidence_note": "string — one sentence explaining why you chose this causal_type"
    }
  ],
  "connections_shown": [],
  "compartments_shown": [],
  "gaps": [
    "string — each gap is a piece of missing information or an unanswered question from this text"
  ],
  "questions_for_expert": [
    "string — each question is something the curator should ask the domain expert"
  ]
}
```

---

## Extraction Rules

1. **Extract ALL proteins, genes, and molecular complexes** mentioned by name — even if their function is not described.
2. **For every interaction, include the exact quote** from the text. No quote → do not include the interaction.
3. **Capture the PMID for every interaction.** Scientific papers print their PubMed ID (PMID) in the header, footer, or first page (e.g., "PMID: 20530663", "doi:10.1016/j.cell.2010..."). Extract it and put the digits in the `pmid` field on every interaction from that paper. If no PMID is visible anywhere in the text, leave null — do NOT invent one.
4. **Capture the exact figure reference for every interaction.** Copy the figure citation verbatim as it appears in the sentence (e.g., "Fig. 3B", "Figure 1C–E", "Supplementary Fig. S2"). If the supporting sentence cites no figure, leave null — do NOT invent a figure.
3. **Apply the CAR TEST** to classify causal_type:
   - `DIRECT` — enzymatic or mechanistic evidence (kinase assay, electrophysiology, etc.)
   - `STRUCTURAL_PREREQUISITE` — removal causes downstream failure due to structural role (scaffold, organizer)
   - `INDIRECT` — effect is real but passes through intermediate steps not described here
   - `UNKNOWN` — insufficient evidence to determine mechanism
4. **Flag binding-only descriptions** in gaps: if text says "Protein A binds Protein B" with no further activity, add a gap: "Only binding described for [Protein A] — molecular function unknown."
5. **Generate expert questions** for anything ambiguous, contradictory, or missing (especially upstream regulators, missing mechanisms, or binding-only descriptions).
6. **Do NOT invent gene symbols** — use `null` if uncertain.
7. **Do NOT map to GO terms** — that is Phase 4 (gocam translate).
8. **Compartments** (`compartments_shown`) — list only if explicitly mentioned in text (e.g., "postsynaptic density", "synaptic vesicle"). Leave empty array if not mentioned.
