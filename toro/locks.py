"""Synchronization primitives."""

__all__ = ['Event', 'Condition',  'Semaphore', 'BoundedSemaphore', 'Lock']

import contextlib
import collections

from tornado import ioloop
from tornado.concurrent import Future

from . import _util


class _ContextManagerFuture(Future):
    """A Future that can be used with the "with" statement.

    When a coroutine yields this Future, the return value is a context manager
    that can be used like:

        with (yield future):
            pass

    At the end of the block, the Future's exit callback is run. Used for
    Lock.acquire() and Semaphore.acquire().
    """
    def __init__(self, wrapped, exit_callback):
        super(_ContextManagerFuture, self).__init__()
        wrapped.add_done_callback(self._done_callback)
        self.exit_callback = exit_callback

    def _done_callback(self, wrapped):
        if wrapped.exception():
            self.set_exception(wrapped.exception())
        else:
            self.set_result(wrapped.result())

    def result(self):
        if self.exception():
            raise self.exception()

        # Otherwise return a context manager that cleans up after the block.
        @contextlib.contextmanager
        def f():
            try:
                yield
            finally:
                self.exit_callback()
        return f()

class Condition(object):
    """A condition allows one or more coroutines to wait until notified.

    Like a standard Condition_, but does not need an underlying lock that
    is acquired and released.

    .. _Condition: http://docs.python.org/library/threading.html#threading.Condition

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or ioloop.IOLoop.current()
        self.waiters = collections.deque()  # Futures.

    def __str__(self):
        result = '<%s' % (self.__class__.__name__, )
        if self.waiters:
            result += ' waiters[%s]' % len(self.waiters)
        return result + '>'

    def wait(self, deadline=None):
        """Wait for :meth:`notify`. Returns a Future.

        The Future raises :exc:`~tornado.gen.TimeoutError` after a timeout.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        future = Future()
        self.waiters.append(future)
        return _util.future_with_timeout(deadline, future, self.io_loop)

    def notify(self, n=1):
        """Wake up `n` waiters.

        :Parameters:
          - `n`: The number of waiters to awaken (default: 1)
        """
        waiters = []  # Waiters we plan to run right now.
        while n and self.waiters:
            waiter = self.waiters.popleft()
            if not waiter.done():  # Might have timed out.
                n -= 1
                waiters.append(waiter)

        for waiter in waiters:
            waiter.set_result(None)

    def notify_all(self):
        """Wake up all waiters."""
        self.notify(len(self.waiters))


# TODO: show correct examples that avoid thread / process issues w/ concurrent.futures.Future
class Event(object):
    """An event blocks coroutines until its internal flag is set to True.

    Similar to threading.Event_.

    .. _threading.Event: http://docs.python.org/library/threading.html#threading.Event

    .. seealso:: :doc:`examples/event_example`

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or ioloop.IOLoop.current()
        self.condition = Condition(io_loop=io_loop)
        self._flag = False

    def __str__(self):
        return '<%s %s>' % (
            self.__class__.__name__, 'set' if self._flag else 'clear')

    def is_set(self):
        """Return ``True`` if and only if the internal flag is true."""
        return self._flag

    def set(self):
        """Set the internal flag to ``True``. All waiters are awakened.
        Calling :meth:`wait` once the flag is true will not block.
        """
        self._flag = True
        self.condition.notify_all()

    def clear(self):
        """Reset the internal flag to ``False``. Calls to :meth:`wait`
        will block until :meth:`set` is called.
        """
        self._flag = False

    def wait(self, deadline=None):
        """Block until the internal flag is true. Returns a Future.

        The Future raises :exc:`~tornado.gen.TimeoutError` after a timeout.

        :Parameters:
          - `callback`: Function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        if self._flag:
            return _util.null_future
        else:
            return self.condition.wait(deadline)


