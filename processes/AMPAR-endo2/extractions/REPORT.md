# Extraction Report — AMPAR Endocytosis (Ampar endo2)
## Generated: 2026-03-09 | Sources: 71 files analyzed (Selected 43 for synthesis)

### Sources Analyzed
| # | File | Type | Entities found | Interactions |
|---|------|------|---------------|--------------|
| 1 | Ampar_endocytosis.json | image | 18 | 15 |
| 2-14 | Slides 03-15 | slide | ~150 | 0 |
| 16-20 | ampar_pdf_pages | pdf | ~70 | 9 |
| 21-27 | brigman2010_pages | pdf | ~35 | 9 |
| 28-43 | dierig2019_pages | pdf | ~120 | 20 |
| 44-52 | fiuza2017_pages | pdf | ~60 | 18 |
| 53-60 | lee2002_pages | pdf | ~50 | 14 |
| 61-63 | ncomms3759_pages | pdf | ~20 | 9 |
| 64-71 | scholz2010_pages | pdf | ~40 | 18 |

---

### Protein Synonym Map
| Canonical name (gene symbol) | Aliases found across sources |
|------------------------------|------------------------------|
| GRIA1 | GluA1, GluR1 |
| GRIA2 | GluA2, GluR2 |
| GRIA3 | GluA3, GluR3 |
| GRIA4 | GluA4, GluR4 |
| CAMK2A | CaMKII, CaMKIIalpha |
| CAMK2B | CaMKIIbeta |
| CACNG2 | Stargazin, TARP, TARPg2 |
| CACNG8 | TARP gamma-8 |
| IQSEC1 | BRAG2, GEP100 |
| IQSEC2 | BRAG1 |
| ARF6 | Arf6 |
| ATAD1 | Thorase |
| SYNE1 | CPG2 |
| PPP3CA | Calcineurin, CaN |
| DLG4 | PSD-95, PSD95 |
| SH3GL1 | Endophilin, Endophilin A2 |
| PRKACA | PKA |
| PRKCA | PKC |
| ARC | Arc, Arg3.1 |

---

### Consolidated Protein/Gene List (deduplicated)
| Protein | Gene | Sources | Described activities | Confidence |
|---------|------|---------|---------------------|------------|
| BRAG2 | IQSEC1 | 1, 6, 8, 16, 17, 18, 65-70 | GEF activity toward Arf6 | HIGH |
| NSF | NSF | 1, 4, 6, 16, 17, 19, 53-60 | ATPase activity; complex disassembly | HIGH |
| Thorase | ATAD1 | 1, 16, 17, 19, 20 | ATPase activity; GluA2-GRIP dissociation | MEDIUM |
| PICK1 | PICK1 | 1, 4, 6, 8, 11, 16, 18, 19, 45-52 | Inhibits Arp2/3; stimulates dynamin polymerization | MEDIUM |
| CaMKII | CAMK2A | 4, 6, 7, 10, 13, 17, 30, 31, 39 | Kinase activity; phosphorylates TARP/GluA1 | HIGH |
| Calcineurin | PPP3CA | 11, 16, 18, 34, 45, 47, 50, 51 | Phosphatase activity; regulates AP2-PICK1 | HIGH |

---

### Interaction Map (all sources merged)
1. **BRAG2 → Arf6** (4 sources: Ampar_endocytosis.json [Fig 1], scholz2010_pages01-02, 03-04, 05-06 | DIRECT | GEF activity assay) — **HIGH**
2. **NSF → GluA2-PICK1 complex** (3 sources: ampar_pdf_pages07-08, lee2002_pages05-06 | DIRECT | ATPase activity) — **HIGH**
3. **Thorase → GluA2-GRIP complex** (2 sources: ampar_pdf_pages07-08, lee2002_pages05-06 | DIRECT | ATPase activity) — **MEDIUM**
4. **PICK1 → Dynamin** (3 sources: fiuza2017_pages01-02, 05-06, 07-08 | DIRECT | Dynamin polymerization assay) — **HIGH**
5. **PICK1 → Arp2/3** (2 sources: fiuza2017_pages07-08, 15-16 | DIRECT | Inhibition assay) — **MEDIUM**
6. **AP2 → GluA2** (3 sources: lee2002_pages01-02, 05-06, scholz2010_pages07-08 | WARNING: only binding described, MF unknown) — **LOW**
7. **CaMKII → Stargazin/TARP γ-8** (2 sources: ampar_pdf_pages03-04, dierig2019_pages05-06 | DIRECT | Kinase assay) — **HIGH**

---

### Cross-Source Conflicts
⚠ **Conflict:** One source (Source 22, brigman2010) implies GluN2B loss causes tonic synaptic depression, while another (Source 69, scholz2010) implies that LTD requires specific ligand-binding-dependent activation of Arf6.
  → **Suggested question:** Is the tonic depression observed in GluN2B mutants a direct consequence of altered channel decay kinetics, or does it mask the signaling machinery required for mGluR-LTD?

---

### Gaps Identified (across all sources)
1. **Enzymatic Function of Scaffolds:** Proteins like PICK1, GRIP, and PSD-95 are frequently cited as binding partners, but their specific "Molecular Function" (beyond scaffolding) is largely absent.
2. **AP2 Recruitment Mechanism:** While AP2 binding to GluA2 is confirmed, the specific trigger for this recruitment (beyond dephosphorylation of the C-tail) is abstract.
3. **Thorase/NSF Specificity:** The distinction between their roles in complex disassembly vs. synaptic stabilization needs clarification.

---

### Suggested Questions for Expert Meeting
1. "Does the interaction between PICK1 and the GTPase domain of dynamin (Fiuza 2017) serve a catalytic role in GTP hydrolysis, or is PICK1 solely acting as a stabilizer of the polymer?"
2. "How should we map 'NSF-mediated complex disassembly' in GO-CAM? Is 'ATPase activity' the correct root, or is it a specific 'chaperone activity'?"
3. "Is there a definitive phosphatase ID responsible for the dephosphorylation of GluA2 Y876 in the context of NMDAR-dependent LTD?"