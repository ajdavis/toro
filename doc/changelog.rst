Changelog
=========

Changes in Next Version
-----------------------

Rewritten for Tornado 3.

Dropped support for Tornado 2 and Python 2.5.

Added support for Tornado 3's Futures_:
  - All Toro methods that took callbacks no longer take callbacks but return
    Futures.
  - All Toro methods that took *optional* callbacks have been split into two
    methods: one that returns a Future, and a "nowait" method that returns
    immediately or raises an exception. "nowait" methods:
    - :meth:`~toro.AsyncResult.get_nowait`
    - :meth:`~toro.Queue.get_nowait`
    - :meth:`~toro.Queue.put_nowait`
  - All Toro methods that return Futures accept an optional ``deadline``
    parameter. Whereas before each Toro class had different behavior after a
    timeout, all now return a Future that raises :exc:`toro.Timeout` after the
    deadline.

Tulip compatibility:
  - Toro's API has been updated to closely match the locks and queues in
    Tulip_.
  - The requirement has been dropped that a coroutine that calls
    :meth:`~toro.Queue.put` resumes only *after* any coroutine it awakens.
    Similar for :meth:`~toro.Queue.get`. The order in which the two coroutines
    resume is now unspecified.
  - A Queue with maxsize 0 (the default) is no longer a "channel" as in Gevent
    but is an unbounded Queue as in Tulip and the standard library. ``None`` is
    no longer a valid maxsize.
  - The ``initial`` argument to Queue() was removed.
  - maxsize can no longer be changed after a Queue is created.
  - :class:`~toro.Lock` can now be used as a context manager.

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

Fixed error in the :ref:`wait / notify table <wait-notify-table>`.

Added :doc:`examples/lock_example` to docs.

Changes in Version 0.1.1
------------------------

Fixed the docs to render correctly in PyPI.

Version 0.1
-----------

First release.
