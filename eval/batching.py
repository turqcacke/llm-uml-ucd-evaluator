import argparse
import asyncio
from collections.abc import Awaitable, Callable, Sequence
from itertools import batched
from typing import TypeVar

from src.infrastructure.rate_limiter import (
    BaseRateLimiter,
    SlidingWindowRateLimiter,
)

T = TypeVar("T")

DEFAULT_BATCH_SIZE = 3
DEFAULT_REQUESTS_PER_MINUTE = 10


def add_batch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=DEFAULT_BATCH_SIZE,
        help="concurrent samples per batch (default: 3)",
    )
    parser.add_argument(
        "--requests-per-minute",
        type=_positive_int,
        default=DEFAULT_REQUESTS_PER_MINUTE,
        help="maximum sample starts per minute (default: 10)",
    )


async def run_in_batches(
    steps: Sequence[T],
    *,
    start_iteration: int,
    batch_size: int,
    requests_per_minute: int,
    before_batch: Callable[[int], Awaitable[None]],
    worker: Callable[[int, T], Awaitable[None]],
) -> None:
    limiter = SlidingWindowRateLimiter(requests_per_minute, 60.0)
    indexed_steps = enumerate(
        steps[start_iteration - 1 :], start=start_iteration
    )
    for batch in batched(indexed_steps, batch_size):
        await before_batch(batch[0][0])
        await asyncio.gather(
            *(
                _run_limited(limiter, worker, iteration, step)
                for iteration, step in batch
            )
        )


async def _run_limited(
    limiter: BaseRateLimiter,
    worker: Callable[[int, T], Awaitable[None]],
    iteration: int,
    step: T,
) -> None:
    await limiter.acquire()
    await worker(iteration, step)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed
