"""Prepare exactly one Notion article for a reviewed pull request."""

import argparse
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="指定單篇文章的網址代稱")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.slug):
        parser.error("文章網址代稱只能包含小寫英文字母、數字及中間的連字號")

    print(f"已指定文章：{args.slug}")
    print("目前僅檢查文章代稱，不會讀取 Notion 或修改網站檔案。")


if __name__ == "__main__":
    main()
