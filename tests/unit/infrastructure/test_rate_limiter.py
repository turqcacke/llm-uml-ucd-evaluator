import pytest

from src.infrastructure import rate_limiter


@pytest.mark.anyio
async def test_sliding_window_delays_requests_over_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = 0.0
    delays: list[float] = []

    def monotonic() -> float:
        return now

    async def sleep(delay: float) -> None:
        nonlocal now
        delays.append(delay)
        now += delay

    monkeypatch.setattr(rate_limiter.time, "monotonic", monotonic)
    monkeypatch.setattr(rate_limiter.asyncio, "sleep", sleep)
    limiter = rate_limiter.SlidingWindowRateLimiter(2, 1.0)

    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()

    assert delays == [1.0]


@pytest.mark.parametrize(
    ("max_requests", "period"),
    [(0, 1.0), (1, 0.0), (-1, 1.0), (1, -1.0)],
)
def test_sliding_window_rejects_non_positive_configuration(
    max_requests: int,
    period: float,
) -> None:
    with pytest.raises(ValueError, match="must be positive"):
        rate_limiter.SlidingWindowRateLimiter(max_requests, period)
