"""Unit tests for ia_investing.ai.rate_limiter — TokenBucketRateLimiter."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from ia_investing.ai.rate_limiter import TokenBucketRateLimiter


@pytest.mark.unit
class TestTokenBucketRateLimiter:
    def test_init_valid(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=1000)
        assert limiter.max_rpm == 10
        assert limiter.max_tpm == 1000

    def test_init_rpm_zero_raises(self):
        with pytest.raises(ValueError, match="rpm"):
            TokenBucketRateLimiter(rpm=0, tpm=1000)

    def test_init_tpm_zero_raises(self):
        with pytest.raises(ValueError, match="tpm"):
            TokenBucketRateLimiter(rpm=10, tpm=0)

    @pytest.mark.asyncio
    async def test_acquire_within_limits(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=1000)
        wait = await limiter.acquire(estimated_tokens=100)
        assert wait == 0.0
        assert limiter.rpm_used == 1
        assert limiter.tpm_used == 100

    @pytest.mark.asyncio
    async def test_acquire_exceeds_rpm(self):
        limiter = TokenBucketRateLimiter(rpm=2, tpm=1000, window_seconds=0.1)
        await limiter.acquire(1)
        await limiter.acquire(1)
        wait = await limiter.acquire(1)
        assert wait > 0  # should wait

    @pytest.mark.asyncio
    async def test_acquire_exceeds_tpm(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=10, window_seconds=0.1)
        await limiter.acquire(10)
        wait = await limiter.acquire(1)
        assert wait > 0

    @pytest.mark.asyncio
    async def test_eviction(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=1000, window_seconds=0.05)
        await limiter.acquire(1)
        assert limiter.rpm_used == 1
        # Wait for eviction
        await asyncio.sleep(0.1)
        wait = await limiter.acquire(1)
        assert wait == 0.0
        assert limiter.rpm_used == 1  # old one evicted, new one added

    @pytest.mark.asyncio
    async def test_zero_wait_when_no_requests(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=1000)
        wait = await limiter.acquire(0)
        assert wait == 0.0

    @pytest.mark.asyncio
    async def test_properties(self):
        limiter = TokenBucketRateLimiter(rpm=10, tpm=1000)
        await limiter.acquire(50)
        await limiter.acquire(50)
        assert limiter.rpm_used == 2
        assert limiter.tpm_used == 100
