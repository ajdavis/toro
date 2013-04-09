=======================================================
toro: Synchronization primitives for Tornado coroutines
=======================================================

.. module:: toro

.. image:: _static/toro.png
    :align: center

.. getting the caption italicized with a hyperlink in it requires some RST hackage

*Toro logo by* |musho|_

.. _musho: http://whimsyload.com

.. |musho| replace:: *Musho Rodney Alan Greenblat*

With Tornado's `gen`_ module, you can turn Python generators into full-featured
coroutines, but coordination among these coroutines is difficult without
mutexes, semaphores, and queues.

Toro provides to Tornado coroutines a set of locking primitives and queues
analogous to those that Gevent provides to Greenlets, or that the standard
library provides to threads.

*(Note that these primitives and queues are not actually thread-safe and cannot
be used in place of those from the standard library--they are meant to
coordinate Tornado coroutines in single-threaded apps, not to protect shared
objects in multithreaded apps.)*

.. _gen: http://www.tornadoweb.org/en/stable/gen.html

.. _the-wait-notify-pattern:

The Wait / Notify Pattern
=========================
Toro's :ref:`primitives <primitives>` follow a "wait / notify pattern": one
coroutine waits to be notified by another. Let's take :class:`Condition` as an
example:

.. doctest::

    >>> import toro
    >>> from tornado import ioloop, gen
    >>> loop = ioloop.IOLoop.current()
    >>> condition = toro.Condition()
    >>> @gen.coroutine
    ... def waiter():
    ...     print "I'll wait right here"
    ...     yield condition.wait()  # Yield a Future
    ...     print "I'm done waiting"
    ...
    >>> @gen.coroutine
    ... def notifier():
    ...     print "About to notify"
    ...     condition.notify()
    ...     print "Done notifying"
    ...
    >>> @gen.coroutine
    ... def runner():
    ...     # Yield two Futures; wait for waiter() and notifier() to finish
    ...     yield [waiter(), notifier()]
    ...     loop.stop()
    ...
    >>> future = runner(); loop.start()
    I'll wait right here
    About to notify
    Done notifying
    I'm done waiting

Wait-methods take an optional ``deadline`` argument, which is either an
absolute timestamp::

    loop = ioloop.IOLoop.current()

    # Wait up to 1 second for a notification
    yield condition.wait(deadline=loop.time() + 1)

...or a ``datetime.timedelta`` for a deadline relative to the current time::

    # Wait up to 1 second
    yield condition.wait(deadline=datetime.timedelta(seconds=1))

If there's no notification before the deadline, the Toro-specific
:class:`Timeout` exception is raised.

.. _the-get-put-pattern:

The Get / Put Pattern
=====================
:class:`Queue` and its subclasses support methods :meth:`Queue.get` and
:meth:`Queue.put`. These methods are each both a wait-method **and** a
notify-method:

* :meth:`Queue.get` waits until there is an available item in the queue, and
  may notify a coroutine waiting to put an item.
* :meth:`Queue.put` waits until the queue has a free slot, and may notify a
  coroutine waiting to get an item.

:meth:`Queue.get` and :meth:`Queue.put` accept deadlines and raise
:exc:`Timeout` if the deadline passes.

See the :doc:`examples/producer_consumer_example`.

Additionally, :class:`JoinableQueue` supports
the wait-method :meth:`JoinableQueue.join`
and the notify-method :meth:`JoinableQueue.task_done`.

Contents
========
.. toctree::
    examples/index
    classes
    faq
    changelog

Source
======
Is on GitHub: https://github.com/ajdavis/toro

Bug Reports and Feature Requests
================================
Also on GitHub: https://github.com/ajdavis/toro/issues

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
