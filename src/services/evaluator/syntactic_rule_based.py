from collections import defaultdict
from typing import Protocol

from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.domain.evaluation import (
    ElementSyntacticEvaluation,
    SyntacticEvaluationResult,
)
from src.services.use_case import UseCase, map_use_case_exceptions


class ValidationRule[T](Protocol):
    rule_id: str
    stop_on_failure: bool = False

    def __call__(self, data: T) -> bool | None: ...


def apply_rules[T](
    data: T, rules: tuple[ValidationRule[T], ...]
) -> dict[str, bool]:
    checks = {}
    for rule in rules:
        passed = rule(data)
        if passed is None:
            continue
        checks[rule.rule_id] = passed
        if not passed and rule.stop_on_failure:
            break
    return checks


class NamePresent(ValidationRule[Node]):
    rule_id = "name_present"

    def __call__(self, data: Node) -> bool:
        return bool(data.name.strip())


class ParentExists(ValidationRule[Node]):
    rule_id = "parent_exists"

    def __init__(self, node_uids: set[str]) -> None:
        self._node_uids = node_uids

    def __call__(self, data: Node) -> bool:
        return data.parent is None or data.parent in self._node_uids


class EndpointsExist(ValidationRule[NodeRelation]):
    rule_id = "endpoints_exist"
    stop_on_failure = True

    def __init__(self, node_uids: set[str]) -> None:
        self._node_uids = node_uids

    def __call__(self, data: NodeRelation) -> bool:
        return (
            data.source in self._node_uids and data.target in self._node_uids
        )


class EndpointTypesValid(ValidationRule[NodeRelation]):
    rule_id = "endpoint_types_valid"

    def __init__(self, nodes: dict[str, Node]) -> None:
        self._nodes = nodes

    def __call__(self, data: NodeRelation) -> bool:
        source = self._nodes[data.source].type
        target = self._nodes[data.target].type
        actor_like = {NodeType.ACTOR, NodeType.EXTERNAL_SYSTEM}

        if data.type == NodeRelationType.ASSOCIATION:
            return (source in actor_like and target == NodeType.USECASE) or (
                target in actor_like and source == NodeType.USECASE
            )
        if data.type in {NodeRelationType.INCLUDE, NodeRelationType.EXTEND}:
            return source == target == NodeType.USECASE
        return (source == target == NodeType.USECASE) or (
            source in actor_like and target in actor_like
        )


def find_cycles(
    relations: list[NodeRelation],
    relation_type: NodeRelationType,
    node_uids: set[str],
) -> set[NodeRelation]:
    graph = defaultdict(list)
    relations_map = defaultdict(list)

    for relation in relations:
        if (
            relation.type != relation_type
            or relation.source not in node_uids
            or relation.target not in node_uids
        ):
            continue
        graph[relation.source].append(relation.target)
        relations_map[relation.source].append(relation)
        graph[relation.target] = graph.get(relation.target, list())

    cycles = set()
    visited = set()

    def dfs(node: str, nodes_stack: set):
        if node in visited:
            return

        visited.add(node)
        nodes_stack.add(node)

        for i, neigh in enumerate(graph[node]):
            if neigh not in nodes_stack:
                dfs(neigh, nodes_stack)
            else:
                cycles.add(relations_map[node][i])

        nodes_stack.remove(node)

    for node in graph:
        dfs(node, set())

    return cycles


class IncludeAcyclic(ValidationRule[NodeRelation]):
    rule_id = "include_acyclic"

    def __init__(self, cycles: set[NodeRelation]) -> None:
        self._cycles = cycles

    def __call__(self, data: NodeRelation) -> bool | None:
        if data.type != NodeRelationType.INCLUDE:
            return None
        return data not in self._cycles


class GeneralizationAcyclic(ValidationRule[NodeRelation]):
    rule_id = "generalization_acyclic"

    def __init__(self, cycles: set[NodeRelation]) -> None:
        self._cycles = cycles

    def __call__(self, data: NodeRelation) -> bool | None:
        if data.type != NodeRelationType.GENERALIZATION:
            return None
        return data not in self._cycles


class SyntacticDiagramEvaluator(
    UseCase[UseCaseDiagramPresentation, SyntacticEvaluationResult]
):
    @map_use_case_exceptions
    async def execute(
        self, data: UseCaseDiagramPresentation
    ) -> SyntacticEvaluationResult:
        nodes = {node.uid: node for node in data.nodes}
        node_uids = set(nodes)
        node_rules = (
            NamePresent(),
            ParentExists(node_uids),
        )
        relation_rules = (
            EndpointsExist(node_uids),
            EndpointTypesValid(nodes),
            IncludeAcyclic(
                find_cycles(
                    data.relations, NodeRelationType.INCLUDE, node_uids
                )
            ),
            GeneralizationAcyclic(
                find_cycles(
                    data.relations,
                    NodeRelationType.GENERALIZATION,
                    node_uids,
                )
            ),
        )

        return SyntacticEvaluationResult(
            nodes=[
                ElementSyntacticEvaluation(
                    uid=node.uid,
                    checks=apply_rules(node, node_rules),
                )
                for node in data.nodes
                if node.type not in {NodeType.NOTE, NodeType.OTHER}
            ],
            relations=[
                ElementSyntacticEvaluation(
                    uid=relation.uid,
                    checks=apply_rules(relation, relation_rules),
                )
                for relation in data.relations
            ],
        )
