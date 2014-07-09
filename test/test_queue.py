"""
Test toro.Queue.

There are three sections, one each for tests that are
1. adapted from Gevent's test_queue.py, except for FailingQueueTest which
    isn't applicable
2. adapted from Gevent's test__queue.py,
3. written specifically for Toro.
"""

import time
from datetime import timedelta
from Queue import Empty, Full

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.testing import gen_test, AsyncTestCase


import toro
from test import make_callback, assert_raises, pause

# TODO: update from tulip tests

# SECTION 1: Tests adapted from Gevent's test_queue.py (single underscore)

QUEUE_SIZE = 5


class QueueTest1(AsyncTestCase):
    type2test = toro.Queue

    @gen.coroutine
    def simple_queue_test(self, q):
        if not q.empty():
            raise RuntimeError("Call this function with an empty queue")
        # I guess we better check things actually queue correctly a little :)
        q.put_nowait(111)
        q.put_nowait(333)
        q.put_nowait(222)
        target_order = dict(Queue=[111, 333, 222],
                            LifoQueue=[222, 333, 111],
                            PriorityQueue=[111, 222, 333])
        actual_order = [q.get_nowait(), q.get_nowait(), q.get_nowait()]
        self.assertEquals(actual_order, target_order[q.__class__.__name__],
                          "Didn't seem to queue the correct data!")
        for i in range(QUEUE_SIZE-1):
            q.put_nowait(i)
            self.assert_(not q.empty(), "Queue should not be empty")
        self.assert_(not q.full(), "Queue should not be full")
        q.put_nowait(444)
        self.assert_(q.full(), "Queue should be full")
        try:
            q.put_nowait(555)
            self.fail("Didn't appear to block with a full queue")
        except Full:
            pass

        with assert_raises(toro.Timeout):
            yield q.put(555, deadline=timedelta(seconds=0.01))

        self.assertEquals(q.qsize(), QUEUE_SIZE)
        # Empty it
        for i in range(QUEUE_SIZE):
            q.get_nowait()
        self.assert_(q.empty(), "Queue should be empty")
        try:
            q.get_nowait()
            self.fail("Didn't appear to block with an empty queue")
        except Empty:
            pass

        with assert_raises(toro.Timeout):
            yield q.get(deadline=timedelta(seconds=0.01))

    simple_queue_test.__test__ = False  # Hide from nose

    @gen_test
    def test_simple_queue(self):
        # Do it a couple of times on the same queue.
        # Done twice to make sure works with same instance reused.
        q = self.type2test(QUEUE_SIZE)
        yield self.simple_queue_test(q)
        yield self.simple_queue_test(q)


class LifoQueueTest1(QueueTest1):
    type2test = toro.LifoQueue


class PriorityQueueTest1(QueueTest1):
    type2test = toro.PriorityQueue


class TestJoinableQueue1(AsyncTestCase):
    def setUp(self):
        super(TestJoinableQueue1, self).setUp()
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

    @gen.coroutine
    def worker(self, q):
        while True:
            x = yield q.get()
            if x is None:
                q.task_done()
                break

            self.cum += x
            q.task_done()

    @gen.coroutine
    def queue_join_test(self, q):
        self.cum = 0
        for i in (0,1):
            self.worker(q)
        for i in xrange(100):
            q.put(i)
        yield q.join()
        self.assertEquals(self.cum, sum(range(100)),
                          "q.join() did not block until all tasks were done")
        for i in (0,1):
            q.put(None)         # instruct the tasks to end
        yield q.join()          # verify that you can join twice

    queue_join_test.__test__ = False # It's a utility, hide it from nosetests

    @gen_test
    def test_queue_join(self):
        # Test that a queue join()s successfully, and before anything else
        # (done twice for insurance).
        q = toro.JoinableQueue()
        yield self.queue_join_test(q)
        yield self.queue_join_test(q)
        try:
            q.task_done()
        except ValueError:
            pass
        else:
            self.fail("Did not detect task count going negative")


# SECTION 2: Tests adapted from Gevent's test__queue.py (double underscore)

