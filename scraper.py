import os
import sys
import argparse
import requests
import json
import re
from urllib.parse import urlparse

# ---------------- Configuration ----------------

# It's better to store keys in environment variables (os.getenv), but keeping them here as fallback
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
PROMPT_FILE = "prompt.txt"

# -----------------------------------------------

def get_safe_filename(url, extension=".md"):
    """Generate a valid Windows/Linux file name from a URL."""
    parsed_url = urlparse(url)
    raw_name = f"{parsed_url.netloc}{parsed_url.path}"
    if raw_name.endswith('/'):
        raw_name = raw_name[:-1]
    
    # Replace invalid filename characters with underscore
    safe_filename = re.sub(r'[\\/*?:"<>|]', '_', raw_name)
    if not safe_filename:
        safe_filename = "scraped_page"
    return safe_filename + extension

def read_prompt(prompt_file):
    if not os.path.exists(prompt_file):
        print(f"Error: Prompt file '{prompt_file}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def scrape_with_jina(url):
    print(f"Fetching content from: {url} ...", file=sys.stderr)
    
    # Actually using the Jina API key!
    headers = {
        "Authorization": f"Bearer {JINA_API_KEY}",
        "X-Return-Format": "markdown"
    } if JINA_API_KEY else {}

    try:
        response = requests.get(f"https://r.jina.ai/{url}")
        if response.status_code != 200:
            print(f"Error: Jina API returned status code {response.status_code}", file=sys.stderr)
            print(response.text, file=sys.stderr)
            sys.exit(1)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL from Jina: {e}", file=sys.stderr)
        sys.exit(1)

def extract_data_with_groq(markdown_content, instruction_prompt):
    # Free tier limit check
    MAX_CHARS = 30000
    if len(markdown_content) > MAX_CHARS:
        print(f"Warning: Text is too long for Groq API. Truncating from {len(markdown_content)} to {MAX_CHARS} characters...", file=sys.stderr)
        markdown_content = markdown_content[:MAX_CHARS]
        
    print("Sending to Groq API...", file=sys.stderr)
    full_user_prompt = f"{instruction_prompt}\n\nHere is the scraped Markdown content from the webpage:\n\n{markdown_content}"
    
    groq_url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {
                "role": "user",
                "content": full_user_prompt
            }
        ],
        "response_format": {"type": "json_object"}
    }
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(groq_url, json=payload, headers=headers)
        response.raise_for_status()
        
        response_data = response.json()
        final_text = response_data['choices'][0]['message']['content']
        return final_text
    except Exception as e:
        error_details = "\nServer response: " + response.text if 'response' in locals() and hasattr(response, 'text') else ""
        print(f"Error generating content with Groq: {e}{error_details}", file=sys.stderr)
        sys.exit(1)

def main():
    # Setup argparse for better CLI usage
    parser = argparse.ArgumentParser(description="Scrape a webpage and extract structured JSON using an LLM.")
    parser.add_argument("url", nargs="?", help="The URL to scrape")
    args = parser.parse_args()

    target_url = args.url
    if not target_url:
        try:
            target_url = input("Enter the URL to scrape: ").strip()
        except EOFError:
            target_url = ""
            
    if not target_url:
        print("URL is empty. Exiting.", file=sys.stderr)
        sys.exit(1)
        
    # User-friendly URL formatting
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    # 1. Read Prompt
    instruction_prompt = read_prompt(PROMPT_FILE)

    # 2. Scrape Page
    markdown_content = scrape_with_jina(target_url)
    print(f"Successfully fetched {len(markdown_content)} characters.", file=sys.stderr)

    # Save Markdown to file
    md_filename = get_safe_filename(target_url, ".md")
    try:
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"Saved full Markdown text to '{md_filename}'", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not save markdown to file: {e}", file=sys.stderr)

    # 3. Extract JSON
    json_result_text = extract_data_with_groq(markdown_content, instruction_prompt)
    
    # 4. Parse, Save, and Print JSON Result
    try:
        parsed_json = json.loads(json_result_text)
        json_filename = get_safe_filename(target_url, ".json")
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(parsed_json, f, indent=4, ensure_ascii=False)
            
        print(f"\n--- Extracted Data Saved to '{json_filename}' ---", file=sys.stderr)
        print(json.dumps(parsed_json, indent=4, ensure_ascii=False))
        
    except json.JSONDecodeError:
        print("Warning: Groq API did not return valid JSON. Printing raw output:", file=sys.stderr)
        print(json_result_text)

if __name__ == "__main__":
    main()
