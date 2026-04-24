"""
scrape.py  –  Universal AI Web Scraper
========================================

A two-engine scraping pipeline that extracts structured JSON from any URL
using an LLM (OpenRouter / Llama 3.3-70B).

Engines
-------
  jina   – Lightweight, fast. Uses Jina Reader API to return clean Markdown.
  zyte   – Heavy-duty, browser-rendered. Uses Zyte API for JS-heavy or
           bot-protected pages.
  auto   – (default) Tries Jina first; falls back to Zyte when Jina fails
           or returns low-quality content.

Auto-fallback triggers
----------------------
  1. Jina returns an HTTP error (e.g. 403, 422).
  2. Jina response is < 500 characters (empty / placeholder page).
  3. Jina response contains bot-challenge keywords (Cloudflare, captcha, etc.).
  4. LLM sets "target_audience" to "I don't know" (dynamic SPA content missed).

Usage
-----
  python scrape.py "https://example.com"
  python scrape.py "https://example.com" --engine zyte
  python scrape.py "https://example.com" --engine zyte --zyte-no-browser
  python scrape.py --engine jina           # will prompt for URL

Environment variables  (put these in a .env file)
--------------------------------------------------
  OPENROUTER_API_KEY  – https://openrouter.ai
  JINA_API_KEY        – https://jina.ai  (optional but increases rate limits)
  ZYTE_API_KEY        – https://app.zyte.com

Dependencies
------------
  pip install requests markdownify beautifulsoup4 python-dotenv
"""

import os
import sys
import time
import argparse
import requests
import json
import re
from functools import wraps
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print(
        "Warning: 'python-dotenv' not installed. .env file will not be loaded.\n"
        "Install it with:  pip install python-dotenv",
        file=sys.stderr,
    )

try:
    import markdownify
