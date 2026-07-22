"""Unit tests for rate limiter."""
import pytest
import time
from app.core.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_within_limit(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("test") is True

    def test_blocks_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("test")
        assert limiter.is_allowed("test") is False

    def test_different_keys(self):
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("a")
        limiter.is_allowed("a")
        assert limiter.is_allowed("a") is False
        assert limiter.is_allowed("b") is True

    def test_remaining_count(self):
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.get_remaining("test") == 5
        limiter.is_allowed("test")
        assert limiter.get_remaining("test") == 4

    def test_window_expiry(self):
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        limiter.is_allowed("test")
        limiter.is_allowed("test")
        assert limiter.is_allowed("test") is False
        time.sleep(1.1)
        assert limiter.is_allowed("test") is True
