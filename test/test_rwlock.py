"""
Test toro.RWLock.
"""

from functools import partial

from random import randint

from datetime import timedelta
import time

from tornado import gen
from tornado.testing import gen_test, AsyncTestCase

import toro
from test import make_callback, assert_raises, ContextManagerTestsMixin


# Adapted from toro.test_lock.py
class RWLockReadTests(AsyncTestCase):
    def test_acquire_release(self):
        lock = toro.RWLock(max_readers=1)
        self.assertFalse(lock.locked())
        self.assertTrue(lock.acquire_read().done())
        self.assertTrue(lock.locked())
        lock.release_read()
        self.assertFalse(lock.locked())

    def test_release_unlocked(self):
        lock = toro.RWLock(max_readers=1)

        with assert_raises(RuntimeError):
            lock.release_read()

    @gen_test
    def test_acquire_contended(self):
        lock = toro.RWLock(max_readers=1)
        self.assertTrue(lock.acquire_read().done())
        N = 5

        @gen.coroutine
        def f():
            yield lock.acquire_read()
            lock.release_read()

        futures = [f() for _ in range(N)]
        lock.release_read()
        yield futures

    @gen_test
    def test_reacquire(self):
        # Lock needs to be released before re-acquiring.
        lock = toro.RWLock(max_readers=1)
        phase = []

        @gen.coroutine
        def f():
            yield lock.acquire_read()
            self.assertTrue(lock.locked())
            phase.append(None)

            yield lock.acquire_read()
            self.assertTrue(lock.locked())
            phase.append(None)

        future = f()

        while len(phase) == 0:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(len(phase), 1)
        lock.release_read()
        yield future
        self.assertEqual(len(phase), 2)


# Adapted from toro.test_lock.py
class RWLockWriteTests(AsyncTestCase):
    @gen_test
    def test_acquire_release(self):
        lock = toro.RWLock(max_readers=10)
        self.assertFalse(lock.locked())
        yield lock.acquire_write()
        self.assertTrue(lock.locked())
        lock.release_write()
        self.assertFalse(lock.locked())

    @gen_test
    def test_acquire_contended(self):
        lock = toro.RWLock(max_readers=10)
        yield lock.acquire_write()
        N = 5

        @gen.coroutine
        def f():
            yield lock.acquire_write()
            lock.release_write()

        futures = [f() for _ in range(N)]
        lock.release_write()
        yield futures

    @gen_test
    def test_reacquire(self):
        # Lock needs to be released before re-acquiring.
        lock = toro.RWLock(max_readers=10)
        phase = []

        @gen.coroutine
        def f():
            yield lock.acquire_write()
            self.assertTrue(lock.locked())
            phase.append(None)

            yield lock.acquire_write()
            self.assertTrue(lock.locked())
            phase.append(None)

        future = f()

        while len(phase) == 0:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(len(phase), 1)
        lock.release_write()
        yield future
        self.assertEqual(len(phase), 2)


