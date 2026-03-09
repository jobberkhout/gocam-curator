# Extraction Report — Test synapse
## Generated: 2026-03-05 | Sources: 2 files analyzed

### Sources Analyzed
| # | File | Type | Entities found | Interactions |
|---|------|------|---------------|--------------|
| 1 | ampar_pdf_pages09-10.json | pdf | 40 | 33 |
| 2 | sample.json | text | 10 | 5 |

---

### Consolidated Protein/Gene List (deduplicated)
| Protein | Gene | Sources | Described activities | Confidence |
|---------|------|---------|---------------------|------------|
| AMPA receptor (complex) | (complex) | 1, 2 | down-regulation, trafficking, cycling, mediated synaptic transmission, synaptic surface accumulation, endocytosis, intracellular sorting, degradation, synaptic incorporation, removal, receptor-dependent synaptic plasticity, single-channel conductance increase (upon GRIA1 phosphorylation), recycling to the plasma membrane | MEDIUM — broad biological roles, specific interactions with components |
| GluA1 | GRIA1 | 1, 2 | ubiquitination of GluA1, phosphorylation at Ser831 (as target) | HIGH — direct phosphorylation described and confirmed |
| GluA2 | GRIA2 | 1, 2 | synaptic removal, ubiquitination of GluA2, binds PICK1 via its PDZ domain | HIGH — direct binding described |
| PICK1 | PICK1 | 1, 2 | inhibition of the Arp2/3 complex, regulates neuronal morphology, regulates AMPA receptor endocytosis, regulates synaptic strength, regulates AMPA receptor subunit composition, binds GluA2 via its PDZ domain | HIGH — explicit direct inhibition described |
| NSF | NSF | 1, 2 | play distinct roles in AMPA receptor trafficking, play distinct roles in hippocampal LTD, required for the synaptic incorporation and removal of AMPA receptors, ATPase activity, disassembles the GluA2-PICK1 complex | HIGH — direct ATPase activity and complex disassembly described |
| CaMKII | CAMK2 | 2 | phosphorylates GluA1 at Ser831, enzymatic activity | HIGH — direct enzymatic activity confirmed by kinase-dead mutant |
| Arp2/3 complex | (complex) | 1 | Arp2/3-mediated actin polymerization | MEDIUM — target of direct inhibition |
| CPG2 | CPG2 | 1 | recruits endophilin B2 to the cytoskeleton | HIGH — direct recruitment described |
| dynamin-3 | DNM3 | 1 | physical coupling of dynamin-3 to Homer results in postsynaptic positioning of endocytic zones and AMPA receptor cycling | HIGH — direct physical coupling leading to positioning/cycling |
| Eps15 | EPS15 | 1 | involved in the trafficking of ubiquitinated α-amino-3-hydroxy-5-methyl-4-isoxazolepropionic acid receptors | MEDIUM — described as 'involved in', suggesting an indirect role |
| GRIP1 (ABP/GRIP) | GRIP1 | 1 | directly steers kinesin to dendrites, role in synaptic surface accumulation of the AMPA receptor | HIGH — direct steering described |
| Homer | (protein) | 1 | (implied interaction partner for Dynamin-3) | MEDIUM — part of a direct physical interaction |
| PKA | (kinase) | 1 | (implied role in CPG2 association) | LOW — implied role, no direct activity specified |
| Arf1 | ARF1 | 1 | modulates Arp2/3-mediated actin polymerization via PICK1 | MEDIUM — modulation via an intermediate |
| BRAG2 | BRAG2 | 1 | (implied in AMPA receptor signaling) | LOW — described as 'signaling through', implying indirect involvement |
| Arf6 | ARF6 | 1 | (implied in AMPA receptor signaling) | LOW — described as 'signaling through', implying indirect involvement |
| Arc/Arg3.1 | ARC | 1 | mediates homeostatic synaptic scaling of AMPA receptors | MEDIUM — mediates a complex process |
| NEEP21 | (protein) | 1 | (implied in interactions with GRIP1 and GluR2) | LOW — implied by 'interactions regulate' |
| TARP family (TARP, stargazin-like TARPs) | (family) | 1 | dephosphorylation, phosphorylation | MEDIUM — phosphorylation/dephosphorylation mentioned for the family |
| PACSIN1 | PACSIN1 | 1 | regulates the dynamics of AMPA receptor trafficking | MEDIUM — regulates a dynamic process |
| PKC | (kinase) | 1 | regulates interactions between GluR2/3 and PDZ domain-containing proteins | MEDIUM — regulates interactions |
| tyrosine phosphatase STEP | PTPN5 | 1 | mediates AMPA receptor endocytosis | HIGH — direct phosphatase activity implied for endocytosis |
| AAA+ ATPase Thorase | (ATPase) | 1 | regulates AMPA receptor-dependent synaptic plasticity, regulates behavior | MEDIUM — regulates complex biological processes |
| Hippocalcin | HPCA | 1 | functions as a calcium sensor | HIGH — direct sensor function described |
| clathrin adaptor complex AP-2 | (complex) | 1 | interacts with AMPA receptor, interacts with GluR2 | MEDIUM — direct interaction mentioned |
| PDZ domains | (domain) | 1 | interact with GRIA2 | LOW — only interaction described |
| endophilin B2 | (protein) | 1 | (recruited by CPG2) | MEDIUM — target of direct recruitment |
| cytoskeleton | (structure) | 1 | contribution to the internalization of AMPA receptors | HIGH — structural prerequisite for internalization |
| amphiphysin | (protein) | 1 | has binding motifs for AP2 complex α-appendage | LOW — only binding motifs described |
| AP2 complex α-appendage | (component) | 1 | (binding motifs for amphiphysin and accessory proteins) | LOW — only binding motifs described |
| accessory proteins | (proteins) | 1 | have binding motifs for AP2 complex α-appendage | LOW — only binding motifs described |
| kinesin | (motor protein) | 1 | directly steered to dendrites by GRIP1 | HIGH — target of direct steering |
| metabotropic glutamate receptor | (receptor) | 1 | stimulation | LOW — general stimulation, no specific activity of the receptor itself |
| calcium | (ion) | 1 | (sensed by Hippocalcin) | LOW — input, not an entity with intrinsic activity |
| calcineurin | (phosphatase) | 1 | (implied role in hippocampal long-term depression) | LOW — general context |
| inhibitor-1 phosphatase | (phosphatase) | 1 | (implied role in hippocampal long-term depression) | LOW — general context |

