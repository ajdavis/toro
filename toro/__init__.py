# TODO: check against API at http://www.gevent.org/gevent.queue.html#module-gevent.queue
#   and emulate the example at its bottom in my docs
# TODO: check on Gevent's licensing
# TODO: review reprs and __str__'s
# TODO: did I omit Gevent tests from the 2.7/ dir?
# TODO: Py 3, test Jython & PyPy & add to classifiers
from __future__ import with_statement

import heapq
import logging
import collections
from functools import partial
from Queue import Full, Empty

from tornado import stack_context
from tornado.ioloop import IOLoop


version_tuple = (0, 1)

version = '.'.join(map(str, version_tuple))
"""Current version of Toro."""


__all__ = [
    # Exceptions
    'NotReady', 'AlreadySet', 'Full', 'Empty',

    # Classes
    'AsyncResult', 'Event', 'Condition',  'Semaphore', 'BoundedSemaphore',
    'Lock',

    # Queue classes
    'Queue', 'PriorityQueue', 'LifoQueue', 'JoinableQueue'
]


class NotReady(Exception):
    pass


class AlreadySet(Exception):
    pass


def _check_callback(callback):
    """
    Toro runs this on any callback before registering on IOLoop for future
    execution, to reduce confusion about the source of a TypeError. Note that
    calling a callback directly, or putting it in a _Waiter, don't require
    check_callback().
    """
    if not callable(callback):
        raise TypeError(
            "callback must be callable, not %s" % repr(callback))


class ToroBase(object):
    def __init__(self, io_loop):
        self.io_loop = io_loop or IOLoop.instance()

    def _next_tick(self, callback, *args, **kwargs):
        if callback:
            _check_callback(callback)
            self.io_loop.add_callback(partial(callback, *args, **kwargs))

    def _consume_expired_waiters(self, waiters):
        # Delete waiters at the head of the queue who've timed out
        while waiters and waiters[0].expired:
            waiters.popleft()

    def _run_callback(self, callback, *args, **kwargs):
        if callback:
            try:
                callback(*args, **kwargs)
            except Exception:
                self.handle_callback_exception(callback)

    def handle_callback_exception(self, callback):
        """This method is called whenever a callback run Toro throws an
        exception.

        By default simply logs the exception as an error.  Subclasses
        may override this method to customize reporting of exceptions.

        The exception itself is not passed explicitly, but is available
        in sys.exc_info.

        Copied from IOLoop's implementation.
        """
        logging.error("Exception in callback %r", callback, exc_info=True)


class _Waiter(ToroBase):
    """Internal Toro utility class"""
    def __init__(self, deadline, timeout_args, io_loop, callback):
        """
        Create a deferred callback. If deadline is not None, it may be a number
        denoting a unix timestamp (as returned by ``time.time()``) or a
        ``datetime.timedelta`` object for a deadline relative to the current time.
        callback(*timeout_args) is executed after a timeout.

        Waiters are only ever executed once.
        """
        super(_Waiter, self).__init__(io_loop)
        _check_callback(callback)
        if deadline is not None:
            self.io_loop.add_timeout(deadline, partial(self.run, *timeout_args))

        # Capture the current stack context so it's restored when we're run
        # after deferral.
        self.callback = stack_context.wrap(callback)

    def run(self, *args, **kwargs):
        if self.callback:
            callback, self.callback = self.callback, None
            # Clear the current stack context and run in the context that was
            # captured when we initialized.
            with stack_context.NullContext():
                self._run_callback(callback, *args, **kwargs)

    @property
    def expired(self):
        return not self.callback


