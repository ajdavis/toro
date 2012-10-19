toro: Synchronization primitives for Tornado coroutines
=======================================================

.. image:: _static/toro.png
    :align: center

.. getting the caption italicized with a hyperlink in it requires some RST hackage

*Toro logo by* |musho|_

.. _musho: http://whimsyload.com

.. |musho| replace:: *Musho Rodney Alan Greenblat*

The Wait / Notify Pattern
-------------------------

E.g. Condition.wait(callback, deadline)

Sometimes you get a value telling you what happened, other times there's
no change of state, other times you need to check the original object to
see what happened

.. todo:: fix that inconsistency?!

`deadline` is either an absolute timestamp as a Unix timestamp::

    # Wait up to 1 second for a notification
    yield gen.Task(cond.wait, deadline=time.time() + 1)

...or `datetime.timedelta` for a deadline relative to the current time::

    # Wait up to 1 second
    yield gen.Task(cond.wait, deadline=time.time() + datetime.timedelta(seconds=1))

E.g. Condition.notify(callback), optionally resuming after waiters are
awakened

Contents:
---------

.. toctree::
    examples/index
    classes
    faq

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`

