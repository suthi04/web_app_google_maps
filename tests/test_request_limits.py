import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from request_limits import ConcurrencyGate, SlidingWindowRateLimiter


class TestSlidingWindowRateLimiter(unittest.TestCase):
    def test_zero_limit_disables_limiter(self):
        limiter = SlidingWindowRateLimiter(0, 60)
        for _ in range(100):
            self.assertEqual(limiter.consume("client", now=10), (True, 0))

    def test_blocks_after_limit_and_returns_retry_after(self):
        limiter = SlidingWindowRateLimiter(2, 60)
        self.assertEqual(limiter.consume("client", now=100), (True, 0))
        self.assertEqual(limiter.consume("client", now=110), (True, 0))
        self.assertEqual(limiter.consume("client", now=120), (False, 40))

    def test_old_events_expire_from_sliding_window(self):
        limiter = SlidingWindowRateLimiter(1, 10)
        self.assertEqual(limiter.consume("client", now=100), (True, 0))
        self.assertEqual(limiter.consume("client", now=109), (False, 1))
        self.assertEqual(limiter.consume("client", now=110), (True, 0))

    def test_clients_have_independent_quotas(self):
        limiter = SlidingWindowRateLimiter(1, 60)
        self.assertEqual(limiter.consume("a", now=100), (True, 0))
        self.assertEqual(limiter.consume("b", now=100), (True, 0))
        self.assertEqual(limiter.consume("a", now=101), (False, 59))


class TestConcurrencyGate(unittest.TestCase):
    def test_snapshot_tracks_capacity_without_mutating_it(self):
        gate = ConcurrencyGate(2)
        self.assertEqual(
            gate.snapshot(), {"capacity": 2, "inflight": 0, "available": 2}
        )
        self.assertTrue(gate.try_acquire())
        self.assertEqual(gate.snapshot()["inflight"], 1)
        self.assertEqual(gate.snapshot()["available"], 1)
        gate.release()

    def test_rejects_when_capacity_is_in_use(self):
        gate = ConcurrencyGate(1)
        self.assertTrue(gate.try_acquire())
        self.assertFalse(gate.try_acquire())
        gate.release()

    def test_release_makes_capacity_available_again(self):
        gate = ConcurrencyGate(1)
        self.assertTrue(gate.try_acquire())
        gate.release()
        self.assertTrue(gate.try_acquire())
        gate.release()


if __name__ == "__main__":
    unittest.main()
