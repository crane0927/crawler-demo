from __future__ import annotations

from crawler_demo.spiders.site_mirror.spider import (
    SiteMirrorHtmlPageParser as QhezeHtmlPageParser,
)
from crawler_demo.spiders.site_mirror.spider import SiteMirrorSpider
from crawler_demo.spiders.site_mirror.spider import (
    SiteMirrorSpiderConfig as QhezeSiteSpiderConfig,
)


class QhezeSiteSpider(SiteMirrorSpider):
    """兼容旧 spider 名称，内部复用通用整站抓取实现。"""

    name = "qheze_site"
