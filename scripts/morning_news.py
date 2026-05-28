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
    "politics_election": [],
    "economy": [],
    "global_tech": [],
}

TV_SOURCES = ["SBS", "MBC", "KBS", "JTBC"]


def google_news_url(query):
    params = urllib.parse.urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return f"https://news.google.com/rss/search?{params}"


FEEDS["politics_election"] = [
    google_news_url("전국동시지방선거 OR 지방선거 OR 선거 여론조사"),
    google_news_url("(SBS OR MBC OR KBS OR JTBC) 선거 후보 공약 판세 검증"),
    google_news_url("선거관리 허위정보 논란 후보 정당"),
]
FEEDS["economy"] = [
    google_news_url("한국 경제 환율 증시 금리 물가"),
    google_news_url("이란 중동 긴장 국제유가 원달러 환율 한국 경제"),
    google_news_url("에너지 석유화학 항공 해운 자동차 반도체 수출 물류 운임"),
]
FEEDS["global_tech"] = [
    google_news_url("국제 세계 안보 외교"),
    google_news_url("AI 반도체 기술 플랫폼 기업"),
]


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


def importance_note(category, item):
    text = f"{item['title']} {item.get('description', '')}"
    if category == "politics_election":
        if any(word in text for word in ["여론조사", "판세", "지지율"]):
            return "왜 중요: 선거 구도와 지역별 표심 변화를 가늠할 단서입니다."
        if any(word in text for word in ["공약", "정책"]):
            return "왜 중요: 후보와 정당의 실제 선택지를 비교하는 기준이 됩니다."
        if any(word in text for word in ["허위", "논란", "검증", "선관위"]):
            return "왜 중요: 유권자 판단과 선거 신뢰에 직접 영향을 줄 수 있습니다."
        return "왜 중요: 선거 전 정치 일정과 여론 흐름을 읽는 데 필요합니다."
    if category == "economy":
        if any(word in text for word in ["이란", "중동", "유가", "호르무즈"]):
            return "왜 중요: 에너지 비용, 물류비, 환율을 통해 한국 기업 비용에 번질 수 있습니다."
        if any(word in text for word in ["환율", "원/달러", "금리", "증시"]):
            return "왜 중요: 금융시장과 가계·기업 자금 조달 여건에 영향을 줍니다."
        if any(word in text for word in ["반도체", "자동차", "수출", "해운", "항공"]):
            return "왜 중요: 한국 주력 산업의 실적과 공급망 리스크로 이어질 수 있습니다."
        return "왜 중요: 한국 경제의 오늘 시장 분위기와 정책 대응을 보여줍니다."
    return "왜 중요: 국제 질서와 기술 산업 흐름이 국내 정책·기업 전략에 영향을 줍니다."


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


def format_section_item(category, index, item):
    return f"{format_item(index, item)}\n   {importance_note(category, item)}"


def lead_sentence(politics, economy):
    first_politics = politics[0]["title"] if politics else "정치권 주요 이슈"
    first_economy = economy[0]["title"] if economy else "경제 주요 변수"
    return textwrap.shorten(
        f"핵심 알림: 오늘은 '{first_politics}'와 '{first_economy}'를 중심으로 선거·경제 리스크를 함께 확인하세요.",
        width=120,
        placeholder="...",
    )


def should_focus_election(now):
    election_day = datetime(2026, 6, 3, 23, 59, tzinfo=ZoneInfo("Asia/Seoul"))
    return now <= election_day


def build_message():
    now_dt = datetime.now(ZoneInfo("Asia/Seoul"))
    now = now_dt.strftime("%Y-%m-%d %H:%M")
    politics = collect("politics_election", 5 if should_focus_election(now_dt) else 3)
    economy = collect("economy", 5)
    global_items = collect("global_tech", 4)

    lines = [
        lead_sentence(politics, economy),
        "",
        f"아침 뉴스 브리핑 ({now} KST)",
        "",
        "정치/선거 주요 뉴스",
    ]
    lines.extend(format_section_item("politics_election", index, item) for index, item in enumerate(politics, 1))
    lines.extend(["", "경제 주요 뉴스"])
    lines.extend(format_section_item("economy", index, item) for index, item in enumerate(economy, 1))
    lines.extend(["", "국제/기술 핵심 뉴스"])
    lines.extend(format_section_item("global_tech", index, item) for index, item in enumerate(global_items, 1))
    lines.extend(
        [
            "",
            "오늘의 관전 포인트",
            "1. 후보·정당별 공약, 지역별 판세, 여론조사 변화가 실제 투표 구도에 미치는 영향",
            "2. 중동 긴장, 국제유가, 원/달러 환율이 한국 증시와 주력 수출 업종에 주는 압력",
            "3. AI, 반도체, 플랫폼 기업 관련 정책·실적 뉴스가 국내 산업 전략에 주는 신호",
            "",
            "참고: 방송사 공식 보도와 주요 뉴스 검색 결과를 우선 반영하며, 여러 출처에서 반복되는 쟁점을 중심으로 요약합니다.",
        ]
    )
    return "\n".join(lines)


def split_message(message, limit=3800):
    chunks = []
    current = ""
    for block in message.split("\n\n"):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = block
    if current:
        chunks.append(current)
    return chunks


def send_telegram_message(token, chat_id, message):
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


def send_telegram(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    chunks = split_message(message)
    for index, chunk in enumerate(chunks, 1):
        prefix = f"({index}/{len(chunks)})\n" if len(chunks) > 1 else ""
        send_telegram_message(token, chat_id, f"{prefix}{chunk}")


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
