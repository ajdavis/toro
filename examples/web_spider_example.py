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
from datetime import timedelta

from tornado import httpclient, gen, ioloop

import toro


@gen.coroutine
def spider(base_url, concurrency):
    q = toro.JoinableQueue()
    sem = toro.BoundedSemaphore(concurrency)

    start = time.time()
    fetching, fetched = set(), set()

    @gen.coroutine
    def fetch_url():
        current_url = yield q.get()
        try:
            if current_url in fetching:
                return

            print 'fetching', current_url
            fetching.add(current_url)
            urls = yield get_links_from_url(current_url)
            fetched.add(current_url)

            for new_url in urls:
                # Only follow links beneath the base URL
                if new_url.startswith(base_url):
                    yield q.put(new_url)

        finally:
            q.task_done()
            sem.release()

    @gen.coroutine
    def worker():
        while True:
            yield sem.acquire()
            # Launch a subtask
            fetch_url()

    q.put(base_url)

    # Start worker, then wait for the work queue to be empty.
    worker()
    yield q.join(deadline=timedelta(seconds=300))
    assert fetching == fetched
    print 'Done in %d seconds, fetched %s URLs.' % (
        time.time() - start, len(fetched))


@gen.coroutine
def get_links_from_url(url):
    """Download the page at `url` and parse it for links. Returned links have
    had the fragment after `#` removed, and have been made absolute so, e.g.
    the URL 'gen.html#tornado.gen.coroutine' becomes
    'http://www.tornadoweb.org/en/stable/gen.html'.
    """
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url)
        print 'fetched', url
        urls = [urlparse.urljoin(url, remove_fragment(new_url))
                for new_url in get_links(response.body)]
    except Exception, e:
        print e, url
        raise gen.Return([])

    raise gen.Return(urls)


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
    import logging
    logging.basicConfig()
    loop = ioloop.IOLoop.current()
    
    def stop(future):
        loop.stop()
        future.result()  # Raise error if there is one
        
    future = spider('http://www.tornadoweb.org/en/stable/', 10)
    future.add_done_callback(stop)
    loop.start()
