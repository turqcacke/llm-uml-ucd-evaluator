from src.services.shared.evaluation_rules import SYNTACTIC_RULES
from src.services.shared.prompts import PRAGMATIC_SYNTACTIC_EVALUATOR


def test_evaluator_prompt_contains_the_stable_rule_catalog() -> None:
    assert SYNTACTIC_RULES == {
        1: "A use case name must be a concise verb phrase describing a goal.",
        2: "An actor name must be a noun phrase naming an external role.",
        3: "A system name must be a noun phrase identifying the modeled system.",
        4: (
            "An external system name must identify an external system or "
            "service."
        ),
        5: (
            "An association may connect only an actor-like node and a use "
            "case."
        ),
        6: "An include relation may connect only two use cases.",
        7: "An extend relation may connect only two use cases.",
        8: (
            "A generalization may connect only two use cases or two "
            "actor-like nodes."
        ),
        9: "Every relation endpoint must reference a node in the diagram.",
        10: "A use case parent, when present, must reference a system node.",
    }
    for rule_id, rule in SYNTACTIC_RULES.items():
        assert f"{rule_id}: {rule}" in PRAGMATIC_SYNTACTIC_EVALUATOR
