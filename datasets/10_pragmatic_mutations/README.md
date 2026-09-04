# Pragmatic naming mutations

This 40-case dataset tests Naming Understandability Scores for controlled
actor and use case renames.

| Directory | Reference Diagram | Context Description | Cases |
|---|---|---|---:|
| `1` | `datasets/60_ideal_UCD/1-10/1_result.json` | `datasets/60_artificial/1-10/1.txt` | 4 |
| `2` | `datasets/60_ideal_UCD/1-10/2_result.json` | `datasets/60_artificial/1-10/2.txt` | 4 |
| `3` | `datasets/60_ideal_UCD/1-10/3_result.json` | `datasets/60_artificial/1-10/3.txt` | 4 |
| `4` | `datasets/60_ideal_UCD/1-10/4_result.json` | `datasets/60_artificial/1-10/4.txt` | 4 |
| `5` | `datasets/60_ideal_UCD/1-10/5_result.json` | `datasets/60_artificial/1-10/5.txt` | 4 |
| `6` | `datasets/60_ideal_UCD/1-10/6_result.json` | `datasets/60_artificial/1-10/6.txt` | 4 |
| `7` | `datasets/60_ideal_UCD/1-10/7_result.json` | `datasets/60_artificial/1-10/7.txt` | 4 |
| `8` | `datasets/60_ideal_UCD/1-10/8_result.json` | `datasets/60_artificial/1-10/8.txt` | 4 |
| `9` | `datasets/60_ideal_UCD/1-10/9_result.json` | `datasets/60_artificial/1-10/9.txt` | 4 |
| `10` | `datasets/60_ideal_UCD/1-10/10_result.json` | `datasets/60_artificial/1-10/10.txt` | 4 |

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
structure remain unchanged. Mixed cases assign LOW to the actor in directories
1, 3, 5, 7, and 9, and to the use case in directories 2, 4, 6, 8, and 10.

Expected and actual results are compared as exact `(uid, score)` pairs: a
matching pair is TP, an actual-only pair is FP, and an expected-only pair is
FN. All runs use the full-context expectations as the single oracle.

`eval.pragmatic.models.load_dataset` loads four cases from every numeric
directory.

## Collect observations

Start MongoDB, configure the evaluator as described in the root README, and
run the contextual experiment from the repository root:

```sh
uv run python -m eval.pragmatic.collect_observations \
  --experiment-name pragmatic_context_2026-09-18
```

Run without the Context Description:

```sh
uv run python -m eval.pragmatic.collect_observations \
  --experiment-name pragmatic_no_context_2026-09-18 --with-context 0
```

Use one, two, or three repetitions (the default is three):

```sh
uv run python -m eval.pragmatic.collect_observations \
  --experiment-name pragmatic_context_once_2026-09-18 --repetitions 1
```

Resume an interrupted run with the original experiment name and repetition
count:

```sh
uv run python -m eval.pragmatic.collect_observations \
  --experiment-name pragmatic_context_2026-09-18 --repetitions 3 --resume
```

The checkpoint's context mode controls the resumed run. Omitting
`--with-context` uses it silently; supplying a different value warns and still
uses the checkpoint value. Fresh runs require a new experiment name.

## Exact mutations

`[CD]` marks an original name whose HIGH interpretation depends on the Context
Description. Without it, the marked name remains plausibly ambiguous.

Unless specified by the mutation table, every expected node score is HIGH
(`3`).

