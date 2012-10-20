"""A simple web-spider that crawls all the pages in http://tornadoweb.org.

``spider()`` downloads the page at `base_url` and any pages it links to,
recursively. It ignores pages that are not beneath `base_url` hierarchically.

This function demos two Toro classes: :class:`~toro.JoinableQueue` and
:class:`~toro.BoundedSemaphore`.
The :class:`~toro.JoinableQueue` is a work queue; it begins containing only
`base_url`, and each discovered URL is added to it. We wait for
:meth:`~toro.JoinableQueue.join` to complete before exiting. This ensures that
the function as a whole ends when all URLs have been downloaded.

The :class:`~toro.BoundedSemaphore` regulates concurrency. We block trying to
decrement the semaphore before each download, and increment it after each
download completes.
"""

# start-file
import HTMLParser
import time
import urlparse

from tornado import httpclient, gen, ioloop

import toro


@gen.engine
def spider(base_url, concurrency, callback):
    q = toro.JoinableQueue()
    sem = toro.BoundedSemaphore(concurrency)

    start = time.time()
    fetched = set()

    @gen.engine
    def fetch_url(callback):
        current_url = yield gen.Task(q.get)
        try:
            if current_url in fetched:
                return

            print 'fetching', current_url
            fetched.add(current_url)
            urls = yield gen.Task(get_links_from_url, current_url)

            for new_url in urls:
                # Only follow links beneath the base URL
                if new_url.startswith(base_url):
                    yield gen.Task(q.put, new_url)

        finally:
            q.task_done()

            # callback is sem.release(), so releasing here frees a slot for the
            # main loop in worker() to launch another fetch_url() task.
            callback()

    @gen.engine
    def worker():
        while True:
            yield gen.Task(sem.acquire)
            # Launch a subtask
            fetch_url(callback=sem.release)

    q.put(base_url)

    # Start worker, then wait for the work queue to be empty.
    worker()
    yield gen.Task(q.join, deadline=time.time() + 300)

    if q.unfinished_tasks:
        print 'Timed out!'
    else:
        print 'Done in %d seconds, fetched %s URLs.' % (
            time.time() - start, len(fetched))

    # callback is loop.stop(), so this allows the whole program to exit.
    callback()


@gen.engine
def get_links_from_url(url, callback):
    """Download the page at `url` and parse it for links. Returned links have
    had the fragment after `#` removed, and have been made absolute so, e.g.
    the URL 'gen.html#tornado.gen.Task' becomes
    'http://tornadoweb.org/documentation/gen.html'.
    """
    response = yield gen.Task(httpclient.AsyncHTTPClient().fetch, url)

    if response.error:
        print url, response.error
        callback([])
        return
    else:
        print 'fetched', url

    try:
        urls = [
            urlparse.urljoin(url, remove_fragment(new_url))
            for new_url in get_links(response.body)
        ]

        callback(urls)
    except Exception, e:
        print url, e
        callback([])
        return


def remove_fragment(url):
    scheme, netloc, url, params, query, fragment = urlparse.urlparse(url)
    return urlparse.urlunparse((scheme, netloc, url, params, query, ''))


def get_links(html):
    class URLSeeker(HTMLParser.HTMLParser):
        def __init__(self):
            HTMLParser.HTMLParser.__init__(self)
            self.urls = []

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get('href')
            if href and tag == 'a':
                self.urls.append(href)

    url_seeker = URLSeeker()
    url_seeker.feed(html)
    return url_seeker.urls


if __name__ == '__main__':
    spider('http://tornadoweb.org', 10, ioloop.IOLoop.instance().stop)
    ioloop.IOLoop.instance().start()
