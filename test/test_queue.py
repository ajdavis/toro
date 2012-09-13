# TODO: complete test suite from gevent's test__queue.py
import time
from Queue import Empty, Full

from tornado import testing
from tornado import gen
from tornado.gen import Task
from tornado.ioloop import IOLoop

import toro
from test.async_test_engine import async_test_engine


# TODO: move to __init__, copy Gevent's docs for this
class AsyncResult(object):
    def __init__(self):
        self._ready = False
        self.value = None
        self.callback = None

    def set(self, value):
        self.value = value
        self._ready = True
        if self.callback:
            callback, self.callback = self.callback, None
            callback(self.value)

    def ready(self):
        return self._ready

    def get(self, callback):
        if self.ready():
            callback(self.value)
        else:
            self.callback = callback


class TestQueue(testing.AsyncTestCase):
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

        e1 = AsyncResult()
        e2 = AsyncResult()

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
        evts = [AsyncResult() for x in sendings]
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


class TestChannel(testing.AsyncTestCase):

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


class TestNoWait(testing.AsyncTestCase):

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


class TestJoinEmpty(testing.AsyncTestCase):

    @async_test_engine()
    def test_issue_45(self):
        """Test that join() exits immediatelly if not jobs were put into the queue"""
        self.switch_expected = False
        q = queue.JoinableQueue()
        q.join()
