from __future__ import annotations

from crawler_demo.core.base import BaseSpider
from crawler_demo.spiders.github_projects.spider import GitHubProjectsSpider
from crawler_demo.spiders.qheze_site.spider import QhezeSiteSpider
from crawler_demo.spiders.site_mirror.spider import SiteMirrorSpider
from crawler_demo.spiders.weibo_hot.spider import WeiboHotSpider

SPIDER_REGISTRY: dict[str, type[BaseSpider]] = {
    GitHubProjectsSpider.name: GitHubProjectsSpider,
    QhezeSiteSpider.name: QhezeSiteSpider,
    SiteMirrorSpider.name: SiteMirrorSpider,
    WeiboHotSpider.name: WeiboHotSpider,
}


def get_spider(name: str) -> type[BaseSpider]:
    try:
        return SPIDER_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"未找到 spider: {name}") from exc


def list_spider_names() -> list[str]:
    return sorted(SPIDER_REGISTRY)
