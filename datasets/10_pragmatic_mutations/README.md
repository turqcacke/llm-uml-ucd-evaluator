# Pragmatic naming mutations

This dataset tests Naming Understandability Scores for controlled actor and
use case renames. Directories `1`–`10` correspond to source annotations
`1_result.json`–`10_result.json` from `datasets/60_ideal_UCD/1-10` and use the
matching Context Descriptions from `datasets/60_artificial/1-10`.

Each file is a benchmark case:

```json
{
    "mutation": {},
    "expectation": {
        "nodes": [
            { "uid": "actor-0", "score": 3 }
        ]
    },
    "description": "Complete original task text"
}
```

- `mutation` is a complete ReqUCD60 diagram.
- `expectation` contains exactly one UID and integer score for every actor and
  use case; it excludes the synthetic `system` node.
- `description` is the unchanged source Context Description.

UIDs are assigned by `ReqUCD60ToDomainConverter`: `actor-0`, `usecase-0`, and
so on.

Scores:

1. LOW (`1`): basic meaning is unrecognizable.
2. MEDIUM (`2`): general meaning is recognizable but remains ambiguous or
   insufficiently specific in context.
3. HIGH (`3`): meaning is clearly identifiable in context.

The source slice contains no external systems, so the dataset does not cover
their naming.

## Mutations

| Case | Changes | Target scores |
|---|---|---|
| `_0` | Unchanged control. | Original full-context scores. |
| `_1` | Rename one actor and one use case with meaningless names. | LOW, LOW. |
| `_2` | Rename the same actor and use case with overly general names. | MEDIUM, MEDIUM. |
| `_3` | Apply one meaningless and one overly general rename to the same pair. | LOW, MEDIUM. |

Every mutant is derived independently from `_0`. Only names and affected
name-based relationship references change; node order, types, and graph
structure remain unchanged. Mixed cases assign LOW to the actor in five
directories and to the use case in the other five.

Expected and actual results are compared as exact `(uid, score)` pairs: a
matching pair is TP, an actual-only pair is FP, and an expected-only pair is
FN. All runs use the full-context expectations as the single oracle.

`eval.pragmatic.models.load_dataset` loads four cases from every numeric
directory.

## Exact mutations

`[CD]` marks an original name whose HIGH interpretation depends on the Context
Description.

Unless specified by the mutation table, every expected node score is HIGH
(`3`).

| Directory | Control (`_0`) | Meaningless (`_1`) | Overly general (`_2`) | Mixed (`_3`) |
|---|---|---|---|---|
| `7` | Copy of `7_result.json`. | `[CD] User` → `Zorple`; `Watch Live Stream` → `Flarnibble`; updated association references. | `[CD] User` → `Person`; `Watch Live Stream` → `Access Content`; updated association references. The names retain meaning but omit the viewer role and live-viewing behavior. | `[CD] User` → `Zorple`; `Watch Live Stream` → `Access Content`; updated association references. |
