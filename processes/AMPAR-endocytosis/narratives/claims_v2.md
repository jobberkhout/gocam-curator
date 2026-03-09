# Expert Validation — AMPAR endocytosis
## Generated: 2026-03-07 | Status: DRAFT

Dear Expert,

Below is a numbered list of claims derived from our model of AMPAR endocytosis. Please review each claim and indicate whether it is correct. Respond per number: "OK", "WRONG — [correction]", or "UNCERTAIN".

---

**Claim 1:** BRAG2 (IQSEC1) functions as a guanine nucleotide exchange factor to activate the small GTPase Arf6 within the postsynaptic density.
- Molecular Function: guanine nucleotide exchange factor activity
- Biological Process: GTPase activation
- Cellular Component: postsynaptic density
- Relation: directly positively regulates → Arf6
- Evidence: GTPg35S binding assay, Fig 1, IQSEC1 et al. (PMID: 20530663)
- Confidence: HIGH

**Claim 2:** Thorase (ATAD1) utilizes its ATPase activity to promote the disassembly of the GluA2-GRIP protein complex, facilitating endocytosis.
- Molecular Function: ATPase activity
- Biological Process: protein complex disassembly
- Cellular Component: endocytic zone
- Relation: directly negatively regulates → GluA2:GRIP complex
- Evidence: ATPase assay, Zhang et al. (PMID: UNKNOWN)
- Confidence: MEDIUM (Note: Cellular component "endocytic zone" requires verification)

**Claim 3:** NSF utilizes its ATPase activity to promote the disassembly of the PICK1-GluA2 protein complex at the postsynaptic density.
- Molecular Function: ATPase activity
- Biological Process: protein complex disassembly
- Cellular Component: postsynaptic density
- Relation: directly negatively regulates → PICK1:GluA2 complex
- Evidence: biochemical disassembly assay, (PMID: UNKNOWN)
- Confidence: HIGH

**Claim 4:** PICK1 promotes the polymerization of dynamin to drive clathrin-mediated endocytosis.
- Molecular Function: Unknown — activity is not currently characterized beyond binding/polymerization stimulation
- Biological Process: positive regulation of endocytosis
- Cellular Component: clathrin-coated pit
- Relation: directly positively regulates → dynamin polymerization
- Evidence: in vitro sedimentation assay, Fig 4, Cao et al. (PMID: 28135165)
- Confidence: MEDIUM (Warning: No catalytic molecular function identified; PICK1 mechanism is interaction-based.)

**Claim 5:** The AP2 complex acts as a structural component to facilitate clathrin coat assembly and cargo recognition.
- Molecular Function: Unknown — currently only defined by protein-protein interactions
- Biological Process: clathrin-mediated endocytosis
- Cellular Component: clathrin-coated pit
- Relation: part of → clathrin coat assembly
- Evidence: pull-down assay, Fig 1C, Lee et al. (PMID: 12007421)
- Confidence: LOW (Warning: This is modeled as a structural prerequisite, not a catalytic molecular function. Binding to GluA2/GluA3 is an interaction, not a function.)

---

## Flagged Uncertainties
- **Claim 2:** The identifier for the "endocytic zone" is currently unverified.
- **Claim 4 & 5:** These proteins lack an identifiable catalytic molecular function; interactions are captured as relations, but they do not meet the criteria for a "Molecular Function" node.
- **Missing PMIDs:** Claims 2 and 3 require formal PubMed IDs to finalize evidence provenance.