class Semaphore(object):
    """A lock that can be acquired a fixed number of times before blocking.

    A Semaphore manages a counter representing the number of release() calls
    minus the number of acquire() calls, plus an initial value. The acquire()
    method blocks if necessary until it can return without making the counter
    negative.

    If not given, value defaults to 1.

    :meth:`acquire` supports the context manager protocol:

    >>> from tornado import gen
    >>> import toro
    >>> semaphore = toro.Semaphore()
    >>> @gen.coroutine
    ... def f():
    ...    with (yield semaphore.acquire()):
    ...        assert semaphore.locked()
    ...
    ...    assert not semaphore.locked()

    .. note:: Unlike the standard threading.Semaphore_, a :class:`Semaphore`
      can tell you the current value of its :attr:`counter`, because code in a
      single-threaded Tornado app can check these values and act upon them
      without fear of interruption from another thread.

    .. _threading.Semaphore: http://docs.python.org/library/threading.html#threading.Semaphore

    .. seealso:: :doc:`examples/web_spider_example`

    :Parameters:
      - `value`: An int, the initial value (default 1).
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, value=1, io_loop=None):
        if value < 0:
            raise ValueError('semaphore initial value must be >= 0')

        self.io_loop = io_loop or ioloop.IOLoop.current()
        self._value = value
        self._waiters = collections.deque()

    def __repr__(self):
        res = super(Semaphore, self).__repr__()
        extra = 'locked' if self.locked() else 'unlocked,value:{0}'.format(
            self._value)
        if self._waiters:
            extra = '{0},waiters:{1}'.format(extra, len(self._waiters))
        return '<{0} [{1}]>'.format(res[1:-1], extra)

    @property
    def counter(self):
        """An integer, the current semaphore value."""
        return self._value

    def locked(self):
        """True if the semaphore cannot be acquired immediately."""
        return self._value == 0

    def release(self):
        """Increment :attr:`counter` and wake one waiter."""
        self._value += 1
        for waiter in self._waiters:
            if not waiter.done():
                self._value -= 1
                waiter.set_result(None)
                break

    def acquire(self, deadline=None):
        """Decrement :attr:`counter`. Returns a Future.

        Block if the counter is zero and wait for a :meth:`release`. The
        Future raises :exc:`~tornado.gen.TimeoutError` after the deadline.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        if self._value > 0:
            self._value -= 1
            future = _util.null_future
        else:
            waiter = Future()
            self._waiters.append(waiter)
            future = _util.future_with_timeout(deadline, waiter, self.io_loop)
        return _ContextManagerFuture(future, self.release)

    def __enter__(self):
        raise RuntimeError(
            "Use Semaphore like 'with (yield semaphore.acquire)', not like"
            " 'with semaphore'")

    __exit__ = __enter__


class BoundedSemaphore(Semaphore):
    """A semaphore that prevents release() being called too often.

    A bounded semaphore checks to make sure its current value doesn't exceed
    its initial value. If it does, ``ValueError`` is raised. In most
    situations semaphores are used to guard resources with limited capacity.
    If the semaphore is released too many times it's a sign of a bug.

    If not given, *value* defaults to 1.

    .. seealso:: :doc:`examples/web_spider_example`
    """
    def __init__(self, value=1, io_loop=None):
        super(BoundedSemaphore, self).__init__(value=value, io_loop=io_loop)
        self._initial_value = value

    def release(self):
        if self.counter >= self._initial_value:
            raise ValueError("Semaphore released too many times")
        super(BoundedSemaphore, self).release()


class Lock(object):
    """A lock for coroutines.

    It is created unlocked. When unlocked, :meth:`acquire` changes the state
    to locked. When the state is locked, yielding :meth:`acquire` waits until
    a call to :meth:`release`.

    The :meth:`release` method should only be called in the locked state;
    an attempt to release an unlocked lock raises RuntimeError.

    When more than one coroutine is waiting for the lock, the first one
    registered is awakened by :meth:`release`.

    :meth:`acquire` supports the context manager protocol:

    >>> from tornado import gen
    >>> import toro
    >>> lock = toro.Lock()
    >>>
    >>> @gen.coroutine
    ... def f():
    ...    with (yield lock.acquire()):
    ...        assert lock.locked()
    ...
    ...    assert not lock.locked()

    .. note:: Unlike with the standard threading.Lock_, code in a
      single-threaded Tornado application can check if a :class:`Lock`
      is :meth:`locked`, and act on that information without fear that another
      thread has grabbed the lock, provided you do not yield to the IOLoop
      between checking :meth:`locked` and using a protected resource.

    .. _threading.Lock: http://docs.python.org/2/library/threading.html#lock-objects

    .. seealso:: :doc:`examples/lock_example`

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, io_loop=None):
        self._block = BoundedSemaphore(value=1, io_loop=io_loop)

    def __str__(self):
        return "<%s _block=%s>" % (
            self.__class__.__name__,
            self._block)

    def acquire(self, deadline=None):
        """Attempt to lock. Returns a Future.

        The Future raises :exc:`~tornado.gen.TimeoutError` after a timeout.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        return self._block.acquire(deadline)

    def release(self):
        """Unlock.

        If any coroutines are waiting for :meth:`acquire`,
        the first in line is awakened.

        If not locked, raise a RuntimeError.
        """
        if not self.locked():
            raise RuntimeError('release unlocked lock')
        self._block.release()

    def locked(self):
        """``True`` if the lock has been acquired"""
        return self._block.locked()

    def __enter__(self):
        raise RuntimeError(
            "Use Lock like 'with (yield lock)', not like"
            " 'with lock'")

    __exit__ = __enter__
