Frequently Asked Questions
==========================

.. module:: toro

What's it for?
--------------
Toro makes it easy for Tornado coroutines--that is, functions decorated with
`gen.engine`_--to coordinate using Events, Conditions, Queues, and Semaphores.
Toro supports patterns in which coroutines wait for notifications from others.

.. _gen.engine: http://www.tornadoweb.org/documentation/gen.html#decorator

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

Does it need gen?
-----------------

Toro does not directly depend on Tornado's gen_ module. Toro's primitives use
normal callback functions, and in theory one could use Toro with callbacks
instead of coroutines. However, Toro is intended for use in complex asynchronous
programs. Simplifying such programs with coroutines is vehemently endorsed.

See :doc:`../examples/producer_consumer_example`
and :doc:`../examples/producer_consumer_example_callbacks`
to compare the relative difficulty of using a :class:`Queue` with and without
coroutines.

.. _gen: http://www.tornadoweb.org/documentation/gen.html

Why no RLock?
-------------

The standard-library RLock_ (reentrant lock) can be acquired multiple times by
a single thread without blocking, reducing the chance of deadlock, especially
in recursive functions. The thread currently holding the RLock is the "owning
thread."

In Toro, simulating a concept like an "owning chain of callbacks" would be
over-complicated and under-useful, so there is no RLock, only a :class:`Lock`.

.. _RLock: http://docs.python.org/library/threading.html#rlock-objects
