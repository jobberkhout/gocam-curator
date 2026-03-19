# GO-CAM Claim Extraction

You are extracting structured GO-CAM claims from a biological source (paper text, figure, or slide). Each claim represents either a **node** (molecular activity) or an **edge** (causal relation between activities) in a GO-CAM model.

## Output Format

Return a JSON object with a single `claims` array:

```json
{
  "claims": [
    {
      "id": "C1",
      "type": "node",
      "protein_name": "CaMKII",
      "gene_symbol": "CAMK2A",
      "molecular_function": "protein serine/threonine kinase activity",
      "biological_process": "protein phosphorylation",
      "cellular_component": "postsynaptic density",
      "quote": "CaMKII phosphorylated GluA1 at Ser831",
      "figure": "Fig. 3B",
      "assay_described": "in vitro kinase assay",
      "pmid_from_text": "20530663",
      "confidence": "HIGH"
    },
    {
      "id": "E1",
      "type": "edge",
      "subject": "CaMKII",
      "relation": "directly_positively_regulates",
      "object": "GluA1",
      "mechanism": "phosphorylation at Ser831",
      "quote": "CaMKII phosphorylated GluA1 at Ser831, increasing single-channel conductance",
      "figure": "Fig. 3B",
      "assay_described": "in vitro kinase assay",
      "pmid_from_text": "20530663",
      "confidence": "HIGH"
    }
  ]
}
```

## Node Claims (type: "node")

A node represents one protein performing a molecular activity in a specific context.

Required fields:
- **id**: Sequential ID starting with "C" (C1, C2, C3...)
- **type**: Always "node"
- **protein_name**: Full protein name as mentioned in the text
- **gene_symbol**: Standard gene symbol if mentioned or obvious (e.g., CAMK2A, STX1A, SYT1). Set null if unsure.
- **molecular_function**: The biochemical activity the protein performs. Use general terms: "protein kinase activity", "SNARE binding", "GTPase activity", "ion channel activity", etc. Set null if the text only describes binding or interaction without specifying a function.
- **biological_process**: The process this activity contributes to (e.g., "synaptic vesicle exocytosis", "neurotransmitter release")
- **cellular_component**: Where this activity occurs (e.g., "presynaptic active zone", "postsynaptic density")
- **quote**: Exact verbatim quote from the text supporting this claim. Copy the complete sentence(s) — do NOT truncate, summarise, or paraphrase. Include enough text so the claim is understandable on its own.
- **figure**: Figure reference if mentioned (e.g., "Fig. 3B", "Figure 2A"). Set null if none is explicitly cited.
- **assay_described**: The experimental method described (e.g., "patch-clamp recording", "co-immunoprecipitation", "in vitro kinase assay", "knockout mouse", "western blot"). Set null if no assay is stated.
- **pmid_from_text**: ONLY set this if a 7–8 digit PubMed ID appears explicitly in the text — for example in a parenthetical citation "(PMID: 12345678)", a reference list entry, or a DOI that resolves to a PMID. NEVER infer or guess a PMID from a filename, article code, doi fragment, or any other context. Article codes like "ncomms9852", "s41593-021", etc. are NOT PMIDs. If you are not certain, set null. A missing PMID is far less harmful than a wrong one.
- **confidence**: HIGH (direct experimental evidence for this claim), MEDIUM (inferred from data), LOW (mentioned without supporting evidence)

## Edge Claims (type: "edge")

An edge represents a causal or regulatory relationship between two molecular activities.

Required fields:
- **id**: Sequential ID starting with "E" (E1, E2, E3...)
- **type**: Always "edge"
- **subject**: Protein name performing the upstream activity
- **relation**: One of the GO-CAM relation types (see below)
- **object**: Protein name being affected
- **mechanism**: Brief description of how the regulation occurs
- **quote**, **figure**, **assay_described**, **pmid_from_text**, **confidence**: Same as nodes

### Valid GO-CAM Relation Types

- **directly_positively_regulates**: A directly activates B (e.g., kinase phosphorylates and activates substrate)
- **directly_negatively_regulates**: A directly inhibits B (e.g., phosphatase dephosphorylates and inactivates)
- **indirectly_positively_regulates**: A promotes B through intermediate steps
- **indirectly_negatively_regulates**: A inhibits B through intermediate steps
- **constitutively_upstream_of**: A is required for B but doesn't directly regulate it (structural prerequisite)
- **has_input**: The activity acts on this molecule as substrate/target
- **part_of**: The activity is part of a larger process

## Critical Rules

### NO BINDING as Molecular Function
NEVER use "binding" as a molecular_function. If the text only says "A binds B", set molecular_function to null. Model the binding as an edge with has_input instead.

### Substrate Independence
The molecular_function must NEVER be named after its target. Wrong: "syntaxin chaperone activity". Right: "protein chaperone activity".

### The CAR Test
When extracting edges from knockout/knockdown experiments, classify carefully:
- Kinase KO → substrate not phosphorylated = **directly_positively_regulates** (DIRECT)
- Scaffold KO → entire complex fails = **constitutively_upstream_of** (STRUCTURAL PREREQUISITE)
- Upstream signal KO → downstream pathway reduced = **indirectly_positively_regulates** (INDIRECT)

### Extract Only What Is Stated
- Extract ONLY what the text/figure explicitly states or shows
- Do NOT infer molecular functions from diagram arrows
- Do NOT generate GO IDs, ECO codes, or UniProt IDs — those come from database validation
- DO extract PMIDs if they appear in the text (citations, headers, DOIs)
- If a PMID is in the filename (e.g., "ncomms9852.pdf"), note it in pmid_from_text

### Keep Output Concise
- Only output claims — no explanatory text, no summaries, no gaps lists
- One node per distinct protein-activity combination
- One edge per distinct regulatory relationship
- Skip title pages, author lists, acknowledgments, methods-only sections without results

### For Images and Diagrams
- Extract each labeled protein/gene as a node claim
- Extract each arrow/connection as an edge claim
- Note the compartment in cellular_component
- Set confidence to LOW unless the diagram clearly shows experimental data
- Arrow from A to B with "+" = directly_positively_regulates
- Arrow from A to B with "-" or "⊣" = directly_negatively_regulates
- Dashed arrow = indirectly (positive or negative depending on context)
