# Match mutations

This dataset tests semantic matching between a Reference Diagram and a
Candidate Diagram across different models.

| Directory | Reference Diagram | Context Description | Cases |
|---|---|---|---:|
| `1` | `datasets/60_ideal_UCD/51-60/51_result.json` | `datasets/60_artificial/51-60/51.txt` | 6 |
| `2` | `datasets/60_ideal_UCD/51-60/52_result.json` | `datasets/60_artificial/51-60/52.txt` | 6 |
| `3` | `datasets/60_ideal_UCD/51-60/53_result.json` | `datasets/60_artificial/51-60/53.txt` | 6 |
| `4` | `datasets/60_ideal_UCD/51-60/54_result.json` | `datasets/60_artificial/51-60/54.txt` | 6 |
| `5` | `datasets/60_ideal_UCD/51-60/55_result.json` | `datasets/60_artificial/51-60/55.txt` | 6 |
| `6` | `datasets/60_ideal_UCD/51-60/56_result.json` | `datasets/60_artificial/51-60/56.txt` | 6 |
| `7` | `datasets/60_ideal_UCD/51-60/57_result.json` | `datasets/60_artificial/51-60/57.txt` | 6 |
| `8` | `datasets/60_ideal_UCD/51-60/58_result.json` | `datasets/60_artificial/51-60/58.txt` | 6 |
| `9` | `datasets/60_ideal_UCD/51-60/59_result.json` | `datasets/60_artificial/51-60/59.txt` | 6 |
| `10` | `datasets/60_ideal_UCD/51-60/60_result.json` | `datasets/60_artificial/51-60/60.txt` | 6 |

Each file is an executable benchmark case:

```json
{
    "mutation": {
        "actors": [],
        "usecases": [],
        "association_relationships": {},
        "inclusion_relationships": {},
        "extension_relationships": {},
        "generalization_relationships_for_usecases": {},
        "generalization_relationships_for_actors": {}
    },
    "expectation": {
        "node_matches": [
            { "reference_uid": "system", "candidate_uid": "system" }
        ],
        "relation_matches": []
    }
}
```

- `mutation` is a complete ReqUCD60 result.
- `expectation` is the complete MinMatching that a semantically correct
  matcher returns when comparing the mutation with that directory's `_0`
  Reference Diagram.

Expectation rules:

1. Every pair uses the ordinal UIDs assigned by
   `ReqUCD60ToDomainConverter`.
2. An omitted pair means unmatched elements, not an abbreviated answer.
3. Every case includes the converter's synthetic `system` to `system` Node
   Match.

In each directory, `{n}_0.json` is also the unchanged self-match control.
Its expectation matches every node and relation to itself. Files
`{n}_1.json`–`{n}_5.json` are independent Candidate Diagram mutations:

- `_1` reorders the diagram. Its expectation follows semantic elements across
  changed ordinal UIDs.
- `_2` introduces a typo and still matches the renamed use case and relations.
- `_3` paraphrases a use case and still matches the renamed use case and
  relations.
- `_4` removes a use case. Its expectation omits that node and its relations.
- `_5` adds an unrelated use case. Its expectation omits the added node.

`eval.matching.load_dataset` loads all 60 cases and rejects unknown or reused
Reference/Candidate UIDs and expectations without the system match before an
experiment invokes the matcher.

## Run the experiment

Start a three-repetition experiment from the repository root:

```sh
uv run python -m eval.matching.collect_observations \
  --experiment-name matcher_2026-09-16
```

Resume an interrupted experiment with the same name and repetition count:

```sh
uv run python -m eval.matching.collect_observations \
  --experiment-name matcher_2026-09-16 --repetitions 3 --resume
```

Progress is stored atomically in `eval_out/`. A completed experiment
name cannot be reused; choose a new name for another run.

## Expected metrics changes

| Mutation | Specification | Metric changes |
|---|---|---|
| `_1` | Reorder actors, use cases, and relationships without changing the graph. | None |
| `_2` | Introduce one typo in a use case name. | None |
| `_3` | Paraphrase one use case name without changing its meaning. | None |
| `_4` | Remove one use case and all its relationships. | `node_matches↓, relation_matches↓, missing_nodes↑, missing_relations↑` |
| `_5` | Add one similarly named but semantically different unconnected use case. | `redundant_nodes↑` |

