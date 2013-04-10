"""
Test toro.Condition.
"""

from datetime import timedelta
import time

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase


import toro
from test import make_callback, assert_raises


class TestCondition(AsyncTestCase):
    def test_str(self):
        c = toro.Condition()
        self.assertTrue('Condition' in str(c))
        self.assertFalse('waiters' in str(c))
        c.wait()
        self.assertTrue('waiters' in str(c))

    @gen_test
    def test_notify(self):
        c = toro.Condition(self.io_loop)
        self.io_loop.add_timeout(time.time() + 0.1, c.notify)
        yield c.wait()

    def test_notify_1(self):
        c = toro.Condition()
        history = []
        c.wait().add_done_callback(make_callback('wait1', history))
        c.wait().add_done_callback(make_callback('wait2', history))
        c.notify(1)
        history.append('notify1')
        c.notify(1)
        history.append('notify2')
        self.assertEqual(['wait1', 'notify1', 'wait2', 'notify2'], history)

    def test_notify_n(self):
        c = toro.Condition()
        history = []
        for i in range(6):
            c.wait().add_done_callback(make_callback(i, history))

        c.notify(3)

        # Callbacks execute in the order they were registered
        self.assertEqual(list(range(3)), history)
        c.notify(1)
        self.assertEqual(list(range(4)), history)
        c.notify(2)
        self.assertEqual(list(range(6)), history)

    def test_notify_all(self):
        c = toro.Condition()
        history = []
        for i in range(4):
            c.wait().add_done_callback(make_callback(i, history))

        c.notify_all()
        history.append('notify_all')

        # Callbacks execute in the order they were registered
        self.assertEqual(
            list(range(4)) + ['notify_all'],
            history)

    @gen_test
    def test_wait_timeout(self):
        c = toro.Condition(self.io_loop)
        st = time.time()
        with assert_raises(toro.Timeout):
            yield c.wait(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)

    @gen_test
    def test_wait_timeout_preempted(self):
        c = toro.Condition(self.io_loop)
        st = time.time()

        # This fires before the wait times out
        self.io_loop.add_timeout(st + .1, c.notify)
        yield c.wait(deadline=timedelta(seconds=0.2))
        duration = time.time() - st

        # Verify we were awakened by c.notify(), not by timeout
        self.assertAlmostEqual(0.1, duration, places=1)

    @gen_test
    def test_notify_n_with_timeout(self):
        # Register callbacks 0, 1, 2, and 3. Callback 1 has a timeout.
        # Wait for that timeout to expire, then do notify(2) and make
        # sure everyone runs. Verifies that a timed-out callback does
        # not count against the 'n' argument to notify().
        c = toro.Condition(self.io_loop)
        st = time.time()
        history = []

        c.wait().add_done_callback(make_callback(0, history))
        c.wait(deadline=timedelta(seconds=.1)).add_done_callback(
            make_callback(1, history))

        c.wait().add_done_callback(make_callback(2, history))
        c.wait().add_done_callback(make_callback(3, history))

        # Wait for callback 1 to time out
        yield gen.Task(self.io_loop.add_timeout, st + 0.2)
        self.assertEqual(['Timeout'], history)

        c.notify(2)
        self.assertEqual(['Timeout', 0, 2], history)
        c.notify()
        self.assertEqual(['Timeout', 0, 2, 3], history)

    @gen_test
    def test_notify_all_with_timeout(self):
        c = toro.Condition(self.io_loop)
        st = time.time()
        history = []

        c.wait().add_done_callback(make_callback(0, history))
        c.wait(deadline=timedelta(seconds=.1)).add_done_callback(
            make_callback(1, history))

        c.wait().add_done_callback(make_callback(2, history))

        # Wait for callback 1 to time out
        yield gen.Task(self.io_loop.add_timeout, st + 0.2)
        self.assertEqual(['Timeout'], history)

        c.notify_all()
        self.assertEqual(['Timeout', 0, 2], history)
