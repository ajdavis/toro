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

.. _gen: http://www.tornadoweb.org/documentation/gen.html

.. _the-wait-notify-pattern:

The Wait / Notify Pattern
=========================
Toro's :ref:`primitives <primitives>` follow a "wait / notify pattern": one
coroutine waits to be notified by another. Let's take :class:`Condition` as an
example:

.. doctest::

    >>> import toro
    >>> from tornado import gen
    >>> condition = toro.Condition()
    >>> @gen.engine
    ... def waiter(callback):
    ...     print "I'll wait right here"
    ...     yield gen.Task(condition.wait)
    ...     print "I'm done waiting"
    ...     callback()
    ...
    >>> @gen.engine
    ... def notifier(callback):
    ...     print "About to notify"
    ...     condition.notify()
    ...     print "Done notifying"
    ...     callback()
    ...
    >>> @gen.engine
    ... def runner():
    ...     waiter(callback=(yield gen.Callback('waiter')))
    ...     notifier(callback=(yield gen.Callback('notifier')))
    ...     yield gen.WaitAll(['waiter', 'notifier'])
    ...
    >>> runner()
    I'll wait right here
    About to notify
    I'm done waiting
    Done notifying

Wait-methods take an optional ``deadline`` argument, which is either a Unix
timestamp (seconds since epoch)::

    # Wait up to 1 second for a notification
    yield gen.Task(condition.wait, deadline=time.time() + 1)

...or a ``datetime.timedelta`` for a deadline relative to the current time::

    # Wait up to 1 second
    yield gen.Task(condition.wait, deadline=datetime.timedelta(seconds=1))

When a coroutine passes a deadline to a wait-method, there are different ways
to determine whether it was awakened by a notify-method or if it timed out; see
:ref:`the table below <wait-notify-table>`.

Some wait-methods can be called without a callback: in that case they may raise
an exception (:meth:`AsyncResult.get` raises :exc:`NotReady`) if the
notify-method hasn't run yet, or they return ``False``
(:meth:`Lock.acquire` and :meth:`Semaphore.acquire`).

.. _wait-notify-table:

======================= ==================================  ================================= ================================ ===============================================
Class                   Notify Method                       Wait Method                       Without Callback                 After A Timeout....
======================= ==================================  ================================= ================================ ===============================================
:class:`AsyncResult`    :meth:`AsyncResult.set`             :meth:`AsyncResult.get`           value / raise :exc:`NotReady`    Callback receives ``None``
:class:`Lock`           :meth:`Lock.release`                :meth:`Lock.acquire`              ``True`` / ``False``             Callback receives ``False``
:class:`Semaphore`      :meth:`Semaphore.release`           :meth:`Semaphore.acquire`         ``True`` / ``False``             :meth:`Semaphore.locked` still ``True``
:class:`Semaphore`                                          :meth:`Semaphore.wait`            callback required                :meth:`Semaphore.locked` still ``True``
:class:`Condition`      :meth:`Condition.notify`            :meth:`Condition.wait`            callback required                No way to know if it was a timeout
:class:`Event`          :meth:`Event.set`                   :meth:`Event.wait`                callback required                :meth:`Event.is_set` still ``False``
======================= ==================================  ================================= ================================ ===============================================

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

======================== ======================================== ======================================
Method                   Without Callback                         After A Timeout.....
======================== ======================================== ======================================
:meth:`Queue.get`        returns item or raises ``Empty``         callback receives ``Empty``
:meth:`Queue.put`        returns ``None`` or raises ``Full``      callback receives ``Full``
======================== ======================================== ======================================

See the :doc:`examples/producer_consumer_example`.

Additionally, :class:`JoinableQueue` supports
the wait-method :meth:`JoinableQueue.join`
and the notify-method :meth:`JoinableQueue.task_done`:

.. _join-task-done-table:

======================== ==================================  ================================= ============================== ===============================================
Class                    Notify Method                       Wait Method                       Without Callback               After A Timeout....
======================== ==================================  ================================= ============================== ===============================================
:class:`JoinableQueue`   :meth:`JoinableQueue.task_done`     :meth:`JoinableQueue.join`        callback required              ``JoinableQueue.unfinished_tasks > 0``
======================== ==================================  ================================= ============================== ===============================================

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

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

