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
    "politics": [],
    "economy": [],
    "global_tech": [],
}

PRIMARY_SOURCES = ["KBS", "MBC", "SBS", "JTBC"]
SECONDARY_SOURCES = ["중앙일보", "경향신문", "한국경제"]
YOUTUBE_NEWS_SOURCES = [
    "KBS News",
    "MBCNEWS",
    "SBS 뉴스",
    "JTBC News",
    "YTN",
    "연합뉴스TV",
    "채널A News",
    "MBN News",
    "TV조선 뉴스",
    "오마이TV",
]
GARAK_DONG_LATITUDE = 37.4933
GARAK_DONG_LONGITUDE = 127.1183


def google_news_url(query):
    params = urllib.parse.urlencode({"q": query, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
    return f"https://news.google.com/rss/search?{params}"


FEEDS["politics"] = [
    google_news_url("(KBS OR MBC OR SBS OR JTBC) 정치 국회 대통령실 정당 정책 논쟁"),
    google_news_url("(중앙일보 OR 경향신문 OR 한국경제) 정치 국회 대통령실 정당 정책"),
    google_news_url("site:youtube.com (KBS News OR MBCNEWS OR SBS 뉴스 OR JTBC News OR YTN OR 연합뉴스TV) 정치 뉴스"),
]
FEEDS["economy"] = [
    google_news_url("(KBS OR MBC OR SBS OR JTBC) 한국 경제 환율 증시 금리 물가"),
    google_news_url("(중앙일보 OR 경향신문 OR 한국경제) 경제 환율 증시 금리 물가"),
    google_news_url("이란 중동 긴장 국제유가 원달러 환율 한국 경제"),
    google_news_url("에너지 석유화학 항공 해운 자동차 반도체 수출 물류 운임"),
]
FEEDS["global_tech"] = [
    google_news_url("(KBS OR MBC OR SBS OR JTBC) 국제 안보 외교 미중 중동 공급망"),
    google_news_url("(중앙일보 OR 경향신문 OR 한국경제) AI 반도체 공급망 미국 중국 한국 기업"),
    google_news_url("site:youtube.com (KBS News OR MBCNEWS OR SBS 뉴스 OR JTBC News OR YTN OR 연합뉴스TV) 국제 기술 뉴스"),
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


def source_text(item):
    return f"{item.get('source', '')} {item.get('title', '')}"


def source_rank(item):
    source = item.get("source", "")
    text = source_text(item)
    if "YouTube" in source:
        return 2
    if any(source_name in source for source_name in PRIMARY_SOURCES):
        return 0
    if any(source_name in source for source_name in SECONDARY_SOURCES):
        return 1
    if any(source_name in text for source_name in YOUTUBE_NEWS_SOURCES):
        return 2
    return 3


def normalized_source(item):
    source_name = item.get("source", "")
    if "YouTube" in source_name:
        return "YouTube"
    text = source_text(item)
    for source in PRIMARY_SOURCES + SECONDARY_SOURCES + YOUTUBE_NEWS_SOURCES:
        if source in text:
            return source
    return source_name or "기타"


def weather_description(code):
    descriptions = {
        0: "맑음",
        1: "대체로 맑음",
        2: "구름 조금",
        3: "흐림",
        45: "안개",
        48: "서리 안개",
        51: "약한 이슬비",
        53: "이슬비",
        55: "강한 이슬비",
        61: "약한 비",
        63: "비",
        65: "강한 비",
        71: "약한 눈",
        73: "눈",
        75: "강한 눈",
        80: "약한 소나기",
        81: "소나기",
        82: "강한 소나기",
        95: "뇌우",
    }
    return descriptions.get(code, "날씨 변동")


def air_quality_note(pm25, pm10):
    if pm25 is None and pm10 is None:
        return "대기질 정보 확인 필요"
    value = max(value for value in [pm25, pm10] if value is not None)
    if value <= 15:
        return "대기질 좋음"
    if value <= 35:
        return "대기질 보통"
    if value <= 75:
        return "대기질 나쁨"
    return "대기질 매우 나쁨"


def commute_note(temp, precipitation, pm25, pm10):
    notes = []
    if precipitation and precipitation > 0:
        notes.append("우산을 챙기세요")
    if temp is not None and temp >= 28:
        notes.append("더위와 수분 보충을 신경 쓰세요")
    elif temp is not None and temp <= 5:
        notes.append("겉옷을 따뜻하게 챙기세요")
    if air_quality_note(pm25, pm10) in ["대기질 나쁨", "대기질 매우 나쁨"]:
        notes.append("마스크를 준비하면 좋습니다")
    if not notes:
        notes.append("출근길 큰 불편은 적어 보입니다")
    return ", ".join(notes) + "."


def fetch_weather():
    forecast_params = urllib.parse.urlencode(
        {
            "latitude": GARAK_DONG_LATITUDE,
            "longitude": GARAK_DONG_LONGITUDE,
            "current": "temperature_2m,apparent_temperature,precipitation,rain,weather_code",
            "timezone": "Asia/Seoul",
        }
    )
    air_params = urllib.parse.urlencode(
        {
            "latitude": GARAK_DONG_LATITUDE,
            "longitude": GARAK_DONG_LONGITUDE,
            "current": "pm10,pm2_5",
            "timezone": "Asia/Seoul",
        }
    )
    forecast = json.loads(fetch_text(f"https://api.open-meteo.com/v1/forecast?{forecast_params}"))
    air = json.loads(fetch_text(f"https://air-quality-api.open-meteo.com/v1/air-quality?{air_params}"))
    current = forecast.get("current", {})
    air_current = air.get("current", {})
    temp = current.get("temperature_2m")
    feels_like = current.get("apparent_temperature")
    precipitation = current.get("precipitation")
    pm10 = air_current.get("pm10")
    pm25 = air_current.get("pm2_5")
    return {
        "description": weather_description(current.get("weather_code")),
        "temperature": temp,
        "feels_like": feels_like,
        "precipitation": precipitation,
        "air_quality": air_quality_note(pm25, pm10),
        "commute": commute_note(temp, precipitation, pm25, pm10),
    }


def format_weather(weather):
    if not weather:
        return "서울 가락동 오늘의 날씨: 실시간 날씨 정보를 가져오지 못했습니다."
    temp = f"{weather['temperature']}°C" if weather.get("temperature") is not None else "확인 필요"
    feels = f"{weather['feels_like']}°C" if weather.get("feels_like") is not None else "확인 필요"
    precipitation = weather.get("precipitation")
    rain = f"{precipitation}mm" if precipitation is not None else "확인 필요"
    return (
        f"서울 가락동 오늘의 날씨: {weather['description']}, 현재 {temp}, "
        f"체감 {feels}, 강수 {rain}, {weather['air_quality']}. "
        f"출근길: {weather['commute']}"
    )


def importance_note(category, item):
    text = f"{item['title']} {item.get('description', '')}"
    if category == "politics":
        if any(word in text for word in ["국회", "입법", "법안"]):
            return "왜 중요: 정책 변화와 입법 일정이 생활·기업 환경에 영향을 줄 수 있습니다."
        if any(word in text for word in ["공약", "정책"]):
            return "왜 중요: 정부와 정당의 정책 방향을 가늠하는 기준입니다."
        if any(word in text for word in ["외교", "안보", "북한", "미국", "중국", "일본"]):
            return "왜 중요: 외교·안보 변수는 시장과 산업 정책에도 영향을 줍니다."
        if any(word in text for word in ["논란", "수사", "검찰", "법원"]):
            return "왜 중요: 정치 신뢰와 국정 운영 동력에 영향을 줄 수 있습니다."
        return "왜 중요: 한국 정치 흐름과 정책 우선순위를 읽는 데 필요합니다."
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
    items.sort(
        key=lambda item: (
            source_rank(item),
            -(item["published_at"] or datetime.min.replace(tzinfo=ZoneInfo("UTC"))).timestamp(),
        )
    )
    selected = []
    counts = {}
    for item in items:
        source = normalized_source(item)
        if counts.get(source, 0) >= 2:
            continue
        selected.append(item)
        counts[source] = counts.get(source, 0) + 1
        if len(selected) == limit:
            return selected
    for item in items:
        if item in selected:
            continue
        selected.append(item)
        if len(selected) == limit:
            break
    return selected


def format_item(index, item):
    title = html.escape(item["title"])
    source = f" / {html.escape(item['source'])}" if item.get("source") else ""
    link = html.escape(item["link"], quote=True)
    return f'{index}. {title}{source} | <a href="{link}">기사 보기</a>'


def format_section_item(category, index, item):
    note = html.escape(importance_note(category, item).replace("왜 중요: ", ""))
    return f"{format_item(index, item)} | {note}"


def lead_sentence(politics, economy):
    first_politics = politics[0]["title"] if politics else "정치권 주요 이슈"
    first_economy = economy[0]["title"] if economy else "경제 주요 변수"
    sentence = textwrap.shorten(
        f"핵심 알림: 오늘은 '{first_politics}'와 '{first_economy}'를 중심으로 정치·경제 흐름을 함께 확인하세요.",
        width=120,
        placeholder="...",
    )
    return html.escape(sentence)


def build_message():
    now_dt = datetime.now(ZoneInfo("Asia/Seoul"))
    now = now_dt.strftime("%Y-%m-%d %H:%M")
    try:
        weather = fetch_weather()
    except Exception as exc:
        print(f"Weather failed: {exc}", file=sys.stderr)
        weather = None
    politics = collect("politics", 5)
    economy = collect("economy", 5)
    global_items = collect("global_tech", 4)

    lines = [
        lead_sentence(politics, economy),
        "",
        f"아침 뉴스 브리핑 ({now} KST)",
        "",
        format_weather(weather),
        "",
        "정치 주요 뉴스",
    ]
    lines.extend(format_section_item("politics", index, item) for index, item in enumerate(politics, 1))
    lines.extend(["", "경제 주요 뉴스"])
    lines.extend(format_section_item("economy", index, item) for index, item in enumerate(economy, 1))
    lines.extend(["", "국제/기술 핵심 뉴스"])
    lines.extend(format_section_item("global_tech", index, item) for index, item in enumerate(global_items, 1))
    lines.extend(
        [
            "",
            "오늘의 관전 포인트",
            "1. 국회·대통령실·정당 간 정책 논쟁이 국정 운영과 민생 정책에 미치는 영향",
            "2. 중동 긴장, 국제유가, 원/달러 환율이 한국 증시와 주력 수출 업종에 주는 압력",
            "3. AI, 반도체, 플랫폼 기업 관련 정책·실적 뉴스가 국내 산업 전략에 주는 신호",
            "",
            "참고: KBS·MBC·SBS·JTBC를 우선 보고, 중앙일보·경향신문·한국경제와 주요 유튜브 뉴스 채널에서 반복되는 쟁점을 함께 반영합니다.",
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
            "parse_mode": "HTML",
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