# Adapted from toro.test_lock.py
class RWLockReadTests2(AsyncTestCase):
    def test_str(self):
        lock = toro.RWLock(max_readers=1)
        # No errors in various states.
        str(lock)
        lock.acquire_read()
        str(lock)

    @gen_test
    def test_acquire_timeout(self):
        lock = toro.RWLock(max_readers=1)
        self.assertTrue(lock.acquire_read().done())
        self.assertTrue(lock.locked())
        st = time.time()

        with assert_raises(toro.Timeout):
            yield lock.acquire_read(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertTrue(lock.locked())

    @gen_test
    def test_acquire_callback(self):
        lock = toro.RWLock(max_readers=1)
        history = []
        lock.acquire_read().add_done_callback(make_callback('acq1', history))
        lock.acquire_read().add_done_callback(make_callback('acq2', history))
        lock.release_read()
        history.append('release')
        self.assertEqual(['acq1', 'acq2', 'release'], history)

    def test_multi_release(self):
        lock = toro.RWLock(max_readers=1)
        lock.acquire_read()
        lock.release_read()
        self.assertRaises(RuntimeError, lock.release_read)


# Adapted from toro.test_lock.py
class RWLockWriteTests2(AsyncTestCase):
    def test_str(self):
        lock = toro.RWLock(max_readers=10)
        # No errors in various states.
        str(lock)
        lock.acquire_write()
        str(lock)

    @gen_test
    def test_acquire_timeout(self):
        lock = toro.RWLock(max_readers=10)
        yield lock.acquire_write()
        self.assertTrue(lock.locked())
        st = time.time()

        with assert_raises(toro.Timeout):
            yield lock.acquire_write(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertTrue(lock.locked())

    @gen_test
    def test_acquire_callback(self):
        lock = toro.RWLock(max_readers=10)
        history = []
        lock.acquire_write().add_done_callback(make_callback('acq1', history))
        future = lock.acquire_write()
        future.add_done_callback(make_callback('acq2', history))
        lock.release_write()
        yield future
        history.append('release')
        self.assertEqual(['acq1', 'acq2', 'release'], history)

    def test_multi_release(self):
        lock = toro.RWLock(max_readers=10)
        lock.acquire_write()
        lock.release_write()
        self.assertRaises(RuntimeError, lock.release_write)


class RWLockWithReadDefault(toro.RWLock):
    def acquire(self, *args, **kwargs):
        return self.acquire_read(*args, **kwargs)


class RWLockWithWriteDefault(toro.RWLock):
    @gen.coroutine
    def acquire(self, *args, **kwargs):
        raise gen.Return((yield self.acquire_write(*args, **kwargs)))


# Adapted from toro.test_lock.py
class RWLockWithReadDefaultContextManagerTest(ContextManagerTestsMixin,
                                              AsyncTestCase):
    toro_class = RWLockWithReadDefault


# Adapted from toro.test_lock.py
class RWLockWithWriteDefaultContextManagerTest(ContextManagerTestsMixin,
                                               AsyncTestCase):
    toro_class = RWLockWithWriteDefault


# Adapted from toro.test_lock.py
class RWLockWithWriteMultipleReadersContextManagerTest(ContextManagerTestsMixin,
                                                       AsyncTestCase):
    toro_class = partial(RWLockWithWriteDefault, max_readers=10)


# Not adapted from toro lock tests, written just for RWLock
class RWLockTests3(AsyncTestCase):
    @gen_test
    def test_read_lock(self):
        MAX_READERS = randint(2, 10)
        lock = toro.RWLock(max_readers=MAX_READERS)
        for i in range(MAX_READERS):
            self.assertFalse(lock.locked())
            yield lock.acquire_read()

        self.assertTrue(lock.locked())

    @gen_test
    def test_write_lock(self):
        MAX_READERS = randint(2, 10)
        lock = toro.RWLock(max_readers=MAX_READERS)
        self.assertFalse(lock.locked())
        yield lock.acquire_write()
        self.assertTrue(lock.locked())

    @gen_test
    def test_reacquire(self):
        MAX_READERS = randint(2, 10)

        # Lock needs to be released before re-acquiring.
        lock = toro.RWLock(max_readers=MAX_READERS)
        phase = []

        @gen.coroutine
        def f():
            yield lock.acquire_read()
            self.assertFalse(lock.locked())
            phase.append(None)

            yield lock.acquire_write()
            self.assertTrue(lock.locked())
            phase.append(None)

        future = f()

        while len(phase) == 0:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(len(phase), 1)
        lock.release_read()
        yield future
        self.assertEqual(len(phase), 2)

    @gen_test
    def test_reacquire_concurrent(self):
        MAX_READERS = 10

        # Lock needs to be released before re-acquiring.
        lock = toro.RWLock(max_readers=MAX_READERS)
        phase = []

        @gen.coroutine
        def f():
            for _ in range(MAX_READERS):
                yield lock.acquire_read()

            self.assertTrue(lock.locked())
            phase.append(None)

            # concurrent acquire_write
            yield [lock.acquire_write(), lock.acquire_write()]
            self.assertTrue(lock.locked())
            phase.append(None)

        future = f()

        while len(phase) == 0:
            yield gen.Task(self.io_loop.add_callback)

        self.assertEqual(len(phase), 1)
        for i in range(MAX_READERS):
            lock.release_read()

        lock.release_write()

        yield future
        self.assertEqual(len(phase), 2)

    @gen_test
    def test_read_context_managers(self):
        MAX_READERS = 2
        lock = toro.RWLock(max_readers=MAX_READERS)

        self.assertFalse(lock.locked())
        with (yield lock.acquire_read()):
            self.assertFalse(lock.locked())
            with (yield lock.acquire_read()):
                self.assertTrue(lock.locked())
            self.assertFalse(lock.locked())
        self.assertFalse(lock.locked())

    @gen_test
    def test_write_context_managers(self):
        MAX_READERS = randint(2, 10)
        lock = toro.RWLock(max_readers=MAX_READERS)

        self.assertFalse(lock.locked())
        with (yield lock.acquire_write()):
            self.assertTrue(lock.locked())
        self.assertFalse(lock.locked())

    @gen_test
    def test_write_acquire_timeout(self):
        MAX_READERS = randint(2, 10)
        lock = toro.RWLock(max_readers=MAX_READERS)
        yield lock.acquire_write()
        self.assertTrue(lock.locked())
        st = time.time()

        with assert_raises(toro.Timeout):
            yield lock.acquire_write(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertTrue(lock.locked())

    @gen_test
    def test_partial_release(self):
        lock = toro.RWLock(max_readers=5)
        N = 5

        for i in range(N):
            yield lock.acquire_read()

        for i in range(N):
            lock.release_read()

        yield lock.acquire_write()
        lock.release_write()

    @gen_test
    def test_release_unlocked(self):
        lock = toro.RWLock(max_readers=5)
        N = 5

        for i in range(N):
            yield lock.acquire_read()

        for i in range(N):
            lock.release_read()

        with assert_raises(RuntimeError):
            lock.release_read()
