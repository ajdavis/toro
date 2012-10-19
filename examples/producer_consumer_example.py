"""A classic producer-consumer example for using :class:`~toro.JoinableQueue`.

(Inspired by `Gevent's example <http://www.gevent.org/gevent.queue.html>`_.)
"""

# start-file
from tornado import ioloop, gen
import toro

q = toro.JoinableQueue(maxsize=3)

@gen.engine
def consumer():
    while True:
        item = yield gen.Task(q.get)
        try:
            print 'Doing work on', item
        finally:
            q.task_done()

@gen.engine
def producer():
    for item in range(10):
        yield gen.Task(q.put, item)

producer()
consumer()
loop = ioloop.IOLoop.instance()
q.join(callback=loop.stop) # block until all tasks are done
loop.start()
