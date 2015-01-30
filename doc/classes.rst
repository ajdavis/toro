:mod:`toro` Classes
===================

.. currentmodule:: toro

.. contents:: Contents
   :local:

.. _primitives:

Primitives
~~~~~~~~~~

Lock
----
.. autoclass:: Lock
  :members:

Semaphore
---------
.. autoclass:: Semaphore
  :members:

BoundedSemaphore
----------------
.. autoclass:: BoundedSemaphore
  :members:

Condition
---------
.. autoclass:: Condition
  :members:

Event
-----
.. autoclass:: Event
  :members:

Queues
~~~~~~

Queue
-----
.. autoclass:: Queue
  :members:

PriorityQueue
-------------
.. autoclass:: PriorityQueue
  :members:

LifoQueue
---------
.. autoclass:: LifoQueue
  :members:

Exceptions
~~~~~~~~~~

Toro uses :exc:`tornado.gen.TimeoutError`, and the exceptions Empty_ and Full_
from the standard module Queue_.

.. _Empty: http://docs.python.org/library/queue.html#Queue.Empty

.. _Full: http://docs.python.org/library/queue.html#Queue.Full

.. _Queue: http://docs.python.org/library/queue.html

Class relationships
~~~~~~~~~~~~~~~~~~~

Toro uses some of its primitives in the implementation of others.
For example, :class:`LifoQueue` is a subclass of :class:`Queue`, and
:class:`Queue` uses an :class:`Event`.

.. graphviz::

   digraph Toro {
       graph [splines=false];
       node [shape=record];

       // First show UML-style subclass relationships.
       edge [label=subclass arrowtail=empty arrowhead=none dir=both];

       Queue -> PriorityQueue
       Queue -> LifoQueue
       Semaphore -> BoundedSemaphore

       // Now UML-style composition or has-a relationships.
       edge [label="has a" arrowhead=odiamond arrowtail=none];

       Event -> Queue
       Condition -> Event
       Event -> Semaphore
       Queue -> Semaphore
       Semaphore -> Lock
   }
