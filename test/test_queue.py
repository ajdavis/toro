# TODO: complete test suite from gevent's test__queue.py
import time

from tornado import testing
from tornado import gen
from tornado.gen import Task
from tornado.ioloop import IOLoop

import toro
from test.async_test_engine import async_test_engine


# TODO: useful outside framework?
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

        def waiter(q, evt):
            evt.set((yield Task(q.get)))

        sendings = ['1', '2', '3', '4']
        evts = [AsyncResult() for x in sendings]
        for i, x in enumerate(sendings):
            gevent.spawn(waiter, q, evts[i])  # use waitall for them

        gevent.sleep(0.01)  # get 'em all waiting

        results = set()

        def collect_pending_results():
            for i, e in enumerate(evts):
                timer = gevent.Timeout.start_new(.1)
                try:
                    x = yield Task(e.get)
                    results.add(x)
                    timer.cancel()
                except gevent.Timeout:
                    pass  # no pending result at that event
#            return len(results)
        yield Task(q.put, sendings[0])
        self.assertEquals(collect_pending_results(), 1)
        yield Task(q.put, sendings[1])
        self.assertEquals(collect_pending_results(), 2)
        yield Task(q.put, sendings[2])
        yield Task(q.put, sendings[3])
        self.assertEquals(collect_pending_results(), 4)

    @async_test_engine()
    def test_waiters_that_cancel(self):
        q = toro.Queue()

        def do_receive(q, evt):
            gevent.Timeout.start_new(0, RuntimeError())
            try:
                result = yield Task(q.get)
                evt.set(result)
            except RuntimeError:
                evt.set('timed out')

        evt = AsyncResult()
        gevent.spawn(do_receive, q, evt)
        self.assertEquals((yield Task(evt.get)), 'timed out')

        yield Task(q.put, 'hi')
        self.assertEquals((yield Task(q.get)), 'hi')

    @async_test_engine()
    def test_senders_that_die(self):
        q = toro.Queue()

        def do_send(q):
            yield Task(q.put, 'sent')

        gevent.spawn(do_send, q)
        self.assertEquals((yield Task(q.get)), 'sent')

    @async_test_engine()
    def test_two_waiters_one_dies(self):

        def waiter(q, evt):
            evt.set((yield Task(q.get)))

        def do_receive(q, evt):
            timeout = gevent.Timeout.start_new(0, RuntimeError())
            try:
                try:
                    result = yield Task(q.get)
                    evt.set(result)
                except RuntimeError:
                    evt.set('timed out')
            finally:
                timeout.cancel()

        q = toro.Queue()
        dying_evt = AsyncResult()
        waiting_evt = AsyncResult()
        gevent.spawn(do_receive, q, dying_evt)
        gevent.spawn(waiter, q, waiting_evt)
        gevent.sleep(0)
        yield Task(q.put, 'hi')
        self.assertEquals((yield Task(dying_evt.get)), 'timed out')
        self.assertEquals((yield Task(waiting_evt.get)), 'hi')

    @async_test_engine()
    def test_two_bogus_waiters(self):
        def do_receive(q, evt):
            gevent.Timeout.start_new(0, RuntimeError())
            try:
                result = yield Task(q.get)
                evt.set(result)
            except RuntimeError:
                evt.set('timed out')
            # XXX finally = timeout

        q = toro.Queue()
        e1 = AsyncResult()
        e2 = AsyncResult()
        gevent.spawn(do_receive, q, e1)
        gevent.spawn(do_receive, q, e2)
        gevent.sleep(0)
        yield Task(q.put, 'sent')
        self.assertEquals((yield Task(e1.get)), 'timed out')
        self.assertEquals((yield Task(e2.get)), 'timed out')
        self.assertEquals((yield Task(q.get)), 'sent')


