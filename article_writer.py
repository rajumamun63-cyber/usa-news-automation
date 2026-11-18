import os
import json
import re
import urllib.request
import urllib.error

API_KEY = os.environ["GEMINI_API_KEY"]

MODEL = "gemini-2.5-flash"

INPUT_FILE = "collected_news.json"
OUTPUT_FILE = "generated_articles.json"


def generate_article(news):

    prompt = f"""
You are a professional US news journalist and editor.

Create an original, factual and SEO-friendly news article
using the information supplied below.

NEWS TITLE: {news['title']}

SOURCE: {news['source']}

SOURCE DESCRIPTION: {news['description']}

ORIGINAL NEWS URL: {news['link']}

STRICT REQUIREMENTS:

1. Write in natural American English.
2. Article must contain at least 300 words.
3. Create an SEO-friendly headline.
4. Include a meta description.
5. Include relevant SEO keywords.
6. Use H2 and H3 headings.
7. Write original sentences.
8. Do not copy the original publisher's article.
9. Do not invent facts, quotations, statistics or events.
10. Do not claim information that is not supported by the source.
11. Include the original news source URL.
12. If information is insufficient, return status as "insufficient".

Return valid JSON in this format:

{{
  "status": "ready",
  "title": "News headline",
  "meta_description": "SEO description",
  "keywords": ["keyword1", "keyword2"],
  "article_html": "<h2>...</h2><p>...</p>",
  "word_count": 350,
  "source_url": "{news['link']}"
}}

If information is insufficient, return:

{{
  "status": "insufficient",
  "reason": "Not enough verified information"
}}
"""

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "maxOutputTokens": 5000
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": API_KEY
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.loads(response.read())

    text = result["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(text)


def main():

    with open(INPUT_FILE, encoding="utf-8") as f:
        news_list = json.load(f)

    articles = []

    for news in news_list:

        if news.get("status") != "new":
            continue

        if len(news.get("description", "")) < 300:
            print("Skipping: insufficient source information")
            continue

        try:

            article = generate_article(news)

            if article.get("status") != "ready":
                print("Article rejected")
                continue

            if article.get("word_count", 0) < 300:
                print("Article too short")
                continue

            articles.append(article)

            news["status"] = "drafted"

            print("Article generated:", article["title"])

        except Exception as error:

            print("Generation error:", error)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            articles,
            f,
            ensure_ascii=False,
            indent=2
        )

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            news_list,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("Total articles generated:", len(articles))


if __name__ == "__main__":
    main()
