# Universal AI Web Scraper & Persona Generator

A robust, enterprise-grade scraping pipeline that combines the speed of **Jina Reader** with the unblockable reliability of **Zyte API**. It extracts structured JSON from any single URL or **synthesizes multiple URLs** (e.g., a product page + a brand's "About Us" page) to generate deep buyer personas using the **Llama 3.3-70B** model via OpenRouter.

## Key Features
- **Context Stitching (Multi-URL):** Pass multiple URLs to merge product specs with brand philosophy. The script intelligently combines them into a massive single document (up to 250,000 chars) to give the LLM perfect context for deep marketing analysis.
- **Hybrid Auto-Fallback:** Automatically switches from Jina to Zyte if a site is protected by Cloudflare, heavily JS-rendered, or if the LLM detects missing dynamic content.
- **Robust JSON Extraction:** Built-in regex cleaners strip conversational text and markdown fences, guaranteeing clean JSON output even when the LLM hallucinates formatting.
- **Smart Cleanup:** Uses BeautifulSoup and Markdownify to strip junk HTML (scripts, navs, footers), saving up to 80% on AI token costs.
- **Clean Workspace:** Automatically saves all generated `.md` and `.json` artifacts into a dedicated `results/` folder.

## Setup

1. **Install requirements**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Configuration**:
   Create a `.env` file in the root directory and add your keys:
   ```env
   OPENROUTER_API_KEY=your_key
   ZYTE_API_KEY=your_key
   JINA_API_KEY=your_key_optional
   ```

## Usage

The script runs in **Auto mode** by default, trying Jina first and falling back to Zyte.

### 1. Product Data Extraction (Default)
Extracts pricing, availability, specs, and basic audience data.
```bash
python scrape.py https://example.com/product --prompt prompt.txt
```

### 2. Deep Persona Generation (Marketing Analysis)
Use `prompt2.txt` to generate detailed buyer personas, pain points, and goals.
```bash
python scrape.py https://example.com/product --prompt prompt2.txt
```

### 3. Context Stitching (Product + Brand History)
Pass two URLs. The script will stitch them together. Perfect for generating high-quality personas that take both the product features and the brand's core values into account.
```bash
python scrape.py https://www.yeti.com/coolers/tundra.html https://www.yeti.com/about-us.html --prompt prompt2.txt
```

## How the Fallback Logic Works
The script will trigger a fallback to **Zyte API** if:
1. **HTTP Error**: Jina is blocked (403, 422, etc.).
2. **Bot Protection**: Cloudflare or "Please enable JS" detected in Jina's output.
3. **Skeleton Page**: Jina returns less than 500 characters of text.
4. **AI Quality Check**: The LLM cannot find meaningful data in Jina's output (returns empty target audience), meaning vital SPA/JS content was missed.

## Output
Each run generates files in the `results/` directory:
- A `.md` file with the cleaned-up source text (or combined text from multiple URLs).
- A `.json` file with the structured business data/personas.
