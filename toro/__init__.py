# TODO: check against API at http://www.gevent.org/gevent.queue.html#module-gevent.queue
#   and emulate the example at its bottom in my docs
# TODO: doc! mostly copy Gevent's
# TODO: note that altering maxsize doesn't unlock putters as it should
# TODO: check on Gevent's licensing
# TODO: review reprs and __str__'s
import heapq
import logging
import time
import collections
from functools import partial
from Queue import Full, Empty

from tornado.ioloop import IOLoop

# TODO: we may need to do serious thinking about exceptions and Tornado
#   StackContexts and get some input from bdarnell
# TODO: move into a file per class

__all__ = [
    'Event', 'Condition', 'Empty', 'Full', 'Queue', 'PriorityQueue',
    'LifoQueue'
]


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
    def _run_callback(self, callback, *args, **kwargs):
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

        Copied from IOLoop.
        """
        logging.error("Exception in callback %r", callback, exc_info=True)


class _Waiter(ToroBase):
    """Internal Toro utility class"""
    def __init__(self, timeout, timeout_args, io_loop, callback):
        """
        Create a deferred callback. If timeout is not None, it's the number of
        seconds in the future at which to time-out this waiter. Note that
        timeout is seconds into the future, not a "deadline" in Unix timestamp
        as in Tornado. callback(*timeout_args) is executed after the timeout.
        Waiters are only ever executed once.
        """
        _check_callback(callback)
        if timeout is not None:
            io_loop.add_timeout(
                time.time() + timeout, partial(self.run, *timeout_args))
        self.callback = callback

    def run(self, *args, **kwargs):
        if self.callback:
            callback, self.callback = self.callback, None
            self._run_callback(callback, *args, **kwargs)

    @property
    def expired(self):
        return not self.callback


# TODO: copy Gevent's docs and tests for this
class AsyncResult(ToroBase):
    def __init__(self, io_loop=None):
        self.io_loop = io_loop or IOLoop.instance()
        self._ready = False
        self.value = None
        self.callback = None

    def set(self, value):
        self.value = value
        self._ready = True
        if self.callback:
            callback, self.callback = self.callback, None
            self._run_callback(callback, self.value)

    def ready(self):
        return self._ready

    def get(self, callback):
        if self.ready():
            _check_callback(callback)
            self.io_loop.add_callback(partial(callback, self.value))
        else:
            self.callback = callback


# TODO: Note we don't have or need acquire() and release()
class Condition(ToroBase):
    def __init__(self, io_loop=None):
        self.waiters = collections.deque([]) # Queue of _Waiter objects
        self.io_loop = io_loop or IOLoop.instance()

    def _consume_timed_out_waiters(self):
        # Delete waiters at the head of the queue who've timed out
        while self.waiters and self.waiters[0].expired:
            self.waiters.popleft()

    def wait(self, callback=None, timeout=None):
        # TODO: True / False argument, called by notify() or timeout?
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with threading.Condition
        self.waiters.append(
            _Waiter(timeout, (), self.io_loop, callback))

    def notify(self, n=1, callback=None):
        self._consume_timed_out_waiters()
        waiters = [] # Waiters we plan to run right now
        while n and self.waiters:
            waiter = self.waiters.popleft()
            n -= 1
            waiters.append(waiter)
            self._consume_timed_out_waiters()

        for waiter in waiters:
            waiter.run()

        if callback:
            _check_callback(callback)
            self.io_loop.add_callback(callback)

    def notify_all(self, callback):
        self.notify(len(self.waiters), callback)


# TODO: tests! copy from Gevent.Event tests?
class Event(ToroBase):
    """A synchronization primitive that allows one greenlet to wake up one or more others.
    It has the same interface as :class:`threading.Event` but works across greenlets.

    An event object manages an internal flag that can be set to true with the
    :meth:`set` method and reset to false with the :meth:`clear` method. The :meth:`wait` method
    blocks until the flag is true.
    """

    def __init__(self, io_loop=None):
        self.io_loop = io_loop or IOLoop.instance()
        self._links = []
        self._flag = False

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, (self._flag and 'set') or 'clear')

    def is_set(self):
        """Return true if and only if the internal flag is true."""
        return self._flag

    isSet = is_set  # makes it a better drop-in replacement for threading.Event
    ready = is_set  # makes it compatible with AsyncResult and Greenlet (for example in wait())

    def set(self):
        """Set the internal flag to true. All greenlets waiting for it to become true are awakened.
        Greenlets that call :meth:`wait` once the flag is true will not block at all.
        """
        self._flag = True
        links, self._links = self._links, []
        for waiter in links:
            waiter.run()

    def clear(self):
        """Reset the internal flag to false.
        Subsequently, threads calling :meth:`wait`
        will block until :meth:`set` is called to set the internal flag to true again.
        """
        self._flag = False

    def wait(self, callback, timeout=None):
        """Block until the internal flag is true.
        If the internal flag is true on entry, return immediately. Otherwise,
        block until another thread calls :meth:`set` to set the flag to true,
        or until the optional timeout occurs.

        When the *timeout* argument is present and not ``None``, it should be a
        floating point number specifying a timeout for the operation in seconds
        (or fractions thereof).

        Return the value of the internal flag (``True`` or ``False``).
        """
        if self._flag:
            _check_callback(callback)
            self.io_loop.add_callback(callback)
        else:
            self._links.append(
                _Waiter(timeout, (False,), self.io_loop, callback))

    # TODO
    def rawlink(self, callback):
        """Register a callback to call when the internal flag is set to true.

        *callback* will be called in the :class:`Hub <gevent.hub.Hub>`, so it must not use blocking gevent API.
        *callback* will be passed one argument: this instance.
        """
        self._links.append(callback)
        if self._flag:
            core.active_event(self._notify_links, list(self._links))  # XXX just pass [callback]

    # TODO
    def unlink(self, callback):
        """Remove the callback set by :meth:`rawlink`"""
        try:
            self._links.remove(callback)
        except ValueError:
            pass

    # TODO
    def _notify_links(self, links):
        assert getcurrent() is get_hub()
        for link in links:
            if link in self._links:  # check that link was not notified yet and was not removed by the client
                try:
                    link(self)
                except:
                    traceback.print_exc()
                    try:
                        sys.stderr.write('Failed to notify link %r of %r\n\n' % (link, self))
                    except:
                        traceback.print_exc()


class Queue(ToroBase):
    def __init__(self, maxsize=None, io_loop=None):
        self.io_loop = io_loop or IOLoop.instance()
        self.maxsize = maxsize

        # _Waiters
        self.getters = collections.deque([])
        # Pairs of (item, _Waiter)
        self.putters = collections.deque([])
        self._init(maxsize)

    def _init(self, maxsize):
        self.queue = collections.deque()

    def _get(self):
        return self.queue.popleft()

    def _put(self, item):
        self.queue.append(item)
        
    def _consume_expired_getters(self):
        while self.getters and not self.getters[0].callback:
            self.getters.popleft()

    def _consume_expired_putters(self):
        while self.putters and not self.putters[0][1].callback:
            self.putters.popleft()

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

    def qsize(self):
        return len(self.queue)

    def empty(self):
        """Return ``True`` if the queue is empty, ``False`` otherwise."""
        return not self.queue

    def full(self):
        if self.maxsize is None:
            return False
        elif self.maxsize == 0:
            return True
        else:
            return self.qsize() == self.maxsize

    def put(self, item, callback=None, timeout=None):
        """Put an item into the queue.

        # TODO: update, 'block' isn't exactly the right term
        If optional arg *block* is true and *timeout* is ``None`` (the default),
        block if necessary until a free slot is available. If *timeout* is
        a positive number, it blocks at most *timeout* seconds and raises
        the :class:`Full` exception if no free slot was available within that time.
        Otherwise (*block* is false), put an item on the queue if a free slot
        is immediately available, else raise the :class:`Full` exception (*timeout*
        is ignored in that case).
        """
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with Queue.Queue and Gevent's Queue
        # TODO: negative maxsize?
        self._consume_expired_getters()
        if self.getters:
            assert not self.queue, "queue non-empty, why are getters waiting?"
            getter = self.getters.popleft()

            # Call _put and _get in case subclasses have special logic for them
            self._put(item)
            getter.run(self._get())
            if callback:
                _check_callback(callback)
                self.io_loop.add_callback(partial(callback, True))
        elif self.maxsize == self.qsize() and callback:
            _check_callback(callback)

            # When a getter runs and frees up a slot so this putter can run,
            # we need to defer the put callback for one more iteration of the
            # loop to ensure that getters and putters alternate perfectly.
            # See TestChannel2.test_wait.
            def _callback(success):
                self.io_loop.add_callback(partial(callback, success))

            waiter = _Waiter(timeout, (False,), self.io_loop, _callback)
            self.putters.append((item, waiter))
        elif self.maxsize == self.qsize():
            raise Full
        else:
            self._put(item)
            if callback:
                _check_callback(callback)
                self.io_loop.add_callback(partial(callback, True))

    def get(self, callback=None, timeout=None):
        """Remove and return an item from the queue.

        If optional args *block* is true and *timeout* is ``None`` (the default),
        block if necessary until an item is available. If *timeout* is a positive number,
        it blocks at most *timeout* seconds and raises the :class:`Empty` exception
        if no item was available within that time. Otherwise (*block* is false), return
        an item if one is immediately available, else raise the :class:`Empty` exception
        (*timeout* is ignored in that case).
        """
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with Queue.Queue and Gevent's Queue
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
                _Waiter(timeout, (Empty,), self.io_loop, callback))
        else:
            raise Empty


class PriorityQueue(Queue):
    """A subclass of :class:`Queue` that retrieves entries in priority order (lowest first).

    Entries are typically tuples of the form: ``(priority number, data)``.
    """

    def _init(self, maxsize):
        self.queue = []

    def _put(self, item, heappush=heapq.heappush):
        heappush(self.queue, item)

    def _get(self, heappop=heapq.heappop):
        return heappop(self.queue)


class LifoQueue(Queue):
    '''A subclass of :class:`Queue` that retrieves most recently added entries first.'''

    def _init(self, maxsize):
        self.queue = []

    def _put(self, item):
        self.queue.append(item)

    def _get(self):
        return self.queue.pop()


class JoinableQueue(Queue):
    '''A subclass of :class:`Queue` that additionally has :meth:`task_done` and :meth:`join` methods.'''

    def __init__(self, maxsize=None):
        Queue.__init__(self, maxsize)
        self.unfinished_tasks = 0
        self._cond = Event()
        self._cond.set()

    def _format(self):
        result = Queue._format(self)
        if self.unfinished_tasks:
            result += ' tasks=%s _cond=%s' % (self.unfinished_tasks, self._cond)
        return result

    def _put(self, item):
        Queue._put(self, item)
        self.unfinished_tasks += 1
        self._cond.clear()

    def task_done(self):
        '''Indicate that a formerly enqueued task is complete. Used by queue consumer threads.
        For each :meth:`get <Queue.get>` used to fetch a task, a subsequent call to :meth:`task_done` tells the queue
        that the processing on the task is complete.

        If a :meth:`join` is currently blocking, it will resume when all items have been processed
        (meaning that a :meth:`task_done` call was received for every item that had been
        :meth:`put <Queue.put>` into the queue).

        Raises a :exc:`ValueError` if called more times than there were items placed in the queue.
        '''
        if self.unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            self._cond.set()

    def join(self, callback, timeout=None):
        '''Block until all items in the queue have been gotten and processed.

        The count of unfinished tasks goes up whenever an item is added to the queue.
        The count goes down whenever a consumer thread calls :meth:`task_done` to indicate
        that the item was retrieved and all work on it is complete. When the count of
        unfinished tasks drops to zero, :meth:`join` unblocks.

        If timeout is not None, the callback may be executed before all tasks
        are complete. Check the value of unfinished_tasks after a join() with a
        timeout to determine if this has happened.
        '''
        if self.unfinished_tasks == 0:
            _check_callback(callback)
            self.io_loop.add_callback(callback)
        else:
            self._cond.wait(callback, timeout)


# TODO
class Semaphore(ToroBase):
    pass


# TODO
class BoundedSemaphore(ToroBase):
    pass


# TODO
class RLock(ToroBase):
    pass
