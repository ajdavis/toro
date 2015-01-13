"""
Test toro.Timeout exception.
"""

from tornado.testing import AsyncTestCase

import toro


class TestTimeout(AsyncTestCase):
    def test_str(self):
        exception = toro.Timeout()
        str(exception)
