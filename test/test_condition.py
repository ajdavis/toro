"""
Test toro.Condition.
"""

from datetime import timedelta
import time
import unittest

from tornado import gen
from tornado.ioloop import IOLoop

import toro

from test import make_callback, BaseToroCommonTest
from test.async_test_engine import async_test_engine


class TestCondition(unittest.TestCase):
    def test_str(self):
        c = toro.Condition()
        self.assertTrue('Condition' in str(c))
        self.assertFalse('waiters' in str(c))
        c.wait(lambda: None)
        self.assertTrue('waiters' in str(c))

    @async_test_engine()
    def test_notify(self, done):
        loop = IOLoop.instance()
        c = toro.Condition()
        loop.add_timeout(time.time() + .1, c.notify)
        yield gen.Task(c.wait)
        done()

    @async_test_engine()
    def test_notify_1(self, done):
        c = toro.Condition()
        history = []
        c.wait(make_callback('wait1', history))
        c.wait(make_callback('wait2', history))
        c.notify(1)
        history.append('notify1')
        c.notify(1)
        history.append('notify2')
        self.assertEqual(['wait1', 'notify1', 'wait2', 'notify2'], history)
        done()

    @async_test_engine()
    def test_notify_n(self, done):
        c = toro.Condition()
        history = []
        for i in range(6):
            c.wait(make_callback(i, history))

        c.notify(3)

        # Callbacks execute in the order they were registered
        self.assertEqual(list(range(3)), history)
        c.notify(1)
        self.assertEqual(list(range(4)), history)
        c.notify(2)
        self.assertEqual(list(range(6)), history)
        done()

    @async_test_engine()
    def test_notify_all(self, done):
        c = toro.Condition()
        history = []
        for i in range(4):
            c.wait(make_callback(i, history))

        c.notify_all()
        history.append('notify_all')

        # Callbacks execute in the order they were registered
        self.assertEqual(
            list(range(4)) + ['notify_all'],
            history)
        done()

    @async_test_engine()
    def test_wait_timeout(self, done):
        c = toro.Condition()
        st = time.time()
        yield gen.Task(c.wait, deadline=timedelta(seconds=.1))
        duration = time.time() - st
        self.assertAlmostEqual(.1, duration, places=2)
        done()

    @async_test_engine()
    def test_wait_timeout_preempted(self, done):
        loop = IOLoop.instance()
        c = toro.Condition()
        st = time.time()

        # This fires before the wait times out
        loop.add_timeout(st + .1, c.notify)
        yield gen.Task(c.wait, deadline=timedelta(seconds=.2))
        duration = time.time() - st

        # Verify we were awakened by c.notify(), not by timeout
        self.assertAlmostEqual(.1, duration, places=2)
        done()

    @async_test_engine()
    def test_notify_n_with_timeout(self, done):
        # Register callbacks 0, 1, 2, and 3. Callback 1 has a timeout.
        # Wait for that timeout to expire, then do notify(2) and make
        # sure everyone runs. Verifies that a timed-out callback does
        # not count against the 'n' argument to notify().
        loop = IOLoop.instance()
        c = toro.Condition()
        st = time.time()
        history = []

        c.wait(make_callback(0, history))
        c.wait(make_callback(1, history), deadline=timedelta(seconds=.1))
        c.wait(make_callback(2, history))
        c.wait(make_callback(3, history))

        # Wait for callback 1 to time out
        yield gen.Task(loop.add_timeout, st + .2)
        self.assertEqual([1], history)

        c.notify(2)
        self.assertEqual([1, 0, 2], history)
        c.notify()
        self.assertEqual([1, 0, 2, 3], history)
        done()

    @async_test_engine()
    def test_notify_all_with_timeout(self, done):
        loop = IOLoop.instance()
        c = toro.Condition()
        st = time.time()
        history = []

        c.wait(make_callback(0, history))
        c.wait(make_callback(1, history), deadline=timedelta(seconds=.1))
        c.wait(make_callback(2, history))

        # Wait for callback 1 to time out
        yield gen.Task(loop.add_timeout, st + .2)
        self.assertEqual([1], history)

        c.notify_all()
        self.assertEqual([1, 0, 2], history)
        done()


class TestConditionCommon(unittest.TestCase, BaseToroCommonTest):
    def toro_object(self, io_loop=None):
        return toro.Condition(io_loop)

    def notify(self, toro_object, value):
        toro_object.notify()

    def wait(self, toro_object, callback, deadline):
        toro_object.wait(callback, deadline)

