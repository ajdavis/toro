"""
Test toro.Queue.

There are three sections, one each for tests that are
1. adapted from Gevent's test_queue.py, except for FailingQueueTest of which I
   don't understand the purpose,
2. adapted from Gevent's test__queue.py,
3. written specifically for Toro.
"""

import time
import unittest
from Queue import Empty, Full

from tornado import gen
from tornado.gen import Task
from tornado.ioloop import IOLoop

import toro
from test.async_test_engine import async_test_engine

# SECTION 1: Tests adapted from Gevent's test_queue.py (single underscore)

QUEUE_SIZE = 5


class _TriggerTask(object):
    def __init__(self, fn, args, kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.startedEvent = toro.Event()
        IOLoop.instance().add_timeout(time.time() + 0.1, self.run)

    def run(self):
        self.startedEvent.set()
        self.fn(*self.args, **self.kwargs)


class QueueTest1(unittest.TestCase):
    type2test = toro.Queue

    @gen.engine
    def do_blocking_test(self, block_func, block_args, block_kwargs, trigger_func, trigger_args, trigger_kwargs, callback):
        self.t = _TriggerTask(trigger_func, trigger_args, trigger_kwargs)
        self.result = yield Task(block_func, *block_args, **block_kwargs)
        # If block_func returned before our thread made the call, we failed!
        if not self.t.startedEvent.isSet():
            self.fail("blocking function '%r' appeared not to block" %
                      block_func)
        callback(self.result)

    do_blocking_test.__test__ = False # Hide from nose

    # Call this instead if block_func is supposed to raise an exception.
    # TODO: useful?
    def do_exceptional_blocking_test(self,block_func, block_args, trigger_func,
                                   trigger_args, expected_exception_class):
        self.t = _TriggerThread(trigger_func, trigger_args)
        self.t.start()
        try:
            try:
                block_func(*block_args)
            except expected_exception_class:
                raise
            else:
                self.fail("expected exception of kind %r" %
                                 expected_exception_class)
        finally:
            self.t.join(10) # make sure the thread terminates
            if self.t.isAlive():
                self.fail("trigger function '%r' appeared to not return" %
                                 trigger_func)
            if not self.t.startedEvent.isSet():
                self.fail("trigger thread ended but event never set")

    do_exceptional_blocking_test.__test__ = False # Hide from nose

    @gen.engine
    def simple_queue_test(self, q, callback):
        if not q.empty():
            raise RuntimeError, "Call this function with an empty queue"
        # I guess we better check things actually queue correctly a little :)
        q.put(111)
        q.put(333)
        q.put(222)
        target_order = dict(Queue=[111, 333, 222],
                            LifoQueue=[222, 333, 111],
                            PriorityQueue=[111, 222, 333])
        actual_order = [q.get(), q.get(), q.get()]
        self.assertEquals(actual_order, target_order[q.__class__.__name__],
                          "Didn't seem to queue the correct data!")
        for i in range(QUEUE_SIZE-1):
            q.put(i)
            self.assert_(not q.empty(), "Queue should not be empty")
        self.assert_(not q.full(), "Queue should not be full")
        q.put("last")
        self.assert_(q.full(), "Queue should be full")
        try:
            q.put("full")
            self.fail("Didn't appear to block with a full queue")
        except Full:
            pass

        # False is passed to the put() callback if it times out
        self.assertFalse((yield Task(q.put, "full", timeout=0.01)))
        self.assertEquals(q.qsize(), QUEUE_SIZE)
        # Test a blocking put
        yield Task(self.do_blocking_test, q.put, ("full",), {}, q.get, (), {})
        yield Task(self.do_blocking_test, q.put, ("full",), {'timeout': 10}, q.get, (), {})
        # Empty it
        for i in range(QUEUE_SIZE):
            q.get()
        self.assert_(q.empty(), "Queue should be empty")
        try:
            q.get()
            self.fail("Didn't appear to block with an empty queue")
        except Empty:
            pass
        # Empty is passed to the get() callback if it times out
        self.assertEqual(Empty, (yield Task(q.get, timeout=0.01)))
        # Test a blocking get
        yield Task(self.do_blocking_test, q.get, (), {}, q.put, ('empty',), {})
        yield Task(self.do_blocking_test, q.get, (), {'timeout': 10}, q.put, ('empty',), {})
        callback()

    simple_queue_test.__test__ = False # Hide from nose

    @async_test_engine()
    def test_simple_queue(self):
        # Do it a couple of times on the same queue.
        # Done twice to make sure works with same instance reused.
        q = self.type2test(QUEUE_SIZE)
        yield Task(self.simple_queue_test, q)
        yield Task(self.simple_queue_test, q)


class LifoQueueTest1(QueueTest1):
    type2test = toro.LifoQueue


class PriorityQueueTest1(QueueTest1):
    type2test = toro.PriorityQueue


class TestJoinableQueue1(unittest.TestCase):
    def setUp(self):
        self.cum = 0

    def test_queue_task_done(self):
        # Test to make sure a queue task completed successfully.
        q = toro.JoinableQueue()
        # XXX the same test in subclasses
        try:
            q.task_done()
        except ValueError:
            pass
        else:
            self.fail("Did not detect task count going negative")

    @gen.engine
    def worker(self, q):
        while True:
            x = yield Task(q.get)
            if x is None:
                q.task_done()
                break

            self.cum += x
            q.task_done()

    @gen.engine
    def queue_join_test(self, q, callback):
        self.cum = 0
        for i in (0,1):
            self.worker(q)
        for i in xrange(100):
            q.put(i)
        yield Task(q.join)
        self.assertEquals(self.cum, sum(range(100)),
                          "q.join() did not block until all tasks were done")
        for i in (0,1):
            q.put(None)         # instruct the tasks to end
        yield Task(q.join)      # verify that you can join twice
        callback()

    queue_join_test.__test__ = False # It's a utility, hide it from nosetests

    @async_test_engine()
    def test_queue_join(self):
        # Test that a queue join()s successfully, and before anything else
        # (done twice for insurance).
        q = toro.JoinableQueue()
        yield Task(self.queue_join_test, q)
        yield Task(self.queue_join_test, q)
        try:
            q.task_done()
        except ValueError:
            pass
        else:
            self.fail("Did not detect task count going negative")


# SECTION 2: Tests adapted from Gevent's test__queue.py (double underscore)

class TestQueue2(unittest.TestCase):
    def test_repr(self):
        # No exceptions
        str(toro.Queue())
        repr(toro.Queue())

    @async_test_engine()
    def test_send_first(self):
        q = toro.Queue()
        yield Task(q.put, 'hi')
        self.assertEqual('hi', (yield Task(q.get)))

    @async_test_engine()
    def test_send_last(self):
        q = toro.Queue()

        @gen.engine
        def f():
            val = yield Task(q.get)
            self.assertEqual('hi2', val)
            yield Task(q.put, 'ok')

        # Start a task; blocks yield Task(on.get) until we do a put()
        f()
        yield Task(q.put, 'hi2')
        self.assertEqual('ok', (yield Task(q.get)))

    @async_test_engine()
    def test_max_size(self):
        loop = IOLoop.instance()
        q = toro.Queue(2)
        results = []

        @gen.engine
        def putter(callback):
            yield Task(q.put, 'a')
            results.append('a')
            yield Task(q.put, 'b')
            results.append('b')
            yield Task(q.put, 'c')
            results.append('c')
            callback("OK")

        putter((yield gen.Callback('putter')))
        yield Task(loop.add_timeout, time.time() + .1)
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals((yield Task(q.get)), 'a')
        yield Task(loop.add_timeout, time.time() + .1)
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals((yield Task(q.get)), 'b')
        self.assertEquals((yield Task(q.get)), 'c')
        self.assertEquals("OK", (yield gen.Wait('putter')))

    @async_test_engine()
    def test_zero_max_size(self):
        loop = IOLoop.instance()
        q = toro.Queue(0)

        @gen.engine
        def sender(evt, q):
            yield Task(q.put, 'hi')
            evt.set('done')

        @gen.engine
        def receiver(evt, q):
            x = yield Task(q.get)
            evt.set(x)

        e1 = toro.AsyncResult()
        e2 = toro.AsyncResult()

        sender(e1, q)
        yield Task(loop.add_timeout, time.time() + .1)
        self.assertTrue(not e1.ready())
        receiver(e2, q)
        self.assertEquals((yield Task(e2.get)), 'hi')
        self.assertEquals((yield Task(e1.get)), 'done')

    @async_test_engine()
    def test_multiple_waiters(self):
        # tests that multiple waiters get their results back
        q = toro.Queue()

        @gen.engine
        def waiter(q, evt):
            evt.set((yield Task(q.get)))

        sendings = ['1', '2', '3', '4']
        evts = [toro.AsyncResult() for x in sendings]
        for i, x in enumerate(sendings):
            waiter(q, evts[i]) # start task

        @gen.engine
        def collect_pending_results(callback):
            results = set()
            for e in evts:
                if e.ready():
                    # Won't block
                    x = yield Task(e.get)
                    results.add(x)
            callback(len(results))

        yield Task(q.put, sendings[0])
        self.assertEquals((yield Task(collect_pending_results)), 1)
        yield Task(q.put, sendings[1])
        self.assertEquals((yield Task(collect_pending_results)), 2)
        yield Task(q.put, sendings[2])
        yield Task(q.put, sendings[3])
        self.assertEquals((yield Task(collect_pending_results)), 4)

    # Gevent's test_waiters_that_cancel isn't relevant to Toro
    #def test_waiters_that_cancel(self):

    @async_test_engine()
    def test_senders_that_die(self):
        q = toro.Queue()

        @gen.engine
        def do_send(q):
            yield Task(q.put, 'sent')

        do_send(q)
        self.assertEquals((yield Task(q.get)), 'sent')

    # Gevent's test_two_waiters_one_dies isn't relevant to Toro
    #def test_two_waiters_one_dies(self):

    # Gevent's test_two_bogus_waiters isn't relevant to Toro
    #def test_two_bogus_waiters(self):

    # TODO: test timeouts
    # TODO: test exception-throwing in callbacks
    # TODO: test StackContext-handling
    # TODO: test non-blocking puts and gets


class TestChannel2(unittest.TestCase):

    @async_test_engine()
    def test_send(self):
        channel = toro.Queue(0)

        events = []

        @gen.engine
        def another_task(callback):
            events.append((yield Task(channel.get)))
            events.append((yield Task(channel.get)))
            callback()

        another_task(callback=(yield gen.Callback('done')))

        events.append('sending')
        channel.put('hello')
        events.append('sent hello')
        channel.put('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)
        yield gen.Wait('done')

    @async_test_engine()
    def test_wait(self):
        channel = toro.Queue(0)
        events = []

        @gen.engine
        def another_task(callback):
            events.append('sending hello')
            yield Task(channel.put, 'hello')
            events.append('sending world')
            yield Task(channel.put, 'world')
            events.append('sent world')
            callback()

        another_task(callback=(yield gen.Callback('done')))

        events.append('waiting')
        events.append((yield Task(channel.get)))
        events.append((yield Task(channel.get)))

        self.assertEqual(['sending hello', 'waiting', 'hello', 'sending world', 'world'], events)
        yield Task(IOLoop.instance().add_timeout, time.time() + .1)
        self.assertEqual(['sending hello', 'waiting', 'hello', 'sending world', 'world', 'sent world'], events)
        yield gen.Wait('done')

    @async_test_engine()
    def test_task_done(self):
        channel = toro.JoinableQueue(0)
        X = object()
        channel.put(X, callback=(yield gen.Callback('put')))
        result = yield Task(channel.get)
        assert result is X, (result, X)
        assert channel.unfinished_tasks == 1, channel.unfinished_tasks
        channel.task_done()
        assert channel.unfinished_tasks == 0, channel.unfinished_tasks
        yield gen.Wait('put')


class TestNoWait2(unittest.TestCase):

    def test_put_nowait_simple(self):
        q = toro.Queue(1)
        q.put('hi')
        self.assertRaises(Full, q.put, 'bye')

    def test_get_nowait_simple(self):
        q = toro.Queue(1)
        q.put(4)
        self.assertEqual(4, q.get())
        self.assertRaises(Empty, q.get)

    @async_test_engine()
    def test_get_nowait_unlock(self):
        q = toro.Queue(0)

        q.put(5, callback=(yield gen.Callback('done')))

        assert q.empty(), q
        assert q.full(), q
        yield Task(IOLoop.instance().add_callback)
        assert q.empty(), q
        assert q.full(), q
        self.assertEqual(5, q.get())
        assert q.empty(), q
        assert q.full(), q
        yield gen.Wait('done')

    @async_test_engine()
    def test_put_nowait_unlock(self):
        q = toro.Queue(0)
        q.get(callback=(yield gen.Callback('get')))

        assert q.empty(), q
        assert q.full(), q
        yield Task(IOLoop.instance().add_callback)
        assert q.empty(), q
        assert q.full(), q
        q.put(10)
        assert q.full(), q
        assert q.empty(), q
        self.assertEqual(10, (yield gen.Wait('get')))
        assert q.full(), q
        assert q.empty(), q


class TestJoinEmpty2(unittest.TestCase):

    @async_test_engine()
    def test_issue_45(self):
        # Test that join() exits immediately if not jobs were put into the queue
        # From Gevent's test_issue_45()
        self.switch_expected = False
        q = toro.JoinableQueue()
        yield Task(q.join)


# SECTION 3: Tests written specifically for Toro
# TODO

class TestJoinableQueue3(unittest.TestCase):
    @async_test_engine()
    def test_queue_join_timeout(self):
        # Test that a queue join()s successfully, and before anything else
        # (done twice for insurance).
        q = toro.JoinableQueue()
        q.put(1)
        st = time.time()
        yield Task(q.join, timeout=.1)
        duration = time.time() - st
        self.assertAlmostEqual(.1, duration, places=2)
        self.assertEqual(1, q.unfinished_tasks)