class AsyncResult(ToroBase):
    """A one-time event that stores a value or an exception.

    Like :class:`Event` it wakes up all the waiters when :meth:`set`
    is called. Waiters receive the passed value by calling :meth:`get`.
    An :class:`AsyncResult` instance cannot be reset.

    To pass a value call :meth:`set`. Calls to :meth:`get` (those currently
    blocking as well as those made in the future) will return the value:

        >>> result = toro.AsyncResult()
        >>> result.set(100)
        >>> result.get()
        100

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, io_loop=None):
        super(AsyncResult, self).__init__(io_loop)
        self._ready = False
        self.value = None
        self.waiters = []

    def __str__(self):
        result = '<%s ' % (self.__class__.__name__, )
        if self._ready:
            result += 'value=%r' % self.value
        else:
            result += 'unset'
            if self.waiters:
                result += ' waiters[%s]' % len(self.waiters)
        return result + '>'

    def set(self, value):
        """Set a value and wake up all the waiters."""
        if self._ready:
            raise AlreadySet

        self.value = value
        self._ready = True
        waiters, self.waiters = self.waiters, []
        for waiter in waiters:
            waiter.run(value)

    def ready(self):
        return self._ready

    def get(self, callback=None, deadline=None):
        """Get a value now or after :meth:`set` is called. If called without a
        callback, returns the value or raises :class:`NotReady`. If called
        with a callback, passes the value to the callback on the next iteration
        of the IOLoop, after :meth:`set` is called.

        :Parameters:
          - `callback`: Optional callback taking one argument, this
            AsyncResult's value. Receives ``None`` after a timeout.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        if self.ready():
            if not callback:
                # Non-blocking get
                return self.value

            self._next_tick(callback, self.value)
        else:
            if not callback:
                raise NotReady

            # After timeout, callback will be passed None
            self.waiters.append(
                _Waiter(deadline, (None,), self.io_loop, callback))


class Condition(ToroBase):
    """A condition allows one or more callbacks to wait until they are notified.

    Like a standard Condition_, but does not need an underlying lock that
    is acquired and released.

    .. _Condition: http://docs.python.org/library/threading.html#threading.Condition

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, io_loop=None):
        super(Condition, self).__init__(io_loop)
        self.waiters = collections.deque([]) # Queue of _Waiter objects

    def __str__(self):
        result = '<%s' % (self.__class__.__name__, )
        if self.waiters:
            result += ' waiters[%s]' % len(self.waiters)
        return result + '>'

    def wait(self, callback, deadline=None):
        """Register a callback to be executed after :meth:`notify`.

        .. note:: If you set a deadline, there is no way to determine whether
           `callback` was run because of a notify or a timeout.

        :Parameters:
          - `callback`: Function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        self.waiters.append(
            _Waiter(deadline, (), self.io_loop, callback))

    def notify(self, n=1):
        """Wake up `n` waiters.

        :Parameters:
          - `n`: The number of waiters to awaken (default: 1)
        """
        self._consume_expired_waiters(self.waiters)

        waiters = [] # Waiters we plan to run right now
        while n and self.waiters:
            waiter = self.waiters.popleft()
            n -= 1
            waiters.append(waiter)
            self._consume_expired_waiters(self.waiters)

        for waiter in waiters:
            waiter.run()

    def notify_all(self):
        """Wake up all waiters."""
        self.notify(len(self.waiters))


class Event(ToroBase):
    """A synchronization primitive that allows one task to wake up one or more others.
    It has a similar interface as threading.Event_.

    An Event object manages an internal flag that can be set to true with
    the :meth:`set` method and reset to false with the :meth:`clear` method.
    The :meth:`wait` method blocks until the flag is true.

    .. _threading.Event: http://docs.python.org/library/threading.html#threading.Event

    .. seealso:: :doc:`examples/event_example`

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, io_loop=None):
        super(Event, self).__init__(io_loop)
        self.condition = Condition(io_loop)
        self._flag = False

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, (self._flag and 'set') or 'clear')

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
        """Reset the internal flag to ``False``. Subsequently, calls to :meth:`wait`
        will block until :meth:`set` is called to set the internal flag to true again.
        """
        self._flag = False

    def wait(self, callback, deadline=None):
        """Block until the internal flag is true.
        If the flag is already true, the callback is run immediately.
        Otherwise, block until the deadline, or until another task
        calls :meth:`set` to set the flag to true.

        .. note:: If you set a deadline, you can determine whether
           `callback` was run because of a :meth:`set` or a timeout by
           checking :meth:`is_set`.

        :Parameters:
          - `callback`: Function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        if self._flag:
            self._next_tick(callback)
        else:
            self.condition.wait(callback, deadline)


