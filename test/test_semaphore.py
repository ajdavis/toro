"""
Test toro.Semaphore.

Adapted from Gevent's lock_tests.py and test__semaphore.py.
"""

from datetime import timedelta
import time
import sys

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase

import toro
from test import make_callback, assert_raises, ContextManagerTestsMixin


# Adapted from Gevent's lock_tests.py
class BaseSemaphoreTests(AsyncTestCase):
    semtype = None

    def test_constructor(self):
        self.assertRaises(ValueError, self.semtype, value = -1)
        self.assertRaises(ValueError, self.semtype, value = -sys.maxint)

    def test_str(self):
        q = self.semtype(5)
        self.assertTrue(self.semtype.__name__ in str(q))
        self.assertTrue('counter=5' in str(q))

    @gen_test
    def test_acquire(self):
        sem = self.semtype(1)
        self.assertFalse(sem.locked())
        result = sem.acquire()
        self.assertTrue(result)
        self.assertTrue(sem.locked())
        # Wait for release()
        future = sem.wait()
        sem.release()
        yield future

        # Now wait() is instant
        yield sem.wait()

        sem = self.semtype(2)
        sem.acquire()
        sem.acquire()
        sem.release()
        sem.release()

    @gen_test
    def test_acquire_contended(self):
        sem = self.semtype(7)
        sem.acquire()
        N = 10
        results1 = []
        results2 = []
        phase_num = 0

        @gen.coroutine
        def f():
            yield sem.acquire()
            results1.append(phase_num)
            yield sem.acquire()
            results2.append(phase_num)

        # Start independent tasks
        for i in range(N):
            f()

        # Let them all run until the counter reaches 0
        while len(results1) + len(results2) < 6:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(results1 + results2, [0] * 6)
        phase_num = 1

        for i in range(7):
            sem.release()

        while len(results1) + len(results2) < 13:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(sorted(results1 + results2), [0] * 6 + [1] * 7)
        phase_num = 2

        for i in range(6):
            sem.release()

        while len(results1) + len(results2) < 19:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(sorted(results1 + results2), [0] * 6 + [1] * 7 + [2] * 6)

        # The semaphore is still locked
        self.assertTrue(sem.locked())
        with assert_raises(toro.Timeout):
            yield sem.acquire(deadline=timedelta(seconds=0.1))

        # Final release, to let the last task finish
        sem.release()

    @gen_test
    def test_try_acquire(self):
        sem = self.semtype(2)
        yield sem.acquire()
        yield sem.acquire()
        with assert_raises(toro.Timeout):
            yield sem.acquire(deadline=timedelta(seconds=0.1))

        sem.release()
        yield sem.acquire()

    @gen_test
    def test_default_value(self):
        # The default initial value is 1.
        sem = self.semtype()
        sem.acquire()

        f_finished = [False]

        @gen.coroutine
        def f():
            yield sem.acquire()

            # Allow switching
            yield gen.Task(self.io_loop.add_callback)
            sem.release()
            f_finished[0] = True

        future = f()

        # Let f run
        yield gen.Task(self.io_loop.add_timeout, time.time() + 0.01)
        self.assertFalse(f_finished[0])
        sem.release()
        yield future

    @gen_test
    def test_wait(self):
        sem = self.semtype()
        sem.acquire()
        with assert_raises(toro.Timeout):
            yield sem.wait(deadline=timedelta(seconds=0.1))
        sem.release()


# Not a test - called from SemaphoreTests and BoundedSemaphoreTests
BaseSemaphoreTests.__test__ = False


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

SemaphoreTests.__test__ = True


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

BoundedSemaphoreTests.__test__ = True


# Adapted from Gevent's test__semaphore.py
class TestTimeoutAcquire(AsyncTestCase):
    @gen_test
    def test_timeout_acquire(self):
        s = toro.Semaphore(value=0)
        with assert_raises(toro.Timeout):
            yield s.acquire(deadline=timedelta(seconds=0.01))

    @gen_test
    def test_release_twice(self):
        s = toro.Semaphore()
        result = []
        s.acquire().add_done_callback(lambda x: result.append('a'))
        s.release()
        s.acquire().add_done_callback(lambda x: result.append('b'))
        s.release()
        yield gen.Task(self.io_loop.add_timeout, time.time() + 0.01)
        self.assertEqual(result, ['a', 'b'])


# Not adapted from Gevent's tests, specific to Toro
class SemaphoreTests2(AsyncTestCase):
    def test_repr(self):
        # No exceptions
        str(toro.Semaphore())
        repr(toro.Semaphore())

    @gen_test
    def test_acquire_callback(self):
        # Test that callbacks passed to acquire() run immediately after
        # release(), and that wait() callbacks aren't run until a release()
        # with no waiters on acquire().
        sem = toro.Semaphore(0)
        history = []
        sem.acquire().add_done_callback(make_callback('acquire1', history))
        sem.acquire().add_done_callback(make_callback('acquire2', history))

        def wait_callback(name):
            def cb(_):
                self.assertFalse(sem.locked())
                history.append(name)
            return cb

        sem.wait().add_done_callback(wait_callback('wait1'))
        sem.wait().add_done_callback(wait_callback('wait2'))
        sem.release()
        history.append('release1')
        sem.release()
        history.append('release2')
        sem.release()
        history.append('release3')
        self.assertEqual([
            # First release wakes first acquire
            'acquire1', 'release1',

            # Second release wakes second acquire
            'acquire2', 'release2',

            # Third release wakes all waits
            'wait1', 'wait2', 'release3'
        ], history)


class SemaphoreContextManagerTest(ContextManagerTestsMixin, AsyncTestCase):

    toro_class = toro.Semaphore
