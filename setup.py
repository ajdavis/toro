from distutils.core import setup

classifiers = """\
Intended Audience :: Developers
License :: OSI Approved :: Apache Software License
Development Status :: 4 - Beta
Framework :: Tornado
Natural Language :: English
Programming Language :: Python :: 2
Programming Language :: Python :: 2.5
Programming Language :: Python :: 2.6
Programming Language :: Python :: 2.7
Operating System :: MacOS :: MacOS X
Operating System :: Unix
Programming Language :: Python
"""

description = 'Synchronization primitives for Tornado coroutines'

setup(name='toro',
      version='0.1',
      packages=['toro'],
      description=description,
      long_description=description,
      author='A. Jesse Jiryu Davis',
      author_email='ajdavis@cs.oberlin.edu',
      url='https://github.com/ajdavis/toro/',
      requires=['tornado (>=2.3)'],
      license='http://www.apache.org/licenses/LICENSE-2.0',
      classifiers=filter(None, classifiers.split('\n')),
)
