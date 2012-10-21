"""
Test toro.Queue.

There are three sections, one each for tests that are
1. adapted from Gevent's test_queue.py, except for FailingQueueTest of which I
   don't understand the purpose,
2. adapted from Gevent's test__queue.py,
3. written specifically for Toro.
"""
from __future__ import with_statement

from datetime import timedelta
import time
import unittest
from Queue import Empty, Full

from tornado import gen, stack_context
from tornado.gen import Task
from tornado.ioloop import IOLoop

import toro

from test import make_callback, BaseToroCommonTest
from test.async_test_engine import async_test_engine

# SECTION 1: Tests adapted from Gevent's test_queue.py (single underscore)

QUEUE_SIZE = 5


class _TriggerTask(object):
    def __init__(self, fn, args, kwargs):
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.startedEvent = toro.Event()
        IOLoop.instance().add_timeout(time.time() + 0.01, self.run)

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
        if not self.t.startedEvent.is_set():
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
            if not self.t.startedEvent.is_set():
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
        self.assertEqual(Full, (yield Task(
            q.put, "full", deadline=timedelta(seconds=0.01))))
        self.assertEquals(q.qsize(), QUEUE_SIZE)
        # Test a blocking put
        yield Task(self.do_blocking_test, q.put, ("full",), {}, q.get, (), {})
        yield Task(self.do_blocking_test, q.put,
            ("full",), {'deadline': timedelta(seconds=10)}, q.get, (), {})
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
        self.assertEqual(Empty, (yield Task(
            q.get, deadline=timedelta(seconds=0.01))))
        # Test a blocking get
        yield Task(self.do_blocking_test, q.get, (), {}, q.put, ('empty',), {})
        yield Task(self.do_blocking_test, q.get,
            (), {'deadline': timedelta(seconds=10)}, q.put, ('empty',), {})
        callback()

    simple_queue_test.__test__ = False # Hide from nose

    @async_test_engine()
    def test_simple_queue(self, done):
        # Do it a couple of times on the same queue.
        # Done twice to make sure works with same instance reused.
        q = self.type2test(QUEUE_SIZE)
        yield Task(self.simple_queue_test, q)
        yield Task(self.simple_queue_test, q)
        done()

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
    def test_queue_join(self, done):
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
        done()


# SECTION 2: Tests adapted from Gevent's test__queue.py (double underscore)

class TestQueue2(unittest.TestCase):
    def test_repr(self):
        # No exceptions
        str(toro.Queue())
        repr(toro.Queue())

    @async_test_engine()
    def test_send_first(self, done):
        q = toro.Queue()
        yield Task(q.put, 'hi')
        self.assertEqual('hi', (yield Task(q.get)))
        done()

    @async_test_engine()
    def test_send_last(self, done):
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
        done()

    @async_test_engine()
    def test_max_size(self, done):
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
        yield Task(loop.add_timeout, time.time() + .01)
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals((yield Task(q.get)), 'a')
        yield Task(loop.add_timeout, time.time() + .01)
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals((yield Task(q.get)), 'b')
        self.assertEquals((yield Task(q.get)), 'c')
        self.assertEquals("OK", (yield gen.Wait('putter')))
        done()

    @async_test_engine()
    def test_zero_max_size(self, done):
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
        yield Task(loop.add_timeout, time.time() + .01)
        self.assertTrue(not e1.ready())
        receiver(e2, q)
        self.assertEquals((yield Task(e2.get)), 'hi')
        self.assertEquals((yield Task(e1.get)), 'done')
        done()

    @async_test_engine()
    def test_multiple_waiters(self, done):
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
        done()

    # Gevent's test_waiters_that_cancel isn't relevant to Toro
    #def test_waiters_that_cancel(self):

    @async_test_engine()
    def test_senders_that_die(self, done):
        q = toro.Queue()

        @gen.engine
        def do_send(q):
            yield Task(q.put, 'sent')

        do_send(q)
        self.assertEquals((yield Task(q.get)), 'sent')
        done()

    # Gevent's test_two_waiters_one_dies isn't relevant to Toro
    #def test_two_waiters_one_dies(self):

    # Gevent's test_two_bogus_waiters isn't relevant to Toro
    #def test_two_bogus_waiters(self):


