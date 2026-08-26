import time
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import pytest
from pymongo import AsyncMongoClient, MongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from src.config import get_settings
from src.infrastructure.mongo import prepare_database


@pytest.fixture(scope="session")
def mongodb_uri() -> Iterator[str]:
    container = (
        DockerContainer("mongo:8.0")
        .with_command(["mongod", "--replSet", "rs0", "--bind_ip_all"])
        .with_exposed_ports(27017)
        .waiting_for(LogMessageWaitStrategy("Waiting for connections"))
    )
    with container:
        result = container.exec(
            [
                "mongosh",
                "--quiet",
                "--eval",
                "rs.initiate({_id:'rs0',members:[{_id:0,host:'localhost:27017'}]})",
            ]
        )
        if result.exit_code != 0:
            raise RuntimeError(result.output.decode())

        uri = (
            f"mongodb://{container.get_container_host_ip()}:"
            f"{container.get_exposed_port(27017)}/?directConnection=true"
        )
        client = MongoClient(uri, serverSelectionTimeoutMS=500)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                try:
                    if client.admin.command("hello").get("isWritablePrimary"):
                        break
                except PyMongoError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Test MongoDB did not become PRIMARY.")
        finally:
            client.close()
        yield uri


@pytest.fixture
def mongo_test_uri(
    mongodb_uri: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    parts = urlsplit(mongodb_uri)
    uri = urlunsplit(
        parts._replace(path=f"/test_llm_uml_evaluator_{uuid4().hex}")
    )
    monkeypatch.setenv("MONGODB_URI", uri)
    get_settings.cache_clear()
    try:
        yield uri
    finally:
        try:
            with MongoClient(uri) as client:
                client.drop_database(client.get_default_database())
        finally:
            get_settings.cache_clear()


@pytest.fixture
async def mongo_database(
    mongo_test_uri: str,
) -> AsyncIterator[AsyncDatabase[Any]]:
    client = AsyncMongoClient(mongo_test_uri)
    database = client.get_default_database()
    await prepare_database(database)
    try:
        yield database
    finally:
        await client.close()
