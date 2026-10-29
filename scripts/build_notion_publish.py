"""Prepare one Notion article for a reviewed pull request."""

import argparse
import re
from pathlib import Path
from build_notion_preview import pages, plain

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

    status = plain(matches[0].get("properties", {}).get("發布狀態", {}))
    if status != "待審核":
        raise ValueError(f"文章狀態為「{status}」，不是「待審核」")

    return matches[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="指定單篇文章的網址代稱")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug):
        parser.error("文章網址代稱只能包含小寫英文字母、數字及中間的連字號")

    article_file = ROOT / "articles" / args.slug / "index.html"

    if article_file.exists():
        parser.error(f"停止執行：文章已存在，不允許覆蓋：{article_file}")

    print(f"已指定新文章：{args.slug}")
    print("檢查通過。目前不會讀取 Notion，也不會修改網站檔案。")


if __name__ == "__main__":
    main()