class TestChannel2(unittest.TestCase):

    @async_test_engine()
    def test_send(self, done):
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
        done()

    @async_test_engine()
    def test_wait(self, done):
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
        yield Task(IOLoop.instance().add_timeout, time.time() + .01)
        self.assertEqual(['sending hello', 'waiting', 'hello', 'sending world', 'world', 'sent world'], events)
        yield gen.Wait('done')
        done()

    @async_test_engine()
    def test_task_done(self, done):
        channel = toro.JoinableQueue(0)
        X = object()
        channel.put(X, callback=(yield gen.Callback('put')))
        result = yield Task(channel.get)
        assert result is X, (result, X)
        assert channel.unfinished_tasks == 1, channel.unfinished_tasks
        channel.task_done()
        assert channel.unfinished_tasks == 0, channel.unfinished_tasks
        yield gen.Wait('put')
        done()


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
    def test_get_nowait_unlock(self, done):
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
        done()

    @async_test_engine()
    def test_put_nowait_unlock(self, done):
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
        done()


class TestJoinEmpty2(unittest.TestCase):

    @async_test_engine()
    def test_issue_45(self, done):
        # Test that join() exits immediately if not jobs were put into the queue
        # From Gevent's test_issue_45()
        self.switch_expected = False
        q = toro.JoinableQueue()
        yield Task(q.join)
        done()


# SECTION 3: Tests written specifically for Toro

def bad_get_callback(item):
    raise Exception('Intentional exception in get callback')


def bad_put_callback(success):
    raise Exception('Intentional exception in put callback')


class TestQueue3(unittest.TestCase):
    def test_str(self):
        self.assertTrue('Queue' in str(toro.Queue()))
        self.assertTrue('maxsize=11' in str(toro.Queue(11)))

        q = toro.Queue(0)
        for i in range(7):
            q.get(callback=lambda value: None)
        self.assertTrue('getters[7]' in str(q))

        q = toro.Queue(0)
        for i in range(5):
            q.put('foo', callback=lambda value: None)
        self.assertTrue('putters[5]' in str(q))

        q = toro.Queue(1)
        self.assertFalse('queue=' in str(q))
        q.put('foo')
        self.assertTrue('queue=' in str(q))

    def test_maxsize(self):
        self.assertRaises(ValueError, toro.Queue, -1)

    def test_full(self):
        self.assertTrue(toro.Queue(0).full())
        self.assertFalse(toro.Queue().full())

        q = toro.Queue(1)
        self.assertFalse(q.full())
        q.put('foo')
        self.assertTrue(q.full())

    def test_callback_checking(self):
        self.assertRaises(TypeError, toro.Queue().get, callback='foo')
        self.assertRaises(TypeError, toro.Queue().get, callback=1)

    def test_io_loop(self):
        global_loop = IOLoop.instance()
        custom_loop = IOLoop()
        self.assertNotEqual(global_loop, custom_loop)
        q = toro.Queue(None, io_loop=custom_loop)

        def callback(v):
            assert v == 'foo'
            custom_loop.stop()

        q.get(callback)
        q.put('foo')
        custom_loop.start()


class TestQueueTimeouts3(unittest.TestCase):
    @async_test_engine()
    def test_get_timeout(self, done):
        q = toro.Queue()

        # Empty Queue returns Empty if get() times out
        st = time.time()
        self.assertEqual(
            Empty, (yield Task(q.get, deadline=timedelta(seconds=.01))))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)

        # Make sure that putting and getting a value returns Queue to initial
        # state
        q.put(1)
        self.assertEqual(
            1, (yield Task(q.get, deadline=timedelta(seconds=.01))))

        # Queue *still* returns Empty if get() times out
        st = time.time()
        self.assertEqual(
            Empty, (yield Task(q.get, deadline=timedelta(seconds=.01))))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        done()

    @async_test_engine()
    def test_put_timeout(self, done):
        q = toro.Queue(1)
        q.put(1)

        # Full Queue returns False if put() times out
        st = time.time()
        self.assertEqual(
            Full, (yield Task(q.put, 2, deadline=timedelta(seconds=.01))))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)

        # Make sure that getting and putting a value returns Queue to initial
        # state
        self.assertEqual(1, q.get())
        self.assertEqual(
            True, (yield Task(q.put, 1, deadline=timedelta(seconds=.01))))

        # Full Queue *still* returns False if put() times out
        st = time.time()
        self.assertEqual(
            Full, (yield Task(q.put, 2, deadline=timedelta(seconds=.01))))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        done()


