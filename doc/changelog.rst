Changelog
=========

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