class Queue(ToroBase):
    """Create a queue object with a given maximum size.

    If `maxsize` is ``None`` (the default) the queue size is unbounded.

    ``Queue(0)`` is a channel, that is, its :meth:`put` method always blocks until the
    item is delivered. (This emulates `Gevent's Queue`_, but is unlike the
    `standard Queue`_, where 0 means infinite size).

    Also unlike the `standard Queue`_, you can reliably know this Queue's
    size with :meth:`qsize`, since your single-threaded Tornado application won't
    be interrupted between calling :meth:`qsize` and doing an operation on the
    Queue.

    **Examples:**

    :doc:`examples/producer_consumer_example`

    :doc:`examples/web_spider_example`

    .. warning:: Although the ``maxsize`` attribute is mutable, increasing it
      does not automatically unblock functions waiting to :meth:`put <Queue.put>`
      items. This is a bug.

    .. todo:: Fix it.

    :Parameters:
      - `max_size`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.

    .. _`Gevent's Queue`: http://www.gevent.org/gevent.queue.html

    .. _`standard Queue`: http://docs.python.org/library/queue.html#Queue.Queue
    """
    def __init__(self, maxsize=None, initial=None, io_loop=None):
        super(Queue, self).__init__(io_loop)
        if maxsize is not None and maxsize < 0:
            raise ValueError("maxsize can't be negative")
        self.maxsize = maxsize

        # _Waiters
        self.getters = collections.deque([])
        # Pairs of (item, _Waiter)
        self.putters = collections.deque([])
        self._init(maxsize, initial)

    def _init(self, maxsize, initial):
        self.queue = collections.deque(initial or [])

    def _get(self):
        return self.queue.popleft()

    def _put(self, item):
        self.queue.append(item)

    def __repr__(self):
        return '<%s at %s %s>' % (type(self).__name__, hex(id(self)), self._format())

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
        return result

    def _consume_expired_putters(self):
        # Delete waiters at the head of the queue who've timed out
        while self.putters and self.putters[0][1].expired:
            self.putters.popleft()

    def qsize(self):
        """Number of items in the queue"""
        return len(self.queue)

    def empty(self):
        """Return ``True`` if the queue is empty, ``False`` otherwise."""
        return not self.queue

    def full(self):
        """Return ``True`` if there are `maxsize` items in the queue.

        .. note:: if the Queue was initialized with `maxsize=None`
          (the default), then :meth:`full` is never ``True``.
        """
        if self.maxsize is None:
            return False
        elif self.maxsize == 0:
            return True
        else:
            return self.qsize() == self.maxsize

    def put(self, item, callback=None, deadline=None):
        """Put an item into the queue.

        If you pass a callback and `deadline` is ``None`` (the default),
        wait until a free slot is available before adding `item` and executing
        the callback with the argument ``True``.

        If there's a waiting callback registered with :meth:`get`,
        it receives the item and runs **before** the callback registered
        with :meth:`put`.

        If `deadline` is a timestamp or timedelta, the callback is passed
        ``False`` if no free slot becomes available before the deadline.

        Without a callback, this method puts an item on the queue if a free slot
        is immediately available, else raises the ``Queue.Full`` exception.
        `deadline` is ignored.

        :Parameters:
          - `callback`: Optional callback taking one argument, run after a
            waiter registered with :meth:`get`.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        self._consume_expired_waiters(self.getters)
        if self.getters:
            assert not self.queue, "queue non-empty, why are getters waiting?"
            getter = self.getters.popleft()

            # Call _put and _get in case subclasses have special logic for them
            self._put(item)
            getter.run(self._get())
            self._run_callback(callback, True)
        elif self.maxsize == self.qsize() and callback:
            _check_callback(callback)

            # When a getter runs and frees up a slot so this putter can run,
            # we need to defer the put callback for one more iteration of the
            # loop to ensure that getters and putters alternate perfectly.
            # See TestChannel2.test_wait.
            io_loop = self.io_loop
            def _callback(success):
                io_loop.add_callback(partial(callback, success))

            waiter = _Waiter(deadline, (Full,), self.io_loop, _callback)
            self.putters.append((item, waiter))
        elif self.maxsize == self.qsize():
            raise Full
        else:
            self._put(item)
            self._run_callback(callback, True)

    def get(self, callback=None, deadline=None):
        """Remove and return an item from the queue.

        If you pass a callback and `deadline` is ``None`` (the default),
        the callback is passed an item as soon as one is available.

        If `deadline` is a timestamp or timedelta, the callback is passed
        the exception ``Queue.Empty`` if no item becomes available before the
        deadline.

        Without a callback, this method returns an item if one is immediately
        available, else raises exception ``Queue.Full``. `deadline` is ignored.

        :Parameters:
          - `callback`: Optional callback taking one argument, run after a
            waiter registered with :meth:`put`.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        self._consume_expired_putters()
        if self.putters:
            assert self.full(), "queue not full, why are putters waiting?"
            item, putter = self.putters.popleft()
            self._put(item)
            if callback:
                self._run_callback(callback, self._get())
                putter.run(True)
            else:
                self.io_loop.add_callback(partial(putter.run, True))
                return self._get()
        elif self.qsize():
            if callback:
                self._run_callback(callback, self._get())
            else:
                return self._get()
        elif callback:
            self.getters.append(
                _Waiter(deadline, (Empty,), self.io_loop, callback))
        else:
            raise Empty


