from pymongo.asynchronous.database import AsyncDatabase

from .models import MONGO_MODELS

DRAFT_COLLECTION_NAMES = (
    "usecase_digarm_presentations",
    "metrics_presentations",
)


async def prepare_database(database: AsyncDatabase) -> None:
    names = set(await database.list_collection_names())
    for name in set(DRAFT_COLLECTION_NAMES) & names:
        if await database[name].find_one() is not None:
            raise RuntimeError(
                f"Legacy collection {name!r} contains data; migration required."
            )
    for model in MONGO_MODELS:
        await model.ensure_indexes(database)
