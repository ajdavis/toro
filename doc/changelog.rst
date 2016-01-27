Changelog
=========

.. module:: toro

Changes in Version 1.0.1
------------------------

Bug fix in :class:`~toro.RWLock`: when max_readers > 1
:meth:`~toro.RWLock.release_read` must release one reader
in case :meth:`~toro.RWLock.acquire_read` was called at least once::

    @gen.coroutine
    def coro():
        lock = toro.RWLock(max_readers=10)
        assert not lock.locked()

        yield lock.acquire_read()
        lock.release_read()

But, in old version :meth:`~toro.RWLock.release_read` raises RuntimeException
if a lock in unlocked state, even if :meth:`~toro.RWLock.acquire_read`
was already called several times.

Patch by `Alexander Gridnev <https://github.com/alexander-gridnev>`_.


Changes in Version 1.0
----------------------

This is the final release of Toro. Its features are merged into Tornado 4.2.
Further development of locks and queues for Tornado coroutines will continue
in Tornado.

For more information on the end of Toro,
`read my article <http://emptysqua.re/blog/tornado-locks-and-queues/>`_.
The Tornado changelog has comprehensive instructions on
`porting from Toro's locks and queues to Tornado 4.2 locks and queues
<http://www.tornadoweb.org/en/stable/releases/v4.2.0.html#new-modules-tornado-locks-and-tornado-queues>`_.

Toro 1.0 has one new feature, an :class:`.RWLock` contributed by
`Alexander Gridnev <https://github.com/alexander-gridnev>`_.
:class:`.RWLock` has *not* been merged into Tornado.


Changes in Version 0.8
----------------------

Don't depend on "nose" for tests. Improve test quality and coverage.
Delete unused method in internal ``_TimeoutFuture`` class.


Changes in Version 0.7
----------------------

Bug fix in :class:`~toro.Semaphore`: after a call to
:meth:`~toro.Semaphore.acquire`, :meth:`~toro.Semaphore.wait` should block
until another coroutine calls :meth:`~toro.Semaphore.release`::

    @gen.coroutine
    def coro():
        sem = toro.Semaphore(1)
        assert not sem.locked()

        # A semaphore with initial value of 1 can be acquired once,
        # then it's locked.
        sem.acquire()
        assert sem.locked()

        # Wait for another coroutine to release the semaphore.
        yield sem.wait()

However, there was a bug and :meth:`~toro.Semaphore.wait` returned immediately
if the semaphore had **ever** been unlocked. I'm grateful to
`"abing" <https://github.com/DanielBlack>`_ on GitHub for noticing the bug and
contributing a fix.


Changes in Version 0.6
----------------------

:class:`~toro.Queue` now supports floating-point numbers for ``maxsize``. A
``maxsize`` of 1.3 is now equivalent to a ``maxsize`` of 2. Before, it had
been treated as infinite.

This feature is not intended to be useful, but to maintain an API similar to
``asyncio`` and the standard library Queue.

Changes in Version 0.5
----------------------

Rewritten for Tornado 3.

Dropped support for Tornado 2 and Python 2.5.

Added support for Tornado 3's Futures_:
  - All Toro methods that took callbacks no longer take callbacks but return
    Futures.
  - All Toro methods that took *optional* callbacks have been split into two
    methods: one that returns a Future, and a "nowait" method that returns
    immediately or raises an exception.

     - :meth:`AsyncResult.get_nowait` can raise :exc:`NotReady`
     - :meth:`Queue.get_nowait` can raise :exc:`Empty`
     - :meth:`Queue.put_nowait` can raise :exc:`Full`

  - All Toro methods that return Futures accept an optional ``deadline``
    parameter. Whereas before each Toro class had different behavior after a
    timeout, all now return a Future that raises :exc:`toro.Timeout` after the
    deadline.

Toro's API aims to be very similar to Tulip_, since Tulip will evolve into the
Python 3.4 standard library:

  - Toro's API has been updated to closely match the locks and queues in
    Tulip.
  - The requirement has been dropped that a coroutine that calls
    :meth:`~toro.Queue.put` resumes only *after* any coroutine it awakens.
    Similar for :meth:`~toro.Queue.get`. The order in which the two coroutines
    resume is now unspecified.
  - A Queue with maxsize 0 (the default) is no longer a "channel" as in Gevent
    but is an unbounded Queue as in Tulip and the standard library. ``None`` is
    no longer a valid maxsize.
  - The ``initial`` argument to Queue() was removed.
  - maxsize can no longer be changed after a Queue is created.

The chief differences between Toro and Tulip are that Toro uses ``yield``
instead of ``yield from``, and that Toro uses absolute deadlines instead of
relative timeouts. Additionally, Toro's :class:`~toro.Lock` and
:class:`~toro.Semaphore` aren't context managers (they can't be used with a
``with`` statement); instead, the Futures returned from
:meth:`~toro.Lock.acquire` and :meth:`~toro.Semaphore.acquire` are context
managers.

.. _Futures: http://www.tornadoweb.org/en/stable/concurrent.html#tornado.concurrent.Future

.. _Tulip: http://code.google.com/p/tulip/

Changes in Version 0.4
----------------------

Bugfix in :class:`~toro.JoinableQueue`, `JoinableQueue doesn't accept an
explicit IOLoop <https://github.com/ajdavis/toro/issues/1>`_.

Changes in Version 0.3
----------------------

Increasing the :attr:`~toro.Queue.maxsize` of a :class:`~toro.Queue` unblocks
callbacks waiting on :meth:`~toro.Queue.put`.

Travis integration.

Changes in Version 0.2
----------------------

Python 3 support.

Bugfix in :class:`~toro.Semaphore`: :meth:`release` shouldn't wake callbacks
registered with :meth:`wait` unless no one is waiting for :meth:`acquire`.

Fixed error in the "Wait-Notify" table.

Added :doc:`examples/lock_example` to docs.

Changes in Version 0.1.1
------------------------

Fixed the docs to render correctly in PyPI.

Version 0.1
-----------

First release.
