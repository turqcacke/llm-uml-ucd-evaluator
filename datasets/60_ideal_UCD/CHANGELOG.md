# ReqUCD60 — Dataset Correction Log

This document lists the issues found in the original annotations and the
changes made to the local dataset. Actor and use case names are reproduced
exactly as they appear in the JSON files.

A comparison of all 60 annotations with the original dataset snapshot
identified changes in 8 files.

## 1. Example 13 — Reference to an undeclared actor

File: [11-20/13_result.json](11-20/13_result.json).

**Error:** Six associations used `User` as their source, but no actor with
that name was declared.

**Correction:** The source `User` was replaced with the declared actor
`Customer`. The target use cases of all six associations were preserved.

## 2. Example 14 — Missing use case

File: [11-20/14_result.json](11-20/14_result.json).

**Error:** `Handling Book Lending` was used as the source of an `include`
relationship but was absent from `usecases`.

**Correction:** `Handling Book Lending` was added to `usecases`, using the
exact name already referenced by the relationship.

## 3. Example 17 — Missing use case

File: [11-20/17_result.json](11-20/17_result.json).

**Error:** `Complete Maintenance Operation` was referenced by an association
and used as the source of an `include` relationship but was absent from
`usecases`.

**Correction:** `Complete Maintenance Operation` was added to `usecases`.

## 4. Example 36 — Duplicate use case

File: [31-40/36_result.json](31-40/36_result.json).

**Error:** `Create Defect Report` was declared twice.

**Correction:** The duplicate was removed, leaving one declaration.

## 5. Example 42 — Missing use case and disconnected elements

File: [41-50/42_result.json](41-50/42_result.json).

**Error:** The actors `Buyer`, `Seller`, `Administrator`, and `User`
referenced `Perform Authentication`, which was absent from `usecases`.

**Correction:** `Perform Authentication` was added to `usecases`.

**Additional change:** Three declared use cases that did not participate
in any relationship were removed:

- `Confirm Payment Success`;
- `Validate Payment Details`;
- `Notify Payment Failure`.

The absence of relationships alone does not establish that a use case is
incorrect; this entry records the removal of these elements from the local
version.

## 6. Example 47 — Duplicate use case and association

File: [41-50/47_result.json](41-50/47_result.json).

**Errors:** `Correct Homework` was declared twice, and the association
`Teaching Assistant → Correct Homework` was also recorded twice.

**Correction:** One declaration of `Correct Homework` and one association
`Teaching Assistant → Correct Homework` were retained.

## 7. Example 56 — Two missing use cases

File: [51-60/56_result.json](51-60/56_result.json).

**Error:** The actor `Pathologist` referenced `Annotate Medical Images` and
`Generate Pathology Reports`, but both were absent from `usecases`.

**Correction:** Both use cases were added to `usecases`, preserving the
names used in the existing relationships.

## 8. Example 57 — Empty use case list

File: [51-60/57_result.json](51-60/57_result.json).

**Error:** The `usecases` list was empty even though the relationships
already referenced use cases.

**Correction:** All nine names already used in the relationships were
added to `usecases`:

- `Submit Assignment`;
- `Upload Homework File`;
- `Fill In Submission Instructions`;
- `Grade Homework`;
- `Download Homework File`;
- `Batch Download Homework File`;
- `Single Download Homework File`;
- `Enter Specific Scores`;
- `Fill in Feedback`.
