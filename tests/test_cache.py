import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qd766.backend.cache import SingleFlightTTLCache


class CacheTest(unittest.TestCase):
    def test_capacity_eviction_keeps_correct_values(self):
        cache = SingleFlightTTLCache(60, max_entries=3)
        for key in range(100):
            self.assertEqual(cache.get_or_load(key, lambda key=key: key)[0], key)
            self.assertLessEqual(cache.stats().entries, 3)
        self.assertEqual(cache.get_or_load(99, lambda: -1), (99, 'hit'))
        self.assertEqual(cache.get_or_load(0, lambda: 0), (0, 'miss'))
        self.assertLessEqual(cache.stats().entries, 3)

    def test_bounded_cache_prunes_expired_entries_on_new_key(self):
        current = [10.0]
        cache = SingleFlightTTLCache(5, clock=lambda: current[0], max_entries=64)
        for key in range(10):
            cache.get_or_load(key, lambda: 'old')
        current[0] = 16.0
        cache.get_or_load('new', lambda: 'new')
        self.assertEqual(list(cache._entries), ['new'])

    def test_invalid_capacity_and_default_compatibility(self):
        for invalid in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                SingleFlightTTLCache(60, max_entries=invalid)
        self.assertIsNone(SingleFlightTTLCache(60).max_entries)

    def test_bounded_concurrent_reads_still_share_loader(self):
        cache = SingleFlightTTLCache(60, max_entries=64)
        entered, release = threading.Event(), threading.Event()
        calls, results = [], []
        def loader():
            calls.append(1)
            entered.set()
            release.wait(2)
            return 'value'
        threads = [threading.Thread(target=lambda: results.append(cache.get_or_load('same', loader))) for _ in range(5)]
        for thread in threads:thread.start()
        self.assertTrue(entered.wait(1))
        release.set()
        for thread in threads:thread.join(2)
        self.assertEqual(calls, [1])
        self.assertEqual(len(results), 5)
        self.assertTrue(all(value=='value' for value, _ in results))
        self.assertEqual(cache.stats().entries, 1)

    def test_ttl_hit_and_expiry(self):
        current = [10.0]
        cache = SingleFlightTTLCache(5, clock=lambda: current[0])
        calls = []
        first, first_state = cache.get_or_load("key", lambda: calls.append(1) or "a")
        second, second_state = cache.get_or_load("key", lambda: calls.append(2) or "b")
        current[0] = 16.0
        third, third_state = cache.get_or_load("key", lambda: calls.append(3) or "c")
        self.assertEqual((first, first_state), ("a", "miss"))
        self.assertEqual((second, second_state), ("a", "hit"))
        self.assertEqual((third, third_state), ("c", "miss"))
        self.assertEqual(calls, [1, 3])

    def test_concurrent_requests_share_one_loader(self):
        cache = SingleFlightTTLCache(60)
        entered = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def loader():
            calls.append(1)
            entered.set()
            release.wait(2)
            return "value"

        threads = [
            threading.Thread(target=lambda: results.append(cache.get_or_load("key", loader)))
            for _ in range(5)
        ]
        for thread in threads:
            thread.start()
        self.assertTrue(entered.wait(1))
        release.set()
        for thread in threads:
            thread.join(2)
        self.assertEqual(calls, [1])
        self.assertEqual(len(results), 5)
        self.assertEqual({value for value, state in results}, {"value"})
        self.assertEqual({state for value, state in results}, {"miss", "shared"})
        self.assertEqual(cache.stats().waits, 4)


if __name__ == "__main__":
    unittest.main()
