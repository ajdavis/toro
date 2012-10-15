import urlparse
import HTMLParser
import time

from tornado import httpclient, gen, ioloop

import toro


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


def remove_fragment(url):
    scheme, netloc, url, params, query, fragment = urlparse.urlparse(url)
    return urlparse.urlunparse((scheme, netloc, url, params, query, ''))


@gen.engine
def spider(base_url, concurrency, callback):
    start = time.time()
    fetched = set()
    q = toro.JoinableQueue()

    @gen.engine
    def fetch_url():
        while True:
            try:
                current_url = yield gen.Task(q.get)
                if current_url in fetched:
                    continue

                print 'fetching', current_url
                fetched.add(current_url)
                response = yield gen.Task(
                    httpclient.AsyncHTTPClient().fetch, current_url)

                if response.error:
                    print current_url, response.error, 'from', source_url
                    continue
                else:
                    print 'fetched', current_url

                try:
                    urls = get_links(response.body)
                except Exception, e:
                    print current_url, e, 'from', source_url
                    raise StopIteration

                for new_url in urls:
                    absolute_url = urlparse.urljoin(current_url,
                        remove_fragment(new_url))

                    # Only follow links beneath the base URL
                    if absolute_url.startswith(base_url):
                        yield gen.Task(q.put, absolute_url)

            finally:
                q.task_done()

    q.put(base_url)

    # Start workers
    for i in range(concurrency):
        fetch_url()

    yield gen.Task(q.join, timeout=300)
    if q.unfinished_tasks:
        print 'Timed out!'
    else:
        print 'Done in %d seconds, fetched %s URLs.' % (
            time.time() - start, len(fetched))
    callback()


if __name__ == '__main__':
    spider('http://tornadoweb.org', 10, ioloop.IOLoop.instance().stop)
    ioloop.IOLoop.instance().start()
