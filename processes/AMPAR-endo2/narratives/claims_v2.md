# Expert Validation — AMPA receptor endocytosis and synaptic regulation
## Generated: 2026-03-07 | Status: DRAFT

Dear Expert,

Below is a numbered list of claims derived from our model of AMPA receptor endocytosis and associated synaptic processes. Please review each claim and indicate whether it is correct. Respond per number: "OK", "WRONG — [correction]", or "UNCERTAIN".

---

**Claim 1:** BRAG2 functions as a guanine nucleotide exchange factor, directly activating Arf6 in the postsynaptic density to facilitate AMPA receptor endocytosis.
- Molecular Function: guanine nucleotide exchange factor activity
- Biological Process: small GTPase mediated signal transduction
- Cellular Component: postsynaptic density
- Relation: directly positively regulates → Arf6
- Evidence: In vitro nucleotide exchange assay, PMID: 20531393
- Confidence: HIGH

**Claim 2:** NSF functions as an ATPase that directly dissociates the PICK1-GluA2 complex in the postsynaptic density, thereby modulating AMPA receptor internalization.
- Molecular Function: ATPase activity
- Biological Process: protein complex disassembly
- Cellular Component: postsynaptic density
- Relation: directly negatively regulates → GluA2-PICK1 complex
- Evidence: ATPase activity assay, PMID: 12196515
- Confidence: HIGH

**Claim 3:** PICK1 promotes the polymerization of dynamin to support AMPA receptor endocytosis within the endocytic vesicle membrane.
- Molecular Function: Unknown (Evidence only describes physical binding, which is insufficient for functional characterization)
- Biological Process: regulation of endocytosis
- Cellular Component: endocytic vesicle membrane
- Relation: directly positively regulates → dynamin polymerization
- Evidence: In vitro sedimentation assay, Figure 4E, PMID: 28341764
- Confidence: MEDIUM — *Warning: The current evidence describes protein-protein binding, which is an interaction, not a catalytic molecular function. We require evidence of an enzymatic or mechanistic activity beyond binding.*

**Claim 4:** CaMKII performs serine/threonine phosphorylation of TARP gamma-8 within the postsynaptic density, contributing to synaptic potentiation.
- Molecular Function: protein serine/threonine kinase activity
- Biological Process: protein phosphorylation
- Cellular Component: postsynaptic density
- Relation: directly positively regulates → TARP gamma-8
- Evidence: Kinase assay, PMID: 29792965
- Confidence: HIGH

---

## Flagged Uncertainties
- **Claim 3:** The "Molecular Function" for PICK1 is currently undefined. While we have evidence of it regulating dynamin, "binding" is not a valid molecular function in our modeling framework. We ask for clarification if there is evidence of a specific biochemical or mechanistic activity (e.g., stabilizing a conformational state) that PICK1 imparts on dynamin.
- **Cellular Component IDs:** The "postsynaptic density" (GO:0014068) identifier is currently unverified and requires confirmation against your preferred nomenclature.