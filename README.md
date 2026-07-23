# cjm-capability-pysbd

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

pySBD-based sentence-segmentation tool capability for the cjm-substrate runtime — rule-based Golden-Rules sentence boundaries delivered as character spans over the ORIGINAL text, trimmed to non-whitespace extents. Implements the sentence_segmentation task (cjm-sentence-segmentation-adapter-interface): pure compute, pure-pip, no model download, CPU-cheap — the segmenter behind the transcript decomposition pipeline's sentence-split stage (--sentence-split), chosen (DEC cc904eee) for the abbreviation/initial/honorific class ('Mr. Gorbachev', '3 p.m.', 'U.S.') that end-of-token heuristics mis-split. Config is a single language knob (Golden-Rules set selection, reload-triggered); clean=False + char_span=True are contract invariants, not knobs — spans must index into exactly the string the caller passed. Its effective-config hash joins the decomp skeleton-identity composite, so spines cut by different segmenter configs can never share node ids.

## Modules

- **`cjm_capability_pysbd`**
- **`cjm_capability_pysbd.capability`** — Pure-compute sentence-segmentation tool capability using pySBD (Option C; B.5 work item 81e43606).

## API

### `cjm_capability_pysbd.capability`

- `PySBDConfig` _class_ — Configuration for the pySBD segmenter.
- `PySBDSegmentationCapability` _class_ — Sentence-segmentation tool capability using pySBD (pure compute).

## Dependencies

**Depends on:** `cjm-capability-primitives`, `cjm-substrate`, `pysbd`
