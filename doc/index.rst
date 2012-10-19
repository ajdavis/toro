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
mutexes, queues, and semaphores.

Toro provides to Tornado coroutines a set of locking primitives analogous to
those available for Greenlets in Gevent, or for threads in the standard
library.

.. _gen: http://www.tornadoweb.org/documentation/gen.html

.. _the-wait-notify-pattern:

The Wait / Notify Pattern
=========================

Toro's primitives follow a "wait / notify pattern": one coroutine waits for
notification from another. Let's take :class:`Condition` as an example:

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
    yield gen.Task(condition.wait, deadline=time.time() + datetime.timedelta(seconds=1))

When a coroutine passes a deadline to a wait-method, there are different ways
to determine whether it was awakened by a notify-method or if it timed out.

=========================== ==================================  =================================   ===============================================
Class                       Notify Method                       Wait Method                         After A Timeout....
=========================== ==================================  =================================   ===============================================
:class:`AsyncResult`        :meth:`AsyncResult.set`             :meth:`AsyncResult.get`             Callback receives ``None``
:class:`Lock`               :meth:`Lock.release`                :meth:`Lock.acquire`                Callback receives ``False``
:class:`Semaphore`          :meth:`Semaphore.release`           :meth:`Semaphore.acquire`           :meth:`Semaphore.locked` still ``True``
:class:`Condition`          :meth:`Condition.notify`            :meth:`Condition.wait`              No way to know if it was a timeout
:class:`Event`              :meth:`Event.set`                   :meth:`Event.wait`                  :meth:`Event.is_set` still ``False``
:class:`JoinableQueue`      :meth:`JoinableQueue.task_done`     :meth:`JoinableQueue.join`          ``JoinableQueue.unfinished_tasks > 0``
=========================== ==================================  =================================   ===============================================

For :class:`Queue` and its subclasses, :meth:`Queue.put` and :meth:`Queue.get`
are each a wait-method **and** a notify-method: :meth:`Queue.put` blocks until
the queue has a free slot, and :meth:`Queue.get` blocks until there is an
available item.

Contents
========

.. toctree::
    examples/index
    classes
    faq

Source
======

Is on GitHub: https://github.com/ajdavis/toro

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

