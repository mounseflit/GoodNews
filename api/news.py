import os
import json
import datetime as dt
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
from openai import OpenAI

# --- FastAPI app ---
app = FastAPI(title="Positive Morocco News API")

# --- OpenAI client (Responses API) ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Config ---
CASABLANCA_TZ = ZoneInfo("Africa/Casablanca")
NEWS_NUM = int(os.getenv("NEWS_ARTICLES_NUM", "5"))  # default to 5
RECIPIENTS = os.getenv("NEWS_EMAIL_TO", "litnitimounsef@gmail.com")

MAIL_API_URL = os.getenv(
    "MAIL_API_URL",
    "https://mail-api-mounsef.vercel.app/api/send-email"
)

def today_str_in_casablanca() -> str:
    return dt.datetime.now(CASABLANCA_TZ).date().isoformat()

def send_report_via_email(subject: str, body_html: str) -> None:
    """Send the report via a simple external mail API."""
    if not RECIPIENTS:
        return
    payload = {
        "to": RECIPIENTS,
        "cc": "",
        "bcc": "",
        "subject": subject,
        "message": body_html,
        "isHtml": True,
    }
    try:
        resp = httpx.post(MAIL_API_URL, json=payload, timeout=15)
        if resp.ok:
            print(f"[mail] Sent to {RECIPIENTS}")
        else:
            print(f"[mail] Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[mail] Error: {e}")

@app.get("/")
async def root_redirect():
    """Redirect root to interactive docs."""
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/news")
async def get_positive_news():
    # Always compute "today" in Africa/Casablanca to match Morocco outlets
    today = today_str_in_casablanca()

    # Clamp NEWS_NUM to a reasonable positive integer
    num = max(1, NEWS_NUM)

    prompt = f"""
Find exactly {num} strictly positive news articles published today {today} in Morocco,
focusing only on clearly good news stories (economy, culture, sports, innovation,
sustainability, diplomacy, tourism, technology, healthcare, improvements).
Exclude any articles with negative content (crime, accidents, conflict, disasters).

For each article:
- First, critically assess if the tone and content are strictly positive and contain none of the excluded topics.
- Confirm it's Morocco-related, that the publication date is {today}, and fields are available.
- Then extract the required fields.

If fewer than {num} are found, broaden reputable Moroccan sources until you have exactly {num}.

Return ONLY a strict JSON array of exactly {num} objects (no extra text).
Each object must include ALL fields (use null if unavailable), ordered newest → oldest:
- "title": Exact original headline.
- "summary": 2–3 sentences.
- "mini_article": 3–4 PARAGRAPHS, 4–5 sentences each, engaging and upbeat.
- "image": Main article image URL or null.
- "url": Direct link to the article.
- "source": Publishing outlet (e.g., Le Matin, Morocco World News, Yabiladi, Hespress, MAP).
- "tags": Exactly 3 keywords.
- "date": Publication date in YYYY-MM-DD; must equal {today}.

STRICT RULES:
- Output is ONLY the JSON array (no prose, no comments).
- All items must be unique, Morocco-specific, strictly positive, and dated {today}.
- Sort by most recent publication time first.
"""

    try:
        # Use Responses API + web search tool
        # Docs: Tools → Web search (Responses API) and model page for gpt-4o-search-preview
        # https://platform.openai.com/docs/guides/tools-web-search
        # https://platform.openai.com/docs/models/gpt-4o-search-preview
        response = client.responses.create(
        model="gpt-4o-search-preview",   # or "gpt-4o"
        input=prompt,
        tools=[{"type": "web_search"}],  # ✅ enable built-in web search tool
        tool_choice="auto",              # (optional) let the model decide when to search
        )

        # Prefer the SDK helper:
        content_text = getattr(response, "output_text", None)
        if not content_text:
            parts = []
            for item in getattr(response, "output", []) or []:
                if getattr(item, "type", None) == "message":
                    for ct in item.content:
                        if getattr(ct, "type", None) == "output_text":
                            parts.append(ct.text)
            content_text = "".join(parts).strip() if parts else ""
        content_text = (content_text or "").strip()

        # Try parsing strict JSON array; on failure, bubble a 502 with raw text for debugging
        try:
            articles = json.loads(content_text)
            if not isinstance(articles, list):
                raise ValueError("Model output is not a JSON array.")
        except Exception as e:
            # Return raw model output so callers can inspect; also helpful for logs
            return JSONResponse(
                status_code=502,
                content={"error": "Invalid JSON from model", "raw": content_text, "detail": str(e)},
            )

        # Build HTML email body
        subject = f"Daily Positive News Report for {today}"
        body = [f"<h2>Daily Positive News Report for {today}</h2>"]
        body.append("<table border='1' cellpadding='6' cellspacing='0'>")
        body.append(
            "<tr><th>Title</th><th>Summary</th><th>Mini Article</th>"
            "<th>Image</th><th>URL</th><th>Source</th><th>Tags</th><th>Date</th></tr>"
        )
        for a in articles:
            image = a.get("image") or None
            url = a.get("url") or None
            tags = a.get("tags") if isinstance(a.get("tags"), list) else None

            body.append("<tr>")
            body.append(f"<td>{a.get('title','')}</td>")
            body.append(f"<td>{a.get('summary','')}</td>")
            body.append(f"<td>{a.get('mini_article','')}</td>")
            body.append(
                f"<td><img src='{image}' alt='Image' width='100'></td>" if image else "<td>null</td>"
            )
            body.append(f"<td><a href='{url}'>Link</a></td>" if url else "<td>null</td>")
            body.append(f"<td>{a.get('source','')}</td>")
            body.append(f"<td>{', '.join(tags) if tags else 'null'}</td>")
            body.append(f"<td>{a.get('date','')}</td>")
            body.append("</tr>")
        body.append("</table>")
        html_body = "\n".join(body)

        # Fire and forget email (synchronous; keeps things simple)
        send_report_via_email(subject, html_body)

        # Return the parsed JSON array back to caller
        return JSONResponse(content=articles)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

