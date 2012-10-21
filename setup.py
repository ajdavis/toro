from setuptools import setup

classifiers = """\
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Development Status :: 4 - Beta
Natural Language :: English
Programming Language :: Python :: 2
Programming Language :: Python :: 2.5
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Operating System :: MacOS :: MacOS X
Operating System :: Unix
Programming Language :: Python
"""

description = 'Synchronization primitives for Tornado coroutines.'

setup(name='toro',
      version='0.1',
      packages=['toro'],
      description=description,
      author='A. Jesse Jiryu Davis',
      author_email='ajdavis@cs.oberlin.edu',
      url='http://github.com/ajdavis/toro/',
      install_requires=['tornado >= 2.4.0'],
      license='http://www.apache.org/licenses/LICENSE-2.0',
      classifiers=filter(None, classifiers.split('\n')),
      keywords='tornado coroutines semaphore mutex queue asynchronous',
)
