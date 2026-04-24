# AI Web Scraper

This project is a smart web scraper. It downloads content from any website using **Jina Reader API** or **Zyte API**, and then uses a Large Language Model (Llama 3 via Groq) to extract structured information in JSON format.

## Setup

1. **Install Python 3**.
2. **Install requirements**:
   ```bash
   pip install requests markdownify
   ```

## Usage

The new unified `scrape.py` script lets you choose your extraction engine.

### Using Jina (Default)
Best for basic webpages and articles.
```bash
python scrape.py "https://ridge.com/products/titanium-matte-black"
```

### Using Zyte
Best for websites with bot-protection, captchas, or heavy JS (Amazon, Nike, BestBuy).
```bash
python scrape.py "https://www.nike.com/t/air-max-plus" --engine zyte
```

*(By default, Zyte uses a full headless browser. You can pass `--zyte-no-browser` to use fast HTTP mode for Zyte if JS is not needed).*

## Output
The script automatically creates two files:
- A `.md` file containing the raw Markdown of the webpage (cleaned by Markdownify).
- A `.json` file containing the structured data.
