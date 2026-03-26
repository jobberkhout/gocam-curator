# Phase 2 — Visual Extraction Prompt

Your task is to analyze a biological diagram, cartoon, or figure and extract what is visible in it.

**THIS IS PHASE 2 EXTRACTION. DO NOT MAP TO GO TERMS. DO NOT SUGGEST GO IDs.**

A diagram is a hypothesis drawn by an expert — not proven data. Extract what is SHOWN, not what is implied or assumed to be true.

---

## Output Format

Return a single valid JSON object with this exact structure:

```json
{
  "source": "<filename as provided>",
  "source_type": "image",
  "timestamp": "<ISO datetime>",
  "visual_description": "string — 1-3 sentences describing what the diagram depicts overall",
  "entities": [
    {
      "name": "string — protein/gene name (standardized if recognizable)",
      "label_as_shown": "string — exactly as written in the diagram (e.g. AP-2, GluA1/2)",
      "position_in_diagram": "string — where this entity appears (e.g. at membrane, inside vesicle)",
      "implied_activity": "string or null — what role does the diagram suggest? (adaptor, scaffold, enzyme, etc.) — be conservative",
      "mentioned_activities": []
    }
  ],
  "interactions": [],
  "connections_shown": [
    {
      "from_entity": "string — source protein/gene",
      "to_entity": "string — target protein/gene",
      "arrow_type": "string — describe the line/arrow style (solid arrow, dashed arrow, T-bar, double-headed arrow, etc.)",
      "implied_relation": "string — what the arrow likely represents (activation, inhibition, recruitment, transport, physical interaction, etc.)",
      "note": "string or null — any ambiguity, label, or annotation near this connection"
    }
  ],
  "compartments_shown": [
    "string — each compartment visible in the diagram (e.g. presynaptic terminal, postsynaptic membrane, endosome)"
  ],
  "gaps": [
    "string — each gap is something missing from the diagram or something that is shown without a mechanism"
  ],
  "questions_for_expert": [
    "string — each question is something the curator should ask the domain expert about this diagram"
  ]
}
```

---

## MANDATORY: Every Arrow Must Be Logged

**For every arrow, line, or spatial relationship between proteins in the diagram, create a `connections_shown` entry.**

Even if the mechanism is completely unknown, log it:
```json
{ "from_entity": "ProteinA", "to_entity": "ProteinB", "arrow_type": "solid arrow", "implied_relation": "unknown — arrow shown in diagram", "note": null }
```

**Completeness check:** A cartoon with 7 proteins and 6 arrows should produce at least 6 `connections_shown` entries. If you see fewer entries than arrows in the diagram, you have missed connections. Go back and find them.

Do NOT skip an arrow because:
- The mechanism is unknown
- The arrow is dashed or ambiguous
- The proteins are in different compartments
- The arrowhead style is unusual

Every visible edge must be recorded. The curator will interpret them.

---

## Extraction Rules

1. **Read every label** in the diagram — protein names, abbreviations, annotations, figure legends, notes in margins.
2. **For every arrow or line**, record the connection. Distinguish:
   - Solid arrowhead → activation/positive regulation (conventionally)
   - Flat T-bar → inhibition
   - Dashed line → uncertain or indirect
   - Double-headed arrow → bidirectional interaction
   - Simple line without arrowhead → structural/physical association
3. **A drawn arrow from A → B means the expert THINKS A does something to B.** It does NOT prove direct regulation. Do NOT assign causal_type from arrows — that requires experimental evidence.
4. **Record implied_activity conservatively.** If a protein is shown at the membrane with an arrow pointing at a vesicle, say "possible membrane adaptor role" — not "endocytosis regulator."
5. **List all compartments** drawn (membranes, organelles, subcellular regions) even if not labeled.
6. **Identify gaps** — proteins that are present but have no connections, connections without mechanisms, missing steps in the pathway.
7. **Generate questions** for every gap and every ambiguous arrow.
8. Leave `interactions` as an empty array — interactions from visual sources go in `connections_shown`.
