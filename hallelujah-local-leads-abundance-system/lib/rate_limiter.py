"""
Rate Limiter for API Calls

Simple but effective rate limiting: delay between every call,
plus a longer pause every N calls to avoid burst rate limits.

Production-tested values:
- 2s between calls works for Exa, Tavily, Perplexity
- 15s pause every 10 calls prevents 429s on sustained runs
- Adjust these if you're hitting rate limits or want to go faster

Usage:
    from lib.rate_limiter import RateLimiter

    limiter = RateLimiter(delay=2.0, pause_every=10, pause_duration=15.0)

    for item in items:
        limiter.wait()
        result = api_call(item)
"""

import time


class RateLimiter:
    """Rate limiter with periodic pauses.

    Args:
        delay: Seconds between each call (default 2.0)
        pause_every: Pause every N calls (default 10)
        pause_duration: How long to pause in seconds (default 15.0)
    """

    def __init__(self, delay: float = 2.0, pause_every: int = 10,
                 pause_duration: float = 15.0):
        self.delay = delay
        self.pause_every = pause_every
        self.pause_duration = pause_duration
        self._count = 0

    def wait(self):
        """Wait the appropriate amount of time before the next API call."""
        self._count += 1
        time.sleep(self.delay)

        if self.pause_every > 0 and self._count % self.pause_every == 0:
            print(f"    [RATE LIMIT] Pausing {self.pause_duration}s after {self._count} API calls...")
            time.sleep(self.pause_duration)

    @property
    def call_count(self) -> int:
        return self._count


# Convenience: module-level rate limiter with default settings
_default_limiter = RateLimiter()


def rate_limited_delay():
    """Simple rate-limited delay using default settings (2s + 15s every 10)."""
    _default_limiter.wait()
