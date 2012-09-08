# TODO: check against API at http://www.gevent.org/gevent.queue.html#module-gevent.queue
#   and emulate the example at its bottom in my docs
# TODO: doc! mostly copy Gevent's
import time
from collections import deque

from tornado import gen
from tornado.gen import Task
from tornado.ioloop import IOLoop

# TODO: we may need to do serious thinking about Tornado StackContexts and get
#   some input from bdarnell

__all__ = ['Condition', 'Empty', 'Full', 'Queue', 'PriorityQueue', 'LifoQueue']

class _Waiter(object):
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback

    def run(self):
        if self.callback:
            callback, self.callback = self.callback, None
            callback()


# TODO: Note we don't have or need acquire() and release()
class Condition(object):
    def __init__(self, io_loop=None):
        self.waiters = deque([]) # Queue of _Waiter objects
        self.io_loop = io_loop or IOLoop.instance()

    def wait(self, timeout=None, callback=None):
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with threading.Condition
        if not callable(callback):
            raise TypeError(
                "callback must be callable, not %s" % repr(callback))

        if timeout is not None:
            waiter = _Waiter(time.time() + timeout, callback)
            self.io_loop.add_timeout(waiter.timeout, waiter.run)
        else:
            waiter = _Waiter(None, callback)

        self.waiters.append(waiter)

    def notify(self, n=1, callback=None):
        waiters = []
        while n and self.waiters:
            waiter = self.waiters.popleft()

            # Check if this waiter has timed out earlier
            if waiter.callback:
                n -= 1
                waiters.append(waiter)

        for waiter in waiters:
            # TODO: what if this throws?
            # ALSO TODO: ok to call these directly or should they be
            #   scheduled in order on the loop?
            waiter.run()

        if callback:
            self.io_loop.add_callback(callback)

    def notify_all(self, callback):
        self.notify(len(self.waiters), callback)


class Empty(Exception):
    """Exception raised by Queue.get(block=0)/get_nowait()."""
    pass


class Full(Exception):
    """Exception raised by Queue.put(block=0)/put_nowait()."""
    pass


class Queue(object):
    def __init__(self, maxsize=None):
        self.maxsize = maxsize
        self.queue = deque([])

        # This is adapated from Gevent's Queue
        # Notify not_empty whenever an item is added to the queue; a
        # thread waiting to get is notified then.
        self.not_empty = Condition()
        # Notify not_full whenever an item is removed from the queue;
        # a thread waiting to put is notified then.
        self.not_full = Condition()
        # Notify all_tasks_done whenever the number of unfinished tasks
        # drops to zero; thread waiting to join() is notified to resume
        self.all_tasks_done = Condition()
        self.unfinished_tasks = 0

    def task_done(self, callback):
        pass

    def join(self, callback):
        pass

    def qsize(self):
        return len(self.queue)

    def empty(self):
        return not self.queue

    def full(self):
        if self.maxsize is None:
            return False
        elif self.maxsize == 0:
            return True
        else:
            return len(self.queue) == self.maxsize

    @gen.engine
    def put(self, item, block=True, timeout=None, callback=None):
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with threading.Condition
        # TODO: how much could API be simplified, knowing we can reliably
        #   test whether we'll block?
        if self.maxsize > 0:
            if not block:
                if self.qsize() == self.maxsize:
                    raise Full
            elif timeout is None:
                while self.qsize() == self.maxsize:
                    yield Task(self.not_full.wait)
            elif timeout < 0:
                raise ValueError("'timeout' must be a positive number")
            else:
                endtime = time.time() + timeout
                while self.qsize() == self.maxsize:
                    remaining = endtime - time.time()
                    if remaining <= 0.0:
                        raise Full
                    yield Task(self.not_full.wait, remaining)

        self.queue.append(item)
        self.unfinished_tasks += 1
        yield Task(self.not_empty.notify, 1)
        callback() # TODO: exception?

    def put_nowait(self, item):
        # TODO: how much could API be simplified, knowing we can reliably
        #   test whether we'll block?
        pass

    @gen.engine
    def get(self, block=True, timeout=None, callback=None):
        # TODO: NOTE that while Tornado's "timeout" parameters are seconds
        #   since epoch, this timeout is seconds from **now**, consistent
        #   with threading.Condition
        if not block:
            if not self.qsize():
                raise Empty
        elif timeout is None:
            while not self.qsize():
                yield Task(self.not_empty.wait)
        elif timeout < 0:
            raise ValueError("'timeout' must be a positive number")
        else:
            endtime = time.time() + timeout
            while not self.qsize():
                remaining = endtime - time.time()
                if remaining <= 0.0:
                    raise Empty
                yield Task(self.not_empty.wait, remaining)

        item = self.queue.popleft()
        yield Task(self.not_full.notify)
        callback(item)
    
    def get_nowait(self):
        pass


class PriorityQueue(Queue):
    pass


class LifoQueue(Queue):
    pass


class JoinableQueue(Queue):
    pass


class Event(object):
    pass


class Semaphore(object):
    pass


class BoundedSemaphore(object):
    pass


class RLock(object):
    pass