except ImportError:
    print(
        "Error: 'markdownify' is required.\n"
        "Install it with:  pip install markdownify",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(
        "Error: 'beautifulsoup4' is required.\n"
        "Install it with:  pip install beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------- Configuration ----------------

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
JINA_API_KEY       = os.getenv("JINA_API_KEY", "")
ZYTE_API_KEY       = os.getenv("ZYTE_API_KEY", "")

ZYTE_API_URL = "https://api.zyte.com/v1/extract"
PROMPT_FILE  = "prompt.txt"

# -----------------------------------------------


def check_required_keys(*keys: tuple[str, str]) -> None:
    """Raise an error if any required API key is missing."""
    missing = [name for name, value in keys if not value]
    if missing:
        print(
            f"Error: Missing required environment variable(s): {', '.join(missing)}\n"
            "Please set them in your .env file.",
            file=sys.stderr,
        )
        sys.exit(1)


def with_retry(max_retries: int = 3, delay_sec: float = 2):
    """Decorator: retry a function on RequestException up to *max_retries* times."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_err = e
                    if attempt < max_retries:
                        print(
                            f"[Attempt {attempt}/{max_retries} failed] Retrying in {delay_sec}s: {e}",
                            file=sys.stderr,
                        )
                        time.sleep(delay_sec)
                    else:
                        print(
                            f"[Attempt {attempt}/{max_retries} failed] Giving up: {e}",
                            file=sys.stderr,
                        )
            raise last_err
        return wrapper
    return decorator


def get_safe_filename(url: str, extension: str = ".md") -> str:
    """Generate a safe Windows/Linux filename from a URL."""
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}".rstrip("/")
    safe = re.sub(r'[\\/*?:"<>|]', "_", raw) or "scraped_page"
    return safe + extension


def read_prompt(prompt_file: str) -> str:
    """Read the LLM instruction prompt from a text file."""
    if not os.path.exists(prompt_file):
        print(f"Error: Prompt file '{prompt_file}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


# ──────────────── Extraction Engines ────────────────

@with_retry(max_retries=3, delay_sec=2)
def scrape_with_jina(url: str) -> str:
    """Fetch structured Markdown via Jina Reader API."""
    print(f"Fetching: {url}  [engine: Jina Reader]", file=sys.stderr)

    headers = {"X-Return-Format": "markdown"}
    if JINA_API_KEY:
        headers["Authorization"] = f"Bearer {JINA_API_KEY}"

    response = requests.get(f"https://r.jina.ai/{url}", headers=headers, timeout=60)

    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f"Jina API returned HTTP {response.status_code}\n{response.text}"
        )

    return response.text


@with_retry(max_retries=3, delay_sec=3)
def scrape_with_zyte(url: str, use_browser: bool = True) -> str:
    """Scrape a URL via Zyte API and return clean Markdown."""
    mode = "browserHtml" if use_browser else "httpResponseBody"
    print(f"Fetching: {url}  [engine: Zyte / {mode}]", file=sys.stderr)

    payload: dict = {"url": url, "geolocation": "DE"}
    if use_browser:
        payload["browserHtml"] = True
    else:
        payload["httpResponseBody"] = True

    response = requests.post(
        ZYTE_API_URL,
        auth=(ZYTE_API_KEY, ""),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    raw_html = data.get("browserHtml" if use_browser else "httpResponseBody") or ""
    if not raw_html:
        return ""

    # 1. Strip noise tags
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(
        ["script", "style", "svg", "img", "video", "audio",
         "iframe", "canvas", "noscript", "footer", "nav", "aside", "header", "meta"]
    ):
        tag.decompose()

    # 2. Convert to Markdown
    md_text = markdownify.markdownify(str(soup), heading_style="ATX")

    # 3. Strip base64 blobs and excessive blank lines
    md_text = re.sub(r"data:image/[^;]+;base64,[^\)\]\"\'\s]+", "", md_text)
    md_text = re.sub(r"data:font/[^;]+;base64,[^\)\]\"\'\s]+", "", md_text)
    md_text = re.sub(r"\n{3,}", "\n\n", md_text).strip()

    return md_text


# ──────────────── OpenRouter LLM Extraction ────────────────

@with_retry(max_retries=3, delay_sec=2)
def extract_data_with_openrouter(markdown_content: str, instruction_prompt: str) -> str:
    """Send scraped Markdown + prompt to OpenRouter (Llama 3.3-70B) and return JSON."""
    MAX_CHARS = 100_000
    if len(markdown_content) > MAX_CHARS:
        print(
            f"Warning: Content too long ({len(markdown_content):,} chars). "
            f"Truncating to {MAX_CHARS:,}.",
            file=sys.stderr,
        )
        markdown_content = markdown_content[:MAX_CHARS]

    print("Sending to OpenRouter API (llama-3.3-70b-instruct) ...", file=sys.stderr)

    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": [
            {
                "role": "user",
                "content": (
                    f"{instruction_prompt}\n\n"
                    f"Here is the scraped Markdown content from the webpage:\n\n"
                    f"{markdown_content}"
                ),
            }
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ──────────────── Jina Quality Check ────────────────

def is_jina_blocked(text: str) -> bool:
    """Return True if Jina returned a bot-challenge or empty page."""
    if len(text) < 500:
        return True

    block_phrases = [
        "verify you are human",
        "please enable javascript",
        "are you a robot",
        "just a moment...",
        "checking your browser",
        "cloudflare",
    ]
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in block_phrases)


# ──────────────── Main ────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Universal AI Web Scraper – extracts structured JSON from any URL."
    )
    parser.add_argument("url", nargs="?", help="URL to scrape")
    parser.add_argument(
        "--engine",
        choices=["auto", "jina", "zyte"],
        default="auto",
        help="Scraping engine (default: auto – tries Jina, falls back to Zyte).",
    )
    parser.add_argument(
        "--zyte-no-browser",
        action="store_true",
        help="Use Zyte's httpResponseBody instead of full browser rendering (faster).",
    )
    args = parser.parse_args()

    # Resolve URL
    target_url: str = args.url or ""
    if not target_url:
        try:
            target_url = input("Enter the URL to scrape: ").strip()
        except EOFError:
            target_url = ""

    if not target_url:
        print("Error: No URL provided. Exiting.", file=sys.stderr)
        sys.exit(1)

    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    # Validate required keys early
    check_required_keys(("OPENROUTER_API_KEY", OPENROUTER_API_KEY))
    if args.engine in ("zyte", "auto"):
        check_required_keys(("ZYTE_API_KEY", ZYTE_API_KEY))

    # Read prompt
    instruction_prompt = read_prompt(PROMPT_FILE)
    use_browser = not args.zyte_no_browser

    # ── Extraction pipeline ──
    try:
        md = ""
        json_text = "{}"

        if args.engine == "jina":
            md = scrape_with_jina(target_url)
            json_text = extract_data_with_openrouter(md, instruction_prompt)
            print("Extraction finished (Jina only).", file=sys.stderr)

        elif args.engine == "zyte":
            md = scrape_with_zyte(target_url, use_browser=use_browser)
            json_text = extract_data_with_openrouter(md, instruction_prompt)
            print("Extraction finished (Zyte only).", file=sys.stderr)

        else:  # auto
            print("[Auto] Trying Jina first ...", file=sys.stderr)
            jina_failed = False

            try:
                md = scrape_with_jina(target_url)

                if is_jina_blocked(md):
                    print("[Auto] Jina hit a bot-protection / captcha page.", file=sys.stderr)
                    jina_failed = True
                else:
                    print("[Auto] Analyzing Jina content with LLM ...", file=sys.stderr)
                    json_text = extract_data_with_openrouter(md, instruction_prompt)

                    try:
                        parsed = json.loads(json_text)
                        if parsed.get("target_audience") == "I don't know":
                            print(
                                "[Auto] LLM returned 'I don't know' for target_audience – "
                                "likely dynamic/SPA content missed by Jina.",
                                file=sys.stderr,
                            )
                            jina_failed = True
                        else:
                            print("[Auto] Jina successfully extracted the required data!", file=sys.stderr)
                    except json.JSONDecodeError:
                        print("[Auto] LLM returned invalid JSON on Jina pass.", file=sys.stderr)
                        jina_failed = True

            except requests.exceptions.RequestException as e:
                print(f"[Auto] Jina HTTP error: {e}", file=sys.stderr)
                jina_failed = True

            if jina_failed:
                print("\n[--> FALLBACK: Switching to Zyte <--]", file=sys.stderr)
                md = scrape_with_zyte(target_url, use_browser=use_browser)
                print("[Auto] Analyzing Zyte content with LLM ...", file=sys.stderr)
                json_text = extract_data_with_openrouter(md, instruction_prompt)

    except Exception as e:
        print(f"Fatal: scraping failed – {e}", file=sys.stderr)
        sys.exit(1)

    # Save Markdown
    md_filename = get_safe_filename(target_url, ".md")
    try:
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Saved Markdown → '{md_filename}'", file=sys.stderr)
    except OSError as e:
        print(f"Warning: Could not save Markdown: {e}", file=sys.stderr)

    # Save & print JSON
    try:
        parsed_json = json.loads(json_text)
        json_filename = get_safe_filename(target_url, ".json")
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)
        print(f"\n--- Extracted data saved → '{json_filename}' ---", file=sys.stderr)
        print(json.dumps(parsed_json, indent=4, ensure_ascii=False))
    except json.JSONDecodeError:
        print("Warning: LLM did not return valid JSON. Raw output:", file=sys.stderr)
        print(json_text)


if __name__ == "__main__":
    main()
