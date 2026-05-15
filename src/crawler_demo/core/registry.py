from __future__ import annotations

from crawler_demo.core.base import BaseSpider
from crawler_demo.spiders.github_projects.spider import GitHubProjectsSpider

SPIDER_REGISTRY: dict[str, type[BaseSpider]] = {
    GitHubProjectsSpider.name: GitHubProjectsSpider,
}


def get_spider(name: str) -> type[BaseSpider]:
    try:
        return SPIDER_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"未找到 spider: {name}") from exc


def list_spider_names() -> list[str]:
    return sorted(SPIDER_REGISTRY)
