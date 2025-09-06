import os
import json
import datetime
from typing import Any, List, Dict
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import httpx
from openai import OpenAI
import html

app = FastAPI()

# Ensure the key is present at startup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

client = OpenAI(api_key=OPENAI_API_KEY)


async def send_report_via_email(subject: str, body: str) -> None:
    """
    Send the report via email to the configured recipient using an external mail API.
    Non-fatal on failure (logged to stdout).
    """
    recipients = "litnitimounsef@gmail.com"
    if not recipients:
        return

    payload = {
        "to": recipients,
        "cc": "",
        "bcc": "",
        "subject": subject,
        "message": body,
        "isHtml": True,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as session:
            resp = await session.post(
                "https://mail-api-mounsef.vercel.app/api/send-email",
                json=payload,
            )
        if resp.is_success:
            print(f"Email sent to {recipients}")
        else:
            print(f"Failed to send email to {recipients}: {resp.status_code} {resp.text}")
            print(f"Email payload: {payload}")
    except Exception as e:
        print(f"Error sending email to {recipients}: {e}")
        print(f"Email payload: {payload}")


def html_row_for_article(article: Dict[str, Any]) -> str:
    """Safely render a single article to an HTML table row."""
    t = html.escape(str(article.get("title", "")))
    s = html.escape(str(article.get("summary", "")))
    m = html.escape(str(article.get("mini_article", "")))
    src = html.escape(str(article.get("source", "")))
    d = html.escape(str(article.get("date", "")))

    img = article.get("image")
    url = article.get("url")
    tags_list = article.get("tags") or []
    tags = ", ".join(map(str, tags_list))

    img_cell = f"<img src='{html.escape(img)}' alt='Image' width='100'>" if img else "null"
    url_cell = f"<a href='{html.escape(url)}'>Link</a>" if url else "null"

    return (
        "<tr>"
        f"<td>{t}</td>"
        f"<td>{s}</td>"
        f"<td style='white-space:pre-wrap'>{m}</td>"
        f"<td>{img_cell}</td>"
        f"<td>{url_cell}</td>"
        f"<td>{src}</td>"
        f"<td>{html.escape(tags)}</td>"
        f"<td>{d}</td>"
        "</tr>\n"
    )


def validate_articles(payload: Any, expected_num: int, today_iso: str) -> List[Dict[str, Any]]:
    """
    Validate that payload is a JSON array of exactly expected_num objects,
    each containing the required fields, and with date == today_iso.
    Fill missing fields with None as required by the spec.
    """
    if not isinstance(payload, list):
        raise ValueError("Model response must be a JSON array.")

    if len(payload) != expected_num:
        raise ValueError(f"Expected exactly {expected_num} articles, got {len(payload)}.")

    required_fields = {
        "title": None,
        "summary": None,
        "mini_article": None,
        "image": None,
        "url": None,
        "source": None,
        "tags": None,
        "date": None,
    }

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Article #{i} is not an object.")

        # Ensure all fields present; default to None where missing
        article = {k: item.get(k, v) for k, v in required_fields.items()}

        # Basic type adjustments
        if article["tags"] is None:
            article["tags"] = []
        if not isinstance(article["tags"], list):
            raise ValueError(f"Article #{i} 'tags' must be a list of exactly 3 keywords.")
        # Accept whatever the model produced; your downstream can enforce exactly 3 if desired.

        # Date must match today
        if article["date"] != today_iso:
            raise ValueError(f"Article #{i} has date '{article['date']}', expected '{today_iso}'.")

        cleaned.append(article)

    return cleaned


@app.get("/api/news")
async def get_positive_news():
    # Use Africa/Casablanca per your requirements
    tz = ZoneInfo("Africa/Casablanca")
    today_iso = datetime.datetime.now(tz).date().isoformat()

    num =  os.getenv("NEWS_ARTICLES_NUM")

    prompt = f"""
Find exactly {num} strictly positive news articles published today {today_iso} in Morocco, focusing only on clearly good news stories (such as successes in economy, culture, sports victories, innovation, sustainability, diplomacy, tourism, technology, healthcare improvements). Exclude any articles with negative content, such as crime, accidents, conflict, or disasters.

For each article:
- First, critically assess if the tone and content are strictly positive and contain none of the excluded topics. Think step-by-step: check publication date, evaluate positivity, confirm relevance to Morocco and the topic areas, and ensure the required fields are available or can be inferred/null.
- Next, extract and structure the required data fields.
- If fewer than {num} articles are found, persist in searching with broader queries or alternative reputable sources until exactly {num} qualifying articles are gathered.

Return only a strict JSON array, containing exactly {num} article objects, ordered by latest publication time first. Each object must include ALL the following fields (fill with null if unavailable):
- "title": Exact original article headline.
- "summary": Concise summary (2–3 sentences).
- "mini_article": A short, engaging narrative version of the news (3–4 PARAGRAPHS, 4–5 sentences each) that captures the essence and excitement of the story.
- "image": Main article image URL, else null.
- "url": Direct link to the article.
- "source": Name of the publishing outlet.
- "tags": Exactly 3 relevant keywords.
- "date": Publication date (YYYY-MM-DD) matching today {today_iso}.

Output formatting instructions:
- Output must be a JSON array (no extra text or comments, no trailing commas), exactly {num} objects.
- Only the JSON output, with all fields present for all articles.
- Articles must be from reputable Moroccan news sources (e.g., Le Matin, Morocco World News, Yabiladi, Hespress, MAP, etc.).
- Avoid duplicates; each article must be unique.
- Articles must be published today {today_iso} only.
- Articles strictly ordered from most recent to least recent.

Important Reminders:
- Evaluate article content and relevance step-by-step before classifying as positive news.
- Include only strictly positive news published today {today_iso} in Morocco.
- Ensure all required fields are present in each JSON object, using null where necessary.
- Output must be a strictly valid JSON array of exactly {num} articles, ordered by most recent time first.
"""

    try:
        # Use a stable, generally-available model
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        content = completion.choices[0].message.content.strip()

        # Attempt to parse JSON
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            # If the model returned extra text, try to extract the array heuristically
            start = content.find("[")
            end = content.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    parsed = json.loads(content[start : end + 1])
                except Exception:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Model returned non-JSON content and could not be coerced: {e}",
                    )
            else:
                raise HTTPException(
                    status_code=502,
                    detail=f"Model returned non-JSON content: {e}",
                )

        # Validate structure (length, fields, date)
        try:
            articles = validate_articles(parsed, expected_num=5, today_iso=today_iso)
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))

        # Build HTML email body
        subject = f"Daily Positive News Report for {today_iso}"
        body = f"<h2>Daily Positive News Report for {html.escape(today_iso)}</h2>\n"
        body += (
            "<table border='1' cellpadding='5' cellspacing='0'>\n"
            "<tr>"
            "<th>Title</th><th>Summary</th><th>Mini Article</th>"
            "<th>Image</th><th>URL</th><th>Source</th><th>Tags</th><th>Date</th>"
            "</tr>\n"
        )
        for article in articles:
            body += html_row_for_article(article)
        body += "</table>\n"

        # Send the email (non-blocking)
        await send_report_via_email(subject, body)

        # Return the validated JSON array
        return JSONResponse(content=articles)

    except HTTPException:
        raise
    except Exception as e:
        # Catch-all to avoid leaking internals
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

