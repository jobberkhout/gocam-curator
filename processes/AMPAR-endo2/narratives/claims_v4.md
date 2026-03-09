# Expert Validation — Ampar endo2
## Generated: 2026-03-09 | Status: DRAFT

Dear Expert,

Below is a numbered list of claims derived from our model of AMPA receptor internalization. Please review each claim and indicate whether it is correct. Respond per number: "OK", "WRONG — [correction]", or "UNCERTAIN".

---

**Claim 1:** BRAG2 acts as a guanine nucleotide exchange factor (GEF) to activate Arf6 in the postsynaptic density, facilitating AMPA receptor internalization.
- Molecular Function: guanine nucleotide exchange factor activity
- Biological Process: regulation of Arf protein signal transduction
- Cellular Component: postsynaptic density
- Relation: directly_positively_regulates → Arf6
- Evidence: in vitro GEF assay, Fig 1B (PMID: 20530663)
- Confidence: HIGH

**Claim 2:** The ATPase NSF dissociates the PICK1-GluA2 complex in the postsynaptic density, contributing to the maintenance of the AMPA receptor complex.
- Molecular Function: ATPase activity, coupled to dissociation of intracellular complexes
- Biological Process: protein complex disassembly
- Cellular Component: postsynaptic density
- Relation: directly_negatively_regulates → GluA2-PICK1 complex
- Evidence: ATPase activity assay, Figure 1 (PMID: 12007421)
- Confidence: HIGH

**Claim 3:** CaMKII phosphorylates the C-terminal domain of Stargazin in the postsynaptic density, which regulates its association with phospholipids to facilitate LTP-induced synaptic potentiation.
- Molecular Function: protein kinase activity
- Biological Process: protein phosphorylation
- Cellular Component: postsynaptic density
- Relation: directly_positively_regulates → Stargazin
- Evidence: kinase assay, ampar_pdf p03-04 (PMID: null)
- Confidence: HIGH

**Claim 4:** PICK1 interacts with GluA2 in the endocytic zone as part of the AMPA receptor endocytosis pathway.
- Molecular Function: Unknown
- Biological Process: protein localization to synapse
- Cellular Component: endocytic zone
- Relation: has_input → GluA2
- Evidence: co-immunoprecipitation, Figure 1B (PMID: null)
- Confidence: LOW
- *Note: This claim currently only describes a physical interaction (binding); no enzymatic or mechanistic function was identified.*

**Claim 5:** Thorase (ATAD1) uses its ATPase activity to disrupt the GluA2-GRIP complex, promoting AMPA receptor endocytosis.
- Molecular Function: AAA+ ATPase activity
- Biological Process: protein complex disassembly
- Cellular Component: cytoplasm
- Relation: directly_negatively_regulates → GluA2-GRIP complex
- Evidence: ATPase activity assay, ampar_pdf p07-08 (PMID: null)
- Confidence: MEDIUM
- *Note: Warning: Conflicting mechanisms reported in sources (enzymatic vs ATPase); the model currently reflects the ATPase-dependent mechanism.*

---

## Flagged Uncertainties
- **Claim 4 (PICK1):** Confidence is LOW. The model only captures an interaction (co-immunoprecipitation). We require functional/enzymatic data to define a Molecular Function.
- **Claim 5 (Thorase):** Confidence is MEDIUM due to conflicting reports in the literature regarding the exact mechanism of GluA2-GRIP complex disruption.
- **Missing PMIDs:** Claims 3, 4, and 5 lack PubMed identifiers. Please provide these if available.