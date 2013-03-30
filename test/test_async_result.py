"""
Test toro.AsyncResult.
"""

from datetime import timedelta
from functools import partial
import time

from tornado.testing import gen_test, AsyncTestCase


import toro
from test import make_callback, BaseToroCommonTest


class TestAsyncResult(AsyncTestCase):
    def test_str(self):
        result = toro.AsyncResult()
        str(result)
        result.set('fizzle')
        self.assertTrue('fizzle' in str(result))
        self.assertFalse('waiters' in str(result))

        result = toro.AsyncResult()
        result.get(lambda: None)
        self.assertTrue('waiters' in str(result))

    def test_get_nowait(self):
        self.assertRaises(toro.NotReady, toro.AsyncResult().get_nowait)

    @gen_test
    def test_raises_after_timeout(self):
        start = time.time()
        with self.assertRaises(toro.NotReady):
            async_result = toro.AsyncResult(self.io_loop)
            yield async_result.get(deadline=timedelta(seconds=.01))
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)

    @gen_test
    def test_set(self):
        result = toro.AsyncResult(io_loop=self.io_loop)
        self.assertFalse(result.ready())
        self.io_loop.add_timeout(
            time.time() + .01, partial(result.set, 'hello'))
        start = time.time()
        value = yield result.get()
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertTrue(result.ready())
        self.assertEqual('hello', value)

        # Second and third get()'s work too
        self.assertEqual('hello', (yield result.get()))
        self.assertEqual('hello', (yield result.get()))

        # Non-blocking get() works
        self.assertEqual('hello', result.get_nowait())

        # Timeout ignored now
        start = time.time()
        value = yield result.get()
        duration = time.time() - start
        self.assertAlmostEqual(0, duration, places=2)
        self.assertEqual('hello', value)

        # set() only allowed once
        self.assertRaises(toro.AlreadySet, result.set, 'whatever')

    @gen_test
    def test_get_callback(self):
        # Test that callbacks registered with get() run immediately after set()
        result = toro.AsyncResult(io_loop=self.io_loop)
        history = []
        result.get(make_callback('get1', history))
        result.get(make_callback('get2', history))
        result.set('foo')
        history.append('set')
        self.assertEqual(['get1', 'get2', 'set'], history)

    @gen_test
    def test_get_timeout(self):
        result = toro.AsyncResult(io_loop=self.io_loop)
        start = time.time()
        with self.assertRaises(toro.NotReady):
            yield result.get(deadline=timedelta(seconds=.01))

        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertFalse(result.ready())

        # Timed-out waiter doesn't cause error
        result.set('foo')
        self.assertTrue(result.ready())
        start = time.time()
        value = yield result.get(deadline=timedelta(seconds=.01))
        duration = time.time() - start
        self.assertEqual('foo', value)
        self.assertAlmostEqual(0, duration, places=2)


class TestAsyncResultCommon(AsyncTestCase, BaseToroCommonTest):
    def toro_object(self):
        return toro.AsyncResult(self.io_loop)

    def toro_notify(self, toro_object, value):
        toro_object.set(value)

    def toro_wait(self, toro_object, callback=None, deadline=None):
        return toro_object.get(callback=callback, deadline=deadline)
