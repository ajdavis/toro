"""A producer-consumer example for using :class:`~toro.JoinableQueue` with
callbacks instead of with gen_. This is provided simply to prove that using
Toro with explicit callbacks instead of coroutines is *possible*; see
:doc:`../examples/producer_consumer_example` for a much simpler approach using
coroutines.

.. _gen: http://www.tornadoweb.org/documentation/gen.html
"""

# start-file
from tornado import ioloop
import toro

q = toro.JoinableQueue(maxsize=3)

def consumer(item):
    print 'Doing work on', item
    q.task_done()
    q.get(callback=consumer)

item_index = 0

# 'success' is always True; if we set a deadline it could be False after a
# timeout
def producer(success=True):
    global item_index
    if item_index < 10:
        item = item_index
        item_index += 1
        q.put(item, callback=producer)

# Start producer and consumer
producer()
q.get(callback=consumer)
loop = ioloop.IOLoop.instance()
q.join(callback=loop.stop) # block until all tasks are done
loop.start()
