"""
Test toro.AsyncResult.
"""

from __future__ import with_statement

from functools import partial
import time
import unittest

from tornado import gen, stack_context
from tornado.ioloop import IOLoop

import toro

from test.async_test_engine import async_test_engine


class TestAsyncResult(unittest.TestCase):
    def test_get_nowait(self):
        # Without a callback, get() is non-blocking. 'timeout' is ignored.
        self.assertRaises(toro.NotReady, toro.AsyncResult().get)
        self.assertRaises(toro.NotReady, toro.AsyncResult().get, timeout=1)

    @async_test_engine()
    def test_returns_none_after_timeout(self, done):
        start = time.time()
        value = yield gen.Task(toro.AsyncResult().get, timeout=.01)
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(value, None)
        done()

    @async_test_engine()
    def test_set(self, done):
        result = toro.AsyncResult()
        IOLoop.instance().add_timeout(
            time.time() + .01, partial(result.set, 'hello'))
        start = time.time()
        value = yield gen.Task(result.get)
        duration = time.time() - start
        self.assertAlmostEqual(.01, duration, places=2)
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

    def test_exc(self):
        # Test that raising an exception from a get() callback doesn't
        # propagate up to set()'s caller, and that StackContexts are correctly
        # managed
        result = toro.AsyncResult()
        loop = IOLoop.instance()
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'value': None,
            'set_result_exc': None,
            'get_result_exc': None,
        }

        def set_result():
            try:
                result.set('hello')
            except Exception, e:
                outcomes['set_result_exc'] = e

        def callback(value):
            outcomes['value'] = value
            assert False

        def catch_get_result_exception(type, value, traceback):
            outcomes['get_result_exc'] = type

        with stack_context.ExceptionStackContext(catch_get_result_exception):
            result.get(callback)

        loop.add_timeout(time.time() + .01, set_result)
        loop.start()
        self.assertEqual(outcomes['value'], 'hello')
        self.assertEqual(outcomes['get_result_exc'], AssertionError)
        self.assertEqual(outcomes['set_result_exc'], None)
