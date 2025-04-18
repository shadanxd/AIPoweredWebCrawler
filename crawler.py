import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext
from urllib.parse import urlparse, urljoin
import ssl
import certifi
import aiofiles
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductCrawler:
    def __init__(self, start_url, patterns_file="patterns.json"):
        self.start_url = start_url
        self.patterns_file = patterns_file
        self.product_pattern = None
        self.visited = set()
        self.queue = asyncio.Queue()
        self.semaphore = None
        self.active_tasks = set()
        self.max_pages_reached = False
        self.pages_crawled = 0
        self.products_found_count = 0

        try:
            parsed_url = urlparse(start_url)
            self.domain = parsed_url.netloc
            if not self.domain:
                raise ValueError("Could not parse domain from start_url")
            self.output_filename = "product_urls.txt" # Fixed output file
            self._load_pattern()
        except ValueError as e:
            logger.error(f"Initialization error: {e}")
            self.domain = None

    def _load_pattern(self):
        """Loads the URL pattern for the current domain from the patterns file."""
        try:
            with open(self.patterns_file, 'r') as f:
                patterns = json.load(f)
            self.product_pattern = patterns.get(self.domain)
            if self.product_pattern:
                logger.info(f"Loaded pattern '{self.product_pattern}' for domain '{self.domain}' from '{self.patterns_file}'")
            else:
                logger.error(f"Pattern for domain '{self.domain}' not found in '{self.patterns_file}'. Run discover_pattern.py first.")
        except FileNotFoundError:
            logger.error(f"Patterns file '{self.patterns_file}' not found. Run discover_pattern.py first.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from '{self.patterns_file}'.")
        except Exception as e:
             logger.error(f"Error loading pattern file: {e}")

    def is_product_url(self, url):
        """Checks if the URL matches the loaded product pattern for the domain."""
        if not self.product_pattern:
            return False
        try:
            # Check if the loaded pattern string is present anywhere in the full URL string
            return self.product_pattern in url
        except ValueError:
            return False

    def is_same_domain(self, url):
        try:
            # Ensure comparison is between netlocs
            current_netloc = urlparse(url).netloc
            # Handle www. prefix variations simply
            return current_netloc == self.domain or \
                   current_netloc == f"www.{self.domain}" or \
                   f"www.{current_netloc}" == self.domain
        except ValueError:
            return False

    async def worker(self, context: BrowserContext):
        """Worker task to fetch and process URLs using Playwright."""
        while not self.max_pages_reached:
            await self.semaphore.acquire() # Limit concurrency
            page: Page | None = None
            try:
                url = await self.queue.get() # Get URL to process
                if url is None:
                    self.queue.task_done()
                    break

                if url in self.visited or not self.is_same_domain(url) or not url.startswith('http'):
                    self.queue.task_done()
                    continue # Skip if visited, different domain, or not HTTP

                if self.pages_crawled >= self.max_pages:
                    self.max_pages_reached = True
                    self.queue.task_done()
                    # Signal other workers to stop by adding None to the queue
                    for _ in range(len(self.active_tasks)):
                        try:
                            await self.queue.put(None) # Use None as a sentinel
                        except asyncio.QueueFull: break
                    continue # Stop processing if max pages reached

                logger.info(f"Crawling ({self.pages_crawled+1}/{self.max_pages}): {url}")
                self.visited.add(url)
                self.pages_crawled += 1

                try:
                    page = await context.new_page()
                    # Navigate & wait for network idle to ensure JS loads
                    await page.goto(url, timeout=60000, wait_until='networkidle')

                    link_locators = page.locator('a[href]')
                    count = await link_locators.count()
                    for i in range(count):
                        href = await link_locators.nth(i).get_attribute('href')
                        if not href: continue

                        try:
                            full_url = urljoin(url, href).split('#')[0]
                        except ValueError:
                            continue

                        if full_url not in self.visited and self.is_same_domain(full_url) and full_url.startswith('http'):
                            if self.is_product_url(full_url):
                                self.products_found_count += 1
                                try:
                                    # Write in domain,url format
                                    async with aiofiles.open(self.output_filename, mode='a', encoding='utf-8') as f:
                                        await f.write(f"{self.domain},{full_url}\n")
                                except Exception as e:
                                    logger.error(f"Error writing {self.domain},{full_url} to file {self.output_filename}: {e}")
                            else:
                                if not self.max_pages_reached and self.pages_crawled < self.max_pages:
                                             await self.queue.put(full_url) # Add non-product URL back to queue

                except asyncio.TimeoutError:
                     logger.warning(f"Timeout error crawling {url}")
                except Exception as e:
                    if "Playwright" in str(type(e)): # Catch likely Playwright errors
                         logger.warning(f"Playwright error crawling {url}: {e}")
                    else: # Log other errors with traceback
                         logger.error(f"Error processing {url}: {e}", exc_info=True)
                finally:
                    if page: await page.close() # Ensure page is closed
                    self.queue.task_done() # Signal queue item completion

            except asyncio.CancelledError:
                 logger.info("Worker cancelled.")
                 break
            except Exception as e:
                 logger.error(f"Unexpected error in worker: {e}", exc_info=True)
                 if 'url' in locals() and not self.queue.empty():
                     try: self.queue.task_done()
                     except ValueError: pass # Ignore error if task_done already called
            finally:
                 if page and not page.is_closed(): # Double-check page closure
                     await page.close()
                 self.semaphore.release() # Release semaphore slot


    async def crawl(self, max_pages=100, max_concurrent=5): # Reduced default concurrency
        """Starts the asynchronous crawl using Playwright."""
        if not self.domain or not self.product_pattern:
             logger.error("Cannot start crawl: Domain not parsed or product pattern not loaded.")
             return 0

        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_pages = max_pages
        self.max_pages_reached = False
        self.pages_crawled = 0
        self.products_found_count = 0


        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                ignore_https_errors=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            logger.info("Playwright browser context created (ignoring HTTPS errors).")

            try:
                await self.queue.put(self.start_url)

                self.active_tasks = set()
                for _ in range(max_concurrent):
                    task = asyncio.create_task(self.worker(context))
                    self.active_tasks.add(task)
                    task.add_done_callback(self.active_tasks.discard) # Remove task from set when done

                await self.queue.join()
                logger.info("Queue processing finished.")

                for _ in range(max_concurrent):
                    await self.queue.put(None)

                await asyncio.gather(*self.active_tasks, return_exceptions=True) # Wait for tasks to finish

            finally:
                logger.info("Closing Playwright browser context and browser...")
                await context.close()
                await browser.close()
                logger.info("Playwright closed.")

        logger.info(f"Crawling complete. Crawled {self.pages_crawled} pages. Found {self.products_found_count} products. Results saved to {self.output_filename}")
        return self.pages_crawled
