import asyncio
import json
import argparse
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent
import logging
import io

# --- Logging Setup ---
# Capture logs into a string buffer
log_stream = io.StringIO()
agent_logger = logging.getLogger("browser_use") 
agent_logger.setLevel(logging.INFO) # Ensure INFO level messages are captured

# Create a handler that writes to our string stream
stream_handler = logging.StreamHandler(log_stream)
formatter = logging.Formatter('%(levelname)-8s [%(name)s] %(message)s') # Match agent log format
stream_handler.setFormatter(formatter)
# Add the handler ONLY if it doesn't exist to avoid duplicate logs
if not any(isinstance(h, logging.StreamHandler) and h.stream == log_stream for h in agent_logger.handlers):
    agent_logger.addHandler(stream_handler)
    # Prevent logs from propagating to the root logger if it has handlers (like console output)
    # agent_logger.propagate = False # Uncomment if you see duplicate logs in console

load_dotenv()

PATTERNS_FILE = "patterns.json"

def parse_pattern_from_logs(log_content: str) -> str | None:
    """Parses the discovered pattern from captured log output."""
    pattern = None
    result_prefix = "INFO     [agent] 📄 Result: "
    for line in log_content.splitlines():
        if line.strip().startswith(result_prefix):
            pattern = line.strip()[len(result_prefix):].strip()
            # Adjusted validation: Must start with '/', but ending '/' is optional
            # Also check it's not just "/"
            if pattern.startswith('/') and len(pattern) > 1:
                 print(f"Pattern parsed from logs: '{pattern}'")
                 return pattern
            else:
                 print(f"Parsed potential pattern '{pattern}' but it doesn't look valid.")
                 pattern = None # Reset if invalid format
    print("Pattern not found in logs.")
    return None


async def discover_and_save_pattern(start_url: str):
    """
    Uses browser-use agent to discover the product URL pattern for a given site
    and saves it to a JSON file by parsing agent logs.
    """
    print(f"Attempting to discover pattern for: {start_url}")
    discovered_pattern = None # Initialize pattern variable

    try:
        # Extract domain name to use as the key in JSON
        parsed_url = urlparse(start_url)
        domain = parsed_url.netloc
        if not domain:
            print(f"Error: Could not parse domain from URL: {start_url}")
            return

        # --- Configure LLM (Gemini) ---
        import os
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            print("Error: GEMINI_API_KEY not found in environment variables. Check .env file.")
            return
        try:
            llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17", google_api_key=gemini_api_key)
        except Exception as e:
            print(f"Error initializing Gemini LLM. Check GEMINI_API_KEY value in .env file and model name. Error: {e}")
            return

        # --- Configure Agent ---
        task_prompt = (
            f"Analyze the website structure starting from {start_url}. "
            "Follow links for a few pages to understand the site layout. "
            "Identify the primary, common URL path segment that uniquely identifies individual product detail pages "
            "(e.g., '/products/', '/item/', '/p/', '/dp/'). "
            "Exclude category, list, search, or account pages. "
            "Output ONLY the identified path segment string and nothing else. For example, if product URLs look like "
            "'https://example.com/products/widget-123', output only '/products/'."
        )
        agent = Agent(task=task_prompt, llm=llm)

        # --- Run Agent ---
        print("Running browser-use agent (this might take a while)...")
        try:
            await agent.run()
            print("Agent run completed.")
        except Exception as agent_run_e:
            print(f"Error occurred while running the agent: {agent_run_e}")
            # Still try to parse logs even if agent run had non-fatal error
            pass # Continue to log parsing

        # --- Parse Logs and Save Pattern ---
        log_content = log_stream.getvalue()
        discovered_pattern = parse_pattern_from_logs(log_content)

        # Use the same relaxed validation here as in the parsing function
        if discovered_pattern: # Check if parsing returned a non-None value
            print(f"Successfully discovered pattern for {domain}: {discovered_pattern}")
            patterns = {}
            try:
                with open(PATTERNS_FILE, 'r') as f:
                    patterns = json.load(f)
            except FileNotFoundError:
                print(f"'{PATTERNS_FILE}' not found, creating a new one.")
            except json.JSONDecodeError:
                print(f"Error reading '{PATTERNS_FILE}', will overwrite.")

            patterns[domain] = discovered_pattern
            try:
                with open(PATTERNS_FILE, 'w') as f:
                    json.dump(patterns, f, indent=4)
                print(f"Pattern saved to '{PATTERNS_FILE}'.")
            except IOError as e:
                print(f"Error saving patterns to '{PATTERNS_FILE}': {e}")
        else:
            print(f"Error: Failed to extract a valid pattern from agent logs.")
            # print("--- Full Agent Log ---") # Optional: print full log for debugging
            # print(log_content)
            # print("--- End Agent Log ---")

    except Exception as e:
        print(f"An unexpected error occurred in discover_and_save_pattern: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Discover product URL pattern for an e-commerce site.")
    parser.add_argument("start_url", help="The starting URL of the e-commerce website (e.g., https://www.example.com)")
    args = parser.parse_args()
    await discover_and_save_pattern(args.start_url)

if __name__ == "__main__":
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Playwright not found. Please run 'playwright install chromium' first.")
        sys.exit(1)
    asyncio.run(main())
