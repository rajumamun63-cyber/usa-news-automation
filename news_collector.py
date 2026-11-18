import urllib.request
import xml.etree.ElementTree as ET
import json
import os
import re
from datetime import datetime, timezone
from html import unescape

RSS_FILE = "news_sources.txt"
OUTPUT_FILE = "collected_news.json"

def clean_text(text):
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def load_sources():
    with open(RSS_FILE, encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip()]

def load_old_news():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def collect_news():
    old_news = load_old_news()
    existing = {x.get("link") for x in old_news}
    new_news = []

    for url in load_sources():
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urllib.request.urlopen(req, timeout=20) as r:
                root = ET.fromstring(r.read())

            for item in root.findall(".//item"):
                title = clean_text(item.findtext("title"))
                link = item.findtext("link", "")
                description = clean_text(
                    item.findtext("description")
                )
                pub_date = item.findtext("pubDate", "")

                source_element = item.find("source")
                source = (
                    clean_text(source_element.text)
                    if source_element is not None
                    else "Google News"
                )

                if not title or not link or link in existing:
                    continue

                new_news.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "source": source,
                    "published": pub_date,
                    "collected_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "status": "new"
                })

                existing.add(link)

        except Exception as e:
            print("RSS Error:", e)

    all_news = new_news + old_news

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

    print("New news:", len(new_news))
    print("Total stored:", len(all_news))

if __name__ == "__main__":
    collect_news()
