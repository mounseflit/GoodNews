import os
import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from openai import OpenAI
import requests
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

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
        response = requests.post(
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
    # Use recent date range to ensure we can find articles
    recent_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    num = 5  # Number of articles to fetch
    
    # Create prompt using string concatenation to avoid f-string formatting issues
    prompt = f"""
    Find exactly {num} strictly positive news articles published in the last 2 days (between {recent_date} and {today}) in Morocco, focusing only on clearly good news stories (such as successes in economy, culture, sports, innovation, sustainability, diplomacy, tourism, technology, healthcare, improvements). Exclude any articles with negative content, such as crime, accidents, conflict, or disasters.

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
    - "date": Publication date (YYYY-MM-DD) from the last 2 days.

    Output formatting instructions:
    - Output must be a JSON array (no extra text or comments, no trailing commas), exactly {num} objects.
    - Only the JSON output, with all fields present for all articles.
    - Articles must be from reputable Moroccan news sources (e.g., Le Matin, Morocco World News, Yabiladi, hespress, mapnews.ma, etc.).
    - Avoid duplicates; each article must be unique.
    - Articles must be published in the last 2 days only.
    - Articles strictly ordered from most recent to least recent.

    Important Reminders:
    - Evaluate article content and relevance step-by-step before classifying as positive news.
    - Include only strictly positive news published in the last 2 days in Morocco.
    - Ensure all required fields are present in each JSON object, using null where necessary.
    - Output must be a strictly valid JSON array of exactly {num} articles, ordered by most recent time first.

    Reminder: Your main tasks are to filter for strictly positive, Moroccan news articles from the last 2 days only, and provide exactly {num} results in valid, strictly formatted JSON as described.
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
        
        # Try to parse the JSON content
        try:
            # Remove any markdown code block formatting if present
            if "```json" in content:
                # Extract JSON from markdown code blocks
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end != -1:
                    content = content[start:end].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            # Parse the JSON content
            news_data = json.loads(content)
            
            # Validate that we have exactly 5 articles
            if not isinstance(news_data, list) or len(news_data) != num:
                raise ValueError(f"Expected {num} articles, got {len(news_data) if isinstance(news_data, list) else 'invalid format'}")
            
        except (json.JSONDecodeError, ValueError) as e:
            return {"error": f"Failed to parse news data: {str(e)}", "raw_content": content}

        # create a table for logging and email the report
        subject = f"Recent Positive News Report for {today}"
        # prepare email body
        body = f"<h2>Recent Positive News Report for {today}</h2>\n"
        body += f"<p>Here are the {num} strictly positive news articles from Morocco from recent days:</p>\n"
        
        # Format the news articles nicely in the email
        for i, article in enumerate(news_data, 1):
            body += f"<div style='border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;'>\n"
            body += f"<h3>{i}. {article.get('title', 'No title')}</h3>\n"
            body += f"<p><strong>Source:</strong> {article.get('source', 'Unknown')}</p>\n"
            body += f"<p><strong>Date:</strong> {article.get('date', 'Unknown')}</p>\n"
            body += f"<p><strong>Summary:</strong> {article.get('summary', 'No summary')}</p>\n"
            body += f"<div><strong>Full Article:</strong><br>{article.get('mini_article', 'No content')}</div>\n"
            if article.get('url'):
                body += f"<p><a href='{article['url']}' target='_blank'>Read Full Article</a></p>\n"
            if article.get('tags'):
                body += f"<p><strong>Tags:</strong> {', '.join(article['tags'])}</p>\n"
            body += f"</div>\n"
        
        send_report_via_email(subject, body)

        return {"status": "success", "articles": news_data, "count": len(news_data)}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}