====
toro
====

.. image:: https://raw.github.com/ajdavis/toro/master/doc/_static/toro.png

:Info: Synchronization primitives for Tornado coroutines.
:Author: A\. Jesse Jiryu Davis

Documentation: http://toro.readthedocs.org/

.. image:: https://travis-ci.org/ajdavis/toro.png
        :target: https://travis-ci.org/ajdavis/toro

About
=====
A set of locking and synchronizing primitives analogous to those in Python's
`threading module`_ or Gevent's `coros`_, for use with Tornado's `gen.engine`_.

.. _threading module: http://docs.python.org/library/threading.html

.. _coros: http://www.gevent.org/gevent.coros.html

.. _gen.engine: http://www.tornadoweb.org/documentation/gen.html

Dependencies
============
Tornado_ >= version 2.3.

.. _Tornado: http://www.tornadoweb.org/

Examples
========
Here's a basic example (for more see the *examples* section of the docs):

.. code-block:: python

    from tornado import ioloop, gen
    import toro

    q = toro.JoinableQueue(maxsize=3)

    @gen.engine
    def consumer():
        while True:
            item = yield gen.Task(q.get)
            try:
                print 'Doing work on', item
            finally:
                q.task_done()

    @gen.engine
    def producer():
        for item in range(10):
            yield gen.Task(q.put, item)

    producer()
    consumer()
    loop = ioloop.IOLoop.instance()
    q.join(callback=loop.stop) # block until all tasks are done
    loop.start()

Documentation
=============

You will need Sphinx_ and GraphViz_ installed to generate the
documentation. Documentation can be generated like:

.. code-block:: console

    $ sphinx-build doc build

.. _Sphinx: http://sphinx.pocoo.org/

.. _GraphViz: http://www.graphviz.org/

Testing
=======

Run ``python setup.py nosetests`` in the root directory.

Toro boasts 100% code coverage, including branch-coverage!