class TestChannel(testing.AsyncTestCase):

    @async_test_engine()
    def test_send(self):
        channel = toro.Queue(0)

        events = []

        def another_greenlet():
            events.append((yield Task(channel.get)))
            events.append((yield Task(channel.get)))

        g = gevent.spawn(another_greenlet)

        events.append('sending')
        channel.put('hello')
        events.append('sent hello')
        channel.put('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)
        yield Task(g.get)

    @async_test_engine()
    def test_wait(self):
        channel = toro.Queue(0)
        events = []

        def another_greenlet():
            events.append('sending hello')
            channel.put('hello')
            events.append('sending world')
            channel.put('world')
            events.append('sent world')

        g = gevent.spawn(another_greenlet)

        events.append('waiting')
        events.append((yield Task(channel.get)))
        events.append((yield Task(channel.get)))

        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world'], events)
        gevent.sleep(0)
        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world', 'sent world'], events)
        yield Task(g.get)

    @async_test_engine()
    def test_task_done(self):
        channel = queue.JoinableQueue(0)
        X = object()
        gevent.spawn(channel.put, X)
        result = yield Task(channel.get)
        assert result is X, (result, X)
        assert channel.unfinished_tasks == 1, channel.unfinished_tasks
        channel.task_done()
        assert channel.unfinished_tasks == 0, channel.unfinished_tasks


class TestNoWait(testing.AsyncTestCase):

    @async_test_engine()
    def test_put_nowait_simple(self):
        result = []
        q = toro.Queue(1)

        def store_result(func, *args):
            result.append(func(*args))

        core.active_event(store_result, util.wrap_errors(Exception, q.put_nowait), 2)
        core.active_event(store_result, util.wrap_errors(Exception, q.put_nowait), 3)
        gevent.sleep(0)
        assert len(result) == 2, result
        assert result[0] == None, result
        assert isinstance(result[1], queue.Full), result

    @async_test_engine()
    def test_get_nowait_simple(self):
        result = []
        q = toro.Queue(1)
        yield Task(q.put, 4)

        def store_result(func, *args):
            result.append(func(*args))

        core.active_event(store_result, util.wrap_errors(Exception, q.get_nowait))
        core.active_event(store_result, util.wrap_errors(Exception, q.get_nowait))
        gevent.sleep(0)
        assert len(result) == 2, result
        assert result[0] == 4, result
        assert isinstance(result[1], queue.Empty), result

    # get_nowait must work from the mainloop
    @async_test_engine()
    def test_get_nowait_unlock(self):
        result = []
        q = toro.Queue(0)
        p = gevent.spawn(q.put, 5)

        def store_result(func, *args):
            result.append(func(*args))

        assert q.empty(), q
        assert q.full(), q
        gevent.sleep(0)
        assert q.empty(), q
        assert q.full(), q
        core.active_event(store_result, util.wrap_errors(Exception, q.get_nowait))
        gevent.sleep(0)
        assert q.empty(), q
        assert q.full(), q
        assert result == [5], result
        assert p.ready(), p
        assert p.dead, p
        assert q.empty(), q

    # put_nowait must work from the mainloop
    @async_test_engine()
    def test_put_nowait_unlock(self):
        result = []
        q = toro.Queue(0)
        p = gevent.spawn(q.get)

        def store_result(func, *args):
            result.append(func(*args))

        assert q.empty(), q
        assert q.full(), q
        gevent.sleep(0)
        assert q.empty(), q
        assert q.full(), q
        core.active_event(store_result, util.wrap_errors(Exception, q.put_nowait), 10)
        assert not p.ready(), p
        gevent.sleep(0)
        assert result == [None], result
        assert p.ready(), p
        assert q.full(), q
        assert q.empty(), q


class TestJoinEmpty(testing.AsyncTestCase):

    @async_test_engine()
    def test_issue_45(self):
        """Test that join() exits immediatelly if not jobs were put into the queue"""
        self.switch_expected = False
        q = queue.JoinableQueue()
        q.join()
