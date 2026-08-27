from enum import IntEnum

from src.model.domain.node import NodeType
from src.model.domain.relation import NodeRelationType


class SyntacticRuleId(IntEnum):
    USECASE_NAME = 1
    ACTOR_NAME = 2
    SYSTEM_NAME = 3
    EXTERNAL_SYSTEM_NAME = 4
    ASSOCIATION_ENDPOINTS = 5
    INCLUDE_ENDPOINTS = 6
    EXTEND_ENDPOINTS = 7
    GENERALIZATION_ENDPOINTS = 8
    EXISTING_ENDPOINTS = 9
    USECASE_PARENT = 10
    INCLUDE_ACYCLIC = 11
    GENERALIZATION_ACYCLIC = 12


SYNTACTIC_RULES: dict[int, str] = {
    SyntacticRuleId.USECASE_NAME: (
        "Use case must have name identifying its behavior. "
        "Concise verb phrase recommended."
    ),
    SyntacticRuleId.ACTOR_NAME: (
        "Actor must have name. Name must identify role played by person, "
        "organization, device, or other system interacting with subject. "
        "Noun phrase recommended. System or service name valid "
        "if it names such role."
    ),
    SyntacticRuleId.SYSTEM_NAME: (
        "System node name should identify modeled subject. "
        "Noun phrase or proper name recommended."
    ),
    SyntacticRuleId.EXTERNAL_SYSTEM_NAME: (
        "External system node represents UML actor. "
        "Name must identify which system or service takes part, "
        "in its interaction role."
    ),
    SyntacticRuleId.ASSOCIATION_ENDPOINTS: (
        "In this diagram format, association must connect "
        "one actor-like node and one use case."
    ),
    SyntacticRuleId.INCLUDE_ENDPOINTS: (
        "Include relationship must connect two use cases. "
        "Direction: including use case to included use case."
    ),
    SyntacticRuleId.EXTEND_ENDPOINTS: (
        "Extend relationship must connect two use cases. "
        "Direction: extending use case to extended use case."
    ),
    SyntacticRuleId.GENERALIZATION_ENDPOINTS: (
        "In this diagram format, generalization must connect "
        "two use cases or two actor-like nodes. "
        "Direction: specific element to general element."
    ),
    SyntacticRuleId.EXISTING_ENDPOINTS: (
        "Every relationship endpoint must reference "
        "existing node in this diagram."
    ),
    SyntacticRuleId.USECASE_PARENT: (
        "Use case parent field, if present, must reference "
        "system node representing subject use case applies to."
    ),
    SyntacticRuleId.INCLUDE_ACYCLIC: (
        "Include relationships must be acyclic. "
        "Use case must not directly or indirectly include itself."
    ),
    SyntacticRuleId.GENERALIZATION_ACYCLIC: (
        "Generalization must be acyclic. "
        "Actor-like node or use case must not be own ancestor, "
        "direct or indirect."
    ),
}

NODE_RULES: dict[NodeType, list[str]] = {
    NodeType.ACTOR: [
        f"{SyntacticRuleId.ACTOR_NAME}: {SYNTACTIC_RULES[SyntacticRuleId.ACTOR_NAME]}"
    ],
    NodeType.EXTERNAL_SYSTEM: [
        f"{SyntacticRuleId.EXTERNAL_SYSTEM_NAME}: {SYNTACTIC_RULES[SyntacticRuleId.EXTERNAL_SYSTEM_NAME]}"
    ],
    NodeType.SYSTEM: [
        f"{SyntacticRuleId.SYSTEM_NAME}: {SYNTACTIC_RULES[SyntacticRuleId.SYSTEM_NAME]}"
    ],
    NodeType.USECASE: [
        f"{SyntacticRuleId.USECASE_NAME}: {SYNTACTIC_RULES[SyntacticRuleId.USECASE_NAME]}",
        f"{SyntacticRuleId.USECASE_PARENT}: {SYNTACTIC_RULES[SyntacticRuleId.USECASE_PARENT]}",
    ],
}

RELATION_RULES: dict[NodeRelationType, list[str]] = {
    NodeRelationType.ASSOCIATION: [
        f"{SyntacticRuleId.ASSOCIATION_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.ASSOCIATION_ENDPOINTS]}",
        f"{SyntacticRuleId.EXISTING_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.EXISTING_ENDPOINTS]}",
    ],
    NodeRelationType.INCLUDE: [
        f"{SyntacticRuleId.INCLUDE_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.INCLUDE_ENDPOINTS]}",
        f"{SyntacticRuleId.EXISTING_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.EXISTING_ENDPOINTS]}",
        f"{SyntacticRuleId.INCLUDE_ACYCLIC}: {SYNTACTIC_RULES[SyntacticRuleId.INCLUDE_ACYCLIC]}",
    ],
    NodeRelationType.EXTEND: [
        f"{SyntacticRuleId.EXTEND_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.EXTEND_ENDPOINTS]}",
        f"{SyntacticRuleId.EXISTING_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.EXISTING_ENDPOINTS]}",
    ],
    NodeRelationType.GENERALIZATION: [
        f"{SyntacticRuleId.GENERALIZATION_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.GENERALIZATION_ENDPOINTS]}",
        f"{SyntacticRuleId.EXISTING_ENDPOINTS}: {SYNTACTIC_RULES[SyntacticRuleId.EXISTING_ENDPOINTS]}",
        f"{SyntacticRuleId.GENERALIZATION_ACYCLIC}: {SYNTACTIC_RULES[SyntacticRuleId.GENERALIZATION_ACYCLIC]}",
    ],
}