| Directory | Control (`_0`) | Meaningless (`_1`) | Overly general (`_2`) | Mixed (`_3`) |
|---|---|---|---|---|
| `1` | Copy of `1_result.json`. Targets: `[CD] User` (`actor-0`) and `Open PDF File` (`usecase-0`). The description establishes the generic actor as the PDF-reader user. | `User` → `Tavrix` (1); `Open PDF File` → `Quindle` (1); updated association references. | `User` → `Person` (2); `Open PDF File` → `Access File` (2); the names omit the PDF-reader role, PDF format, and opening action. | `User` → `Tavrix` (1); `Open PDF File` → `Access File` (2); updated association references. |
| `2` | Copy of `2_result.json`. Targets: `Employee` (`actor-0`) and `Submit Reimbursement Request` (`usecase-1`). | `Employee` → `Morzap` (1); `Submit Reimbursement Request` → `Flibber` (1); updated association references. | `Employee` → `Person` (2); `Submit Reimbursement Request` → `Handle Request` (2); the names omit the employee role, reimbursement, and submission action. | `Employee` → `Person` (2); `Submit Reimbursement Request` → `Flibber` (1); updated association references. |
| `3` | Copy of `3_result.json`. Targets: `[CD] User` (`actor-0`) and `Synchronize Memo Data` (`usecase-6`). The description establishes the generic actor as the personal-memo user. | `User` → `Nexul` (1); `Synchronize Memo Data` → `Womple` (1); updated association references. | `User` → `Person` (2); `Synchronize Memo Data` → `Manage Data` (2); the names omit the memo-user role and synchronization behavior. | `User` → `Nexul` (1); `Synchronize Memo Data` → `Manage Data` (2); updated association references. |
| `4` | Copy of `4_result.json`. Targets: `User` (`actor-0`) and `Publish Article` (`usecase-5`). | `User` → `Dravik` (1); `Publish Article` → `Snorble` (1); updated association references. | `User` → `Person` (2); `Publish Article` → `Publish Content` (2); the names omit the blog-user role and do not distinguish articles from other content. | `User` → `Person` (2); `Publish Article` → `Snorble` (1); updated association references. |
| `5` | Copy of `5_result.json`. Targets: `User` (`actor-0`) and `Receive Audio Guidance` (`usecase-9`). | `User` → `Kelvot` (1); `Receive Audio Guidance` → `Plimza` (1); updated association references. | `User` → `Person` (2); `Receive Audio Guidance` → `Receive Guidance` (2); the names omit the museum-guide role and audio modality. | `User` → `Kelvot` (1); `Receive Audio Guidance` → `Receive Guidance` (2); updated association references. |
| `6` | Copy of `6_result.json`. Targets: `User` (`actor-0`) and `Generate Order` (`usecase-4`). | `User` → `Ruvex` (1); `Generate Order` → `Tronkle` (1); updated association references. | `User` → `Person` (2); `Generate Order` → `Generate Record` (2); the names omit the shopping role and do not identify the record as an order. | `User` → `Person` (2); `Generate Order` → `Tronkle` (1); updated association references. |
| `7` | Copy of `7_result.json`. Targets: `[CD] User` (`actor-0`) and `Watch Live Stream` (`usecase-2`). The description establishes the generic actor as the live-stream viewer. | `User` → `Zorple` (1); `Watch Live Stream` → `Flarnibble` (1); updated association references. | `User` → `Person` (2); `Watch Live Stream` → `Access Content` (2); the names omit the viewer role and live-viewing behavior. | `User` → `Zorple` (1); `Watch Live Stream` → `Access Content` (2); updated association references. |
| `8` | Copy of `8_result.json`. Targets: `User` (`actor-0`) and `Submit Claims Application` (`usecase-3`). | `User` → `Bexar` (1); `Submit Claims Application` → `Glompit` (1); updated association references. | `User` → `Person` (2); `Submit Claims Application` → `Submit Application` (2); the names omit the insurance-customer role and claim purpose. | `User` → `Person` (2); `Submit Claims Application` → `Glompit` (1); updated association references. |
| `9` | Copy of `9_result.json`. Targets: `User` (`actor-0`) and `Create Custom Form` (`usecase-1`). | `User` → `Varnok` (1); `Create Custom Form` → `Crindle` (1); updated association references. | `User` → `Person` (2); `Create Custom Form` → `Create Item` (2); the names omit the form-user role and do not identify the item as a form. | `User` → `Varnok` (1); `Create Custom Form` → `Create Item` (2); updated association references. |
| `10` | Copy of `10_result.json`. Targets: `Visitor` (`actor-0`) and `Navigate Using Map` (`usecase-2`). | `Visitor` → `Juxel` (1); `Navigate Using Map` → `Frabble` (1); updated association references. | `Visitor` → `Person` (2); `Navigate Using Map` → `Use Map` (2); the names omit the visitor role and navigation behavior. | `Visitor` → `Person` (2); `Navigate Using Map` → `Frabble` (1); updated association references. |
