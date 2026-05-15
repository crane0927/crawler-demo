# Python 爬虫项目骨架

这是一个适合持续扩展的 Python 爬虫项目骨架。当前内置了一个 GitHub 项目抓取 spider，后续你可以继续往 `spiders/` 目录补充不同站点或不同业务场景的抓取脚本。

## 功能说明

- 统一命令行入口
- 按 spider 维度拆分目录，便于后续扩展
- 抽离公共异常、HTTP 请求和 spider 基类
- 当前已内置 GitHub 项目抓取能力
- 支持通过环境变量 `GITHUB_TOKEN` 提升 GitHub API 访问额度
- 支持将结果保存为 JSON 文件

## 项目结构

```text
crawler-demo/
├── pyproject.toml
├── README.md
└── src/
    └── crawler_demo/
        ├── __init__.py
        ├── __main__.py
        ├── cli.py
        ├── core/
        │   ├── base.py
        │   ├── exceptions.py
        │   ├── http.py
        │   └── registry.py
        └── spiders/
            └── github_projects/
                └── spider.py
```

## 环境要求

- Python 3.10 及以上

## 快速开始

1. 创建虚拟环境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. 安装项目

```bash
pip install -e .
```

3. 查看当前已注册 spider

```bash
crawler-demo list
```

4. 执行指定 spider

```bash
crawler-demo run github_projects --query "python crawler" --limit 5 --output output/github/repos.json
```

也可以直接通过模块运行：

```bash
python -m crawler_demo run github_projects --query "python crawler" --limit 5
```

## 兼容旧命令

为了兼容前面已经使用过的命令，旧入口仍可继续使用：

```bash
github-project-crawler "python crawler" --limit 5
```

## 可选配置

如果你有 GitHub Token，建议先设置环境变量，避免未登录请求额度过低：

```bash
export GITHUB_TOKEN="你的 GitHub Token"
```

## 当前内置 spider

### `github_projects`

用于通过 GitHub Search API 搜索仓库项目，默认输出以下字段：

- `name`
- `full_name`
- `html_url`
- `description`
- `language`
- `stargazers_count`
- `forks_count`
- `open_issues_count`
- `watchers_count`
- `created_at`
- `updated_at`
- `pushed_at`
- `topics`
- `owner`

## 后续扩展示例

如果后续要新增其他 spider，推荐按以下方式组织：

```text
src/crawler_demo/spiders/
├── github_projects/
│   └── spider.py
├── juejin_articles/
│   └── spider.py
└── bilibili_videos/
    └── spider.py
```

新增后只需要：

- 在对应目录实现新的 spider 类
- 在 `core/registry.py` 中注册 spider
- 在需要时为该 spider 增加专属参数处理

## 注意事项

- GitHub Search API 有速率限制，未设置 Token 时更容易触发限制
- 当前 GitHub 示例基于 GitHub 官方 API 抓取，不是通过解析网页 HTML
- 如果后续新增需要登录态、代理、限速控制的 spider，建议继续沉淀到 `core/` 公共层