class TestQueue2(AsyncTestCase):
    def test_repr(self):
        # No exceptions
        str(toro.Queue())
        repr(toro.Queue())

    @gen_test
    def test_send_first(self):
        q = toro.Queue()
        yield q.put('hi')
        self.assertEqual('hi', (yield q.get()))

    @gen_test
    def test_send_last(self):
        q = toro.Queue()

        @gen.coroutine
        def f():
            val = yield q.get()
            self.assertEqual('hi2', val)
            yield q.put('ok')

        # Start a task; blocks on get() until we do a put()
        f()
        yield q.put('hi2')
        self.assertEqual('ok', (yield q.get()))

    @gen_test
    def test_max_size(self):
        q = toro.Queue(2)
        results = []

        @gen.coroutine
        def putter():
            yield q.put('a')
            results.append('a')
            yield q.put('b')
            results.append('b')
            yield q.put('c')
            results.append('c')

        future = putter()
        yield pause(timedelta(seconds=.01))
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals((yield q.get()), 'a')
        yield pause(timedelta(seconds=.01))
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals((yield q.get()), 'b')
        self.assertEquals((yield q.get()), 'c')
        yield future

    @gen_test
    def test_multiple_waiters(self):
        # tests that multiple waiters get their results back
        q = toro.Queue()

        @gen.coroutine
        def waiter(q, evt):
            evt.set((yield q.get()))

        sendings = ['1', '2', '3', '4']
        evts = [toro.AsyncResult() for x in sendings]
        for i, x in enumerate(sendings):
            waiter(q, evts[i]) # start task

        @gen.coroutine
        def collect_pending_results():
            results = set()
            for e in evts:
                if e.ready():
                    # Won't block
                    x = yield e.get()
                    results.add(x)
            raise gen.Return(len(results))

        yield q.put(sendings[0])
        yield pause(timedelta(seconds=.01))
        self.assertEquals((yield collect_pending_results()), 1)
        yield q.put(sendings[1])
        yield pause(timedelta(seconds=.01))
        self.assertEquals((yield collect_pending_results()), 2)
        yield q.put(sendings[2])
        yield q.put(sendings[3])
        yield pause(timedelta(seconds=.01))
        self.assertEquals((yield collect_pending_results()), 4)

    @gen_test
    def test_senders_that_die(self):
        q = toro.Queue()

        @gen.coroutine
        def do_send(q):
            yield q.put('sent')

        future = do_send(q)
        self.assertEquals((yield q.get()), 'sent')
        yield future


class TestJoinEmpty2(AsyncTestCase):

    @gen_test
    def test_issue_45(self):
        # Test that join() exits immediately if not jobs were put into the queue
        # From Gevent's test_issue_45()
        self.switch_expected = False
        q = toro.JoinableQueue()
        yield q.join()


# SECTION 3: Tests written specifically for Toro

def bad_get_callback(_):
    raise Exception('Intentional exception in get callback')


def bad_put_callback(_):
    raise Exception('Intentional exception in put callback')


class TestQueue3(AsyncTestCase):
    def test_str(self):
        self.assertTrue('Queue' in str(toro.Queue()))
        self.assertTrue('maxsize=11' in str(toro.Queue(11)))

        q = toro.Queue()
        for i in range(7):
            q.get()
        self.assertTrue('getters[7]' in str(q))

        q = toro.Queue(1)
        for i in range(5):
            q.put('foo')
        self.assertTrue('putters[4]' in str(q))

        q = toro.Queue(1)
        self.assertFalse('queue=' in str(q))
        q.put('foo')
        self.assertTrue('queue=' in str(q))

    def test_maxsize(self):
        self.assertRaises(TypeError, toro.Queue, None)
        self.assertRaises(ValueError, toro.Queue, -1)

    def test_full(self):
        q = toro.Queue()
        self.assertFalse(q.full())
        self.assertEqual(q.maxsize, 0)

        q = toro.Queue(1)
        self.assertEqual(q.maxsize, 1)
        self.assertFalse(q.full())
        q.put('foo')
        self.assertTrue(q.full())

    def test_callback_checking(self):
        self.assertRaises(TypeError, toro.Queue().get, callback='foo')
        self.assertRaises(TypeError, toro.Queue().get, callback=1)

    def test_io_loop(self):
        global_loop = self.io_loop
        custom_loop = IOLoop()
        self.assertNotEqual(global_loop, custom_loop)
        q = toro.Queue(io_loop=custom_loop)

        def callback(future):
            assert future.result() == 'foo'
            custom_loop.stop()

        q.get().add_done_callback(callback)
        q.put('foo')
        custom_loop.start()

    @gen_test
    def test_float_maxsize(self):
        # Adapted from asyncio's test_float_maxsize.
        q = toro.Queue(maxsize=1.3, io_loop=self.io_loop)
        q.put_nowait(1)
        q.put_nowait(2)
        self.assertTrue(q.full())
        self.assertRaises(Full, q.put_nowait, 3)

        q = toro.Queue(maxsize=1.3, io_loop=self.io_loop)
        yield q.put(1)
        yield q.put(2)
        self.assertTrue(q.full())