class PriorityQueue(Queue):
    """A subclass of :class:`Queue` that retrieves entries in priority order
    (lowest first).

    Entries are typically tuples of the form: ``(priority number, data)``.

    :Parameters:
      - `max_size`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.
    """
    def _init(self, maxsize, initial):
        self.queue = list(initial or [])

    def _put(self, item, heappush=heapq.heappush):
        heappush(self.queue, item)

    def _get(self, heappop=heapq.heappop):
        return heappop(self.queue)


class LifoQueue(Queue):
    """A subclass of :class:`Queue` that retrieves most recently added entries
    first.

    :Parameters:
      - `max_size`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.
    """
    def _init(self, maxsize, initial):
        self.queue = list(initial or [])

    def _put(self, item):
        self.queue.append(item)

    def _get(self):
        return self.queue.pop()


class JoinableQueue(Queue):
    """A subclass of :class:`Queue` that additionally has :meth:`task_done`
    and :meth:`join` methods.

    .. seealso:: :doc:`examples/web_spider_example`

    :Parameters:
      - `max_size`: Optional size limit (no limit by default).
      - `initial`: Optional sequence of initial items.
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, maxsize=None, io_loop=None):
        Queue.__init__(self, maxsize, io_loop)
        self.unfinished_tasks = 0
        self._finished = Event(io_loop)
        self._finished.set()

    def _format(self):
        result = Queue._format(self)
        if self.unfinished_tasks:
            result += ' tasks=%s' % self.unfinished_tasks
        return result

    def _put(self, item):
        Queue._put(self, item)
        self.unfinished_tasks += 1
        self._finished.clear()

    def task_done(self):
        """Indicate that a formerly enqueued task is complete. Used by queue consumers.
        For each :meth:`get <Queue.get>` used to fetch a task, a subsequent call
        to :meth:`task_done` tells the queue that the processing on the task is complete.

        If a :meth:`join` is currently blocking, it will resume when all items have been processed
        (meaning that a :meth:`task_done` call was received for every item that had
        been :meth:`put <Queue.put>` into the queue).

        Raises ``ValueError`` if called more times than there were items placed in the queue.
        """
        if self.unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            self._finished.set()

    def join(self, callback, deadline=None):
        """Block until all items in the queue have been gotten and processed.

        The count of unfinished tasks goes up whenever an item is added to the queue.
        The count goes down whenever a consumer thread calls :meth:`task_done` to indicate
        that the item was retrieved and all work on it is complete. When the count of
        unfinished tasks drops to zero, :meth:`join` unblocks.

        If `deadline` is not None, the callback may be executed before all tasks
        are complete. Check the value of unfinished_tasks after a join() with a
        deadline to determine if this has happened.

        :Parameters:
          - `callback`: Function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        if self.unfinished_tasks == 0:
            self._next_tick(callback)
        else:
            self._finished.wait(callback, deadline)


