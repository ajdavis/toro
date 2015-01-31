"""A classic producer-consumer example for using :class:`~toro.Queue`."""

# start-file
from tornado import ioloop, gen
import toro

loop = ioloop.IOLoop.instance()
q = toro.Queue(maxsize=3)


@gen.coroutine
def consumer():
    while True:
        item = yield q.get()
        try:
            print 'Doing work on', item
        finally:
            q.task_done()


@gen.coroutine
def producer():
    for item in range(10):
        print 'Putting', item
        yield q.put(item)


@gen.coroutine
def main():
    producer()
    consumer()

    # Block until all tasks are done.
    yield q.join()

if __name__ == '__main__':
    loop.run_sync(main)
