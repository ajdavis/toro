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

.. autoclass:: QueueEmpty

.. autoclass:: QueueFull

Toro also uses :exc:`tornado.gen.TimeoutError`.

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
