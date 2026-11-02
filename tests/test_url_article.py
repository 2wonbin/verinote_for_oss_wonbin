"""Unit tests for web article URL parsing and HTML extraction."""
import unittest

from verinote.documents import decode_document, fetch_web_article


class TestWebArticle(unittest.TestCase):
    def test_html_document_decoding(self):
        html = b'''<!DOCTYPE html>
<html>
<head><title>Python Tips - Asyncio</title><style>body { color: red; }</style></head>
<body>
  <nav>Navigation links</nav>
  <article>
    <h1>Asyncio Deep Dive</h1>
    <p>Asyncio provides asynchronous I/O primitives.</p>
  </article>
  <footer>Copyright 2026</footer>
</body>
</html>'''
        text = decode_document('article.html', html)
        self.assertIn('Asyncio Deep Dive', text)
        self.assertIn('Asyncio provides asynchronous I/O primitives.', text)
        self.assertNotIn('Navigation links', text)
        self.assertNotIn('Copyright 2026', text)

    def test_url_ssrf_protection(self):
        blocked_urls = [
            'http://localhost:8080/secret',
            'http://127.0.0.1/admin',
            'http://192.168.1.1/',
            'http://10.0.0.1/internal',
            'ftp://example.com/file.txt',
            'file:///etc/passwd'
        ]
        for url in blocked_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    fetch_web_article(url)


if __name__ == '__main__':
    unittest.main()
