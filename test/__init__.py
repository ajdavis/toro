import time
from datetime import timedelta

from tornado import stack_context
from tornado.testing import gen_test


def make_callback(key, history):
    def callback(*args):
        history.append(key)
    return callback


class BaseToroCommonTest(object):
    def toro_object(self):
        raise NotImplementedError()

    def toro_notify(self, toro_object, value):
        raise NotImplementedError()

    def toro_wait(self, toro_object, callback=None, deadline=None):
        raise NotImplementedError()

    @gen_test
    def test_deadline(self):
        # Test that the wait method can take either timedelta since now or
        # seconds since epoch
        toro_object = self.toro_object()

        start = time.time()
        with self.assertRaises(Exception):
            yield self.toro_wait(toro_object, deadline=time.time() + .01)

        self.assertAlmostEqual(time.time() - start, .01, places=2)

        start = time.time()
        with self.assertRaises(Exception):
            yield self.toro_wait(toro_object, deadline=timedelta(seconds=.01))

        self.assertAlmostEqual(time.time() - start, .01, places=2)

    def test_exc(self):
        # Test that raising an exception from a wait callback doesn't
        # propagate up to notify's caller, and that _Waiter calls
        # stack_context.wrap() so a stack context we set when we called
        # wait is restored when wait's callback is run.
        toro_object = self.toro_object()
        loop = self.io_loop
        loop.add_timeout(time.time() + 0.02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'wait_callback_executed': False,
            'notify_exc': None,
            'wait_result_exc': None,
        }

        def notify():
            try:
                self.toro_notify(toro_object, 'value')
            except Exception, e:
                outcomes['notify_exc'] = e

        def wait_callback(value=None):
            outcomes['wait_callback_executed'] = True
            1 / 0

        def catch_wait_result_exception(exc_type, exc_value, exc_traceback):
            outcomes['wait_result_exc'] = exc_type
            return True  # Stop propagation

        with stack_context.ExceptionStackContext(catch_wait_result_exception):
            self.toro_wait(toro_object, callback=wait_callback)

        loop.add_timeout(time.time() + .01, notify)
        loop.start()
        self.assertTrue(outcomes['wait_callback_executed'])
        self.assertEqual(outcomes['wait_result_exc'], ZeroDivisionError)
        self.assertEqual(outcomes['notify_exc'], None)

    def test_stack_context_leak(self):
        # Test that stack context isn't leaked from notify to a deferred wait:
        # If wait()'s callback schedules another callback that raises an
        # exception, that exception isn't caught by notify's stack context.
        # _Waiter passes this test by running the deferred callback in
        # NullContext.
        toro_object = self.toro_object()
        loop = self.io_loop
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'wait_callback_executed': False,
            'wait_exc': None,
            'notify_exc': None,
        }

        def catch_notify_exc(exc_type, exc_value, exc_traceback):
            outcomes['notify_exc'] = exc_type
            return True  # Stop propagation

        def notify():
            with stack_context.ExceptionStackContext(catch_notify_exc):
                self.toro_notify(toro_object, 'value')

        def wait_callback(value=None):
            outcomes['wait_callback_executed'] = True
            loop.add_callback(raise_callback)

        def raise_callback():
            1 / 0

        def catch_wait_exc(exc_type, exc_value, exc_traceback):
            outcomes['wait_exc'] = exc_type
            return True  # Stop propagation

        with stack_context.ExceptionStackContext(catch_wait_exc):
            self.toro_wait(toro_object, callback=wait_callback)

        loop.add_timeout(time.time() + .01, notify)
        loop.start()
        self.assertTrue(outcomes['wait_callback_executed'])
        self.assertEqual(outcomes['wait_exc'], ZeroDivisionError)

        # The exception raised from a callback scheduled by the wait callback
        # wasn't caught by notify's stack context
        self.assertEqual(outcomes['notify_exc'], None)
