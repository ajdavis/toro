"""Internal utilities."""

from tornado import gen
from tornado.concurrent import Future


null_future = Future()
null_future.set_result(None)


def future_with_timeout(deadline, future, io_loop):
    if deadline is not None:
        result = gen.with_timeout(deadline, future, io_loop=io_loop)
        gen.chain_future(result, future)
        return result
    else:
        return future


def consume_expired_waiters(waiters):
    # Delete waiters at the head of the queue who've timed out.
    while waiters and waiters[0].done():
        waiters.popleft()
