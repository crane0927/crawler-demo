from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from crawler_demo.core.exceptions import CrawlerError
from crawler_demo.core.registry import get_spider, list_spider_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="统一爬虫命令行入口")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="执行指定 spider")
    run_parser.add_argument(
        "spider",
        choices=list_spider_names(),
        help="要执行的 spider 名称，例如 github_projects",
    )
    run_parser.add_argument("--query", help="抓取关键字或查询条件，部分 spider 可不传")
    run_parser.add_argument("--limit", type=int, default=10, help="返回数据条数，默认 10")
    run_parser.add_argument(
        "--sort",
        default="stars",
        choices=["stars", "forks", "help-wanted-issues", "updated"],
        help="排序字段，默认 stars",
    )
    run_parser.add_argument(
        "--order",
        default="desc",
        choices=["asc", "desc"],
        help="排序方向，默认 desc",
    )
    run_parser.add_argument(
        "--output",
        help="输出 JSON 文件路径，例如 output/github/repos.json；不传则打印到终端",
    )
    run_parser.add_argument("--start-url", help="整站抓取起始 URL，部分 spider 可使用")
    run_parser.add_argument(
        "--max-pages",
        type=int,
        default=2000,
        help="整站抓取允许访问的最大页面数，默认 2000",
    )
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="单次请求超时时间（秒），默认 20",
    )
    run_parser.add_argument(
        "--resources-dir",
        help="资源文件下载目录，例如 output/qheze_site/resources",
    )
    run_parser.add_argument(
        "--output-dir",
        help="整站抓取输出目录，用于推导资源下载目录等",
    )

    list_parser = subparsers.add_parser("list", help="查看当前已注册的 spider")
    list_parser.set_defaults(command="list")

    return parser


def save_output(output_path: str, payload: Any) -> None:
    path = Path(output_path)
    # 输出目录可能尚未创建，这里统一补齐父目录，避免每个 spider 重复处理。
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def count_output_records(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        pages = payload.get("pages")
        if isinstance(pages, list):
            return len(pages)
    return 1


def run_spider(args: argparse.Namespace) -> int:
    spider_cls = get_spider(args.spider)
    spider = spider_cls()
    spider_args = {
        "query": args.query,
        "limit": args.limit,
        "sort": args.sort,
        "order": args.order,
        "start_url": args.start_url,
        "max_pages": args.max_pages,
        "timeout": args.timeout,
        "resources_dir": args.resources_dir,
        "output_dir": args.output_dir,
    }

    try:
        items = spider.run(spider_args)
    except CrawlerError as exc:
        print(f"执行失败: {exc}")
        return 1

    if args.output:
        save_output(args.output, items)
        print(f"已保存 {count_output_records(items)} 条记录到 {args.output}")
        return 0

    print(json.dumps(items, ensure_ascii=False, indent=2))
    return 0


def print_spider_list() -> int:
    for spider_name in list_spider_names():
        print(spider_name)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "run":
        raise SystemExit(run_spider(args))

    if args.command == "list":
        raise SystemExit(print_spider_list())

    parser.print_help()
    raise SystemExit(1)


def legacy_main() -> None:
    """兼容旧命令行入口，内部转为执行 GitHub 项目 spider。"""
    parser = argparse.ArgumentParser(description="抓取 GitHub 项目信息")
    parser.add_argument("query", help="GitHub 搜索关键词，例如: python crawler")
    parser.add_argument("--limit", type=int, default=10, help="返回项目数量，默认 10")
    parser.add_argument(
        "--sort",
        default="stars",
        choices=["stars", "forks", "help-wanted-issues", "updated"],
        help="排序字段，默认 stars",
    )
    parser.add_argument(
        "--order",
        default="desc",
        choices=["asc", "desc"],
        help="排序方向，默认 desc",
    )
    parser.add_argument(
        "--output",
        help="输出 JSON 文件路径，例如 output/repos.json；不传则打印到终端",
    )
    args = parser.parse_args()

    namespace = argparse.Namespace(
        spider="github_projects",
        query=args.query,
        limit=args.limit,
        sort=args.sort,
        order=args.order,
        output=args.output,
    )
    raise SystemExit(run_spider(namespace))
