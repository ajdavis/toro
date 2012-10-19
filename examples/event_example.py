"""
An oversimplified caching HTTP proxy - start it, and configure your browser to
use localhost:8888 as the proxy server. It doesn't do cookies or redirects,
nor does it obey cache-control headers.

The point is to demonstrate :class:`~toro.Event`. Imagine a client requests a
page, and while the proxy is downloading the page from the external site, a
second client requests the same page. Since the page is not yet in cache, an
inefficient proxy would launch a second external request.

This proxy instead places an :class:`~toro.Event` in the cache, and the second
client request waits for the event to be set, thus requiring only a single
external request.
"""

# start-file
from tornado import httpclient, gen, ioloop, web
import toro


class CacheEntry(object):
    def __init__(self):
        self.event = toro.Event()
        self.type = self.body = None

cache = {}

class ProxyHandler(web.RequestHandler):
    @web.asynchronous
    @gen.engine
    def get(self):
        path = self.request.path
        entry = cache.get(path)
        if entry:
            # Block until the event is set, unless it's set already
            yield gen.Task(entry.event.wait)
        else:
            print path
            cache[path] = entry = CacheEntry()

            # Actually fetch the page
            response = yield gen.Task(httpclient.AsyncHTTPClient().fetch, path)
            entry.type = response.headers.get('Content-Type', 'text/html')
            entry.body = response.body
            entry.event.set()

        self.set_header('Content-Type', entry.type)
        self.write(entry.body)
        self.finish()


if __name__ == '__main__':
    print 'Listening on port 8888'
    print
    print 'Now configure your web browser to use localhost:8888 as an HTTP Proxy.'
    print 'Try visiting some web pages and hitting "refresh".'
    web.Application([('.*', ProxyHandler)], debug=True).listen(8888)
    ioloop.IOLoop.instance().start()
