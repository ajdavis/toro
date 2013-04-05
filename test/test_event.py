"""
Test toro.Event.

Adapted from Gevent's lock_tests.py.
"""

from datetime import timedelta
import time

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase

import toro


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
        with self.assertRaises(toro.Timeout):
            yield e.wait(deadline=timedelta(seconds=.01))

        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)

        # After a timed-out waiter, normal operation works
        self.io_loop.add_timeout(time.time() + .01, e.set)

        st = time.time()
        result = yield e.wait(deadline=timedelta(seconds=1))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(None, result)

    @gen_test
    def test_event_nowait(self):
        e = toro.Event()
        e.set()
        self.assertEqual(True, e.is_set())
        st = time.time()
        result = yield e.wait(deadline=timedelta(seconds=.01))
        duration = time.time() - st
        self.assertAlmostEqual(0, duration, places=2)
        self.assertEqual(None, result)