class TestQueueTimeouts3(AsyncTestCase):
    @gen_test
    def test_get_timeout(self):
        q = toro.Queue()
        st = time.time()
        with assert_raises(toro.Timeout):
            yield q.get(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)

        # Make sure that putting and getting a value returns Queue to initial
        # state
        q.put(1)
        self.assertEqual(
            1, (yield q.get(deadline=timedelta(seconds=0.1))))

        st = time.time()
        with assert_raises(toro.Timeout):
            yield q.get(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)

    @gen_test
    def test_put_timeout(self):
        q = toro.Queue(1)
        q.put(1)
        st = time.time()
        with assert_raises(toro.Timeout):
            yield q.put(2, deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)

        # Make sure that getting and putting a value returns Queue to initial
        # state
        self.assertEqual(1, (yield q.get()))
        yield q.put(1, deadline=timedelta(seconds=0.1))

        st = time.time()
        with assert_raises(toro.Timeout):
            yield q.put(2, deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)


class TestJoinableQueue3(AsyncTestCase):
    def test_str(self):
        q = toro.JoinableQueue()
        self.assertTrue('JoinableQueue' in str(q))
        self.assertFalse('tasks' in str(q))
        q.put('foo')
        self.assertTrue('tasks' in str(q))

    @gen_test
    def test_queue_join(self):
        q = toro.JoinableQueue()
        yield q.put('foo')
        yield q.put('bar')
        self.assertEqual(2, q.unfinished_tasks)
        future = q.join()

        q.task_done()
        self.assertEqual(1, q.unfinished_tasks)
        q.task_done()
        self.assertEqual(0, q.unfinished_tasks)
        yield future

    @gen_test
    def test_queue_join_callback(self):
        # Test that callbacks passed to join() run immediately after task_done()
        q = toro.JoinableQueue()
        history = []
        q.put('foo')
        q.put('foo')
        q.join().add_done_callback(make_callback('join', history))
        q.task_done()
        history.append('task_done1')
        q.task_done()
        history.append('task_done2')
        self.assertEqual(['task_done1', 'join', 'task_done2'], history)

    @gen_test
    def test_queue_join_timeout(self):
        q = toro.JoinableQueue()
        q.put(1)
        st = time.time()
        with assert_raises(toro.Timeout):
            yield q.join(deadline=timedelta(seconds=0.1))

        duration = time.time() - st
        self.assertAlmostEqual(0.1, duration, places=1)
        self.assertEqual(1, q.unfinished_tasks)

    def test_io_loop(self):
        global_loop = self.io_loop
        custom_loop = IOLoop()
        self.assertNotEqual(global_loop, custom_loop)
        q = toro.JoinableQueue(io_loop=custom_loop)

        def callback(future):
            assert future.result() == 'foo'
            custom_loop.stop()

        q.get().add_done_callback(callback)
        q.put('foo')
        custom_loop.start()

    @gen_test
    def test_queue_join_clear(self):
        # Verify that join() blocks again after a task is added
        q = toro.JoinableQueue()
        q.put_nowait('foo')
        q.task_done()

        # The _finished Event is set
        yield q.join()
        yield q.join()

        # Unset the event
        q.put_nowait('bar')

        with assert_raises(toro.Timeout):
            yield q.join(deadline=timedelta(seconds=0.1))

        q.task_done()
        yield q.join()  # The Event is set again.
