from src.model.domain.evaluation import NamingUnderstandabilityScore
from src.services.shared.evaluation_rules import (
    NODE_RULES,
    RELATION_RULES,
    SyntacticRuleId,
)

_RULE_CATALOG = "\n".join(
    f"{kind.value}:\n" + "\n".join(f"- {rule}" for rule in rules)
    for groups in (NODE_RULES, RELATION_RULES)
    for kind, rules in groups.items()
)

PRAGMATIC_SYNTACTIC_EVALUATOR = f"""\
Evaluate syntax and naming understandability of Candidate Use Case Diagram.

# Syntactic rule allow-list

Catalog below exhaustive: report no violation outside these rules. Keep rule
IDs and texts unchanged. Only mandatory requirement violation = syntactic
error. `should` and `recommended` = naming guidance; departures affect
naming_score, not syntactic_errors.

{_RULE_CATALOG}

# Evaluation protocol

- Return whole catalog in `applied_rules`, each rule ID once.
- Return exactly one node eval per actor, external system, system, use case.
  No eval note or other node.
- Return exactly one relation eval per relation.
- `rules_applied`: exactly IDs listed for element type in catalog, in listed
  order, passed check too.
- Rule {SyntacticRuleId.USECASE_PARENT} pass when parent absent or null. No omit check.
- Rule {SyntacticRuleId.EXISTING_ENDPOINTS} count once per relation, even when both endpoint missing.
- Check rule {SyntacticRuleId.INCLUDE_ACYCLIC} on include-only directed graph, rule {SyntacticRuleId.GENERALIZATION_ACYCLIC} on
  generalization-only directed graph. Relation break cycle rule exactly when
  it sit in directed cycle: target reach source through same-type relations.
  Self-loop break rule. Mark every relation in cycle once, not node or edge
  merely lead into or out of cycle. Missing endpoint = rule {SyntacticRuleId.EXISTING_ENDPOINTS} error, not
  cycle.
- `syntactic_errors` hold only failed mandatory check from `rules_applied`,
  each ID once, ascending. Empty list = none failed.
- Treat actor and external_system node as actor-like.
- Association direction no affect whether association connect only
  actor-like node and use case.
- Score naming independent of parent, relation, cycle error:
  - {NamingUnderstandabilityScore.LOW}: name missing or its behavior, role, subject unclear.
  - {NamingUnderstandabilityScore.MEDIUM}: meaning clear, but name break mandatory naming requirement or
    departs from applicable naming guidance in the catalog.
  - {NamingUnderstandabilityScore.HIGH}: meaning clear and name meet mandatory naming requirement and
    applicable naming guidance.
- For actor, system, usecase, use naming guidance from rules {SyntacticRuleId.ACTOR_NAME}, {SyntacticRuleId.SYSTEM_NAME}, {SyntacticRuleId.USECASE_NAME}
  respectively. Name explicitly allowed by rule satisfy that guidance. For
  external_system, use rule {SyntacticRuleId.EXTERNAL_SYSTEM_NAME}; impose no extra phrase-form requirement. Rule
  {SyntacticRuleId.SYSTEM_NAME} advisory only: system node syntactic_errors always empty. Return system
  naming_score as schema require; aggregate naming metric exclude system
  node.
"""


PRAGMATIC_SYNTACTIC_EVALUATOR_REQUEST = """
# Input diagram

<input>
{diagram}
</input>
"""
