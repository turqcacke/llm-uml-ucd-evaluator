from pydantic import BaseModel


class ReqUCD60Result(BaseModel):
    actors: list[str]
    usecases: list[str]
    association_relationships: dict[str, list[str]]
    inclusion_relationships: dict[str, list[str]]
    extension_relationships: dict[str, list[str]]
    generalization_relationships_for_usecases: dict[str, list[str]]
    generalization_relationships_for_actors: dict[str, list[str]]
