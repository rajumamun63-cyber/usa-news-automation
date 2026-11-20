import os
import json
import re
import feedparser
import requests
from bs4 import BeautifulSoup

# Environment Variables (GitHub Secrets থেকে আসবে)
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
BLOGGER_BLOG_ID = os.environ["BLOGGER_BLOG_ID"]
BLOGGER_CLIENT_ID = os.environ["BLOGGER_CLIENT_ID"]
BLOGGER_CLIENT_SECRET = os.environ["BLOGGER_CLIENT_SECRET"]
BLOGGER_REFRESH_TOKEN = os.environ["BLOGGER_REFRESH_TOKEN"]

# প্রথমে Draft হিসেবে সেভ হবে। সরাসরি পাবলিশ করতে চাইলে "false" করে দেবেন।
IS_DRAFT = os.environ.get("IS_DRAFT", "true").lower() == "true"

HISTORY_FILE = "posted_history.json"

# ইউএসএ-ভিত্তিক নির্ভরযোগ্য নিউজ RSS ফিড
RSS_FEEDS = [
    {"name": "NPR News", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"name": "CBS News US", "url": "https://www.cbsnews.com/latest/rss/us"},
    {"name": "ABC News US", "url": "https://abcnews.go.com/abcnews/usheadlines"},
]


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(history):
    # সর্বশেষ ৩০০টি লিংক মনে রাখবে
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history[-300:], f, indent=2)


def clean_html(raw_html):
    return BeautifulSoup(raw_html, "html.parser").get_text(separator=" ").strip()


def fetch_latest_news(history):
    for feed_info in RSS_FEEDS:
        feed = feedparser.parse(feed_info["url"])
        for entry in feed.entries[:10]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            summary = clean_html(entry.get("summary", entry.get("description", "")))

            if link and link not in history and len(summary) > 60:
                return {
                    "source": feed_info["name"],
                    "title": title,
                    "summary": summary,
                    "link": link,
                }
    return None


def generate_article_with_gemini(news):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

    prompt = f"""
You are an experienced US news journalist and SEO content editor.
Based ONLY on the news facts provided below, write an original, engaging, human-sounding news article of 350 to 500 words for a US audience.

Source Name: {news['source']}
Headline: {news['title']}
Summary/Details: {news['summary']}

Strict Guidelines:
1. Do NOT invent any facts, quotes, or statistics not implied by the source text.
2. Write in a natural, conversational yet professional journalistic tone (avoid robotic AI buzzwords like "delve", "tapestry", "in conclusion", "testament", "moreover", "furthermore"). Vary sentence length naturally.
3. Naturally mention the source ({news['source']}) within the article for credibility.
4. Structure the HTML cleanly using <h2> subheadings and <p> paragraphs (do NOT include <h1> or <html>/<body> tags).
5. Include 2 placeholder tags exactly like [[IMAGE_1]] and [[IMAGE_2]] between sections where relevant photos should appear (and optionally [[IMAGE_3]] near the end).
6. Create an SEO-friendly, catchy headline and 3-5 relevant Blogger tags/labels.
7. Provide 3 short, specific English search queries (2-4 words each) for finding stock photos on Pexels related to this topic.

Return ONLY valid JSON with these exact keys:
{{
  "title": "SEO News Headline",
  "html_content": "<p>Intro...</p>[[IMAGE_1]]<h2>...</h2><p>...</p>[[IMAGE_2]]...",
  "labels": ["US News", "Tag2", "Tag3"],
  "image_queries": ["query one", "query two", "query three"]
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
        },
    }

    res = requests.post(url, json=payload, timeout=60)
    res.raise_for_status()
    raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw_text)


def fetch_pexels_images(queries, count=3):
    headers = {"Authorization": PEXELS_API_KEY}
    images = []
    seen_ids = set()

    for query in queries:
        if len(images) >= count:
            break
        try:
            res = requests.get(
                "https://api.pexels.com/v1/search",
                headers=headers,
                params={"query": query, "per_page": 3, "orientation": "landscape"},
                timeout=20,
            )
            res.raise_for_status()
            photos = res.json().get("photos", [])
            for photo in photos:
                if photo["id"] not in seen_ids:
                    seen_ids.add(photo["id"])
                    images.append({
                        "url": photo["src"]["large"],
                        "alt": photo.get("alt") or query,
                        "photographer": photo["photographer"],
                        "photographer_url": photo["photographer_url"],
                    })
                    break
        except Exception as e:
            print(f"Pexels search failed for '{query}': {e}")

    return images


def build_image_html(img):
    return (
        f'<figure style="text-align:center; margin: 20px 0;">'
        f'<img src="{img["url"]}" alt="{img["alt"]}" style="max-width:100%; height:auto; border-radius:6px;" />'
        f'<figcaption style="font-size:12px; color:#666; margin-top:5px;">'
        f'Photo by <a href="{img["photographer_url"]}" target="_blank" rel="nofollow noopener">{img["photographer"]}</a> on Pexels'
        f'</figcaption>'
        f'</figure>'
    )


def get_blogger_access_token():
    res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": BLOGGER_CLIENT_ID,
            "client_secret": BLOGGER_CLIENT_SECRET,
            "refresh_token": BLOGGER_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    res.raise_for_status()
    return res.json()["access_token"]


def post_to_blogger(access_token, title, html_content, labels):
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOGGER_BLOG_ID}/posts/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    params = {"isDraft": "true" if IS_DRAFT else "false"}
    payload = {
        "kind": "blogger#post",
        "title": title,
        "content": html_content,
        "labels": labels,
    }

    res = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
    res.raise_for_status()
    return res.json()


def main():
    history = load_history()
    news = fetch_latest_news(history)

    if not news:
        print("কোনো নতুন নিউজ পাওয়া যায়নি।")
        return

    print(f"নিউজ পাওয়া গেছে ({news['source']}): {news['title']}")

    article = generate_article_with_gemini(news)
    images = fetch_pexels_images(article.get("image_queries", []), count=3)

    html = article["html_content"]

    # প্লেসহোল্ডারগুলোতে ছবি বসানো
    for idx in range(1, 4):
        tag = f"[[IMAGE_{idx}]]"
        if idx - 1 < len(images) and tag in html:
            html = html.replace(tag, build_image_html(images[idx - 1]))
        else:
            html = html.replace(tag, "")

    # সোর্স রেফারেন্স শেষে যুক্ত করা
    html += f'<p style="font-size:13px; color:#555;"><em>Source reference: <a href="{news["link"]}" target="_blank" rel="nofollow noopener">{news["source"]}</a></em></p>'

    access_token = get_blogger_access_token()
    post_result = post_to_blogger(
        access_token=access_token,
        title=article["title"],
        html_content=html,
        labels=article.get("labels", ["US News"]),
    )

    print(f"সফলভাবে Blogger-এ পোস্ট হয়েছে! Post ID: {post_result.get('id')} | Draft: {IS_DRAFT}")

    history.append(news["link"])
    save_history(history)


if __name__ == "__main__":
    main()
