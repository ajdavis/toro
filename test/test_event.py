"""
Test toro.Event.

Adapted from Gevent's lock_tests.py.
"""

from datetime import timedelta
import unittest
import time

from tornado import gen
from tornado.ioloop import IOLoop

import toro

from test import make_callback, BaseToroCommonTest
from test.async_test_engine import async_test_engine


class TestEvent(unittest.TestCase):
    def test_str(self):
        event = toro.Event()
        self.assertTrue('clear' in str(event))
        self.assertFalse('set' in str(event))
        event.set()
        self.assertFalse('clear' in str(event))
        self.assertTrue('set' in str(event))

    @gen.engine
    def test_event(self, n, callback):
        e = toro.Event()
        for i in range(n):
            e.wait(callback=(yield gen.Callback(i)))

        e.set()
        e.clear()
        yield gen.WaitAll(range(n))
        callback()

    # Not a test - called from test_event_1, etc.
    test_event.__test__ = False

    @async_test_engine()
    def test_event_1(self, done):
        yield gen.Task(self.test_event, 1)
        done()

    @async_test_engine()
    def test_event_100(self, done):
        yield gen.Task(self.test_event, 100)
        done()

    @async_test_engine()
    def test_event_10000(self, done):
        yield gen.Task(self.test_event, 10000)
        done()

    @async_test_engine()
    def test_get_callback(self, done):
        # Test that a callback passed to set() runs after callbacks registered
        # with wait()
        e = toro.Event()
        history = []
        e.wait(make_callback('wait1', history))
        e.wait(make_callback('wait2', history))
        e.set()
        history.append('set')
        self.assertEqual(['wait1', 'wait2', 'set'], history)
        done()

    @async_test_engine()
    def test_event_timeout(self, done):
        e = toro.Event()

        st = time.time()
        result = yield gen.Task(e.wait, deadline=timedelta(seconds=.01))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(None, result)

        # After a timed-out waiter, normal operation works
        IOLoop.instance().add_timeout(
            time.time() + .01, e.set)

        st = time.time()
        result = yield gen.Task(e.wait, deadline=timedelta(seconds=1))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(None, result)
        done()

    @async_test_engine()
    def test_event_nowait(self, done):
        e = toro.Event()
        e.set()
        self.assertEqual(True, e.is_set())
        st = time.time()
        result = yield gen.Task(e.wait, deadline=timedelta(seconds=.01))
        duration = time.time() - st
        self.assertAlmostEqual(0, duration, places=2)
        self.assertEqual(None, result)
        done()


class TestEventCommon(unittest.TestCase, BaseToroCommonTest):
    def toro_object(self, io_loop=None):
        return toro.Event(io_loop)

    def notify(self, toro_object, value):
        toro_object.set()

    def wait(self, toro_object, callback, deadline):
        toro_object.wait(callback, deadline)

