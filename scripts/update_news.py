"""
Daily news fetcher for Amazon TW Seller Dashboard.

Fetches latest e-commerce / Amazon / tariff news from Google News RSS,
dedupes, translates titles & summaries to Traditional Chinese using
OpenAI (optional - falls back to raw English if no API key),
and overwrites amazon-tw-seller-dashboard/newsdata.js.

Runs daily via GitHub Actions. See .github/workflows/daily-news.yml
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_FILE = ROOT / "amazon-tw-seller-dashboard" / "newsdata.js"
MAX_ITEMS = 25
LOOKBACK_DAYS = 14  # only keep items newer than this

# Topic -> (tag used in dashboard, Google News query)
TOPICS: list[tuple[str, str]] = [
    ("AMAZON", "Amazon FBA seller policy"),
    ("AMAZON", "Amazon Rufus AI shopping"),
    ("AMAZON", "Amazon marketplace news"),
    ("SHEIN", "Shein US tariff"),
    ("TEMU", "Temu US marketplace"),
    ("SHEIN / TEMU", "Shein Temu tariff"),
    ("TIKTOK SHOP", "TikTok Shop US"),
    ("WALMART", "Walmart marketplace ecommerce"),
    ("EBAY", "eBay earnings marketplace"),
    ("SHOPIFY", "Shopify ecommerce news"),
    ("JD.COM", "JD.com Joybuy Europe"),
    ("GOOGLE", "Google AI shopping agent"),
    ("SCOTUS", "SCOTUS IEEPA tariff refund"),
    ("INDUSTRY", "US retail sales ecommerce"),
    ("AI", "agentic commerce AI shopping"),
    ("BNPL", "buy now pay later ecommerce"),
    ("MARKETPLACE", "online marketplace sellers China"),
]

# Trusted source domains -> display name
SOURCE_MAP = {
    "cnbc.com": "CNBC",
    "bloomberg.com": "Bloomberg",
    "reuters.com": "Reuters",
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "forbes.com": "Forbes",
    "yahoo.com": "Yahoo Finance",
    "finance.yahoo.com": "Yahoo Finance",
    "marketplacepulse.com": "Marketplace Pulse",
    "modernretail.co": "Modern Retail",
    "retaildive.com": "Retail Dive",
    "digitalcommerce360.com": "Digital Commerce 360",
    "pymnts.com": "PYMNTS",
    "theinformation.com": "The Information",
    "axios.com": "Axios",
    "techcrunch.com": "TechCrunch",
    "geekwire.com": "GeekWire",
    "variety.com": "Variety",
    "adweek.com": "AdWeek",
    "marketingdive.com": "Marketing Dive",
    "businesswire.com": "BusinessWire",
    "prnewswire.com": "PR Newswire",
    "theguardian.com": "The Guardian",
    "nytimes.com": "NY Times",
    "apnews.com": "AP News",
    "ppc.land": "PPC Land",
    "ecommercebytes.com": "eCommerceBytes",
    "sellercentral.amazon.com": "Amazon Seller Central",
    "valueaddedresource.net": "Value Added Resource",
    "thefashionlaw.com": "The Fashion Law",
    "wired.com": "Wired",
    "census.gov": "US Census Bureau",
    "corporate.walmart.com": "Walmart",
    "shopify.com": "Shopify",
    "ebayinc.com": "eBay",
    "newsweek.com": "Newsweek",
    "fool.com": "Motley Fool",
    "insideretail.asia": "Inside Retail",
    "quivo.co": "Quivo",
    "wikipedia.org": "Wikipedia",
    "retailbrew.com": "Retail Brew",
    "engadget.com": "Engadget",
    "reutersagency.com": "Reuters",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def google_news_rss(query: str, days: int = LOOKBACK_DAYS) -> str:
    """Build a Google News RSS URL filtering by recency."""
    q = f'{query} when:{days}d'
    return (
        f"https://news.google.com/rss/search?q={quote_plus(q)}"
        f"&hl=en-US&gl=US&ceid=US:en"
    )


def clean_summary(raw: str) -> str:
    """Google News summary is HTML with <a> tags – strip it."""
    if not raw:
        return ""
    # remove tags
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text).strip()
    # keep only first sentence-ish
    text = re.split(r"(?<=[.。!?！？])\s", text)[0]
    return text[:280]


def resolve_source(entry) -> tuple[str, str]:
    """Return (display_name, url). Google News wraps the url; try to get origin."""
    url = entry.get("link", "")
    # Google News RSS often has source tag
    src_name = ""
    source = entry.get("source")
    if source:
        if isinstance(source, dict):
            src_name = source.get("title") or source.get("value") or ""
        else:
            src_name = str(source)

    # Try to detect domain from URL if provided
    if not src_name and url:
        m = re.search(r"https?://([^/]+)/", url)
        if m:
            domain = m.group(1).replace("www.", "")
            src_name = SOURCE_MAP.get(domain, domain)

    # Normalize via SOURCE_MAP if it's a domain-y string
    key = src_name.lower().replace("www.", "")
    src_name = SOURCE_MAP.get(key, src_name)

    return src_name or "Google News", url


def parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_topic(tag: str, query: str) -> list[dict]:
    url = google_news_rss(query)
    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"  ! failed {query}: {e}")
        return []

    items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    for entry in feed.entries[:8]:
        pub = parse_date(entry)
        if not pub or pub < cutoff:
            continue
        src_name, src_url = resolve_source(entry)
        items.append({
            "tag": tag,
            "pub_dt": pub,
            "date": pub.strftime("%m/%d/%Y"),
            "title_en": entry.get("title", "").strip(),
            "body_en": clean_summary(entry.get("summary", "")),
            "src": src_url,
            "via": src_name,
        })
    return items


def dedupe(items: list[dict]) -> list[dict]:
    """Dedupe by normalized title (case-insensitive, alphanumeric)."""
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"[^a-z0-9]+", "", it["title_en"].lower())[:60]
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


# -------- Translation ----------

def translate_batch_openai(items: list[dict]) -> list[dict]:
    """Translate titles & bodies to Traditional Chinese using OpenAI.

    Gracefully falls back to English if no API key / on error.
    """
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("  (no OPENAI_API_KEY set – using English titles)")
        for it in items:
            it["title"] = it["title_en"]
            it["body"] = it["body_en"] or it["title_en"]
        return items

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
    except Exception as e:
        print(f"  ! OpenAI import failed: {e}")
        for it in items:
            it["title"] = it["title_en"]
            it["body"] = it["body_en"] or it["title_en"]
        return items

    # Batch into one prompt for speed + cost
    payload = [
        {"i": i, "title": it["title_en"], "body": it["body_en"]}
        for i, it in enumerate(items)
    ]

    sys_prompt = (
        "You are a business translator. Translate each item's title and body "
        "into Traditional Chinese (zh-TW) suitable for Taiwan Amazon sellers. "
        "Keep tickers / brand names / numbers in original form. Titles must be "
        "concise (under 40 Chinese chars). Bodies must be one sentence under "
        "80 Chinese chars, factual tone, no marketing fluff. Return JSON array "
        "with keys i, title, body. No preamble."
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        # Accept either {"items": [...]} or {"results":[...]} or plain list
        if isinstance(data, dict):
            arr = data.get("items") or data.get("results") or next(
                (v for v in data.values() if isinstance(v, list)), []
            )
        else:
            arr = data
        by_i = {int(x["i"]): x for x in arr if "i" in x}
        for i, it in enumerate(items):
            tr = by_i.get(i, {})
            it["title"] = tr.get("title") or it["title_en"]
            it["body"] = tr.get("body") or it["body_en"] or it["title_en"]
    except Exception as e:
        print(f"  ! translation failed: {e}")
        for it in items:
            it["title"] = it["title_en"]
            it["body"] = it["body_en"] or it["title_en"]

    return items


# -------- Output ----------

def js_escape(s: str) -> str:
    """Escape a string for embedding inside single-quoted JS literal."""
    return (
        s.replace("\\", "\\\\")
         .replace("'", "\\'")
         .replace("\r", " ")
         .replace("\n", " ")
    ).strip()


def write_newsdata(items: list[dict]) -> None:
    lines = ["const NEWS=["]
    for it in items:
        obj = (
            "{"
            f"tag:'{js_escape(it['tag'])}',"
            f"date:'{js_escape(it['date'])}',"
            f"title:'{js_escape(it['title'])}',"
            f"body:'{js_escape(it['body'])}',"
            f"src:'{js_escape(it['src'])}',"
            f"via:'{js_escape(it['via'])}'"
            "},"
        )
        lines.append(obj)
    # Remove trailing comma on last entry
    if len(lines) > 1 and lines[-1].endswith(","):
        lines[-1] = lines[-1][:-1]
    lines.append("];")
    OUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {OUT_FILE.relative_to(ROOT)}")


def main() -> int:
    print(f"=== Daily news update {datetime.utcnow().isoformat()}Z ===")
    all_items: list[dict] = []
    for tag, q in TOPICS:
        print(f"  fetching [{tag}] {q!r} ...")
        all_items.extend(fetch_topic(tag, q))

    print(f"Raw items: {len(all_items)}")
    all_items = dedupe(all_items)
    print(f"After dedupe: {len(all_items)}")

    # Sort newest first, keep top N
    all_items.sort(key=lambda x: x["pub_dt"], reverse=True)
    all_items = all_items[:MAX_ITEMS]
    print(f"Keeping top {len(all_items)}")

    if not all_items:
        print("!! No items fetched – aborting to avoid wiping newsdata.js")
        return 1

    all_items = translate_batch_openai(all_items)
    write_newsdata(all_items)
    return 0


if __name__ == "__main__":
    sys.exit(main())