class Semaphore(object):
    """A semaphore manages a counter representing the number of release() calls minus the number of acquire() calls,
    plus an initial value. The acquire() method blocks if necessary until it can return without making the counter
    negative.

    If not given, value defaults to 1.

    .. note:: Unlike the standard threading.Semaphore_, a :class:`Semaphore`
      can tell you the current value of its :attr:`counter` or whether it
      is :meth:`locked`, because code in a single-threaded Tornado app can check
      these values and act upon them without fear of interruption from another
      thread.

    .. _threading.Semaphore: http://docs.python.org/library/threading.html#threading.Semaphore

    .. seealso:: :doc:`examples/web_spider_example`

    :Parameters:
      - `value`: An int, the initial value (default 1).
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, value=1, io_loop=None):
        if value < 0:
            raise ValueError("semaphore initial value must be >= 0")

        # The semaphore is implemented as a Queue with 'value' objects
        self.q = Queue(None, [None] * value, io_loop)

        self._unlocked = Event(io_loop)
        if value:
            self._unlocked.set()

    def __str__(self):
        return '<%s counter=%s>' % (
            self.__class__.__name__, self.counter)

    @property
    def counter(self):
        """An integer, the current semaphore value"""
        return self.q.qsize()

    def locked(self):
        """True if :attr:`counter` is zero"""
        return self.q.empty()

    def release(self):
        """Increment :attr:`counter` and wake one waiter blocking
        on :meth:`acquire`.
        """
        self.q.put(None)
        # TODO: what if locked() is still True here, because there was a
        #   waiter for get() or because get() triggered a function that did
        #   another acquire()? This needs a lot of testing.
        self._unlocked.set()

    def wait(self, callback, deadline=None):
        """Wait for :attr:`locked` to be False

        .. note:: If you set a deadline, you can determine whether
           `callback` was run because of a :meth:`release` or a timeout by
           checking :meth:`locked`.

        :Parameters:
          - `callback`: Function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        self._unlocked.wait(callback, deadline)

    def acquire(self, callback=None, deadline=None):
        """If a callback is passed, then decrement :attr:`counter` and run
        the callback. If the counter is zero, wait for
        a :meth:`release` or a timeout before running the callback.

        If no callback is passed, then if the counter is zero return ``False``,
        else if the counter is positive decrement it and return ``True``.

        .. note:: If you set a timeout, you can determine whether
           `callback` was run because of a :meth:`release` or a timeout by
           checking :meth:`locked`.

        .. todo:: Correct?

        :Parameters:
          - `callback`: Optional function taking no arguments.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        if callback:
            _check_callback(callback)
            # The Queue will return Empty on timeout, else None. Transform
            # those values into False or True.
            self.q.get(lambda value: callback(value is not Empty), deadline)
        else:
            try:
                self.q.get()
                return True
            except Empty:
                return False


class BoundedSemaphore(Semaphore):
    """A bounded semaphore checks to make sure its current value doesn't exceed its initial value.
    If it does, ``ValueError`` is raised. In most situations semaphores are used to guard resources
    with limited capacity. If the semaphore is released too many times it's a sign of a bug.

    If not given, *value* defaults to 1.

    .. seealso:: :doc:`examples/web_spider_example`
    """
    def __init__(self, value=1, io_loop=None):
        super(BoundedSemaphore, self).__init__(value, io_loop)
        self._initial_value = value

    def release(self):
        if self.counter >= self._initial_value:
            raise ValueError("Semaphore released too many times")
        return super(BoundedSemaphore, self).release()


class Lock(object):
    """A lock is in one of two states, "locked" or "unlocked".
    It is created unlocked.
    When unlocked, :meth:`acquire` changes the state to locked and runs its callback immediately.
    When the state is locked, the callback passed to :meth:`acquire` waits until a call to :meth:`release`.

    The :meth:`release` method should only be called in the locked state;
    it changes the state to unlocked and returns immediately.
    If an attempt is made to release an unlocked lock, a RuntimeError will be raised.

    When more than one callback is waiting to acquire the lock,
    the first one registered is called by :meth:`release`.

    .. note:: Unlike with the standard threading.Lock_, code in a
      single-threaded Tornado application can check if a :class:`Lock`
      is :meth:`locked`, and act on that information without fear that another
      thread has grabbed the lock, provided you do not yield to the IOLoop
      between checking :meth:`locked` and using a protected resource.

    .. _threading.Lock: http://docs.python.org/library/threading.html#threading.Lock

    :Parameters:
      - `io_loop`: Optional custom IOLoop.
    """
    def __init__(self, io_loop=None):
        self._block = BoundedSemaphore(1, io_loop)

    def __str__(self):
        return "<%s _block=%s>" % (
            self.__class__.__name__,
            self._block)

    def acquire(self, callback=None, deadline=None):
        """Attempt to lock.

        When invoked with a callback, the callback waits for the lock to be
        released, then is passed ``True``. If `deadline` is not ``None``, then
        the callback is passed ``False`` if it times out without acquiring the
        lock.

        Without a callback, if locked return False immediately;
        otherwise, lock and return True.

        :Parameters:
          - `callback`: Function taking one argument.
          - `deadline`: Optional timeout, either an absolute timestamp
            (as returned by ``time.time()``) or a ``datetime.timedelta`` for a
            deadline relative to the current time.
        """
        return self._block.acquire(callback, deadline)

    def release(self):
        """Unlock.

        If any callbacks are waiting, the first one registered
        with :meth:`acquire` is passed ``True``.

        If not locked, raise a RuntimeError.
        """
        if not self.locked():
            raise RuntimeError('release unlocked lock')
        self._block.release()

    def locked(self):
        """``True`` if the lock has been acquired"""
        return self._block.locked()

