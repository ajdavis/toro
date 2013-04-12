import contextlib
from datetime import timedelta
from functools import partial

from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.testing import gen_test, gen

import toro


@contextlib.contextmanager
def assert_raises(exc_class):
    """Roughly a backport of Python 2.7's TestCase.assertRaises"""
    try:
        yield
    except exc_class:
        pass
    else:
        assert False, "%s not raised" % exc_class


def make_callback(key, history):
    def callback(future):
        exc = future.exception()
        if exc:
            history.append(exc.__class__.__name__)
        else:
            history.append(key)
    return callback


def pause(deadline):
    future = Future()
    IOLoop.current().add_timeout(deadline, partial(future.set_result, None))
    return future


class ContextManagerTestsMixin(object):
    """Test a Toro object's behavior with the "with" statement

    Combine this mixin with an AsyncTestCase that has a field 'toro_class'
    """

    @gen_test
    def test_context_manager(self):
        toro_obj = self.toro_class()
        with (yield toro_obj.acquire()) as yielded:
            self.assertTrue(toro_obj.locked())
            self.assertTrue(yielded is None)

        self.assertFalse(toro_obj.locked())

    @gen_test
    def test_context_manager_exception(self):
        toro_obj = self.toro_class()
        with assert_raises(ZeroDivisionError):
            with (yield toro_obj.acquire()):
                1 / 0

        # Context manager released toro_obj
        self.assertFalse(toro_obj.locked())

    @gen_test
    def test_context_manager_contended(self):
        toro_obj = toro.Semaphore()
        history = []
        n_coroutines = 10

        @gen.coroutine
        def f(i):
            with (yield toro_obj.acquire()):
                history.append('acquired %d' % i)
                yield pause(timedelta(seconds=0.01))
                history.append('releasing %d' % i)

        yield [f(i) for i in range(n_coroutines)]

        expected_history = []
        for i in range(n_coroutines):
            expected_history.extend(['acquired %d' % i, 'releasing %d' % i])

        self.assertEqual(expected_history, history)

    def test_context_manager_misuse(self):
        toro_obj = self.toro_class()

        # Ensure we catch a "with toro_obj", which should be
        # "with (yield toro_obj)"
        with assert_raises(RuntimeError):
            with toro_obj:
                pass
