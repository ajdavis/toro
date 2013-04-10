"""
Test toro.Event.

Adapted from Gevent's lock_tests.py.
"""

from datetime import timedelta
import time

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase

import toro
from test import assert_raises


class TestEvent(AsyncTestCase):
    def test_str(self):
        event = toro.Event()
        self.assertTrue('clear' in str(event))
        self.assertFalse('set' in str(event))
        event.set()
        self.assertFalse('clear' in str(event))
        self.assertTrue('set' in str(event))

    @gen.coroutine
    def test_event(self, n):
        e = toro.Event()
        futures = []
        for i in range(n):
            futures.append(e.wait())

        e.set()
        e.clear()
        yield futures

    # Not a test - called from test_event_1, etc.
    test_event.__test__ = False

    @gen_test
    def test_event_1(self):
        yield self.test_event(1)

    @gen_test
    def test_event_100(self):
        yield self.test_event(100)

    @gen_test
    def test_event_timeout(self):
        e = toro.Event()
        st = time.time()
        with assert_raises(toro.Timeout):
            yield e.wait(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)

        # After a timed-out waiter, normal operation works
        st = time.time()
        self.io_loop.add_timeout(st + 0.1, e.set)
        result = yield e.wait(deadline=timedelta(seconds=1))
        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertEqual(None, result)

    @gen_test
    def test_event_nowait(self):
        e = toro.Event()
        e.set()
        self.assertEqual(True, e.is_set())
        yield e.wait()
