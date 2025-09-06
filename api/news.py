import os
import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



def send_report_via_email(subject: str, body: str) -> None:
    """
    Send the report via email to all configured recipients using an external
    mail API. If no recipients are configured or requests is unavailable, the
    send is skipped.
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
        "isHtml": True
    }
    try:
        response = httpx.post(
            "https://mail-api-mounsef.vercel.app/api/send-email",
            json=payload,
            timeout=15,
        )
        if response.ok:
            print(f"Email sent to {recipients}")
        else:
            print(f"Failed to send email to {recipients}: {response.status_code} {response.text}")
            print(f"Email payload: {payload}")

    except Exception as e:
        print(f"Error sending email to {recipients}: {e}")
        print(f"Email payload: {payload}")



@app.get("/api/news")
async def get_positive_news():
    today = datetime.date.today().isoformat()

    num = 5  # Number of articles to fetch
    
    prompt = f"""
    Find exactly {num} strictly positive news articles published today {today} in Morocco, focusing only on clearly good news stories (such as successes in economy, culture, sports, innovation, sustainability, diplomacy, tourism, technology, healthcare, improvements). Exclude any articles with negative content, such as crime, accidents, conflict, or disasters.

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
    - "date": Publication date (YYYY-MM-DD) matching today {today}.

    Output formatting instructions:
    - Output must be a JSON array (no extra text or comments, no trailing commas), exactly {num} objects.
    - Only the JSON output, with all fields present for all articles.
    - Articles must be from reputable Moroccan news sources (e.g., Le Matin, Morocco World News, Yabiladi, hespress, mapnews.ma, etc.).
    - Avoid duplicates; each article must be unique.
    - Articles must be published today {today} only.
    - Articles strictly ordered from most recent to least recent.


    Example output:
    [
    {
        "title": "Rabat Tech Startups Secure Major Investments",
        "summary": "Several Rabat-based technology startups have attracted significant investments this morning. The funding round is expected to boost innovation in Morocco’s digital sector.",
        "mini_article": "A wave of optimism swept through Morocco’s tech scene today as several promising startups in Rabat announced new investment deals. Industry leaders believe these funding rounds will not only accelerate digital innovation but also generate new jobs and foster a vibrant tech ecosystem in the capital. Entrepreneurs expressed excitement, and local universities are already planning collaborative research. With these investments, Morocco strengthens its place on the global tech map.",
        "image": "https://example.com/tech_investment.jpg",
        "url": "https://example.com/rabat-tech-investments",
        "source": "Morocco Tech News",
        "tags": ["technology", "investment", "startups"],
        "date": "{today}"
    },
    ...
    ]
    (Real examples should feature unique, in-depth headlines, authentic publications, and more extensive summaries/narratives. Use sources like Moroccan news agencies, sports authorities, cultural institutions, and sector-specific sites for authenticity.)

    Important Reminders:
    - Evaluate article content and relevance step-by-step before classifying as positive news.
    - Include only strictly positive news published today {today} in Morocco.
    - Ensure all required fields are present in each JSON object, using null where necessary.
    - Output must be a strictly valid JSON array of exactly {num} articles, ordered by most recent time first.

    Reminder: Your main tasks are to filter for strictly positive, Moroccan news articles from today {today} only, and provide exactly {num} results in valid, strictly formatted JSON as described.
    """

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-search-preview",
            web_search_options={
                "search_context_size": "high",
                "user_location": {"type": "approximate", "approximate": {"country": "MA", "city": "Casablanca"}}
            },
            messages=[{"role": "user", "content": prompt}],
        )
        content = resp.choices[0].message.content.strip()

        # create a table for logging and email the report
        subject = f"Daily Positive News Report for {today}"
        # prepare email body
        body = f"<h2>Daily Positive News Report for {today}</h2>\n"
        # format content as a table
        try:
            import json
            articles = json.loads(content)
            body += "<table border='1' cellpadding='5' cellspacing='0'>\n"
            body += "<tr><th>Title</th><th>Summary</th><th>Mini Article</th><th>Image</th><th>URL</th><th>Source</th><th>Tags</th><th>Date</th></tr>\n"
            for article in articles:
                body += "<tr>"
                body += f"<td>{article.get('title', '')}</td>"
                body += f"<td>{article.get('summary', '')}</td>"
                body += f"<td>{article.get('mini_article', '')}</td>"
                image = article.get('image', '')
                if image:
                    body += f"<td><img src='{image}' alt='Image' width='100'></td>"
                else:
                    body += "<td>null</td>"
                url = article.get('url', '')
                if url:
                    body += f"<td><a href='{url}'>Link</a></td>"
                else:
                    body += "<td>null</td>"
                body += f"<td>{article.get('source', '')}</td>"
                tags = ", ".join(article.get('tags', [])) if article.get('tags') else 'null'
                body += f"<td>{tags}</td>"
                body += f"<td>{article.get('date', '')}</td>"
                body += "</tr>\n"
            body += "</table>\n"
        except Exception as e:
            body += f"<pre>{content}</pre>\n"
            body += f"<p>Error formatting articles as table: {e}</p>\n"

        # send the email
        send_report_via_email(subject, body)







        return JSONResponse(content=content)
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}