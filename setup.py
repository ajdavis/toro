# Don't force people to install setuptools unless
# we have to.
try:
    from setuptools import setup
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

import sys

try:
    # Work around bug in Python 2.6, TypeError on shutdown.
    import multiprocessing
except ImportError:
    pass

classifiers = """\
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Development Status :: 4 - Beta
Natural Language :: English
Programming Language :: Python :: 2
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3
Programming Language :: Python :: 3.2
Programming Language :: Python :: 3.3
Programming Language :: Python :: 3.4
Operating System :: MacOS :: MacOS X
Operating System :: Unix
Programming Language :: Python
Programming Language :: Python :: Implementation :: CPython
Programming Language :: Python :: Implementation :: PyPy
"""

description = 'Synchronization primitives for Tornado coroutines.'

long_description = open("README.rst").read()

major, minor = sys.version_info[:2]

kwargs = {}
if major >= 3:
    kwargs['use_2to3'] = True

packages = ['toro']
if "test" in sys.argv:
    packages.append('test')

setup(name='toro',
      version='1.0.1',
      packages=packages,
      description=description,
      long_description=long_description,
      author='A. Jesse Jiryu Davis',
      author_email='jesse@emptysquare.net',
      url='http://github.com/ajdavis/toro/',
      install_requires=['tornado >= 3'],
      license='http://www.apache.org/licenses/LICENSE-2.0',
      classifiers=filter(None, classifiers.split('\n')),
      keywords='tornado coroutines semaphore mutex queue asynchronous',
      test_suite='test',
      **kwargs
)
