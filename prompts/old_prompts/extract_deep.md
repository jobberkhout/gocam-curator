# Phase 2 — Second-Pass (Deep) Extraction Prompt

You are performing a **second-pass extraction** to find content that was MISSED in the first pass.

The user message contains two parts:
1. A synthesis report of everything already extracted from all sources
2. A specific source file to re-read

**YOUR TASK: Return ONLY what is NOT already in the report.**

---

## Focus Areas for the Second Pass

Look specifically for things that tend to be missed in first-pass extraction:

1. **Indirect regulators** — proteins mentioned as upstream signals or modulators that were not connected to the main pathway
2. **Scaffolding and adaptor proteins** — proteins whose role is to hold complexes together rather than catalyze reactions (PSD-95, Homer, Shank, GRIP, PICK1, etc.)
3. **Phosphatases and deubiquitinases** — kinases get extracted; their opposing phosphatases often do not
4. **Upstream signals** — what triggers the process? (calcium, receptor activation, synaptic activity, etc.)
5. **Negative regulators** — proteins that suppress or terminate the pathway
6. **Cell-type or condition context** — mentioned experimental conditions, brain regions, cell lines
7. **Proteins mentioned in passing** — named once in a sentence without being given a connection

---

## Output Format

Return the same JSON format as a normal extraction. Set `"extraction_pass": 2`.

If you find nothing new, return:
```json
{
  "extraction_pass": 2,
  "entities": [],
  "interactions": [],
  "connections_shown": [],
  "compartments_shown": [],
  "gaps": [],
  "questions_for_expert": []
}
```

Do NOT re-list things already in the report. Only new findings.

---

## Rules

- **THIS IS PHASE 2. DO NOT MAP TO GO TERMS. DO NOT SUGGEST GO IDs.**
- Do not repeat information already captured in the synthesis report
- If a protein was already extracted but you found a NEW interaction involving it, include just the new interaction
- Be conservative — if something was clearly covered in the report, do not add it again
