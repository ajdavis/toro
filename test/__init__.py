from __future__ import with_statement

from datetime import timedelta
import time

from tornado import stack_context, gen
from tornado.ioloop import IOLoop
from test.async_test_engine import async_test_engine


def make_callback(key, history):
    def callback(*args):
        history.append(key)
    return callback


class BaseToroCommonTest(object):
    def toro_object(self, io_loop=None):
        raise NotImplementedError()

    def notify(self, toro_object, value):
        raise NotImplementedError()

    def wait(self, toro_object, callback, deadline):
        raise NotImplementedError()

    @async_test_engine()
    def test_deadline(self, done):
        # Test that the wait method can take either timedelta since now or
        # seconds since epoch
        toro_object = self.toro_object()

        start = time.time()
        yield gen.Task(self.wait, toro_object, deadline=time.time() + .01)
        self.assertAlmostEqual(time.time() - start, .01, places=2)

        start = time.time()
        yield gen.Task(self.wait, toro_object, deadline=timedelta(seconds=.01))
        self.assertAlmostEqual(time.time() - start, .01, places=2)
        done()

    def test_exc(self):
        # Test that raising an exception from a wait callback doesn't
        # propagate up to notify's caller, and that _Waiter calls
        # stack_context.wrap() so a stack context we set when we called
        # wait is restored when wait's callback is run.
        toro_object = self.toro_object()
        loop = IOLoop.instance()
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'wait_callback_executed': False,
            'notify_exc': None,
            'wait_result_exc': None,
        }

        def notify():
            try:
                self.notify(toro_object, 'value')
            except Exception, e:
                outcomes['notify_exc'] = e

        def wait_callback(value=None):
            outcomes['wait_callback_executed'] = True
            assert False

        def catch_wait_result_exception(type, value, traceback):
            outcomes['wait_result_exc'] = type

        with stack_context.ExceptionStackContext(catch_wait_result_exception):
            self.wait(toro_object, wait_callback, None)

        loop.add_timeout(time.time() + .01, notify)
        loop.start()
        self.assertTrue(outcomes['wait_callback_executed'])
        self.assertEqual(outcomes['wait_result_exc'], AssertionError)
        self.assertEqual(outcomes['notify_exc'], None)

    def test_stack_context_leak(self):
        # Test that stack context isn't leaked from notify to a deferred wait:
        # If wait()'s callback schedules another callback that raises an
        # exception, that exception isn't caught by notify's stack context.
        # _Waiter passes this test by running the deferred callback in
        # NullContext.
        toro_object = self.toro_object()
        loop = IOLoop.instance()
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'wait_callback_executed': False,
            'notify_exc': None,
        }

        def notify():
            with stack_context.ExceptionStackContext(catch_notify_exc):
                self.notify(toro_object, 'value')

        def wait_callback(value=None):
            outcomes['wait_callback_executed'] = True
            loop.add_callback(raise_callback)

        def raise_callback():
            assert False

        def catch_notify_exc(type, value, traceback):
            outcomes['notify_exc'] = type
            return True

        self.wait(toro_object, wait_callback, None)
        loop.add_timeout(time.time() + .01, notify)
        loop.start()
        self.assertTrue(outcomes['wait_callback_executed'])

        # The exception raised from a callback scheduled by the wait callback
        # wasn't caught by notify's stack context
        self.assertEqual(outcomes['notify_exc'], None)

    def test_io_loop(self):
        global_loop = IOLoop.instance()
        custom_loop = IOLoop()
        self.assertNotEqual(global_loop, custom_loop)
        toro_object = self.toro_object(custom_loop)

        def callback(value=None):
            custom_loop.stop()

        self.wait(toro_object, callback, None)
        self.notify(toro_object, 'value')

        # If this completes, we know that wait and notify used the right loop
        custom_loop.start()
