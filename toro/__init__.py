"""Locks and queues for Tornado coroutines."""

__all__ = [
    # Exceptions.
    'QueueFull', 'QueueEmpty',

    # Deprecated exceptions. Keep exporting these for compatibility.
    'Full', 'Empty', 'Timeout',

    # Primitives.
    'Event', 'Condition', 'Semaphore', 'BoundedSemaphore', 'Lock',

    # Queues. Keep exporting "JoinableQueue" for compatibility.
    'Queue', 'PriorityQueue', 'LifoQueue', 'JoinableQueue'
]

from tornado import gen

from .locks import BoundedSemaphore, Condition, Event, Lock, Semaphore
from .queues import (JoinableQueue,
                     LifoQueue,
                     PriorityQueue,
                     Queue,
                     QueueEmpty,
                     QueueFull)

version_tuple = (0, 8, '+')

version = '.'.join(map(str, version_tuple))
"""Current version of Toro."""


Timeout = gen.TimeoutError
"""**DEPRECATED**: Alias for :exc:`tornado.gen.TimeoutError`.

Preserves backward-compatibility with Toro 0.7 and older, which raised a custom
``toro.Timeout`` exception. Your code should catch
:exc:`tornado.gen.TimeoutError` instead of ``toro.Timeout``.

.. versionadded:: 0.9
"""
