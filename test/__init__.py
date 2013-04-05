from functools import partial
from tornado.concurrent import Future
from tornado.ioloop import IOLoop


# TODO: remove once Tornado > 3.0 fixes this
from tornado.testing import gen_test
gen_test.__test__ = False  # hide from Nose


def make_callback(key, history):
    def callback(*args):
        history.append(key)
    return callback


def pause(deadline):
    future = Future()
    IOLoop.current().add_timeout(deadline, partial(future.set_result, None))
    return future
