import json
import urllib.parse
import urllib.request
import html
import re

INPUT_FILE = "generated_articles.json"
OUTPUT_FILE = "generated_articles.json"


def search_images(query):

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 3,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 900,
        "format": "json"
    }

    url = (
        "https://commons.wikimedia.org/w/api.php?"
        + urllib.parse.urlencode(params)
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "USNewsAutomation/1.0 contact: admin"
        }
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read())

    images = []

    pages = data.get("query", {}).get("pages", {})

    for page in pages.values():

        info = page.get("imageinfo", [{}])[0]
        metadata = info.get("extmetadata", {})

        image_url = info.get("thumburl") or info.get("url")
        image_page = info.get("descriptionurl")

        license_name = metadata.get(
            "LicenseShortName", {}
        ).get("value", "")

        artist = metadata.get(
            "Artist", {}
        ).get("value", "Unknown")

        if not image_url or not image_page or not license_name:
            continue

        images.append({
            "url": image_url,
            "source_page": image_page,
            "license": license_name,
            "artist": artist
        })

    return images


def main():

    with open(INPUT_FILE, encoding="utf-8") as f:
        articles = json.load(f)

    for article in articles:

        title = article.get("title", "")

        try:

            images = search_images(title)

            article["images"] = images[:3]

            image_html = ""

            for img in article["images"]:

                image_html += f"""
                <figure>
                    <img src="{html.escape(img['url'], quote=True)}"
                    alt="{html.escape(title, quote=True)}"
                    loading="lazy"
                    style="max-width:100%;height:auto;">

                    <figcaption>
                        Image:
                        <a href="{html.escape(img['source_page'], quote=True)}">
                        Wikimedia Commons
                        </a>
                        | License: {html.escape(img['license'])}
                    </figcaption>
                </figure>
                """

            article["article_html"] = (
                image_html + article.get("article_html", "")
            )

            print(title, "Images:", len(images))

        except Exception as error:

            print("Image Error:", error)
            article["images"] = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        json.dump(
            articles,
            f,
            ensure_ascii=False,
            indent=2
        )


if __name__ == "__main__":
    main()
