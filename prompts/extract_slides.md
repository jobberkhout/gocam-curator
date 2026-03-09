# Phase 2 — Slide Extraction Prompt

Your task is to analyze a single slide from a PowerPoint presentation by an expert biologist.

**THIS IS PHASE 2 EXTRACTION. DO NOT MAP TO GO TERMS. DO NOT SUGGEST GO IDs.**

Apply all rules from the visual extraction prompt. The additional rules below are specific to lecture slides.

---

## Slide Classification — First Decision

Before extracting, classify the slide:

- **SKIP** if it is: a title slide, a table of contents, a methods/protocols slide, an acknowledgments slide, a references/bibliography slide, or a slide with no biological content.
- **EXTRACT** if it contains: protein names, pathway diagrams, experimental results, interaction cartoons, or biological mechanisms.

If the slide should be skipped, return:
```json
{"skip": true, "reason": "string — brief reason (e.g. title slide, acknowledgments)"}
```

---

## Output Format for Relevant Slides

Use the same format as `extract_visual.md` with `"source_type": "slide"`:

```json
{
  "source": "<slide identifier as provided>",
  "source_type": "slide",
  "timestamp": "<ISO datetime>",
  "visual_description": "string — what biological topic does this slide cover?",
  "entities": [ ... ],
  "interactions": [],
  "connections_shown": [ ... ],
  "compartments_shown": [ ... ],
  "gaps": [ ... ],
  "questions_for_expert": [ ... ]
}
```

---

## Slide-Specific Rules

1. **Speaker notes are separate from slide content.** Notes are often more detailed than the slide itself — treat them as additional text evidence. If notes contradict the slide diagram, flag it as a conflict in `gaps`.
2. **Slide titles and headers are metadata**, not biological claims. Include them in `visual_description` but do not extract them as entities.
3. **Bullet points** on slides are often abbreviated. Extract what they say, flag in `gaps` if the mechanism is unclear.
4. **Lab logos, institution names, author names** — ignore entirely.
5. **If the same protein appears across multiple slides** with different arrows or roles, note this as a potential conflict in `gaps` (e.g., "Protein X shown as inhibitor here, but shown as activator in slide N").
6. **Citations on slides.** If the slide shows a literature citation (e.g., "Smith et al. 2010", "(PMID:20530663)", "doi:10.1016/..."), capture the PMID in the `connections_shown[].note` field of the relevant connection, and note it in `questions_for_expert` so it can be looked up. Do not invent PMIDs.
