"""A classic producer-consumer example for using :class:`~toro.JoinableQueue`.

(Inspired by `Gevent's example <http://www.gevent.org/gevent.queue.html>`_.)
"""

# start-file
from tornado import ioloop, gen
import toro
q = toro.JoinableQueue(maxsize=3)


@gen.coroutine
def producer():
    for item in range(10):
        print 'Sending', item
        yield q.put(item)


@gen.coroutine
def consumer():
    while True:
        item = yield q.get()
        print '\t\t', 'Got', item
        q.task_done()


producer()
consumer()
loop = ioloop.IOLoop.current()


def stop(future):
    loop.stop()
    future.result()  # Raise error if there is one

# block until all tasks are done
q.join().add_done_callback(stop)
loop.start()