---

### Interaction Map (all sources merged)
1.  GRIA2 --[interacts with]--> PICK1 (Sources: 1, 2 | INDIRECT (S1) / UNKNOWN (S2) | S1: AMPAR down-regulation involves this interaction. S2: Direct binding via PDZ domain, but functional consequence unclear. WARNING: Only binding described in S2, MF unknown.)
2.  AMPA receptor --[interacts with]--> clathrin adaptor complex AP-2 (Sources: 1 | UNKNOWN | Only interaction stated, no outcome.)
3.  GRIA2 --[interacts with]--> PDZ domains (Sources: 1 | INDIRECT | Regulates hippocampal long-term depression.)
4.  clathrin adaptor AP-2 --[interacts with]--> GRIA2 (Sources: 1 | UNKNOWN | Only interaction stated, no outcome.)
5.  NSF --[interacts with]--> GRIA2 (Sources: 1 | UNKNOWN | Only interaction stated, no outcome.)
6.  clathrin adaptor AP-2 --[plays a role in]--> AMPA receptor trafficking (Sources: 1 | INDIRECT | General role, not specific action.)
7.  NSF --[plays a role in]--> AMPA receptor trafficking (Sources: 1 | INDIRECT | General role, not specific action.)
8.  EPS15 --[involved in the trafficking of]--> ubiquitinated AMPA receptors (Sources: 1 | INDIRECT | General involvement, not specific action.)
9.  CPG2 --[recruits to the cytoskeleton]--> endophilin B2 (Sources: 1 | DIRECT | Recruitment to a location.)
10. PKA-dependent association with CPG2 --[mediates regulation of]--> glutamate receptor internalization (Sources: 1 | INDIRECT | 'Mediation' of 'regulation' implies complex steps.)
11. DNM3 --[physical coupling results in postsynaptic positioning and cycling]--> Homer (Sources: 1 | DIRECT | Physical coupling directly positions endocytic zones and cycles AMPARs.)
12. NSF-GRIA2 interaction --[regulates]--> AMPA receptors (Sources: 1 | INDIRECT | Regulation via interaction implies signaling.)
13. clathrin-dependent receptor internalization --[regulates]--> AMPA receptor-mediated synaptic transmission (Sources: 1 | INDIRECT | Internalization is a complex process.)
14. Stargazin --[regulates through adaptor protein complexes]--> AMPA receptor trafficking (Sources: 1 | INDIRECT | Regulation 'through' intermediates.)
15. PICK1 --[inhibits]--> Arp2/3 complex (Sources: 1 | DIRECT | Explicit inhibition.)
16. amphiphysin --[has binding motifs for]--> AP2 complex α-appendage (Sources: 1 | UNKNOWN | WARNING: only binding described, MF unknown.)
17. accessory proteins --[have binding motifs for]--> AP2 complex α-appendage (Sources: 1 | UNKNOWN | WARNING: only binding described, MF unknown.)
18. GRIP1 binding to GRIA2 --[has a role in]--> synaptic surface accumulation of the AMPA receptor (Sources: 1 | INDIRECT | 'Role in' accumulation implies a broader process.)
19. ARF1 --[modulates via PICK1]--> Arp2/3-mediated actin polymerization (Sources: 1 | INDIRECT | Modulation via an intermediate.)
20. PICK1 --[inhibits]--> Arp2/3-mediated actin polymerization (Sources: 1 | DIRECT | Explicit inhibition.)
21. AMPA receptor signaling --[occurs through]--> BRAG2 and ARF6 (Sources: 1 | INDIRECT | Signaling 'through' intermediates.)
22. ubiquitination of GRIA1 --[mediates]--> AMPA receptor endocytosis and sorting pathway (Sources: 1 | INDIRECT | Modification mediates a pathway.)
23. GRIP1 --[directly steers]--> kinesin (to dendrites) (Sources: 1 | DIRECT | Explicit direct steering.)
24. ARC --[mediates]--> homeostatic synaptic scaling of AMPA receptors (Sources: 1 | INDIRECT | Mediation of a complex process.)
25. Interactions between NEEP21, GRIP1 and GRIA2 --[regulate]--> sorting and recycling of GRIA2 (Sources: 1 | INDIRECT | Interactions 'regulate' a complex process.)
26. TARP family phosphorylation --[regulates through lipid bilayers]--> synaptic AMPA receptors (Sources: 1 | INDIRECT | Regulation 'through' a medium.)
27. PICK1 --[regulates]--> synaptic strength (Sources: 1 | INDIRECT | Regulation of a high-level process.)
28. PICK1 --[regulates]--> AMPA receptor subunit composition (Sources: 1 | INDIRECT | Regulation of a complex process.)
29. PKC --[regulates]--> interactions between GRIA2 and PDZ domain-containing proteins (Sources: 1 | INDIRECT | Regulation of interactions.)
30. PTPN5 --[mediates]--> AMPA receptor endocytosis (Sources: 1 | DIRECT | Phosphatase directly mediates endocytosis.)
31. AAA+ ATPase Thorase --[regulates]--> AMPA receptor-dependent synaptic plasticity (Sources: 1 | INDIRECT | Regulation of a complex process.)
32. AAA+ ATPase Thorase --[regulates]--> behavior (Sources: 1 | INDIRECT | Regulation of a high-level process.)
33. cytoskeleton --[contributes to]--> internalization of AMPA receptors (Sources: 1 | STRUCTURAL_PREREQUISITE | Structural support.)
34. CAMK2 --[phosphorylates]--> GRIA1 at Ser831 (Sources: 2 | DIRECT | Confirmed by kinase-dead mutant.)
35. GRIA1 (phosphorylated at Ser831) --[increasing]--> AMPA receptors (single-channel conductance) (Sources: 2 | DIRECT | Direct effect on biophysical property.)
36. PICK1 --[binds]--> GRIA2 via its PDZ domain (Sources: 2 | UNKNOWN | WARNING: only binding described, MF unknown. Functional consequence unclear from text.)
37. NSF --[disassembles]--> GluA2-PICK1 complex (Sources: 2 | DIRECT | ATPase activity.)
38. GluA2-PICK1 complex disassembly --[promoting]--> AMPA receptor recycling to the plasma membrane (Sources: 2 | INDIRECT | Disassembly promotes recycling through intermediate steps.)

