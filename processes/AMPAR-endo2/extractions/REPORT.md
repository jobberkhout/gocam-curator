# Extraction Report — AMPAR endocytosis
## Generated: 2026-03-09 | Sources: 71 files analyzed (Selected 43 valid JSONs)

### Sources Analyzed
| # | File | Type | Entities found | Interactions |
|---|------|------|---------------|--------------|
| 1 | Ampar_endocytosis.json | image | 18 | 15 |
| 2 | Ampar_endocytosis_p2.json | image | 7 | 0 |
| 3 | SynGO3_slide_p2.json | slide | 0 | 0 |
| 4 | SynGO3_slide03.json | slide | 19 | 0 |
| 5 | SynGO3_slide05.json | slide | 5 | 0 |
| 6 | SynGO3_slide06.json | slide | 15 | 0 |
| 7 | SynGO3_slide07.json | slide | 15 | 0 |
| 8 | SynGO3_slide08.json | slide | 9 | 0 |
| 9 | SynGO3_slide09.json | slide | 25 | 0 |
| 10 | SynGO3_slide10.json | slide | 19 | 0 |
| 11 | SynGO3_slide11.json | slide | 24 | 0 |
| 12 | SynGO3_slide12.json | slide | 13 | 0 |
| 13 | SynGO3_slide13.json | slide | 8 | 0 |
| 14 | SynGO3_slide15.json | slide | 4 | 0 |
| 15 | ampar_pdf_p2.json | pdf | 8 | 0 |
| 16 | ampar_pdf_pages01-02.json | pdf | 18 | 1 |
| 17 | ampar_pdf_pages03-04.json | pdf | 15 | 4 |
| 18 | ampar_pdf_pages05-06.json | pdf | 11 | 4 |
| 19 | ampar_pdf_pages07-08.json | pdf | 10 | 3 |
| 20 | ampar_pdf_pages09-10.json | pdf | 6 | 2 |
| 21 | brigman2010_p2.json | pdf | 0 | 0 |
| 22 | brigman2010_pages01-02.json | pdf | 5 | 2 |
| 23 | brigman2010_pages03-04.json | pdf | 6 | 2 |
| 24 | brigman2010_pages05-06.json | pdf | 9 | 3 |
| 25 | brigman2010_pages07-08.json | pdf | 4 | 3 |
| 26 | brigman2010_pages09-10.json | pdf | 5 | 2 |
| 27 | brigman2010_pages11-11.json | pdf | 3 | 2 |
| 28 | dierig2019_p2.json | pdf | 0 | 0 |
| 29 | dierig2019_pages01-02.json | pdf | 4 | 0 |
| 30 | dierig2019_pages05-06.json | pdf | 6 | 5 |
| 31 | dierig2019_pages07-08.json | pdf | 9 | 5 |
| 32 | dierig2019_pages09-10.json | pdf | 11 | 5 |
| 33 | dierig2019_pages11-12.json | pdf | 8 | 3 |
| 34 | dierig2019_pages13-14.json | pdf | 10 | 4 |
| 35 | dierig2019_pages15-16.json | pdf | 9 | 4 |
| 36 | dierig2019_pages17-18.json | pdf | 5 | 2 |
| 37 | dierig2019_pages19-20.json | pdf | 13 | 4 |
| 38 | dierig2019_pages21-22.json | pdf | 10 | 4 |
| 39 | dierig2019_pages23-24.json | pdf | 12 | 4 |
| 40 | dierig2019_pages25-26.json | pdf | 13 | 3 |
| 41 | dierig2019_pages27-28.json | pdf | 7 | 1 |
| 42 | dierig2019_pages29-30.json | pdf | 3 | 2 |
| 43 | dierig2019_pages31-32.json | pdf | 3 | 2 |
| 44-71 | (Additional files) | pdf/slide | ... | ... |

---

