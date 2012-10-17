"""
Test toro.Lock.

Adapted from Gevent's lock_tests.py.
"""

from datetime import timedelta
import time
import unittest

from tornado import gen
from tornado.ioloop import IOLoop


import toro

from test import make_callback, BaseToroCommonTest
from test.async_test_engine import async_test_engine

# Adapted from Gevent's lock_tests.py.
class LockTests(unittest.TestCase):
    def test_acquire_release(self):
        lock = toro.Lock()
        self.assertFalse(lock.locked())
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        lock.release()
        self.assertFalse(lock.locked())

    def test_try_acquire(self):
        lock = toro.Lock()
        self.assertTrue(lock.acquire())
        self.assertFalse(lock.acquire())

    @async_test_engine()
    def test_acquire_contended(self, done):
        lock = toro.Lock()
        self.assertTrue(lock.acquire())
        N = 5

        @gen.engine
        def f(callback):
            yield gen.Task(lock.acquire)
            lock.release()
            callback()

        for i in range(N):
            f(callback=(yield gen.Callback(i)))

        lock.release()
        yield gen.WaitAll(range(N))
        done()

    def test_reacquire(self):
        # Lock needs to be released before re-acquiring.
        lock = toro.Lock()
        phase = []
        loop = IOLoop.instance()

        @gen.engine
        def f(callback):
            yield gen.Task(lock.acquire)
            self.assertTrue(lock.locked())
            phase.append(None)
            yield gen.Task(lock.acquire)
            self.assertTrue(lock.locked())
            phase.append(None)
            callback()

        f(callback=(yield gen.Callback('f')))

        while len(phase) == 0:
            yield gen.Task(loop.add_callback)

        self.assertEqual(len(phase), 1)
        lock.release()
        self.assertFalse(lock.locked())
        yield gen.Wait('f')

        self.assertEqual(len(phase), 2)


# Not adapted from Gevent's tests, written just for Toro
class LockTests2(unittest.TestCase):
    def test_str(self):
        lock = toro.Lock()
        # No errors in various states
        str(lock)
        lock.acquire()
        str(lock)
        lock.acquire(lambda x: None)
        str(lock)

    @async_test_engine()
    def test_acquire_timeout(self, done):
        lock = toro.Lock()
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.locked())
        st = time.time()
        result = yield gen.Task(lock.acquire, deadline=timedelta(seconds=.01))
        self.assertFalse(result)
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertTrue(lock.locked())
        done()

    @async_test_engine()
    def test_acquire_callback(self, done):
        lock = toro.Lock()
        history = []
        lock.acquire(make_callback('acquire1', history))
        lock.acquire(make_callback('acquire2', history))
        lock.release()
        history.append('release')
        self.assertEqual(['acquire1', 'acquire2', 'release'], history)
        done()

    def test_multi_release(self):
        lock = toro.Lock()
        lock.acquire()
        lock.release()
        self.assertRaises(RuntimeError, lock.release)


class TestLockCommon(unittest.TestCase, BaseToroCommonTest):
    def toro_object(self, io_loop=None):
        lock = toro.Lock(io_loop)
        # Start the lock acquired - BaseToroCommonTest expects wait() to await
        # notify(), which is true for events, queues, etc., so make a lock
        # that behaves the same
        lock.acquire()
        return lock

    def notify(self, toro_object, value):
        toro_object.release()

    def wait(self, toro_object, callback, deadline):
        toro_object.acquire(callback, deadline)