---

### Cross-Source Conflicts
⚠ **Discrepancy in the described functional consequence of PICK1-GluA2 interaction.**
  → Source 1 states that "AMPAR down-regulation involves interaction of the carboxyl terminus of GluR2/3 with Pick1," implying a functional role in this process. However, Source 2 explicitly states for PICK1 binding GluA2: "The functional consequence of this interaction is unclear from the current data." This suggests a conflict in the certainty or understanding of the downstream effects of this specific interaction.
  → Suggested question for expert: "Regarding the interaction between PICK1 and GluA2, Source 1 suggests its involvement in AMPAR down-regulation, while Source 2 states its functional consequence is unclear. Can you clarify the direct molecular outcome and significance of PICK1 binding to GluA2?"

---

### Gaps Identified (across all sources)
1.  **Molecular Function of PICK1-GluA2 Interaction:** The specific molecular function or direct consequence of PICK1 binding to GluA2/GluR2/3 is not clearly described across all sources.
2.  **Molecular Function of AMPA receptor - AP-2 Interaction:** The direct molecular function or specific consequence of AMPA receptor interaction with clathrin adaptor complex AP-2 is not specified.
3.  **Molecular Function of GluR2/3 - PDZ Domains Interaction:** The direct molecular function or specific consequence of GluR2/3 interaction with PDZ domains is not specified beyond 'regulating LTD'.
4.  **Specific Mechanism of Eps15 in Trafficking:** The specific molecular mechanism by which Eps15 is 'involved in' trafficking of ubiquitinated AMPARs is not explained.
5.  **PKA-CPG2-Glutamate Receptor Internalization Mechanism:** The specific molecular mechanism by which PKA-dependent association with CPG2 'mediates' regulation of glutamate receptor internalization is not detailed.
6.  **Molecular Function of ABP/GRIP-GluR2 Binding:** The precise molecular function of ABP/GRIP (GRIP1) binding to GluR2 (GRIA2) in synaptic surface accumulation is not detailed.
7.  **Consequence of Amphiphysin/Accessory Proteins Binding AP2 α-appendage:** The specific molecular consequence of amphiphysin and other accessory proteins having 'binding motifs' for AP2 complex α-appendage is not described.
8.  **Mechanism of Arf1 Modulation of Arp2/3-mediated Actin Polymerization:** The exact molecular mechanism of Arf1 'modulating' Arp2/3-mediated actin polymerization via PICK1 is not detailed.
9.  **AMPA Receptor Signaling through BRAG2 and Arf6:** The specific molecular steps by which AMPA receptor 'signaling through' BRAG2 and Arf6 is critical for LTD are not described.
10. **Upstream Ubiquitin Ligase for GluA1/GluA2:** The specific E3 ligase(s) responsible for the activity-dependent ubiquitination of GluA1 and GluA2 are not named.
11. **Intermediate Steps of Arc/Arg3.1 in Synaptic Scaling:** The intermediate molecular steps through which Arc/Arg3.1 'mediates' homeostatic synaptic scaling of AMPA receptors are not detailed.
12. **Molecular Mechanisms of NEEP21, GRIP1, and GluR2 Interactions:** The precise molecular functions of NEEP21 and GRIP1 in their interactions with GluR2 that regulate sorting and recycling are not provided.
13. **Kinase for TARP Phosphorylation:** The enzyme responsible for 'TARP phosphorylation' is not identified.
14. **PICK1 Regulation of Synaptic Strength/Subunit Composition:** The specific molecular mechanisms by which PICK1 'regulates' synaptic strength and AMPA receptor subunit composition are not described.
15. **PKC Regulation of GluR2/3-PDZ Protein Interactions:** The specific target of PKC's regulation of interactions between GluR2/3 and PDZ domain-containing proteins is not explicitly stated.
16. **Target of Tyrosine Phosphatase STEP on AMPA Receptor:** The specific target on the AMPA receptor for tyrosine phosphatase STEP's mediation of endocytosis is not named.
17. **Mechanism of AAA+ ATPase Thorase in Synaptic Plasticity/Behavior:** The mechanism by which AAA+ ATPase Thorase 'regulates' synaptic plasticity and behavior is not specified.
18. **Specific Tyrosine Phosphatases in AMPAR Trafficking:** The specific 'tyrosine phosphatases' involved in regulating AMPA receptor trafficking are not named.
19. **Calcineurin/Inhibitor-1 Phosphatase Cascade Details:** The specific components of the 'calcineurin/inhibitor-1 phosphatase cascade' and their direct targets are not detailed.
20. **Specific Stargazin-like TARPs and their Kinases:** The specific 'stargazin-like TARPs' are not named, and the upstream kinase for their phosphorylation is not identified.
21. **PACSIN1 Regulation Mechanism:** The exact molecular mechanism by which PACSIN1 regulates the dynamics of AMPA receptor trafficking is not detailed.
22. **Specific Adaptor Protein Complexes for Stargazin Regulation:** The specific 'adaptor protein complexes' through which Stargazin regulates AMPA receptor trafficking are not named.

