:mod:`toro`: Synchronization primitives for Tornado coroutines
===============================================================

.. currentmodule:: toro

.. contents:: Contents
   :depth: 3
   :local:


Classes
-------

AsyncResult
~~~~~~~~~~~
.. autoclass:: AsyncResult
  :members:

Lock
~~~~
.. autoclass:: Lock
  :members:

Semaphore
~~~~
.. autoclass:: Semaphore
  :members:

BoundedSemaphore
~~~~
.. autoclass:: BoundedSemaphore
  :members:

Condition
~~~~
.. autoclass:: Condition
  :members:

Event
~~~~
.. autoclass:: Event
  :members:

Queue
~~~~
.. autoclass:: Queue
  :members:

PriorityQueue
~~~~
.. autoclass:: PriorityQueue
  :members:

LifoQueue
~~~~
.. autoclass:: LifoQueue
  :members:

JoinableQueue
~~~~
.. autoclass:: JoinableQueue
  :members:

Class relationships
-------------------

Toro uses some of its primitives in the implementation of others.
For example, :class:`JoinableQueue` is a subclass of :class:`Queue`, and it
has an :class:`Event`. (:class:`AsyncResult` stands alone.)

.. graphviz::

   digraph Toro {
       graph [splines=false];
       node [shape=record];
       
       // First show UML-style subclass relationships. 
       edge [label=subclass arrowtail=empty arrowhead=none dir=both];

       Queue -> PriorityQueue
       Queue -> LifoQueue
       Queue -> JoinableQueue
       Semaphore -> BoundedSemaphore
       
       // Now UML-style composition or has-a relationships.
       edge [label="has a" arrowhead=odiamond arrowtail=none];

       Event -> JoinableQueue
       Condition -> Event
       Event -> Semaphore
       Queue -> Semaphore
       Semaphore -> Lock
   }