class TestQueueCallbackExceptions3(unittest.TestCase):
    """
    Test what happens when callbacks passed to get() or put() raise
    exceptions
    """
    @gen.engine
    def _test_exceptional_get_callback(self, qsize, deadline, callback):
        q = toro.Queue(qsize)
        while q.qsize() < qsize:
            q.put(None)

        # Block
        q.put(1, callback=(yield gen.Callback('put')), deadline=deadline)
        q.get(bad_get_callback)

        # Put should complete anyway
        self.assertTrue((yield gen.Wait('put')))
        self.assertEqual(qsize, q.qsize())
        callback()

    @gen.engine
    def _test_exceptional_put_callback(self, qsize, deadline, callback):
        q = toro.Queue(qsize)

        q.get(callback=(yield gen.Callback('get')), deadline=deadline) # Block
        q.put(1, bad_put_callback)

        # Get should complete anyway
        self.assertEqual(1, (yield gen.Wait('get')))
        self.assertEqual(0, q.qsize())
        callback()

    @async_test_engine()
    def test_exceptional_get_callback(self, done):
        yield Task(self._test_exceptional_get_callback, 10, None)
        done()

    @async_test_engine()
    def test_exceptional_get_callback_timeout(self, done):
        deadline = timedelta(seconds=0.1)
        yield Task(self._test_exceptional_get_callback, 10, deadline)
        done()

    @async_test_engine()
    def test_channel_exceptional_get_callback(self, done):
        yield Task(self._test_exceptional_get_callback, 0, None)
        done()

    @async_test_engine()
    def test_channel_exceptional_get_callback_timeout(self, done):
        deadline = timedelta(seconds=0.1)
        yield Task(self._test_exceptional_get_callback, 0, deadline)
        done()

    @async_test_engine()
    def test_exceptional_put_callback(self, done):
        yield Task(self._test_exceptional_put_callback, 10, None)
        done()

    @async_test_engine()
    def test_exceptional_put_callback_timeout(self, done):
        deadline = timedelta(seconds=0.1)
        yield Task(self._test_exceptional_put_callback, 10, deadline)
        done()

    @async_test_engine()
    def test_channel_exceptional_put_callback(self, done):
        yield Task(self._test_exceptional_put_callback, 0, None)
        done()

    @async_test_engine()
    def test_channel_exceptional_put_callback_timeout(self, done):
        deadline = timedelta(seconds=0.1)
        yield Task(self._test_exceptional_put_callback, 0, deadline)
        done()

    def test_stack_context(self):
        # Test that raising an exception from a get() callback doesn't
        # propagate up to put()'s caller, and that StackContexts are correctly
        # managed
        queue = toro.Queue()
        loop = IOLoop.instance()
        loop.add_timeout(time.time() + .02, loop.stop)

        # Absent Python 3's nonlocal keyword, we need some place to store
        # results from inner functions
        outcomes = {
            'value': None,
            'put_exc': None,
            'get_exc': None,
        }

        def put():
            try:
                queue.put('hello')
            except Exception, e:
                outcomes['put_exc'] = e

        def callback(value):
            outcomes['value'] = value
            assert False

        def catch_get_exception(type, value, traceback):
            outcomes['get_exc'] = type

        with stack_context.ExceptionStackContext(catch_get_exception):
            queue.get(callback)

        loop.add_timeout(time.time() + .01, put)
        loop.start()
        self.assertEqual(outcomes['value'], 'hello')
        self.assertEqual(outcomes['get_exc'], AssertionError)
        self.assertEqual(outcomes['put_exc'], None)


class TestJoinableQueue3(unittest.TestCase):
    def test_str(self):
        q = toro.JoinableQueue()
        self.assertTrue('JoinableQueue' in str(q))
        self.assertFalse('tasks' in str(q))
        q.put('foo')
        self.assertTrue('tasks' in str(q))

    @async_test_engine()
    def test_queue_join(self, done):
        q = toro.JoinableQueue()
        q.put('foo')
        q.put('bar')
        self.assertEqual(2, q.unfinished_tasks)
        q.join(callback=(yield gen.Callback('join')))

        q.task_done()
        self.assertEqual(1, q.unfinished_tasks)
        q.task_done()
        self.assertEqual(0, q.unfinished_tasks)

        yield gen.Wait('join')
        done()

    @async_test_engine()
    def test_queue_join_callback(self, done):
        # Test that callbacks passed to join() run immediately after task_done()
        q = toro.JoinableQueue()
        history = []
        q.put('foo')
        q.put('foo')
        q.join(make_callback('join', history))
        q.task_done()
        history.append('task_done1')
        q.task_done()
        history.append('task_done2')
        self.assertEqual(['task_done1', 'join', 'task_done2'], history)
        done()

    @async_test_engine()
    def test_queue_join_timeout(self, done):
        q = toro.JoinableQueue()
        q.put(1)
        st = time.time()
        yield Task(q.join, deadline=timedelta(seconds=.01))
        duration = time.time() - st
        self.assertAlmostEqual(.01, duration, places=2)
        self.assertEqual(1, q.unfinished_tasks)
        done()


class TestQueueCommon(unittest.TestCase, BaseToroCommonTest):
    def toro_object(self, io_loop=None):
        return toro.Queue(io_loop=io_loop)

    def notify(self, toro_object, value):
        toro_object.put(value)

    def wait(self, toro_object, callback, deadline):
        toro_object.get(callback, deadline)
