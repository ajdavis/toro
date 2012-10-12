import time
import unittest

from tornado import gen
from tornado.ioloop import IOLoop


import toro
from test.async_test_engine import async_test_engine


def make_callback(key, history):
    def callback():
        history.append(key)
    return callback


class TestCondition(unittest.TestCase):
    @async_test_engine()
    def test_notify(self, done):
        loop = IOLoop.instance()
        c = toro.Condition()
        loop.add_timeout(time.time() + .1, c.notify)
        yield gen.Task(c.wait)
        done()

    @async_test_engine()
    def test_notify_n(self, done):
        c = toro.Condition()
        history = []
        for i in range(6):
            c.wait(make_callback(i, history))

        yield gen.Task(c.notify, 3)

        # Callbacks execute in the order they were registered
        self.assertEqual(list(range(3)), history)
        yield gen.Task(c.notify, 1)
        self.assertEqual(list(range(4)), history)
        yield gen.Task(c.notify, 2)
        self.assertEqual(list(range(6)), history)
        done()

    @async_test_engine()
    def test_notify_all(self, done):
        c = toro.Condition()
        history = []
        for i in range(4):
            c.wait(make_callback(i, history))

        yield gen.Task(c.notify_all)

        # Callbacks execute in the order they were registered
        self.assertEqual(list(range(4)), history)
        done()

    @async_test_engine()
    def test_wait_timeout(self, done):
        c = toro.Condition()
        st = time.time()
        yield gen.Task(c.wait, timeout=.1)
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
        yield gen.Task(c.wait, timeout=.2)
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
        c.wait(make_callback(1, history), timeout=.1)
        c.wait(make_callback(2, history))
        c.wait(make_callback(3, history))

        # Wait for callback 1 to time out
        yield gen.Task(loop.add_timeout, st + .2)
        self.assertEqual([1], history)

        yield gen.Task(c.notify, 2)
        self.assertEqual([1, 0, 2], history)
        yield gen.Task(c.notify)
        self.assertEqual([1, 0, 2, 3], history)
        done()

    @async_test_engine()
    def test_notify_all_with_timeout(self, done):
        loop = IOLoop.instance()
        c = toro.Condition()
        st = time.time()
        history = []

        c.wait(make_callback(0, history))
        c.wait(make_callback(1, history), timeout=.1)
        c.wait(make_callback(2, history))

        # Wait for callback 1 to time out
        yield gen.Task(loop.add_timeout, st + .2)
        self.assertEqual([1], history)

        yield gen.Task(c.notify_all)
        self.assertEqual([1, 0, 2], history)
        done()
