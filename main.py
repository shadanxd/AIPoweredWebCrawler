import asyncio
from crawler import ProductCrawler
import logging 
import argparse 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Crawl an e-commerce website for product URLs using discovered patterns.")
    parser.add_argument("start_url", help="The starting URL of the e-commerce website to crawl (e.g., https://www.example.com)")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of pages to crawl (default: 100)")
    # Reduced default concurrency for Playwright
    parser.add_argument("--max-concurrent", type=int, default=5, help="Maximum concurrent browser pages (default: 5)")
    args = parser.parse_args()

    start_url = args.start_url
    max_pages = args.max_pages
    max_concurrent = args.max_concurrent
    # --- End Argument Parsing ---

    # Instantiate the crawler - it will load the pattern from patterns.json
    logger.info(f"Initializing crawler for {start_url}")
    crawler = ProductCrawler(start_url) # No need to pass output_filename

    # Check if crawler initialized correctly (domain parsed and pattern loaded)
    if not crawler.domain or not crawler.product_pattern:
         logger.error("Crawler initialization failed. Check if pattern exists in patterns.json. Exiting.")
         return # Stop execution if pattern wasn't loaded

    # Run the asynchronous crawl using arguments
    logger.info(f"Starting crawl (max_pages={max_pages}, max_concurrent={max_concurrent})")
    pages_crawled = await crawler.crawl(max_pages=max_pages, max_concurrent=max_concurrent)

    # Use the output filename determined by the crawler
    logger.info(f"Crawl finished. Crawled {pages_crawled} pages. Check '{crawler.output_filename}' for results.")

if __name__ == "__main__":
    asyncio.run(main())
