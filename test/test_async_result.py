"""
Test toro.AsyncResult.
"""

from __future__ import with_statement

from datetime import timedelta
from functools import partial
import time
import unittest

from tornado import gen
from tornado.ioloop import IOLoop

import toro

from test import make_callback, BaseToroCommonTest
from test.async_test_engine import async_test_engine


class TestAsyncResult(unittest.TestCase):
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
        # Without a callback, get() is non-blocking. 'timeout' is ignored.
        self.assertRaises(toro.NotReady, toro.AsyncResult().get)
        self.assertRaises(toro.NotReady,
            toro.AsyncResult().get, deadline=timedelta(seconds=1))

    @async_test_engine()
    def test_returns_none_after_timeout(self, done):
        start = time.time()
        value = yield gen.Task(
            toro.AsyncResult().get, deadline=timedelta(seconds=.01))
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(value, None)
        done()

    @async_test_engine()
    def test_set(self, done):
        result = toro.AsyncResult()
        self.assertFalse(result.ready())
        IOLoop.instance().add_timeout(
            time.time() + .01, partial(result.set, 'hello'))
        start = time.time()
        value = yield gen.Task(result.get)
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertTrue(result.ready())
        self.assertEqual('hello', value)

        # Second and third get()'s work too
        self.assertEqual('hello', (yield gen.Task(result.get)))
        self.assertEqual('hello', (yield gen.Task(result.get)))

        # Non-blocking get() works
        self.assertEqual('hello', result.get())

        # Timeout ignored now
        start = time.time()
        value = yield gen.Task(result.get)
        duration = time.time() - start
        self.assertAlmostEqual(0, duration, places=2)
        self.assertEqual('hello', value)

        # set() only allowed once
        self.assertRaises(toro.AlreadySet, result.set, 'whatever')
        done()

    @async_test_engine()
    def test_get_callback(self, done):
        # Test that callbacks registered with get() run immediately after set()
        result = toro.AsyncResult()
        history = []
        result.get(make_callback('get1', history))
        result.get(make_callback('get2', history))
        result.set('foo')
        history.append('set')
        yield gen.Task(IOLoop.instance().add_callback)
        self.assertEqual(['get1', 'get2', 'set'], history)
        done()

    @async_test_engine()
    def test_get_timeout(self, done):
        result = toro.AsyncResult()
        start = time.time()
        value = yield gen.Task(result.get, deadline=timedelta(seconds=.01))
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(None, value)
        self.assertFalse(result.ready())

        # Timed-out waiter doesn't cause error
        result.set('foo')
        self.assertTrue(result.ready())
        start = time.time()
        value = yield gen.Task(result.get, deadline=timedelta(seconds=.01))
        duration = time.time() - start
        self.assertEqual('foo', value)
        self.assertAlmostEqual(0, duration, places=2)
        done()


class TestAsyncResultCommon(unittest.TestCase, BaseToroCommonTest):
    def toro_object(self, io_loop=None):
        return toro.AsyncResult(io_loop)

    def notify(self, toro_object, value):
        toro_object.set(value)

    def wait(self, toro_object, callback, deadline):
        toro_object.get(callback, deadline)

