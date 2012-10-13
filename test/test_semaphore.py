"""
Test toro.Semaphore.

Adapted from Gevent's lock_tests.py.
"""

import unittest
import time
import sys

from tornado import gen, stack_context
from tornado.ioloop import IOLoop

import toro
from test.async_test_engine import async_test_engine


class BaseSemaphoreTests(unittest.TestCase):
    semtype = None

    def test_constructor(self):
        self.assertRaises(ValueError, self.semtype, value = -1)
        self.assertRaises(ValueError, self.semtype, value = -sys.maxint)

    @async_test_engine()
    def test_acquire(self, done):
        sem = self.semtype(1)
        sem.acquire()
        sem.release()
        sem = self.semtype(2)
        sem.acquire()
        sem.acquire()
        sem.release()
        sem.release()
        done()

    # Gevent's test_acquire_destroy isn't relevant to Toro
    #def test_acquire_destroy(self):

    @async_test_engine()
    def test_acquire_contended(self, done):
        sem = self.semtype(7)
        sem.acquire()
        N = 10
        results1 = []
        results2 = []
        phase_num = 0

        @gen.engine
        def f():
            yield gen.Task(sem.acquire)
            results1.append(phase_num)
            yield gen.Task(sem.acquire)
            results2.append(phase_num)

        # Start independent tasks
        for i in range(N):
            f()

        # Let them all run until the counter reaches 0
        while len(results1) + len(results2) < 6:
            yield gen.Task(IOLoop.instance().add_callback)

        self.assertEqual(results1 + results2, [0] * 6)
        phase_num = 1

        for i in range(7):
            sem.release()

        while len(results1) + len(results2) < 13:
            yield gen.Task(IOLoop.instance().add_callback)

        self.assertEqual(sorted(results1 + results2), [0] * 6 + [1] * 7)
        phase_num = 2

        for i in range(6):
            sem.release()

        while len(results1) + len(results2) < 19:
            yield gen.Task(IOLoop.instance().add_callback)

        self.assertEqual(sorted(results1 + results2), [0] * 6 + [1] * 7 + [2] * 6)

        # The semaphore is still locked
        self.assertFalse(sem.acquire())
        # Final release, to let the last task finish
        sem.release()
        done()

    def test_try_acquire(self):
        sem = self.semtype(2)
        self.assertTrue(sem.acquire())
        self.assertTrue(sem.acquire())
        self.assertFalse(sem.acquire())
        sem.release()
        self.assertTrue(sem.acquire())

    @async_test_engine()
    def test_try_acquire_contended(self, done):
        sem = self.semtype(4)
        sem.acquire()
        results = []

        @gen.engine
        def f(callback):
            results.append(sem.acquire())
            # Allow switching
            yield gen.Task(IOLoop.instance().add_callback)
            results.append(sem.acquire())
            callback()

        # Start subtasks
        for i in range(5):
            f(callback=(yield gen.Callback(i)))

        # Join them
        yield gen.WaitAll(range(5))

        # There can be a thread switch between acquiring the semaphore and
        # appending the result, therefore results will not necessarily be
        # ordered.
        self.assertEqual(sorted(results), [False] * 7 + [True] *  3)
        done()

    @async_test_engine()
    def test_default_value(self, done):
        # The default initial value is 1.
        sem = self.semtype()
        sem.acquire()

        f_finished = [False]

        @gen.engine
        def f(callback):
            yield gen.Task(sem.acquire)

            # Allow switching
            yield gen.Task(IOLoop.instance().add_callback)
            sem.release()
            f_finished[0] = True
            callback()

        f(callback=(yield gen.Callback('f')))

        # Let f run
        yield gen.Task(IOLoop.instance().add_timeout, time.time() + .01)
        self.assertFalse(f_finished[0])
        sem.release()
        yield gen.Wait('f')
        done()

    # Gevent's test_with isn't relevant to Toro
    #def test_with(self):


class SemaphoreTests(BaseSemaphoreTests):
    """
    Tests for unbounded semaphores.
    """
    semtype = toro.Semaphore

    def test_release_unacquired(self):
        # Unbounded releases are allowed and increment the semaphore's value
        sem = self.semtype(1)
        sem.release()
        sem.acquire()
        sem.acquire()
        sem.release()


class BoundedSemaphoreTests(BaseSemaphoreTests):
    """
    Tests for bounded semaphores.
    """
    semtype = toro.BoundedSemaphore

    def test_release_unacquired(self):
        # Cannot go past the initial value
        sem = self.semtype()
        self.assertRaises(ValueError, sem.release)
        sem.acquire()
        sem.release()
        self.assertRaises(ValueError, sem.release)
