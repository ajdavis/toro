"""
Test toro.RWLock.
"""

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
        self.assertTrue(lock.acquire_read())
        self.assertTrue(lock.locked())
        lock.release_read()
        self.assertFalse(lock.locked())

    @gen_test
    def test_acquire_contended(self):
        lock = toro.RWLock(max_readers=1)
        self.assertTrue(lock.acquire_read())
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
    def test_acquire_release(self):
        lock = toro.RWLock(max_readers=10)
        self.assertFalse(lock.locked())
        self.assertTrue(lock.acquire_write())
        self.assertTrue(lock.locked())
        lock.release_write()
        self.assertFalse(lock.locked())

    @gen_test
    def test_acquire_contended(self):
        lock = toro.RWLock(max_readers=10)
        self.assertTrue(lock.acquire_write())
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
        # No errors in various states
        str(lock)
        lock.acquire_read()
        str(lock)

    @gen_test
    def test_acquire_timeout(self):
        lock = toro.RWLock(max_readers=1)
        self.assertTrue(lock.acquire_read())
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
        lock.acquire_read().add_done_callback(make_callback('acquire1', history))
        lock.acquire_read().add_done_callback(make_callback('acquire2', history))
        lock.release_read()
        history.append('release')
        self.assertEqual(['acquire1', 'acquire2', 'release'], history)

    def test_multi_release(self):
        lock = toro.RWLock(max_readers=1)
        lock.acquire_read()
        lock.release_read()
        self.assertRaises(RuntimeError, lock.release_read)

# Adapted from toro.test_lock.py
class RWLockWriteTests2(AsyncTestCase):
    def test_str(self):
        lock = toro.RWLock(max_readers=10)
        # No errors in various states
        str(lock)
        lock.acquire_write()
        str(lock)

    @gen_test
    def test_acquire_timeout(self):
        lock = toro.RWLock(max_readers=10)
        self.assertTrue(lock.acquire_write())
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
        lock.acquire_write().add_done_callback(make_callback('acquire1', history))
        future = lock.acquire_write()
        future.add_done_callback(make_callback('acquire2', history))
        lock.release_write()
        yield future
        history.append('release')
        self.assertEqual(['acquire1', 'acquire2', 'release'], history)

    def test_multi_release(self):
        lock = toro.RWLock(max_readers=10)
        lock.acquire_write()
        lock.release_write()
        self.assertRaises(RuntimeError, lock.release_read)


class RWLockWithReadDefault(toro.RWLock):
    def acquire(self, *args, **kwargs):
        return self.acquire_read(*args, **kwargs)


class RWLockWithWriteDefault(toro.RWLock):
    @gen.coroutine
    def acquire(self, *args, **kwargs):
        raise gen.Return((yield self.acquire_write(*args, **kwargs)))


class RWLockWithWriteMultipleReaders(RWLockWithWriteDefault):
    def __init__(self, max_readers=10, io_loop=None):
        self._max_readers = max_readers
        self._block = toro.BoundedSemaphore(value=max_readers, io_loop=io_loop)


# Adapted from toro.test_lock.py
class RWLockWithReadDefaultContextManagerTest(ContextManagerTestsMixin, AsyncTestCase):
    toro_class = RWLockWithReadDefault


# Adapted from toro.test_lock.py
class RWLockWithWriteDefaultContextManagerTest(ContextManagerTestsMixin, AsyncTestCase):
    toro_class = RWLockWithWriteDefault


# Adapted from toro.test_lock.py
class RWLockWithWriteMultipleReadersContextManagerTest(ContextManagerTestsMixin, AsyncTestCase):
    toro_class = RWLockWithWriteMultipleReaders


# Not adapted from toro lock tests, written just for RWLock
class RWLockTests3(AsyncTestCase):
    @gen_test
    def test_read_lock(self):
        MAX_READERS = randint(2,10)
        lock = toro.RWLock(max_readers=MAX_READERS)
        for i in xrange(MAX_READERS):
            self.assertFalse(lock.locked())
            yield lock.acquire_read()

        self.assertTrue(lock.locked())

    @gen_test
    def test_write_lock(self):
        MAX_READERS = randint(2,10)
        lock = toro.RWLock(max_readers=MAX_READERS)
        self.assertFalse(lock.locked())
        yield lock.acquire_write()
        self.assertTrue(lock.locked())

    @gen_test
    def test_reacquire(self):
        MAX_READERS = randint(2,10)

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
            for i in xrange(MAX_READERS):
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
        for i in xrange(MAX_READERS):
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
        self.assertTrue(lock.acquire_write())
        self.assertTrue(lock.locked())
        st = time.time()

        with assert_raises(toro.Timeout):
            yield lock.acquire_write(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertTrue(lock.locked())
