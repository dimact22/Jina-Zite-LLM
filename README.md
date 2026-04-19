# AI Web Scraper

This project is a smart web scraper. It downloads content from any website using the Jina Reader API, and then uses a Large Language Model (Llama 3 via Groq API) to extract structured information in JSON format (product name, brand, price, target audience). The AI is strictly instructed not to hallucinate: if data is missing, it simply outputs `"I don't know"`.

## How to run it on your PC

1. **Install Python 3** (if not already installed).
2. **Install the required library**:
   Open a terminal in the project folder and run:
   ```bash
   pip install requests
   ```
3. **Run the script**:
   In your terminal, execute:
   ```bash
   python scraper.py
   ```
   The script will ask you for a URL. Just paste a website link and press Enter.

Alternatively, you can run it with a URL directly:
```bash
python scraper.py "https://ridge.com/products/titanium-matte-black"
```

The script will automatically create two files in your folder:
- A `.md` file containing the raw text of the webpage.
- A `.json` file containing the structured data extracted by the AI.
