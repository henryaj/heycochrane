#!/usr/bin/env python3
"""
Automated Cochrane Review Update Script

Discovers new Cochrane reviews, summarizes them using Claude API,
and appends them to summaries.yml.
"""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
RSS_URL = "https://www.cochranelibrary.com/cdsr/table-of-contents/rss.xml"
NEWS_URL = "https://www.cochrane.org/news"
COCHRANE_BASE_URL = "https://www.cochrane.org"
REQUEST_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SUMMARIES_PATH = REPO_ROOT / "summaries.yml"
ENRICHMENT_PROMPT_PATH = REPO_ROOT / "enrichment_prompt.txt"
SUMMARIZE_PROMPT_PATH = SCRIPT_DIR / "prompts" / "summarize_prompt.txt"


def get_existing_cd_numbers() -> set[str]:
    """Extract all CD numbers from existing summaries.yml URLs."""
    if not SUMMARIES_PATH.exists():
        return set()

    with open(SUMMARIES_PATH, 'r') as f:
        content = f.read()

    # Match CD numbers in URLs
    cd_pattern = re.compile(r'CD\d+')
    matches = cd_pattern.findall(content)
    return set(matches)


def fetch_rss_reviews() -> list[dict]:
    """Fetch new reviews from Cochrane RSS feed."""
    logger.info(f"Fetching RSS feed from {RSS_URL}")

    try:
        feed = feedparser.parse(RSS_URL)
        if feed.bozo:
            logger.warning(f"RSS feed parsing issue: {feed.bozo_exception}")

        reviews = []
        for entry in feed.entries:
            # Extract CD number from link
            cd_match = re.search(r'CD\d+', entry.get('link', ''))
            if cd_match:
                reviews.append({
                    'cd_number': cd_match.group(),
                    'url': entry.get('link'),
                    'title': entry.get('title', ''),
                })

        logger.info(f"Found {len(reviews)} reviews in RSS feed")
        return reviews

    except Exception as e:
        logger.error(f"Failed to fetch RSS feed: {e}")
        return []


def scrape_news_page() -> list[dict]:
    """Scrape Cochrane news page for review links (fallback)."""
    logger.info(f"Scraping news page from {NEWS_URL}")

    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(NEWS_URL, timeout=REQUEST_TIMEOUT, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        reviews = []

        # Find all links that contain CD numbers
        for link in soup.find_all('a', href=True):
            href = link['href']
            cd_match = re.search(r'CD\d+', href)
            if cd_match:
                # Normalize URL
                if href.startswith('/'):
                    href = COCHRANE_BASE_URL + href

                reviews.append({
                    'cd_number': cd_match.group(),
                    'url': href,
                    'title': link.get_text(strip=True),
                })

        # Deduplicate by CD number
        seen = set()
        unique_reviews = []
        for r in reviews:
            if r['cd_number'] not in seen:
                seen.add(r['cd_number'])
                unique_reviews.append(r)

        logger.info(f"Found {len(unique_reviews)} reviews on news page")
        return unique_reviews

    except Exception as e:
        logger.error(f"Failed to scrape news page: {e}")
        return []


def fetch_plain_language_summary(url: str, cd_number: str = None) -> Optional[str]:
    """Fetch the Plain Language Summary from a Cochrane review page."""
    headers = {"User-Agent": USER_AGENT}

    # Try cochrane.org URL format first (more reliable)
    urls_to_try = []
    if cd_number:
        urls_to_try.append(f"https://www.cochrane.org/{cd_number}")
    urls_to_try.append(url)

    response = None
    for try_url in urls_to_try:
        logger.info(f"Fetching review content from {try_url}")
        try:
            response = requests.get(try_url, timeout=REQUEST_TIMEOUT, headers=headers, allow_redirects=True)
            if response.status_code == 200:
                break
            logger.warning(f"Got status {response.status_code} for {try_url}")
        except Exception as e:
            logger.warning(f"Failed to fetch {try_url}: {e}")
            continue

    if not response or response.status_code != 200:
        logger.error(f"Could not fetch any URL for {cd_number}")
        return None

    try:

        soup = BeautifulSoup(response.text, 'html.parser')

        # Look for Plain Language Summary section
        # Cochrane pages typically have this in specific elements
        pls_section = None

        # Try various selectors that Cochrane uses
        selectors = [
            '.pls-section',
            '#pls',
            '[data-section="pls"]',
            '.plain-language-summary',
        ]

        for selector in selectors:
            pls_section = soup.select_one(selector)
            if pls_section:
                break

        # Fallback: look for text containing "Plain language summary"
        if not pls_section:
            for header in soup.find_all(['h2', 'h3', 'h4']):
                if 'plain language' in header.get_text().lower():
                    # Get the next sibling elements as content
                    content_parts = []
                    for sibling in header.find_next_siblings():
                        if sibling.name in ['h2', 'h3', 'h4']:
                            break
                        content_parts.append(sibling.get_text(strip=True))
                    if content_parts:
                        return '\n\n'.join(content_parts)

        if pls_section:
            return pls_section.get_text(strip=True)

        # Last resort: get the main article content
        article = soup.find('article') or soup.find('main')
        if article:
            # Get first few paragraphs
            paragraphs = article.find_all('p')[:5]
            if paragraphs:
                return '\n\n'.join(p.get_text(strip=True) for p in paragraphs)

        logger.warning(f"Could not find Plain Language Summary for {url}")
        return None

    except Exception as e:
        logger.error(f"Failed to fetch review content: {e}")
        return None


def call_claude(prompt: str, max_tokens: int = 500) -> Optional[str]:
    """Call Claude API with the given prompt."""
    try:
        from anthropic import Anthropic

        client = Anthropic()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.content[0].text

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return None


def summarize_review(plain_language_summary: str) -> Optional[dict]:
    """Use Claude to generate question/answer/notes from Plain Language Summary.

    Returns None if the review should be skipped (e.g., protocol without results).
    """
    with open(SUMMARIZE_PROMPT_PATH, 'r') as f:
        prompt_template = f.read()

    prompt = prompt_template.replace('{plain_language_summary}', plain_language_summary)

    response = call_claude(prompt, max_tokens=500)
    if not response:
        return None

    try:
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Check if Claude indicated this should be skipped
            if result.get('skip'):
                logger.info(f"Skipping review: {result.get('reason', 'no results')}")
                return None
            return result
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse summary JSON: {e}")

    return None


def enrich_summary(summary: dict) -> Optional[dict]:
    """Use Claude to add interest score and tags."""
    with open(ENRICHMENT_PROMPT_PATH, 'r') as f:
        prompt_template = f.read()

    # Use replace instead of format to avoid issues with JSON curly braces in template
    prompt = prompt_template.replace('{question}', summary['question'])
    prompt = prompt.replace('{answer}', summary['answer'])
    prompt = prompt.replace('{notes}', summary['notes'])

    response = call_claude(prompt, max_tokens=100)
    if not response:
        return None

    try:
        # Extract JSON from response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            enrichment = json.loads(json_match.group())
            return {
                **summary,
                'interest': enrichment.get('interest', 5),
                'tags': enrichment.get('tags', [])
            }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse enrichment JSON: {e}")

    return None


def append_to_summaries(new_summaries: list[dict]):
    """Append new summaries to summaries.yml."""
    if not new_summaries:
        return

    # Read existing content
    with open(SUMMARIES_PATH, 'r') as f:
        existing_content = f.read()

    # Build new entries in YAML format
    new_entries = []
    for s in new_summaries:
        entry = f"""
- question: {json.dumps(s['question'])}
  answer: {json.dumps(s['answer'])}
  url: {s['url']}
  notes: |
    {s['notes']}
  interest: {s['interest']}
  tags: {json.dumps(s['tags'])}
"""
        new_entries.append(entry.strip())

    # Append to file
    with open(SUMMARIES_PATH, 'a') as f:
        f.write('\n\n# New reviews added by automation\n')
        f.write('\n\n'.join(new_entries))
        f.write('\n')

    logger.info(f"Appended {len(new_summaries)} new summaries to {SUMMARIES_PATH}")


def validate_yaml():
    """Validate that summaries.yml is valid YAML."""
    try:
        with open(SUMMARIES_PATH, 'r') as f:
            yaml.safe_load(f)
        logger.info("YAML validation passed")
        return True
    except yaml.YAMLError as e:
        logger.error(f"YAML validation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Update Cochrane summaries')
    parser.add_argument('--dry-run', action='store_true',
                        help='Discover reviews but do not call API or modify files')
    parser.add_argument('--max-reviews', type=int, default=10,
                        help='Maximum number of new reviews to process')
    args = parser.parse_args()

    # Get existing CD numbers
    existing = get_existing_cd_numbers()
    logger.info(f"Found {len(existing)} existing CD numbers in summaries.yml")

    # Discover new reviews (try RSS first, then scrape)
    reviews = fetch_rss_reviews()
    if not reviews:
        logger.info("RSS feed returned no results, trying news page scrape")
        reviews = scrape_news_page()

    if not reviews:
        logger.warning("No reviews found from any source")
        return

    # Filter out existing reviews
    new_reviews = [r for r in reviews if r['cd_number'] not in existing]
    logger.info(f"Found {len(new_reviews)} new reviews to process")

    if not new_reviews:
        logger.info("No new reviews to add")
        return

    # Limit number of reviews to process
    new_reviews = new_reviews[:args.max_reviews]

    if args.dry_run:
        logger.info("DRY RUN - Would process these reviews:")
        for r in new_reviews:
            logger.info(f"  {r['cd_number']}: {r['title'][:50]}...")
        return

    # Process each new review
    processed_summaries = []
    for review in new_reviews:
        logger.info(f"Processing {review['cd_number']}...")

        # Fetch plain language summary
        pls = fetch_plain_language_summary(review['url'], review['cd_number'])
        if not pls:
            logger.warning(f"Skipping {review['cd_number']} - could not fetch content")
            continue

        # Summarize with Claude
        summary = summarize_review(pls)
        if not summary:
            logger.warning(f"Skipping {review['cd_number']} - summarization failed")
            continue

        # Add URL
        summary['url'] = review['url']

        # Enrich with interest score and tags
        enriched = enrich_summary(summary)
        if not enriched:
            logger.warning(f"Skipping {review['cd_number']} - enrichment failed")
            continue

        processed_summaries.append(enriched)
        logger.info(f"Successfully processed {review['cd_number']}")

    # Append to summaries.yml
    if processed_summaries:
        append_to_summaries(processed_summaries)

        # Validate YAML
        if not validate_yaml():
            logger.error("YAML validation failed - manual fix required")
            sys.exit(1)

    # Output summary for GitHub Actions
    print(f"::set-output name=count::{len(processed_summaries)}")
    print(f"::set-output name=reviews::{','.join(s.get('url', '') for s in processed_summaries)}")


if __name__ == '__main__':
    main()