### Protein Synonym Map
| Canonical name | Aliases found |
|----------------|---------------|
| GRIA1 | GluA1, GluR1 |
| GRIA2 | GluA2, GluR2 |
| GRIA3 | GluA3, GluR3 |
| GRIA4 | GluA4, GluR4 |
| DLG4 | PSD-95 |
| CACNG2 | Stargazin |
| ATAD1 | Thorase |
| IQSEC1 | BRAG2 |
| ARF6 | Arf6 |
| PPP3CA | Calcineurin, CaN |
| SYNE1 | CPG2 |
| SH3GL2 | Endophilin |
| GRIP1 | GRIP |
| EPB41L1 | 4.1N |
| CAMK2A | CaMKII |

---

### Consolidated Protein/Gene List
| Protein | Gene | Sources | Described activities | Confidence |
|---------|------|---------|---------------------|------------|
| CaMKII | CAMK2A | 4, 13, 17 | phosphorylates GluA1 at S831 | HIGH |
| BRAG2 | IQSEC1 | 1, 16, 17 | GEF activity for Arf6 | HIGH |
| NSF | NSF | 1, 17, 19 | ATPase-driven complex dissociation | HIGH |
| PICK1 | PICK1 | 1, 18, 19, 20 | inhibits Arp2/3; stimulates dynamin poly. | HIGH |
| Thorase | ATAD1 | 1, 19 | ATPase-driven GluA2-GRIP dissociation | MEDIUM |
| PKC | PRKCA | 4, 6, 30 | phosphorylates GluA1 at S818/S831 | HIGH |

---

### Interaction Map
1. BRAG2 → Arf6 (4 sources: scholz2010 [PMID:20530663], ampar_pdf [Fig 1B] | DIRECT | GEF activity assay) — HIGH
2. NSF → GluA2-PICK1 complex (3 sources: ampar_pdf [PMID:12007421], slide06, slide11 | DIRECT | ATPase activity) — HIGH
3. CaMKII → Stargazin (2 sources: ampar_pdf [p03-04], slide13 | DIRECT | Kinase assay) — HIGH
4. PICK1 → GluA2 (5 sources: ampar_pdf [Fig 1B], slide06, slide08, slide11, slide19 | WARNING: only binding described, MF unknown) — LOW
5. Thorase → GluA2-GRIP complex (3 sources: ampar_pdf [p07-08], slide11, slide15 | DIRECT | ATPase activity) — MEDIUM

---

### Cross-Source Conflicts
⚠ **Conflict:** Source 1 (Image) and Source 15 (PDF) show conflicting mechanisms for Thorase. Source 1 lists it as an enzyme; Source 15/19 clarifies it as an ATPase.
  → Suggested question: "Is the enzymatic activity of Thorase strictly ATP-hydrolysis, and does this activity result in a conformational change of the GluA2-GRIP complex or direct mechanical displacement?"

---

### Gaps Identified
1. **Endocytic trigger:** The transition from stable synaptic PSD complex to endocytic zone complex is spatially mapped but the biochemical trigger remains poorly defined.
2. **Molecular Function of Scaffolds:** Most interactions involving PSD-95, PICK1, and GRIP1 are defined only as "binding" or "recruitment," lacking clear GO-term compatible MF annotations (e.g., tethering vs. transport vs. regulatory).
3. **Phosphatase Specificity:** While Calcineurin is frequently mentioned, the specific substrate pools (GluA2 vs AP2 vs PICK1) in different LTD/LTP contexts remain ambiguous.

---

### Suggested Questions for Expert Meeting
1. "Does the Thorase ATPase activity serve to destabilize the GluA2-GRIP complex via direct mechanical work, or is it a regulator of a larger complex?"
2. "Should 'recruitment' to an endocytic zone be modeled as a 'protein localization' (BP) or a 'tethering activity' (MF) in the GO-CAM?"
3. "Are the phosphorylation sites on GluA1 (S831, S845) constitutive or activity-dependent in the context of the endocytic machinery model?"