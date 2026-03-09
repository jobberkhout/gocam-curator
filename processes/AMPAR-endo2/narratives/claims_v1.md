# Expert Validation — AMPA Receptor Endocytosis
## Generated: 2026-03-07 | Status: DRAFT

Dear Expert,

Below is a numbered list of claims derived from our model of AMPA receptor endocytosis. Please review each claim and indicate whether it is correct. Respond per number: "OK", "WRONG — [correction]", or "UNCERTAIN".

---

**Claim 1:** BRAG2 acts as a guanine nucleotide exchange factor (GEF) to directly activate Arf6 within the postsynaptic density.
- Molecular Function: guanine nucleotide exchange factor activity
- Biological Process: regulation of Arf6 protein signal transduction
- Cellular Component: postsynaptic density
- Relation: directly positively regulates → Arf6
- Evidence: in vitro nucleotide exchange assay, PMID: 20595964
- Confidence: HIGH — Direct biochemical evidence provided.

**Claim 2:** CaMKII alpha utilizes its serine/threonine kinase activity to phosphorylate Stargazin at the postsynaptic density.
- Molecular Function: protein serine/threonine kinase activity
- Biological Process: protein phosphorylation
- Cellular Component: postsynaptic density
- Relation: directly positively regulates → Stargazin
- Evidence: kinase assay, PMID: 18434484
- Confidence: HIGH — Direct biochemical evidence provided.

**Claim 3:** NSF utilizes its ATPase activity to disassemble the GluA2-PICK1 complex, thereby promoting AMPA receptor internalization.
- Molecular Function: ATPase activity
- Biological Process: protein complex disassembly
- Cellular Component: postsynaptic density
- Relation: directly negatively regulates → GluA2-PICK1 complex
- Evidence: ATP-dependent complex dissociation assay, PMID: 12036521
- Confidence: HIGH — Direct biochemical evidence provided.

**Claim 4:** PICK1 inhibits the activity of the Arp2/3 complex at the postsynaptic membrane.
- Molecular Function: Unknown — activity mechanism is not explicitly defined in biochemical terms.
- Biological Process: regulation of actin cytoskeleton organization
- Cellular Component: postsynaptic membrane
- Relation: directly negatively regulates → Arp2/3 complex
- Evidence: in vitro actin polymerization inhibition assay, PMID: 28588075
- Confidence: MEDIUM — While inhibition is observed, the underlying catalytic mechanism is currently unclassified.

**Claim 5:** The AP2 complex mediates the recruitment of GluA2 subunits into clathrin-coated pits.
- Molecular Function: Unknown — activity is described strictly as protein-protein interaction/binding.
- Biological Process: clathrin-mediated endocytosis
- Cellular Component: clathrin-coated pit
- Relation: has_input → GluA2
- Evidence: GST pull-down, Figure 1C, PMID: 11986337
- Confidence: LOW — Only binding/recruitment is established; no catalytic mechanism exists to describe as a "function."

---

## Flagged Uncertainties
- **Claim 4 & 5:** We have flagged these as having "Unknown" molecular functions. Per our internal curation guidelines, we cannot classify "binding" as a molecular function (it is a relation). We require guidance on whether a more specific catalytic or mechanistic activity for PICK1 and AP2 is known, or if these should remain purely as interaction-based nodes in the model.