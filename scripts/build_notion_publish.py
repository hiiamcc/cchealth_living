"""Prepare one Notion article for a reviewed pull request."""

import argparse
import re
from pathlib import Path

from build_notion_preview import pages, plain, blocks, render_children, youtube_embed
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent.parent

def find_notion_article(slug):
    matches = []

    for page in pages():
        properties = page.get("properties", {})
        page_slug = plain(properties.get("文章網址代稱", {})).strip()

        if page_slug == slug:
            matches.append(page)

    if len(matches) != 1:
        raise ValueError(f"找到 {len(matches)} 篇符合網址代稱的文章，必須剛好一篇")

    status = (matches[0].get("properties", {}).get("發布狀態", {}).get("select") or {}).get("name", "")
    if status != "待審核":
        raise ValueError(f"文章狀態為「{status}」，不是「待審核」")

    return matches[0]

def build_article_html(article):
    """使用現有模板產生文章 HTML，不修改網站檔案。"""
    props = article["properties"]

    title = plain(props.get("文章標題"))
    summary = plain(props.get("文章摘要"))
    category = plain(props.get("文章分類"))
    slug = plain(props.get("文章網址代稱"))

    template_path = ROOT / "templates" / "article-template.html"
    template = template_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(template, "html.parser")

    article_element = soup.select_one("article.art-page")
    head = soup.select_one("article .art-head")
    prose = soup.select_one("article .prose")

    if not article_element or not head or not prose:
        raise RuntimeError("文章模板缺少必要元素")

    article_element["id"] = slug

    h1 = head.find("h1")
    if h1:
        h1.clear()
        h1.append(title)

    summary_element = head.find("p")
    if summary_element:
        summary_element.clear()
        summary_element.append(summary)

    badge = head.select_one(".badge")
    if badge:
        badge.string = category or "健康知識"

    # 更新文章上方的分類導覽文字
    breadcrumb = soup.select_one("nav.crumb")
    if breadcrumb:
        links = breadcrumb.find_all("a")
        if len(links) >= 2:
            links[-1].string = category or "健康知識"

    body = render_children(blocks(article["id"]))
    prose.clear()

    for child in BeautifulSoup(body, "html.parser").contents[:]:
        prose.append(child)

    video = plain(props.get("YouTube 網址"))
    wrap = soup.select_one(".video-wrap")

    if wrap:
        embed = youtube_embed(video)
        if embed:
            frame = wrap.find("iframe")
            if not frame:
                raise RuntimeError("文章模板缺少 YouTube iframe")
            frame["src"] = embed
            frame["title"] = title

            anchor = wrap.find("a", href=True)
            if anchor:
                anchor["href"] = video
        else:
            wrap.decompose()

    soup.title.string = title + "｜多C多健康"

    description = soup.find("meta", attrs={"name": "description"})
    if description:
        description["content"] = summary

    article_url = (
        "https://hiiamcc.github.io/cchealth_living/"
        f"articles/{slug}/"
    )

    for meta in soup.find_all("meta", attrs={"property": True}):
        if meta["property"] == "og:title":
            meta["content"] = title
        elif meta["property"] == "og:description":
            meta["content"] = summary
        elif meta["property"] == "og:url":
            meta["content"] = article_url

    canonical = soup.find("link", rel="canonical")
    if canonical:
        canonical["href"] = article_url

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "articles/stroke-brain-recovery" in href:
            raise RuntimeError(
                "文章模板含有固定的舊文章連結，請先檢查"
            )
        
    return str(soup)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="指定單篇文章的網址代稱")
    
    parser.add_argument(
        "--mode",
        choices=["create", "update"],
        default="create",
        help="create 為新增文章；update 為更新既有文章",
    )

    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug):
        parser.error("文章網址代稱只能包含小寫英文字母、數字及中間的連字號")

    article_file = ROOT / "articles" / args.slug / "index.html"

    if args.mode == "create" and article_file.exists():
        parser.error(f"停止執行：文章已存在，不能重複新增：{article_file}")

    if args.mode == "update" and not article_file.exists():
        parser.error(f"停止執行：文章不存在，無法更新：{article_file}")

    article = find_notion_article(args.slug)
    print(f"已找到符合條件的 Notion 文章：{article['id']}")

    html = build_article_html(article)

    test_dir = ROOT / "publish-test-output"
    test_dir.mkdir(exist_ok=True)

    test_file = test_dir / f"{args.slug}.html"
    test_file.write_text(html, encoding="utf-8")

    print(f"HTML 測試檔案已產生：{test_file}")
    print("這只是測試檔案，尚未發布到正式網站。")



if __name__ == "__main__":
    main()