---

### Suggested Questions for Expert Meeting
1.  Regarding the interaction between PICK1 and GluA2, Source 1 suggests its involvement in AMPAR down-regulation, while Source 2 states its functional consequence is unclear. Can you clarify the direct molecular outcome and significance of PICK1 binding to GluA2?
2.  What is the specific molecular function performed by AP2 and NSF when they interact with GluR2 (GRIA2)?
3.  What is the direct molecular outcome of the interaction between GluR2/3 (GRIA2) and PDZ domains that regulates hippocampal LTD?
4.  Can you specify the mechanistic role of Eps15 in the trafficking of ubiquitinated AMPA receptors?
5.  Could you elaborate on the PKA-dependent association between the spine cytoskeleton and CPG2, and how it directly regulates glutamate receptor internalization?
6.  What is the molecular function of ABP/GRIP (GRIP1) when it binds to GluR2 (GRIA2) to promote synaptic surface accumulation of the AMPA receptor?
7.  What are the specific molecular functions or consequences of amphiphysin and other accessory proteins binding to the AP2 complex α-appendage?
8.  How exactly does Arf1 modulate Arp2/3-mediated actin polymerization via PICK1? Is PICK1 a direct target of Arf1?
9.  Can you describe the direct molecular interactions and events that constitute AMPA receptor signaling 'through' BRAG2 and Arf6?
10. Which specific E3 ligase(s) are responsible for the activity-dependent ubiquitination of GluA1 (GRIA1) and GluA2 (GRIA2)?
11. What are the intermediate molecular steps through which Arc/Arg3.1 (ARC) mediates homeostatic synaptic scaling of AMPA receptors?
12. What are the precise molecular functions of NEEP21 and GRIP1 in their interactions with GluR2 (GRIA2) that regulate sorting and recycling?
13. Which kinase phosphorylates TARP family members, and how does this phosphorylation directly lead to the regulation of synaptic AMPA receptors through lipid bilayers?
14. What are the direct molecular mechanisms by which PICK1 regulates synaptic strength and AMPA receptor subunit composition?
15. Which specific kinase activity of PKC directly regulates the interactions between GluR2/3 (GRIA2) and PDZ domain-containing proteins?
16. What is the specific target on the AMPA receptor that tyrosine phosphatase STEP (PTPN5) dephosphorylates to mediate endocytosis?
17. What are the direct molecular targets and mechanisms by which AAA+ ATPase Thorase regulates synaptic plasticity and behavior?
18. Can the specific tyrosine phosphatases involved in regulating AMPA receptor trafficking be identified?
19. Can the specific components and their direct interactions within the calcineurin/inhibitor-1 phosphatase cascade be detailed?
20. Are 'stargazin', 'stargazin-like TARPs', and 'TARP' referring to the same protein or a family? Which specific kinases phosphorylate them?
21. What is the exact molecular mechanism by which PACSIN1 regulates the dynamics of AMPA receptor trafficking?
22. What are the specific adaptor protein complexes through which Stargazin regulates AMPA receptor trafficking?