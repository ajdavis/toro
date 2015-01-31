"""Queues"""

__all__ = ['Queue', 'PriorityQueue', 'LifoQueue', 'JoinableQueue',
           'QueueFull', 'QueueEmpty']

import collections
import heapq
import warnings
from Queue import Full, Empty

from tornado import ioloop
from tornado.concurrent import Future

from . import _util
from .locks import Event


# For compatibility with Toro 0.8 and older, these inherit from the standard
# exceptions. Eventually they should just inherit from Exception, same as
# asyncio's QueueEmpty and QueueFull do.
class QueueEmpty(Empty):
    """Exception raised by :meth:`Queue.get` and :meth:`Queue.get_nowait`."""
    pass


class QueueFull(Full):
    """Exception raised by :meth:`Queue.put` and :meth:`Queue.put_nowait`."""
    pass


class Queue(object):
    """Create a queue object with a given maximum size.

    If `maxsize` is 0 (the default) the queue size is unbounded.

    Unlike the `standard Queue`_, you can reliably know this Queue's size
    with :meth:`qsize`, since your single-threaded Tornado application won't
    be interrupted between calling :meth:`qsize` and doing an operation on the
    Queue.

    **Examples:**

    :doc:`examples/producer_consumer_example`

    :doc:`examples/web_spider_example`

    :Parameters:
      - `maxsize`: Optional size limit (no limit by default).
      - `io_loop`: Optional custom IOLoop.

    .. _`Gevent's Queue`: http://www.gevent.org/gevent.queue.html

    .. _`standard Queue`: http://docs.python.org/library/queue.html#Queue.Queue
    """
    def __init__(self, maxsize=0, io_loop=None):
        self.io_loop = io_loop or ioloop.IOLoop.current()
        if maxsize is None:
            raise TypeError("maxsize can't be None")

        if maxsize < 0:
            raise ValueError("maxsize can't be negative")

        self._maxsize = maxsize

        # Futures.
        self.getters = collections.deque([])
        # Pairs of (item, Future).
        self.putters = collections.deque([])
        self._init(maxsize)
        self.unfinished_tasks = 0
        self._finished = Event(io_loop)
        self._finished.set()

    def _init(self, maxsize):
        self.queue = collections.deque()

    def _get(self):
        return self.queue.popleft()

    def _put(self, item):
        self.unfinished_tasks += 1
        self._finished.clear()
        self.queue.append(item)

    def __repr__(self):
        return '<%s at %s %s>' % (
            type(self).__name__, hex(id(self)), self._format())

    def __str__(self):
        return '<%s %s>' % (type(self).__name__, self._format())

    def _format(self):
        result = 'maxsize=%r' % (self.maxsize, )
        if getattr(self, 'queue', None):
            result += ' queue=%r' % self.queue
        if self.getters:
            result += ' getters[%s]' % len(self.getters)
        if self.putters:
            result += ' putters[%s]' % len(self.putters)
        if self.unfinished_tasks:
            result += ' tasks=%s' % self.unfinished_tasks
        return result

    def _consume_expired_putters(self):
        # Delete waiters at the head of the queue who've timed out.
        while self.putters and self.putters[0][1].done():
            self.putters.popleft()

    def qsize(self):
        """Number of items in the queue"""
        return len(self.queue)

    @property
    def maxsize(self):
        """Number of items allowed in the queue."""
        return self._maxsize

    def empty(self):
        """Return ``True`` if the queue is empty, ``False`` otherwise."""
        return not self.queue

    def full(self):
        """Return ``True`` if there are `maxsize` items in the queue.

        .. note:: if the Queue was initialized with `maxsize=0`
          (the default), then :meth:`full` is never ``True``.
        """
        if self.maxsize == 0:
            return False
        else:
            return self.maxsize <= self.qsize()

    def put(self, item, deadline=None):
        """Put an item into the queue. Returns a Future.

        The Future blocks until a free slot is available for `item`, or raises
        :exc:`~tornado.gen.TimeoutError`.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        _util.consume_expired_waiters(self.getters)
        if self.getters:
            assert not self.queue, "queue non-empty, why are getters waiting?"
            getter = self.getters.popleft()
            self._put(item)
            getter.set_result(self._get())
            return _util.null_future
        else:
            if self.maxsize and self.maxsize <= self.qsize():
                future = Future()
                self.putters.append((item, future))
                return _util.future_with_timeout(deadline, future, self.io_loop)
            else:
                self._put(item)
                return _util.null_future

    def put_nowait(self, item):
        """Put an item into the queue without blocking.

        If no free slot is immediately available, raise :exc:`QueueFull`.
        """
        _util.consume_expired_waiters(self.getters)
        if self.getters:
            assert not self.queue, "queue non-empty, why are getters waiting?"
            getter = self.getters.popleft()

            self._put(item)
            getter.set_result(self._get())
        elif self.maxsize and self.maxsize <= self.qsize():
            raise QueueFull
        else:
            self._put(item)

    def get(self, deadline=None):
        """Remove and return an item from the queue. Returns a Future.

        The Future blocks until an item is available, or raises
        :exc:`~tornado.gen.TimeoutError`.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        self._consume_expired_putters()
        if self.putters:
            assert self.full(), "queue not full, why are putters waiting?"
            item, putter = self.putters.popleft()
            self._put(item)
            putter.set_result(None)

        if self.qsize():
            future = Future()
            future.set_result(self._get())
            return future
        else:
            future = Future()
            self.getters.append(future)
            return _util.future_with_timeout(deadline, future, self.io_loop)

    def get_nowait(self):
        """Remove and return an item from the queue without blocking.

        Return an item if one is immediately available, else raise
        :exc:`QueueEmpty`.
        """
        self._consume_expired_putters()
        if self.putters:
            assert self.full(), "queue not full, why are putters waiting?"
            item, putter = self.putters.popleft()
            self._put(item)
            putter.set_result(None)
            return self._get()
        elif self.qsize():
            return self._get()
        else:
            raise QueueEmpty

    def task_done(self):
        """Indicate that a formerly enqueued task is complete.

        Used by queue consumers. For each :meth:`get <Queue.get>` used to
        fetch a task, a subsequent call to :meth:`task_done` tells the queue
        that the processing on the task is complete.

        If a :meth:`join` is currently blocking, it will resume when all
        items have been processed (meaning that a :meth:`task_done` call was
        received for every item that had been :meth:`put <Queue.put>` into the
        queue).

        Raises ``ValueError`` if called more times than there were items
        placed in the queue.
        """
        if self.unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            self._finished.set()

    def join(self, deadline=None):
        """Block until all items in the queue are processed. Returns a Future.

        The count of unfinished tasks goes up whenever an item is added to
        the queue. The count goes down whenever a consumer calls
        :meth:`task_done` to indicate that all work on the item is complete.
        When the count of unfinished tasks drops to zero, :meth:`join`
        unblocks.

        The Future raises :exc:`~tornado.gen.TimeoutError` if the count is not
        zero before the deadline.

        :Parameters:
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``io_loop.time()``) or a ``datetime.timedelta`` for
            a deadline relative to the current time.
        """
        return self._finished.wait(deadline)


class PriorityQueue(Queue):
    """A subclass of :class:`Queue` that retrieves entries in priority order
    (lowest first).

    Entries are typically tuples of the form: ``(priority number, data)``.

    :Parameters:
      - `maxsize`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.
    """
    def _init(self, maxsize):
        self.queue = []

    def _put(self, item, heappush=heapq.heappush):
        heappush(self.queue, item)

    def _get(self, heappop=heapq.heappop):
        return heappop(self.queue)


class LifoQueue(Queue):
    """A subclass of :class:`Queue` that retrieves most recently added entries
    first.

    :Parameters:
      - `maxsize`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.
    """
    def _init(self, maxsize):
        self.queue = []

    def _put(self, item):
        self.queue.append(item)

    def _get(self):
        return self.queue.pop()


class JoinableQueue(Queue):
    """**DEPRECATED**: Obsolete subclass of toro.Queue."""
    def __init__(self, maxsize=0, io_loop=None):
        warnings.warn("JoinableQueue is deprecated, use Queue.",
                      DeprecationWarning, stacklevel=2)

        Queue.__init__(self, maxsize=maxsize, io_loop=io_loop)
