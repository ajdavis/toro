import unittest
import time

from tornado import gen, stack_context
from tornado.ioloop import IOLoop

import toro
from test.async_test_engine import async_test_engine


def make_callback(key, history):
    def callback():
        history.append(key)
    return callback


class TestEvent(unittest.TestCase):
    @gen.engine
    def test_event(self, n, callback):
        e = toro.Event()
        for i in range(n):
            e.wait(callback=(yield gen.Callback(i)))

        e.set()
        e.clear()
        yield gen.WaitAll(range(n))
        callback()

    # Not a test - called from test_event_1, etc.
    test_event.__test__ = False

    @async_test_engine()
    def test_event_1(self, done):
        yield gen.Task(self.test_event, 1)
        done()

    @async_test_engine()
    def test_event_100(self, done):
        yield gen.Task(self.test_event, 100)
        done()

    @async_test_engine()
    def test_event_10000(self, done):
        yield gen.Task(self.test_event, 10000)
        done()

    def test_exc(self):
        # Test that raising an exception from a wait() callback doesn't
        # propagate up to set()'s caller, and that StackContexts are correctly
        # managed
        event = toro.Event()
        loop = IOLoop.instance()
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'callback_executed': False,
            'set_result_exc': None,
            'wait_result_exc': None,
        }

        def set_result():
            try:
                event.set()
            except Exception, e:
                outcomes['set_result_exc'] = e

        def callback():
            outcomes['callback_executed'] = True
            assert False

        def catch_wait_result_exception(type, value, traceback):
            outcomes['wait_result_exc'] = type

        with stack_context.ExceptionStackContext(catch_wait_result_exception):
            event.wait(callback)

        loop.add_timeout(time.time() + .01, set_result)
        loop.start()
        self.assertTrue(outcomes['callback_executed'])
        self.assertEqual(outcomes['wait_result_exc'], AssertionError)
        self.assertEqual(outcomes['set_result_exc'], None)
