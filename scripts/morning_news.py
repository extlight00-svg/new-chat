#!/usr/bin/env python3
import argparse
import html
import json
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo


FEEDS = {
    "korea": [
        "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
    ],
    "global": [
        "https://news.google.com/rss/search?q=%EA%B5%AD%EC%A0%9C%20OR%20%EC%84%B8%EA%B3%84&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=%EA%B2%BD%EC%A0%9C%20OR%20%EA%B8%88%EC%9C%B5&hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=%EA%B8%B0%EC%88%A0%20OR%20AI%20OR%20%EB%B0%98%EB%8F%84%EC%B2%B4&hl=ko&gl=KR&ceid=KR:ko",
    ],
}


def load_dotenv(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value)


def fetch_text(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 news-briefing-bot/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def clean_text(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def parse_feed(url):
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item"):
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        description = clean_text(item.findtext("description"))
        source = ""
        source_node = item.find("source")
        if source_node is not None:
            source = clean_text(source_node.text)
        published = item.findtext("pubDate")
        published_at = None
        if published:
            try:
                published_at = parsedate_to_datetime(published)
            except (TypeError, ValueError):
                published_at = None
        if title and link:
            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": description,
                    "source": source,
                    "published_at": published_at,
                }
            )
    return items


def dedupe(items):
    seen = set()
    unique = []
    for item in items:
        key = re.sub(r"\W+", "", item["title"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def summarize(item):
    text = item["description"]
    if not text or text == item["title"]:
        text = item["title"]
    text = re.sub(r" - [^-]{2,30}$", "", text)
    return textwrap.shorten(text, width=95, placeholder="...")


def collect(category, limit):
    items = []
    for url in FEEDS[category]:
        try:
            items.extend(parse_feed(url))
        except Exception as exc:
            print(f"Feed failed: {url} ({exc})", file=sys.stderr)
    items = dedupe(items)
    items.sort(key=lambda item: item["published_at"] or datetime.min.replace(tzinfo=ZoneInfo("UTC")), reverse=True)
    return items[:limit]


def format_item(index, item):
    source = f" / {item['source']}" if item.get("source") else ""
    return f"{index}. {item['title']}{source}\n   {summarize(item)}\n   {item['link']}"


def build_message():
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    korea = collect("korea", 5)
    global_items = collect("global", 5)

    lines = [
        f"아침 뉴스 브리핑 ({now} KST)",
        "",
        "한국 주요 뉴스",
    ]
    lines.extend(format_item(index, item) for index, item in enumerate(korea, 1))
    lines.extend(["", "국제/경제/기술 핵심 뉴스"])
    lines.extend(format_item(index, item) for index, item in enumerate(global_items, 1))
    lines.extend(
        [
            "",
            "오늘의 관전 포인트",
            "1. 국내 정치/사회 이슈의 후속 발표와 시장 반응",
            "2. 글로벌 증시, 환율, 원자재 가격의 방향성",
            "3. AI, 반도체, 플랫폼 기업 관련 정책 및 실적 뉴스",
        ]
    )
    return "\n".join(lines)


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    data = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    request = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram send failed: {payload}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--env-file", default=".telegram_news.env")
    args = parser.parse_args()

    load_dotenv(args.env_file)
    message = build_message()
    if args.dry_run:
        print(message)
        return
    send_telegram(message)
    print("Telegram news briefing sent.")


if __name__ == "__main__":
    main()
