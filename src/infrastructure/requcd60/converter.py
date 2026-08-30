from pydantic import ValidationError

from src.model.domain import (
    Node,
    NodeRelation,
    NodeRelationType,
    NodeType,
    UseCaseDiagramPresentation,
)
from src.model.requcd60.result import ReqUCD60Result
from src.services.exceptions import ConversionError
from src.services.extractor.converter import BaseConverter


class ReqUCD60ToDomainConverter(
    BaseConverter[ReqUCD60Result, UseCaseDiagramPresentation]
):
    def convert(
        self, from_value: ReqUCD60Result
    ) -> UseCaseDiagramPresentation:
        system = Node(uid="system", name="Main System", type=NodeType.SYSTEM)
        actors = [
            Node(uid=f"actor-{i}", name=name, type=NodeType.ACTOR)
            for i, name in enumerate(from_value.actors)
        ]
        usecases = [
            Node(
                uid=f"usecase-{i}",
                name=name,
                type=NodeType.USECASE,
                parent=system.uid,
            )
            for i, name in enumerate(from_value.usecases)
        ]
        actor_ids = {node.name: node.uid for node in actors}
        usecase_ids = {node.name: node.uid for node in usecases}
        relationship_maps = (
            (
                from_value.association_relationships,
                actor_ids,
                usecase_ids,
                NodeRelationType.ASSOCIATION,
                False,
            ),
            (
                from_value.inclusion_relationships,
                usecase_ids,
                usecase_ids,
                NodeRelationType.INCLUDE,
                False,
            ),
            (
                from_value.extension_relationships,
                usecase_ids,
                usecase_ids,
                NodeRelationType.EXTEND,
                True,
            ),
            (
                from_value.generalization_relationships_for_usecases,
                usecase_ids,
                usecase_ids,
                NodeRelationType.GENERALIZATION,
                True,
            ),
            (
                from_value.generalization_relationships_for_actors,
                actor_ids,
                actor_ids,
                NodeRelationType.GENERALIZATION,
                True,
            ),
        )
        relations = []
        try:
            for (
                mapping,
                key_ids,
                value_ids,
                relation_type,
                values_as_sources,
            ) in relationship_maps:
                for key, values in mapping.items():
                    for value in values:
                        source, target = key_ids[key], value_ids[value]
                        if values_as_sources:
                            source, target = target, source
                        relations.append(
                            NodeRelation(
                                uid=f"relation-{len(relations)}",
                                source=source,
                                target=target,
                                type=relation_type,
                            )
                        )
            return UseCaseDiagramPresentation(
                nodes=[system, *actors, *usecases], relations=relations
            )
        except (KeyError, ValidationError) as exc:
            raise ConversionError(str(exc), original=exc) from exc
