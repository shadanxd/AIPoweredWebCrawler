# E-commerce Product URL Crawler powered by AI Agent

This project consists of two main components:
1.  An AI-powered script (`discover_pattern.py`) to automatically identify the URL structure of product pages on a given e-commerce website.
2.  An asynchronous web crawler (`crawler.py`, run via `main.py`) that uses these identified patterns to find and save product URLs.

## Workflow

The system operates in two distinct phases:

1.  **Pattern Discovery:**
    *   You run `discover_pattern.py` providing the starting URL of the target e-commerce site (e.g., `https://www.example-store.com/`).
    *   This script utilizes the `browser-use` library, which controls a headless browser (via Playwright) to navigate the site.
    *   It interacts with a configured Large Language Model (LLM - currently set to use Gemini via `langchain-google-genai`) to analyze the site structure and determine the common URL path segment that indicates a product detail page (e.g., `/products/`, `/p/`, `/item/`).
    *   The script parses the LLM's output (extracted from logs) to get the pattern string.
    *   The discovered pattern is saved (or updated) in the `patterns.json` file, mapped to the website's domain name (e.g., `"www.example-store.com": "/products/"`).

2.  **Crawling:**
    *   You run `main.py` providing the starting URL of a site whose pattern has already been discovered and saved in `patterns.json`.
    *   The `ProductCrawler` class in `crawler.py` is initialized. It reads `patterns.json` and loads the specific pattern associated with the target domain.
    *   The crawler launches multiple headless browser instances (using Playwright) up to the specified concurrency limit.
    *   Worker tasks asynchronously navigate through the website, starting from the initial URL.
    *   For each page visited, the crawler extracts all links (`<a>` tags).
    *   It checks if a link belongs to the same domain and hasn't been visited before.
    *   If a link matches the loaded product URL pattern for that domain (using a simple substring check), its URL is appended to the `product_urls.txt` file in the format `domain,url` (e.g., `www.example-store.com,https://www.example-store.com/products/cool-item-123`).
    *   Non-product links on the same domain are added to a queue for further crawling, respecting the `max_pages` limit.
    *   The process continues until the queue is empty or the `max_pages` limit is reached.

## Setup and Installation

1.  **Prerequisites:**
    *   Python 3.10+ recommended.
    *   `pip` (Python package installer).
    *   Access to a Google Gemini API key.

2.  **Clone Repository:** (If applicable)
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
    (Assuming you are already in the `ecom-crawler` directory)

3.  **Create Virtual Environment:** (Recommended)
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

4.  **Install Dependencies:**
    *   Ensure `requirements.txt` is up-to-date or install manually. Key packages are: `browser-use`, `playwright`, `langchain-google-genai`, `python-dotenv`, `aiofiles`.
    ```bash
    # pip install -r requirements.txt
    ```

5.  **Install Playwright Browsers:**
    *   This downloads the necessary headless browser engines.
    ```bash
    playwright install chromium
    ```

6.  **Configure API Key:**
    *   Create a file named `.env` in the project root directory (`ecom-crawler`).
    *   Add your Gemini API key to the file like this:
        ```
        GEMINI_API_KEY='YOUR_ACTUAL_GEMINI_API_KEY'
        ```
    *   **Important:** Replace `YOUR_ACTUAL_GEMINI_API_KEY` with your real key. Do not commit the `.env` file to version control (it's included in the `.gitignore`).

## Usage

1.  **Discover Pattern for a New Site:**
    *   Run the discovery script from your terminal, providing the site's starting URL:
        ```bash
        python discover_pattern.py https://www.new-store.com/
        ```
    *   This will analyze the site (may take a few minutes) and update `patterns.json`. Check the script's output and `patterns.json` to confirm success.

2.  **Crawl a Supported Site:**
    *   Ensure the pattern for the site exists in `patterns.json`.
    *   Run the main crawler script, providing the site's starting URL:
        ```bash
        python main.py https://www.new-store.com/
        ```
    *   Optional arguments:
        *   `--max-pages N`: Limit the crawl to N pages (default: 100).
        *   `--max-concurrent N`: Set the number of concurrent browser pages (default: 5).
        ```bash
        python main.py https://www.new-store.com/ --max-pages 500 --max-concurrent 3
        ```
    *   Found product URLs will be appended to `product_urls.txt` in the format `domain,url`.

## Notes & Limitations

*   **Pattern Accuracy:** The LLM-based pattern discovery is generally effective but might occasionally misidentify patterns or fail on complex sites. Manual verification of `patterns.json` might be needed sometimes. The current pattern matching in the crawler (`pattern in url`) is basic and might need refinement for certain URL structures.
*   **Resource Usage:** The Playwright crawler uses full browser instances and can be memory and CPU intensive, especially with higher concurrency. Adjust `--max-concurrent` based on your system resources.
*   **Error Handling:** Basic error handling (timeouts, network errors) is included, but complex site structures or unexpected errors might still halt the crawl for specific URLs. Check the log output for details.
