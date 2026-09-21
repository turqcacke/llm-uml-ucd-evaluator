# Datasets

| Directory | Dataset |
|---|---|
| [23_exercises/](23_exercises/) | 23 Apollon exercises with JSON diagrams, text descriptions, PDF documents, and an example document. |
| [60_artificial/](60_artificial/) | 60 textual requirements samples from ReqUCD60, grouped by sample number in batches of ten. |
| [60_ideal_UCD/](60_ideal_UCD/) | The corresponding 60 ReqUCD60 Reference Diagrams in JSON; matched to descriptions by sample number. |
| [10_match_mutations/](10_match_mutations/README.md) | 60 semantic matching cases derived from samples 51–60: one control and five mutations per diagram, with expected node and relation matches. |
| [10_pragmatic_mutations/](10_pragmatic_mutations/README.md) | 40 naming cases derived from samples 1–10: one control and three mutations per diagram, with expected Naming Understandability Scores and Context Descriptions. |

The local ReqUCD60 annotations include changes made after inconsistencies were
found in the original dataset. The [Dataset Correction Log](60_ideal_UCD/CHANGELOG.md)
documents the issues, corrections, and additional changes across eight annotation
files.

See the mutation dataset READMEs for formats, expectations, and exact changes.
See [Evaluation](../README.md#evaluation) for experiment commands and arguments.
