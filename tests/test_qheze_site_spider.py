from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from http.client import RemoteDisconnected

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from crawler_demo.core.exceptions import CrawlerError
from crawler_demo.cli import count_output_records
from crawler_demo.spiders.qheze_site.spider import (
    QhezeHtmlPageParser,
    QhezeSiteSpider,
)
from crawler_demo.spiders.site_mirror.spider import (
    FetchResult,
    SiteMirrorHtmlPageParser,
    SiteMirrorSpider,
)


class QhezeSiteSpiderTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.spider = SiteMirrorSpider()

    def test_normalize_url_removes_fragment_and_default_index(self) -> None:
        normalized = self.spider._normalize_url(
            "http://www.qheze.com/products/index.html#section"
        )
        self.assertEqual(normalized, "http://www.qheze.com/products/")

    def test_should_follow_page_only_allows_same_domain_html_pages(self) -> None:
        self.assertTrue(
            self.spider._should_follow_page(
                "http://www.qheze.com/news/detail.html?id=1",
                allowed_domain="www.qheze.com",
            )
        )
        self.assertFalse(
            self.spider._should_follow_page(
                "https://cdn.qheze.com/banner.jpg",
                allowed_domain="www.qheze.com",
            )
        )
        self.assertFalse(
            self.spider._should_follow_page(
                "http://example.com/about.html",
                allowed_domain="www.qheze.com",
            )
        )

    def test_is_resource_url_detects_common_downloadable_assets(self) -> None:
        self.assertTrue(
            self.spider._is_resource_url("http://www.qheze.com/files/guide.pdf")
        )
        self.assertTrue(
            self.spider._is_resource_url("http://www.qheze.com/assets/logo.png")
        )
        self.assertFalse(
            self.spider._is_resource_url("http://www.qheze.com/product/detail.html")
        )

    def test_extract_page_record_collects_links_resources_and_text(self) -> None:
        html = """
        <html>
          <head>
            <title>测试页面</title>
            <meta name="keywords" content="云服务器,高防" />
            <meta name="description" content="页面描述" />
          </head>
          <body>
            <header>
              <a href="/products/index.html">产品中心</a>
            </header>
            <main>
              <h1>企业上云</h1>
              <p>提供稳定的云服务。</p>
              <a href="/docs/guide.pdf">产品手册</a>
              <img src="/assets/banner.png" />
            </main>
          </body>
        </html>
        """

        page_record = self.spider._extract_page_record(
            url="http://www.qheze.com/",
            html=html,
            status_code=200,
        )

        self.assertEqual(page_record["title"], "测试页面")
        self.assertEqual(page_record["meta"]["keywords"], "云服务器,高防")
        self.assertIn("企业上云", page_record["text"])
        self.assertIn("http://www.qheze.com/products/", page_record["links"])
        self.assertIn("http://www.qheze.com/docs/guide.pdf", page_record["resources"])
        self.assertIn("http://www.qheze.com/assets/banner.png", page_record["resources"])

    def test_fetch_url_wraps_remote_disconnected_error(self) -> None:
        with patch(
            "crawler_demo.spiders.site_mirror.spider.urlopen",
            side_effect=RemoteDisconnected("closed"),
        ):
            with self.assertRaises(CrawlerError):
                self.spider._fetch_url("http://www.qheze.com/", timeout=5)

    def test_run_continues_when_child_page_fetch_fails(self) -> None:
        first_page = FetchResult(
            url="http://www.qheze.com/",
            status_code=200,
            content_type="text/html; charset=utf-8",
            body=b'<html><head><title>Home</title></head><body><a href="/bad.html">bad</a></body></html>',
        )

        with patch.object(
            self.spider,
            "_fetch_url",
            side_effect=[first_page, CrawlerError("boom")],
        ):
            payload = self.spider.run(
                {
                    "start_url": "http://www.qheze.com/",
                    "max_pages": 5,
                    "timeout": 5,
                    "resources_dir": "output/test/resources",
                    "output_dir": "output/test",
                }
            )

        self.assertEqual(len(payload["pages"]), 1)
        self.assertEqual(len(payload["errors"]), 1)
        self.assertEqual(payload["errors"][0]["url"], "http://www.qheze.com/bad.html")

    def test_build_request_url_encodes_non_ascii_path(self) -> None:
        request_url = self.spider._build_request_url(
            "https://www.shsnc.com/uploads/案例/图片 文件.png?name=中文"
        )
        self.assertEqual(
            request_url,
            "https://www.shsnc.com/uploads/%E6%A1%88%E4%BE%8B/%E5%9B%BE%E7%89%87%20%E6%96%87%E4%BB%B6.png?name=%E4%B8%AD%E6%96%87",
        )


class CompatibilityTestCase(unittest.TestCase):
    def test_qheze_site_keeps_backward_compatible_name(self) -> None:
        self.assertEqual(QhezeSiteSpider.name, "qheze_site")
        self.assertTrue(issubclass(QhezeSiteSpider, SiteMirrorSpider))

    def test_qheze_html_parser_aliases_generic_parser(self) -> None:
        self.assertIs(QhezeHtmlPageParser, SiteMirrorHtmlPageParser)

    def test_count_output_records_uses_pages_when_payload_is_dict(self) -> None:
        payload = {"pages": [{"url": "a"}, {"url": "b"}], "resources": []}
        self.assertEqual(count_output_records(payload), 2)


class SiteMirrorHtmlPageParserTestCase(unittest.TestCase):
    def test_parser_ignores_script_and_style_text(self) -> None:
        parser = SiteMirrorHtmlPageParser(base_url="http://www.qheze.com/")
        parser.feed(
            """
            <html>
              <head>
                <title>标题</title>
                <style>.hidden { display:none; }</style>
              </head>
              <body>
                <script>console.log('ignore')</script>
                <p>正文内容</p>
              </body>
            </html>
            """
        )

        self.assertEqual(parser.title, "标题")
        self.assertEqual(parser.text_chunks, ["标题", "正文内容"])


if __name__ == "__main__":
    unittest.main()
