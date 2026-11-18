import urllib.request
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime, timezone

RSS_FILE = "news_sources.txt"
OUTPUT_FILE = "collected_news.json"

def load_sources():
    with open(RSS_FILE, "r", encoding="utf-8") as file:
        return [
            line.strip()
            for line in file
            if line.strip().startswith("http")
        ]

def load_old_news():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return []

def collect_news():
    sources = load_sources()
    old_news = load_old_news()

    existing_links = {
        item.get("link") for item in old_news
    }

    new_news = []

    for url in sources:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )

            with urllib.request.urlopen(
                request, timeout=20
            ) as response:
                data = response.read()

            root = ET.fromstring(data)

            for item in root.findall(".//item"):
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                
                source_element = item.find("source")
                source = (
                    source_element.text
                    if source_element is not None
                    else "Google News"
                )

                if not title or not link:
                    continue

                if link in existing_links:
                    continue

                news = {
                    "title": title,
                    "link": link,
                    "source": source,
                    "published": pub_date,
                    "collected_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "status": "new"
                }

                new_news.append(news)
                existing_links.add(link)

        except Exception as error:
            print(f"RSS Error: {error}")

    all_news = new_news + old_news

    with open(
        OUTPUT_FILE, "w", encoding="utf-8"
    ) as file:
        json.dump(
            all_news,
            file,
            ensure_ascii=False,
            indent=2
        )

    print("New news collected:", len(new_news))
    print("Total news stored:", len(all_news))


if __name__ == "__main__":
    collect_news()
