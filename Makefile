PYTHON_PATH := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FILE ?= $(or $(word 2,$(MAKECMDGOALS)),main.py)
COMPOSE_INFRA := docker compose -f docker-compose-infra.yml

.PHONY: run-script run-api tests-run lint build-infra up-infra down-infra
run-script:
	PYTHONPATH=${PYTHON_PATH} uv run python ${FILE}

run-api:
	uv run uvicorn src.controller.api.app:app --reload

tests-run:
	PYTHONPATH=${PYTHON_PATH} uv run pytest tests

lint:
	uv run --group tools ruff check . --fix
	uv run --group tools ty check .

build-infra:
	$(COMPOSE_INFRA) build --no-cache

up-infra:
	$(COMPOSE_INFRA) up -d --build --wait

down-infra:
	$(COMPOSE_INFRA) down $(if $(V),-v)

%:
	@:
