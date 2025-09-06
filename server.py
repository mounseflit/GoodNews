import asyncio
import json
import logging
import os
import re
import tempfile
import time
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from requests.adapters import HTTPAdapter, Retry

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:
    BeautifulSoup = None  # type: ignore

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError


# ---------------------------------------------------------------------------
# Logger setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)



# User agent for HTTP requests
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; WatcherBot/3.0; +https://example.com/bot) "
    "PythonRequests"
)


# ---------------------------------------------------------------------------
# OpenAI configuration
#
# We use OpenAI's Chat Completions with the web search tool enabled to
# summarise pages and compile reports. The model name and the default
# location used for search results can be overridden via environment variables.

from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable not set. API calls will fail.")

OPENAI_SEARCH_MODEL = os.getenv("OPENAI_SEARCH_MODEL", "gpt-4o-search-preview")
OPENAI_LOCATION = {
    "country": os.getenv("WATCHER_COUNTRY", "MA"),
    "city": os.getenv("WATCHER_CITY", "Casablanca"),
    "region": os.getenv("WATCHER_REGION", "Casablanca-Settat"),
}
oa_client = OpenAI(api_key=OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# HTTP and scraping and AI helpers

class HTTPClient:
    """
    A simple HTTP client using requests.Session with retry logic.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
        )
        # Configure retries
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "HEAD"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def get(self, url: str, timeout: int = 10) -> Optional[str]:
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code >= 400:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                return None
            # Attempt to set correct encoding
            if resp.encoding is None:
                resp.encoding = resp.apparent_encoding  # type: ignore
            return resp.text
        except Exception as e:
            logger.warning(f"Network error fetching {url}: {e}")
            return None


http_client = HTTPClient()


def _clean_text(text: str) -> str:
    """
    Normalize whitespace and collapse excessive blank lines.
    """
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_main_text(html: str) -> Tuple[str, str]:
    """
    Extract title and main text from an HTML document. If BeautifulSoup is not
    available, fall back to regex tag stripping.
    """
    if not html:
        return ("", "")
    if BeautifulSoup is None:
        title_match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        title = title_match.group(1).strip() if title_match else ""
        # Strip scripts/styles
        text = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return (title, _clean_text(text))
    soup = BeautifulSoup(html, "html.parser")
    # Remove scripts, styles, and non-content
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for sel in ["nav", "footer", "header", "form", "aside"]:
        for t in soup.select(sel):
            t.decompose()
    # Title extraction
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    else:
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            title = og["content"].strip()  # type: ignore
    # Attempt to find main text inside article or main tags
    candidates = soup.select("article") or soup.select("main") or [soup.body or soup]
    chunks: List[str] = []
    for node in candidates:
        text = node.get_text(separator="\n", strip=True)
        if text:
            chunks.append(text)
    text = "\n\n".join(chunks) if chunks else soup.get_text(separator="\n", strip=True)
    return (title, _clean_text(text))


def fetch_url_text(url: str, timeout: int = 12) -> Tuple[str, str]:
    """
    Fetch an HTML page and extract title and main text. Returns empty strings
    on failure.
    """
    html = http_client.get(url, timeout=timeout)
    if not html:
        return ("", "")
    return extract_main_text(html)


def call_search(
    prompt: str,
    max_retries: int = 3,
    initial_delay: int = 5,
    model_name: str = OPENAI_SEARCH_MODEL,
    search_context_size: str = "medium",
) -> Dict[str, Any]:
    """
    Call OpenAI's Chat Completions API with the web search tool enabled.

    Returns a dictionary with keys:
      - 'text': the generated text (may include inline citations)
      - 'citations': list of citations (URL, title, start, end indices)

    Retries on errors up to `max_retries` times with exponential backoff.
    """
    last_error: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            resp = oa_client.chat.completions.create(
                model=model_name,
                web_search_options={
                    "search_context_size": search_context_size,
                    "user_location": {
                        "type": "approximate",
                        "approximate": OPENAI_LOCATION,
                    },
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a monitoring assistant. "
                            "Answer concisely in the language of the prompt and include inline citations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            msg = resp.choices[0].message
            content = msg.content or ""
            citations: List[Dict[str, Any]] = []
            for ann in getattr(msg, "annotations", []) or []:
                if getattr(ann, "type", "") == "url_citation" and hasattr(ann, "url_citation"):
                    uc = ann.url_citation
                    citations.append(
                        {
                            "url": uc.url,
                            "title": uc.title,
                            "start": uc.start_index,
                            "end": uc.end_index,
                        }
                    )
            return {"text": content.strip(), "citations": citations}
        except Exception as e:
            last_error = e
            logger.error(f"OpenAI web search error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                # exponential backoff
                time.sleep(initial_delay * (2 ** attempt))
    logger.error(f"All OpenAI calls failed. Last error: {last_error}")
    return {"text": "", "citations": []}


def summarize_with_url_context(url: str, scraped_text: str) -> str:
    """
    Summarise the content of a URL using OpenAI's web search tool. The URL
    itself is provided in the prompt to anchor the search. If the call
    fails or returns empty, a fallback summarisation using the scraped text
    is attempted.
    """
    # Primary prompt referencing the URL
    url_prompt = (
        "Analyse et résume précisément en français le contenu de cette URL. "
        "Mets en avant les nouvelles informations et points clés, en indiquant les dates si elles sont présentes. "
        "Structure la réponse en puces, suivie d'un court paragraphe de synthèse. "
        "Ajoute des citations en ligne pour les sources utilisées."
    )
    try:
        combined_prompt = f"{url_prompt}\n\nURL: {url}"
        result = call_openai_with_search(prompt=combined_prompt, search_context_size="medium")
        if result["text"]:
            return result["text"]
    except Exception as e:
        logger.info(f"OpenAI URL summarisation failed for {url}: {e}")
    # Fallback: summarise the scraped text directly
    if scraped_text:
        fallback_prompt = (
            "Voici le contenu d'une page web. Résume-le en français, en listant d'abord les points clés, "
            "puis une synthèse courte et actionnable. Ajoute des citations si possible.\n\n"
            f"CONTENU:\n{scraped_text[:15000]}"
        )
        result = call_openai_with_search(prompt=fallback_prompt, search_context_size="low")
        if result["text"]:
            return result["text"]
    return "Aucune description disponible pour cette URL."


def perform_search(
    keyword: str,
    site: str,
    max_results: int = 5,
    time_window_hours: int = 48,
) -> List[Dict[str, str]]:
    """
    Use OpenAI's web search tool to find recent pages for `site` and `keyword`.
    Returns a list of dictionaries with keys: title, url, snippet.
    If parsing fails or the model returns non-JSON, an empty list is returned.
    """
    prompt = (
        "Find the most recent pages in the last {hrs} hours relevant to the following search query:\n"
        f"site:{site} {keyword}\n\n"
        "Return a STRICT JSON array of objects with keys: title, url, snippet. "
        "Do not include any extra text before or after the JSON. Limit the list to {limit} items."
    ).format(hrs=time_window_hours, limit=max_results)
    result = call_openai_with_search(prompt=prompt, search_context_size="low")
    text = result.get("text", "")
    if not text:
        return []
    # Try to parse JSON from the model output
    try:
        data = json.loads(text)
        if isinstance(data, list):
            parsed_items: List[Dict[str, str]] = []
            for item in data[:max_results]:
                try:
                    parsed_items.append(
                        {
                            "title": str(item.get("title", "")),
                            "url": str(item.get("url", "")),
                            "snippet": str(item.get("snippet", "")),
                        }
                    )
                except Exception:
                    continue
            return parsed_items
    except Exception:
        pass
    # Fallback: attempt to extract JSON array from text
    try:
        match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.S)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                parsed_items: List[Dict[str, str]] = []
                for item in data[:max_results]:
                    try:
                        parsed_items.append(
                            {
                                "title": str(item.get("title", "")),
                                "url": str(item.get("url", "")),
                                "snippet": str(item.get("snippet", "")),
                            }
                        )
                    except Exception:
                        continue
                return parsed_items
    except Exception:
        pass
    return []


def watch_site(site: str, keywords: List[str]) -> List[Dict[str, str]]:
    """
    Use OpenAI's web search to perform a watch task on an entire website for a list of keywords.

    For the given `site` (e.g. 'https://example.com'), this function instructs OpenAI to search
    for all pages or articles published in the last 48 hours that relate to any of the provided
    keywords. The assistant is expected to return a JSON array of objects where each object has
    the following keys:

      - "Source": the name or title of the publication or source
      - "Contexte et Résumé de la publication": a concise French summary of the content
      - "Date de Publication": the publication date of the content (ISO or human readable)
      - "Implications et Impacts sur UM6P": analysis of how the content affects UM6P
      - "Recommandations Stratégiques pour UM6P": actionable recommendations for UM6P
      - "Lien": the URL of the original content

    Returns an empty list if no results or if parsing fails.
    """
    if not keywords:
        return []
    keywords_str = ", ".join(keywords)
    # Construct prompt instructing the model to perform a comprehensive site search.
    prompt = (
        "Vous êtes un assistant de veille stratégique. "
        f"Sur le site suivant: {site}, recherchez toutes les publications des dernières 48 heures "
        f"qui traitent des mots-clés suivants: {keywords}. "
        "Pour chaque publication trouvée, renvoyez un tableau JSON (array) d'objets avec les champs suivants: "
        "\"Source\", \"Contexte et Résumé de la publication\", \"Date de Publication\", "
        "\"Implications et Impacts sur UM6P\", \"Recommandations Stratégiques pour UM6P\", \"Lien\". "
        "Incluez uniquement les publications publiées au cours des dernières 48 heures. "
        "Le résultat doit être STRICTEMENT du JSON sans aucun texte supplémentaire avant ou après."
    ).format(site=site, keywords=keywords_str)
    result = call_openai_with_search(prompt=prompt, search_context_size="high")
    text = result.get("text", "")
    print(text)
    if not text:
        return []
    # Attempt to parse JSON array from the model output
    try:
        data = json.loads(text)
        if isinstance(data, list):
            parsed_items: List[Dict[str, str]] = []
            for item in data:
                if isinstance(item, dict):
                    parsed_items.append(item)
            return parsed_items
    except Exception:
        pass
    # Fallback: extract the first JSON array in the output if extra text is present
    try:
        match = re.search(r"\[\s*\{.*\}\s*\]", text, re.S)
        if match:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                parsed_items: List[Dict[str, str]] = []
                for item in data:
                    if isinstance(item, dict):
                        parsed_items.append(item)
                print(parsed_items)
                return parsed_items
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Core watch logic with concurrency control

async def perform_watch_task() -> None:
    """
    Main watch task. Processes the configured keywords and URLs, fetches and
    summarises new content, updates the memory, and sends email reports.

    A file lock is used to prevent concurrent executions.
    """

    try:
        logger.info("Watch task started.")
        # Load configuration
        try:
            config_data = safe_load_json(SOURCES_FILE, {})
            config = SourceConfig(**config_data)
        except (ValidationError, Exception) as e:
            logger.error(f"Invalid sources configuration: {e}. Aborting watch.")
            return
        keywords = config.keywords or []
        urls_to_watch = config.veille_par_url or []
        # Normalize URLs to watch
        urls_to_watch = [normalize_url(u) for u in urls_to_watch if u]
        # Load memory
        memory = safe_load_memory()
        seen_urls_set: Set[str] = set(memory.get("seen_urls", []))
        new_urls: Set[str] = set()
        new_details: Dict[str, Any] = {}
        all_results: List[Dict[str, Any]] = []
        # Watch each site for the list of keywords using OpenAI
        for site in urls_to_watch:
            if not site:
                continue
            try:
                print(f"Watching : {site}")
                site_results = watch_site_for_keywords(site, keywords)
            except Exception as e:
                logger.error(f"Error watching site {site}: {e}")
                site_results = []
            for entry in site_results:
                # Extract and normalize the URL of the publication
                link = normalize_url(str(entry.get("Lien", "")))
                if not link:
                    continue
                if link in seen_urls_set:
                    continue
                # Mark as seen and accumulate
                seen_urls_set.add(link)
                new_urls.add(link)
                new_details[link] = entry
                all_results.append(entry)
        # Build report
        report_text = ""
        if all_results:
            # Compose prompt asking the model to create a concise Markdown table and summary
            try:
                json_results = json.dumps(all_results, ensure_ascii=False)
            except Exception:
                json_results = str(all_results)


            report_prompt = (
                "Vous êtes un assistant de veille stratégique. "
                "À partir de la liste JSON suivante d'actualités, génère un rapport structuré pour envoi par email. "
                "Commence par un titre 'RAPPORT DE VEILLE STRATÉGIQUE' et la date du jour. "
                "Ensuite, pour chaque actualité, crée une section bien formatée avec les rubriques suivantes : "
                "\n\n1. SOURCE: [nom de la source]\n"
                "2. DATE: [date de publication]\n"
                "3. RÉSUMÉ: [résumé concis]\n"
                "4. IMPLICATIONS POUR UM6P: [analyse d'impact]\n"
                "5. RECOMMANDATIONS: [actions suggérées]\n"
                "6. LIEN: [URL complète]\n"
                "\nSépare chaque section par une ligne de tirets pour améliorer la lisibilité. "
                "À la fin du rapport, ajoute une section 'SYNTHÈSE GLOBALE' avec 2-3 paragraphes courts "
                "et une section 'RECOMMANDATIONS PRIORITAIRES' avec 2-3 points actionnables clairs. "
                "Optimise le format pour la lecture dans un client email standard (évite les tableaux complexes et les formatages élaborés). "
                "Voici la liste JSON:\n\n"
                f"{json_results}"
            )
            result = call_openai_with_search(prompt=report_prompt, search_context_size="high")
            report_text = result.get("text", "")

            # if report_text:
            # # Convert the text report to HTML with proper tables
            #     html_report = convert_report_to_html(report_text)
            #     send_report_via_email(
            #         subject=f"Rapport de veille - {len(new_urls)} nouvelles actualités",
            #         body=html_report
            #     )
            if not report_text:
                # Build fallback report manually - email-friendly format
                today = datetime.datetime.now().strftime("%d/%m/%Y")
                lines = [
                    "RAPPORT DE VEILLE STRATÉGIQUE - " + today,
                    "=" * 50,
                    "\n"
                ]
                for i, entry in enumerate(all_results, 1):
                    lines.extend([
                        f"ACTUALITÉ #{i}",
                        "-" * 30,
                        f"SOURCE: {str(entry.get('Source', 'Non spécifiée'))}",
                        f"DATE: {str(entry.get('Date de Publication', 'Non spécifiée'))}",
                        f"RÉSUMÉ: {str(entry.get('Contexte et Résumé de la publication', 'Non disponible'))}",
                        f"IMPLICATIONS POUR UM6P: {str(entry.get('Implications et Impacts sur UM6P', 'Non analysées'))}",
                        f"RECOMMANDATIONS: {str(entry.get('Recommandations Stratégiques pour UM6P', 'Non disponibles'))}",
                        f"LIEN: {str(entry.get('Lien', ''))}",
                        "\n" + "-" * 50 + "\n"
                    ])
                
                # Complete the fallback report with a synthesis section
                lines.extend([
                    "\nSYNTHÈSE GLOBALE",
                    "=" * 30,
                    f"Ce rapport contient {len(all_results)} actualités pertinentes relatives aux mots-clés suivis.",
                    "Veuillez analyser les implications et recommandations pour chaque élément.",
                    "\nRECOMMANDATIONS PRIORITAIRES",
                    "=" * 30,
                    "1. Examiner en détail les actualités signalées et valider leur pertinence.",
                    "2. Partager les informations importantes avec les équipes concernées.",
                    "3. Planifier une réunion de suivi pour discuter des actions à entreprendre."
                ])
                
                report_text = "\n".join(lines)
        
        
        # Persist memory and send report
        if new_urls:
            memory["seen_urls"] = list(seen_urls_set)
            memory_details = memory.get("details", {})
            memory_details.update(new_details)
            memory["details"] = memory_details
            if report_text:
                report_entry = {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "new_urls": sorted(new_urls),
                    "report": report_text,
                }
                memory_reports = memory.get("reports", [])
                memory_reports.append(report_entry)
                memory["reports"] = memory_reports

            # Send email with details json in format of html table 
            
             # Convert the details json to HTML with proper tables
            html_details = convert_details_to_html(memory_details)
            send_report_via_email(
                    subject=f"Rapport de veille - {len(new_urls)} nouvelles actualités",
                    body=html_details
            )

            # Save memory
            atomic_save_memory(memory)
        else:
            logger.info("No new relevant content found.")
        logger.info("Watch task completed.")
    finally:
        # Release lock
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except Exception:
            pass



# ---------------------------------------------------------------------------
# FastAPI app

app = FastAPI(
    title="Watcher API",
    description=(
        "API de veille stratégique pour Surveiller et analyser les tendances : politiques publiques, innovation, recherche, durabilité "
    ),
)

# Enable open CORS as requested. In production you should restrict origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/news", summary="Déclenche la veille en tâche de fond")
async def trigger_watch_endpoint(background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    Launch the watch task asynchronously. If a watch is already running, it will
    skip launching another instance.
    """
    background_tasks.add_task(perform_watch_task)
    logger.info("Watch request received. Task scheduled in background.")
    return {"message": "La veille a été lancée en arrière-plan. Consultez les logs pour les détails."}



@app.get("/", summary="Endpoint de santé")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Watcher API is operational."}


