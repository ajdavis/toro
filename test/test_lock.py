"""
Test toro.Lock.

Adapted from Gevent's lock_tests.py.
"""

from datetime import timedelta
import time

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase


import toro
from test import make_callback, assert_raises, ContextManagerTestsMixin


# Adapted from Gevent's lock_tests.py.
class LockTests(AsyncTestCase):
    def test_acquire_release(self):
        lock = toro.Lock()
        self.assertFalse(lock.locked())
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        lock.release()
        self.assertFalse(lock.locked())

    @gen_test
    def test_acquire_contended(self):
        lock = toro.Lock()
        self.assertTrue(lock.acquire())
        N = 5

        @gen.coroutine
        def f():
            yield lock.acquire()
            lock.release()

        futures = [f() for _ in range(N)]
        lock.release()
        yield futures

    @gen_test
    def test_reacquire(self):
        # Lock needs to be released before re-acquiring.
        lock = toro.Lock()
        phase = []

        @gen.coroutine
        def f():
            yield lock.acquire()
            self.assertTrue(lock.locked())
            phase.append(None)
            yield lock.acquire()
            self.assertTrue(lock.locked())
            phase.append(None)

        future = f()

        while len(phase) == 0:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(len(phase), 1)
        lock.release()
        yield future
        self.assertEqual(len(phase), 2)


# Not adapted from Gevent's tests, written just for Toro
class LockTests2(AsyncTestCase):
    def test_str(self):
        lock = toro.Lock()
        # No errors in various states
        str(lock)
        lock.acquire()
        str(lock)

    @gen_test
    def test_acquire_timeout(self):
        lock = toro.Lock()
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        st = time.time()

        with assert_raises(toro.Timeout):
            yield lock.acquire(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertTrue(lock.locked())

    @gen_test
    def test_acquire_callback(self):
        lock = toro.Lock()
        history = []
        lock.acquire().add_done_callback(make_callback('acquire1', history))
        lock.acquire().add_done_callback(make_callback('acquire2', history))
        lock.release()
        history.append('release')
        self.assertEqual(['acquire1', 'acquire2', 'release'], history)

    def test_multi_release(self):
        lock = toro.Lock()
        lock.acquire()
        lock.release()
        self.assertRaises(RuntimeError, lock.release)


class LockContextManagerTest(ContextManagerTestsMixin, AsyncTestCase):

    toro_class = toro.Lock
