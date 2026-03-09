# Extraction Report — AMPAR Endocytosis
## Generated: 2026-03-07 | Sources: 42 files analyzed

### Sources Analyzed
| # | File | Type | Entities found | Interactions |
|---|------|------|---------------|--------------|
| 1 | Ampar_endocytosis.json | image | 20 | 0 |
| 15 | ampar_pdf_pages01-02.json | pdf | 16 | 1 |
| 16 | ampar_pdf_pages03-04.json | pdf | 12 | 4 |
| 36 | scholz2010_pages01-02.json | pdf | 3 | 4 |
| 37 | scholz2010_pages03-04.json | pdf | 4 | 4 |
| 40 | scholz2010_pages09-10.json | pdf | 5 | 4 |
| 41 | scholz2010_pages11-12.json | pdf | 5 | 4 |
| 20 | fiuza2017_pages01-02.json | pdf | 7 | 3 |
| 23 | fiuza2017_pages07-08.json | pdf | 8 | 5 |
| 31 | lee2002_pages05-06.json | pdf | 5 | 3 |
| 33 | lee2002_pages09-10.json | pdf | 5 | 3 |
| 34 | lee2002_pages11-12.json | pdf | 6 | 3 |

---

### Protein Synonym Map
| Canonical name (gene symbol) | Aliases found across sources |
|------------------------------|------------------------------|
| GRIA2 | GluA2, GluR2 |
| GRIA1 | GluA1, GluR1 |
| DLG4 | PSD-95, PSD95 |
| CACNG2 | TARP, Stargazin, TARPg2 |
| IQSEC1 | BRAG2, GEP100 |
| ARF6 | Arf6, ARF6 |
| ATAD1 | Thorase |
| DNM1 | Dynamin |
| SYNE1 | CPG2 |
| PPP3CA | Calcineurin, PP2B |
| SH3GL2 | Endophilin |
| ARC | Arc, Arg3.1 |

---

### Consolidated Protein/Gene List (deduplicated)
| Protein | Gene | Sources | Described activities | Confidence |
|---------|------|---------|---------------------|------------|
| BRAG2 | IQSEC1 | 36-41 | GEF for Arf6 | HIGH — direct biochemical evidence |
| Arf6 | ARF6 | 36-42 | GTPase activity, membrane remodeling | HIGH — catalytic |
| NSF | NSF | 15, 18, 29, 33 | ATPase, dissociates PICK1/GluA2 | HIGH — direct enzymatic |
| PICK1 | PICK1 | 1, 17, 20, 23 | Stimulates dynamin polymerization | MEDIUM — direct in vitro |
| Dynamin | DNM1 | 1, 20, 23 | GTPase, membrane scission | HIGH — direct catalytic |
| Thorase | ATAD1 | 18 | ATPase, disassembles GluA2/GRIP | MEDIUM — direct |
| Calcineurin| PPP3CA| 22, 26, 34| Dephosphorylation of endocytic complex | MEDIUM — indirect/regulatory |

---

### Interaction Map (all sources merged)
1. BRAG2 → Arf6 (4 sources: scholz2010_pages01-02, 03-04, 09-10, 11-12 | directly_positively_regulates | GEF activity) — HIGH
2. Thorase → GluA2:GRIP (2 sources: ampar_pdf_pages07-08, ampar_pdf_pages01-02 | directly_negatively_regulates | ATPase disruption) — MEDIUM
3. NSF → PICK1:GluA2 (2 sources: ampar_pdf_pages03-04, ampar_pdf_pages07-08 | directly_negatively_regulates | ATPase disassembly) — HIGH
4. PICK1 → Dynamin (5 sources: fiuza2017_pages01-02, 05-06, 07-08, 09-10, 11-12 | directly_positively_regulates | stimulation of polymerization) — MEDIUM
5. AP2 → GluA2 (6 sources: ampar_pdf_pages03-04, 05-06, lee2002_pages01-02, 05-06, 07-08, 09-10 | WARNING: only binding described, MF unknown | recruitment/tethering) — LOW
6. Calcineurin → PICK1:AP2 interaction (4 sources: fiuza2017_pages05-06, 07-08, 09-10, 11-12 | indirectly_positively_regulates | enhancement via dephosphorylation) — MEDIUM

---

### Cross-Source Conflicts
⚠ **Conflict:** Sources 16 and 31 describe AP2 as a direct recruiter, whereas source 15 states "the mechanism... has not been revealed." 
  → Suggested question: "Is the interaction between AP2 and GluA2 a direct protein-protein binding event that initiates clathrin coat assembly, or does it require an intermediary adaptor not shown in the diagrams?"

---

### Gaps Identified
1. **Enzymatic regulation:** While binding is extensively cataloged, the specific catalytic effect of many adaptors (PICK1, PACSIN) on the endocytic cycle beyond "polymerization stimulation" remains unclear.
2. **Signaling link:** The link between NMDAR activation and calcineurin-mediated enhancement of PICK1 interactions is stated, but the intermediate kinases/phosphatases in the cascade are largely missing.
3. **Thorase target:** The structural mechanism of Thorase-mediated GluA2/GRIP disassembly is described as ATPase-dependent, but the specific residues targeted are unknown.

---

### Suggested Questions for Expert Meeting
1. "Does PICK1 have a catalytic molecular function in endocytosis, or is it exclusively an adaptor/scaffold for dynamin and AP2?"
2. "Regarding Calcineurin: Is it directly dephosphorylating PICK1, AP2, or both, to stabilize the endocytic complex?"
3. "Is there a canonical enzymatic activity for the BAR-domain proteins (PACSIN/Endophilin) in this pathway, or should these be strictly modeled as structural curvature-inducers?"
4. "Should 'recruitment' to the membrane be mapped to a specific GO term or handled as a result of binding interactions?"