PYTHON_PATH := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FILE ?= $(or $(word 2,$(MAKECMDGOALS)),main.py)

.PHONY: run-script tests-run lint
run-script:
	PYTHONPATH=${PYTHON_PATH} uv run python ${FILE}

tests-run:
	PYTHONPATH=${PYTHON_PATH} uv run pytest tests

lint:
	ruff check .
	ty check .

%:
	@:
