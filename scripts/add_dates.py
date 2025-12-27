#!/usr/bin/env python3
"""
Add publication dates to existing summaries by fetching from CrossRef API or Cochrane pages.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SUMMARIES_PATH = REPO_ROOT / "summaries.yml"
REQUEST_TIMEOUT = 15
USER_AGENT = "HeyCochrane/1.0 (https://github.com/henryaj/heycochrane; mailto:contact@example.com)"

# Rate limiting
CROSSREF_DELAY = 0.1  # Be polite to CrossRef
COCHRANE_DELAY = 0.5  # Be polite to Cochrane


def extract_doi(url: str) -> Optional[str]:
    """Extract DOI from a Cochrane URL."""
    # Pattern: 10.1002/14651858.CD...
    doi_patterns = [
        r'(10\.1002/14651858\.CD\d+(?:\.pub\d+)?)',
        r'doi/(10\.[^/]+/[^/]+)',
    ]
    for pattern in doi_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_cd_number(url: str) -> Optional[str]:
    """Extract CD number from URL for Cochrane.org lookup."""
    match = re.search(r'(CD\d+)', url, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def get_date_from_crossref(doi: str) -> Optional[str]:
    """Fetch publication date from CrossRef API."""
    try:
        url = f"https://api.crossref.org/works/{doi}"
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            message = data.get("message", {})

            # Try different date fields
            for field in ["published", "issued", "published-online", "created"]:
                if field in message:
                    date_parts = message[field].get("date-parts", [[]])[0]
                    if len(date_parts) >= 3:
                        return f"{date_parts[0]}-{date_parts[1]:02d}-{date_parts[2]:02d}"
                    elif len(date_parts) >= 2:
                        return f"{date_parts[0]}-{date_parts[1]:02d}-01"
                    elif len(date_parts) >= 1:
                        return f"{date_parts[0]}-01-01"
        return None
    except Exception as e:
        logger.debug(f"CrossRef error for {doi}: {e}")
        return None


def get_date_from_cochrane_page(cd_number: str) -> Optional[str]:
    """Fetch publication date from Cochrane.org page structured data."""
    try:
        # Try the standard Cochrane.org URL pattern
        url = f"https://www.cochrane.org/{cd_number}"
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)

        if response.status_code == 200:
            # Look for JSON-LD structured data
            match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', response.text)
            if match:
                date_str = match.group(1)
                # Parse ISO date
                date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', date_str)
                if date_match:
                    return f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        return None
    except Exception as e:
        logger.debug(f"Cochrane page error for {cd_number}: {e}")
        return None


def get_date_for_entry(entry: dict, index: int) -> tuple[int, Optional[str]]:
    """Get publication date for a single entry."""
    url = entry.get("url", "")

    # Skip if already has date
    if entry.get("date"):
        return index, entry["date"]

    # Try CrossRef first (faster, more reliable)
    doi = extract_doi(url)
    if doi:
        date = get_date_from_crossref(doi)
        if date:
            logger.info(f"[{index}] Found date via CrossRef: {date}")
            return index, date
        time.sleep(CROSSREF_DELAY)

    # Fall back to Cochrane page
    cd_number = extract_cd_number(url)
    if cd_number:
        time.sleep(COCHRANE_DELAY)
        date = get_date_from_cochrane_page(cd_number)
        if date:
            logger.info(f"[{index}] Found date via Cochrane page: {date}")
            return index, date

    logger.warning(f"[{index}] Could not find date for: {url}")
    return index, None


def main():
    """Main entry point."""
    logger.info(f"Reading summaries from {SUMMARIES_PATH}")

    with open(SUMMARIES_PATH, 'r') as f:
        summaries = yaml.safe_load(f)

    if not summaries:
        logger.error("No summaries found")
        return

    total = len(summaries)
    logger.info(f"Found {total} summaries")

    # Count entries without dates
    without_dates = sum(1 for s in summaries if not s.get("date"))
    logger.info(f"{without_dates} entries need dates")

    if without_dates == 0:
        logger.info("All entries already have dates!")
        return

    # Process entries with threading for speed
    updated = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(get_date_for_entry, entry, i): i
            for i, entry in enumerate(summaries) if not entry.get("date")
        }

        for future in as_completed(futures):
            index, date = future.result()
            if date:
                summaries[index]["date"] = date
                updated += 1
            else:
                failed += 1

            # Progress update every 50 entries
            if (updated + failed) % 50 == 0:
                logger.info(f"Progress: {updated + failed}/{without_dates} processed ({updated} updated, {failed} failed)")

    logger.info(f"Finished: {updated} dates added, {failed} could not be found")

    # Write back
    logger.info(f"Writing updated summaries to {SUMMARIES_PATH}")
    with open(SUMMARIES_PATH, 'w') as f:
        yaml.dump(summaries, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Done!")


if __name__ == "__main__":
    main()
