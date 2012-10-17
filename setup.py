from distutils.core import setup

setup(name='toro',
      version='0.1',
      py_modules=['toro'],
      description='Synchronization primitives for Tornado coroutines',
      author='A. Jesse Jiryu Davis',
      author_email='ajdavis@cs.oberlin.edu',
      url='https://github.com/ajdavis/toro/',
      requires=['tornado>=2.3'],
)
