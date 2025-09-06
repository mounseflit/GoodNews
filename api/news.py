import os
import json
import datetime as dt
from zoneinfo import ZoneInfo
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
import google.generativeai as genai


app = FastAPI(title="Positive Morocco News API (Gemini Web Search)")

CASABLANCA_TZ = ZoneInfo("Africa/Casablanca")
NEWS_NUM = int(os.getenv("NEWS_ARTICLES_NUM", "5"))
RECIPIENTS = os.getenv("NEWS_EMAIL_TO", "litnitimounsef@gmail.com")
MAIL_API_URL = os.getenv("MAIL_API_URL", "https://mail-api-mounsef.vercel.app/api/send-email")

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Use a Gemini model that supports tools; enable Google Search grounding
# NOTE: We also ask for JSON directly with response_mime_type to keep parsing simple.
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    tools=[{"google_search_retrieval": {}}],  # <-- Web Search grounding
)

GENERATION_CONFIG = {
    "response_mime_type": "application/json",
    # Optional: set a higher max output tokens for large "mini_article" fields
    "max_output_tokens": 4000,
}

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

# =========================
# Routes
# =========================
@app.get("/")
async def root_redirect():
    """Redirect root to interactive docs."""
    return RedirectResponse(url="/docs", status_code=307)

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/news")
async def get_positive_news():
    """
    Returns strictly-positive Morocco news for 'today' (Africa/Casablanca),
    using Gemini + Google Search grounding, as a strict JSON array.
    Also emails an HTML table report.
    """
    today = today_str_in_casablanca()
    num = max(1, NEWS_NUM)

    prompt = f"""
You are a precise news curator that uses web search.

TASK:
Find exactly {num} strictly positive news articles published today ({today}) in Morocco.
Focus ONLY on clearly good news: economy, culture, sports, innovation, sustainability,
diplomacy, tourism, technology, healthcare, improvements.

EXCLUDE any article containing negative topics: crime, accidents, conflict, disasters, scandals.

QUALITY CHECK (do this before including any article):
1) Verify the article is Morocco-related.
2) Verify the publication DATE equals {today} (Africa/Casablanca).
3) Verify the tone and content are strictly positive (none of the excluded topics).
4) Ensure required fields exist; fill with null if truly unavailable.
5) Prefer reputable Moroccan sources (Le Matin, MAP (mapnews.ma), Hespress, Yabiladi, Morocco World News, etc.).

If fewer than {num} are found initially, broaden reputable sources until you have EXACTLY {num}.

RETURN FORMAT (STRICT):
Return ONLY a JSON array of EXACTLY {num} objects (no other text).
Each object MUST contain ALL fields (use null if unavailable), and the array MUST be ordered newest → oldest:
- "title": Exact original headline.
- "summary": 2–3 sentences.
- "mini_article": 3–4 PARAGRAPHS, 4–5 sentences each, engaging.
- "image": Main article image URL or null.
- "url": Direct link to the article.
- "source": Publishing outlet (name).
- "tags": Exactly 3 keywords.
- "date": Publication date in YYYY-MM-DD; MUST equal {today}.

STRICT RULES:
- Output is ONLY the JSON array (no prose or comments).
- Avoid duplicates; each article must be unique and Morocco-specific.
- Every article must be dated {today} and strictly positive.
- Sort by most recent publication time first.
- Prefer results geo-relevant to Casablanca, Morocco.

Use Google Search grounding to verify dates, sources, and positivity before including.
"""

    try:
        # Ask Gemini to perform the task using Google Search grounding.
        # We request JSON output directly with response_mime_type in GENERATION_CONFIG.
        response = model.generate_content(
            prompt,
            generation_config=GENERATION_CONFIG,
            tools=[{"google_search_retrieval": {}}],
        )

        # The SDK returns JSON as .text when response_mime_type is application/json.
        content_text = (response.text or "").strip()

        # Parse strict JSON array
        try:
            articles = json.loads(content_text)
            if not isinstance(articles, list):
                raise ValueError("Model output is not a JSON array.")
            if len(articles) != num:
                raise ValueError(f"Expected exactly {num} articles, got {len(articles)}.")
        except Exception as e:
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
            body.append(f"<td>{a.get('mini_article','').replace('<', '&lt;')}</td>")
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

        # Email the report (sync call for simplicity)
        send_report_via_email(subject, html_body)

        # Return JSON to client
        return JSONResponse(content=articles)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

