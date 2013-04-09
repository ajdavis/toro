Frequently Asked Questions
==========================

.. module:: toro

What's it for?
--------------
Toro makes it easy for Tornado coroutines--that is, functions decorated with
`gen.coroutine`_--to coordinate using Events, Conditions, Queues, and Semaphores.
Toro supports patterns in which coroutines wait for notifications from others.

.. _gen.coroutine: http://www.tornadoweb.org/en/stable/gen.html#tornado.gen.coroutine

Why the name?
-------------
A coroutine is often called a "coro", and a library of primitives useful for
managing coroutines is called "`coros`_" in Gevent and "`coro`_" in Shrapnel.
So I call a library to manage Tornado coroutines "toro".

.. _coros: http://www.gevent.org/gevent.coros.html

.. _coro: https://github.com/ironport/shrapnel

Why do I need synchronization primitives for a single-threaded app?
-------------------------------------------------------------------
Protecting an object shared across coroutines is mostly unnecessary in a
single-threading Tornado program. For example, a multithreaded app would protect
``counter`` with a `Lock`_::

    import threading

    lock = threading.Lock()
    counter = 0

    def inc():
        lock.acquire()
        counter += 1
        lock.release()

.. _Lock: http://docs.python.org/library/threading.html#lock-objects

This isn't needed in a Tornado coroutine, because the coroutine won't be
interrupted until it explicitly yields. Thus Toro is *not* designed to protect
shared state.

Instead, Toro supports complex coordination among coroutines with
:ref:`the-wait-notify-pattern`: Some coroutines wait at particular points in
their code for other coroutines to awaken them.

Why no RLock?
-------------

The standard-library RLock_ (reentrant lock) can be acquired multiple times by
a single thread without blocking, reducing the chance of deadlock, especially
in recursive functions. The thread currently holding the RLock is the "owning
thread."

In Toro, simulating a concept like an "owning chain of coroutines" would be
over-complicated and under-useful, so there is no RLock, only a :class:`Lock`.

.. _RLock: http://docs.python.org/library/threading.html#rlock-objects

Has Toro anything to do with Tulip?
-----------------------------------

Toro predates Tulip_, which has very similar ideas about coordinating async
coroutines using locks and queues. Toro's author implemented Tulip's queues,
and version 0.5 of Toro strives to match Tulip's API.

The chief differences between Toro and Tulip are that Toro uses ``yield``
instead of ``yield from``, and that Toro uses absolute deadlines instead of
relative timeouts. Additionally, Toro's :class:`~toro.Lock` and
:class:`~toro.Semaphore` aren't context managers (they can't be used with a
``with`` statement); instead, the Futures returned from
:meth:`Lock.acquire` and :meth:`Semaphore.acquire` are context
managers:

    >>> from tornado import gen
    >>> import toro
    >>> lock = toro.Lock()
    >>>
    >>> @gen.coroutine
    ... def f():
    ...    with (yield lock.acquire()):
    ...        assert lock.locked()
    ...
    ...    assert not lock.locked()

.. _Tulip: http://code.google.com/p/tulip/