## Exact mutations

| Directory | Reference Diagram (`_0`) | Reordered (`_1`) | Typo (`_2`) | Paraphrase (`_3`) | Removed (`_4`) | Added (`_5`) |
|---|---|---|---|---|---|---|
| `1` | Copy of `51_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `View Delivery Records` → `View Delivry Records`; updated its `Administrator` association and incoming `extend`. | `Check Delivery Status` → `Monitor Delivery Status`; updated its `Customer` association. | Removed `Record Return Time` and its `Delivery Personnel` association. | Added unconnected `Check Account Status`. |
| `2` | Copy of `52_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Search Catalog` → `Search Catlog`; updated its `Library Member` and `Student Member` associations. | `Process Returns` → `Handle Returned Books`; updated its `Librarian` and `Senior Librarian` associations. | Removed `Generate Monthly Acquisition Reports` and its `Senior Librarian` association. | Added unconnected `Borrow E-Books`. |
| `3` | Copy of `53_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Access Patient Histories` → `Access Patient Histores`; updated its `Doctor`, `Oncologist`, and `Senior Doctor` associations. | `Verify Insurance Coverage` → `Confirm Insurance Eligibility`; updated its `Hospital Patient` association and two incoming `include` relationships. | Removed `Order Genomic Testing` and its `Oncologist` association. | Added unconnected `Schedule Dental Checkup`. |
| `4` | Copy of `54_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Monitor Traffic Congestion` → `Monitor Traffic Congeston`; updated its `Road Sensors` association and incoming `include`. | `Find Optimal Routes` → `Calculate Best Routes`; updated its `City Drivers` association and two outgoing `include` relationships. | Removed `Create 3D Collision Analysis` and its `Accident Reconstruction Specialists` association. | Added unconnected `Monitor Network Traffic`. |
| `5` | Copy of `55_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Manage Listings` → `Manage Listngs`; updated its `Sellers` and `Power Sellers` associations. | `Access Exclusive Deals` → `View Members-Only Offers`; updated its `Premium Members` association. | Removed `Handle VAT Registration for EU Customers` and its `Power Sellers` association. | Added unconnected `Place Advertisement`. |
| `6` | Copy of `56_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Annotate Medical Images` → `Annotate Medical Imags`; updated its `Pathologist` association. | `Review AI-Generated Diagnostic Suggestions` → `Examine AI Diagnostic Recommendations`; updated three actor associations and its incoming `include`. | Removed `Manage User Roles` and its `Hospital Administrator` association. | Added unconnected `Finalize Discharge Plans`. |
| `7` | Copy of `57_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Submit Assignment` → `Submit Assigment`; updated its `Student` association and two outgoing `include` relationships. | `Fill in Feedback` → `Provide Grading Feedback`; updated its `Teacher` association and incoming `include`. | Removed `Single Download Homework File`, its `Teacher` association, and its use case generalization. | Added unconnected `Upload Profile Picture`. |
| `8` | Copy of `58_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Download Signed Contract` → `Download Signed Contrat`; updated its `User` association. | `Receive Contract Expiration Reminder` → `Get Contract Expiry Notification`; updated its `User` association. | Removed `Sign Contract Via Scan Code`, its `User` association, and its use case generalization. | Added unconnected `Sign Employment Contract`. |
| `9` | Copy of `59_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Review Diving Plan` → `Review Divng Plan`; updated its `Diving Master` association. | `Keep Diving Log` → `Maintain Dive Log`; updated two actor associations and two outgoing `include` relationships. | Removed `Mark Potential Risk Events` and its `Diving Master` association. | Added unconnected `Develop Travel Plan`. |
| `10` | Copy of `60_result.json` | Reordered actors, use cases, relationship entries, and target lists. | `Track Supply Orders` → `Track Suply Orders`; updated its `Remote Logistics Coordinator` association. | `Check Current Inventory Level` → `View Available Stock`; updated two actor associations and its incoming `include`. | Removed `Release Weekly Reports` and its `Scientific Expedition Team Chief` association. | Added unconnected `Process Purchase Orders`. |
