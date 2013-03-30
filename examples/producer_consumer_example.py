"""A classic producer-consumer example for using :class:`~toro.JoinableQueue`.

(Inspired by `Gevent's example <http://www.gevent.org/gevent.queue.html>`_.)
"""

# start-file
from tornado import ioloop, gen
import toro
q = toro.JoinableQueue(maxsize=3)

@gen.engine
def producer():
    for item in range(10):
        print 'Sending', item
        yield gen.Task(q.put, item)

@gen.engine
def consumer():
    while True:
        item = yield gen.Task(q.get)
        print '\t\t', 'Got', item
        q.task_done()

producer()
consumer()
loop = ioloop.IOLoop.instance()
# block until all tasks are done
q.join(callback=loop.stop)
loop.start()