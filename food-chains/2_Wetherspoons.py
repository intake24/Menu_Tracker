import requests
import logging
import json
from typing import Optional
from define_collection_wave import folder
import pandas as pd
from helpers import create_folder

logger = logging.getLogger(__name__)

path_out = create_folder('2_Wetherspoons', folder)
file_csv = f"{path_out}/Wetherspoons_items.csv"
pub_id = 70  # Example pub ID; replace with desired ID

START_URL = f'https://api.order.jdwetherspoon.com/api/v1/allergens/pubs/{pub_id}/food'



def _fetch_json(url: str, headers: dict, timeout: int = 20, retries: int = 2) -> Optional[dict]:
    """GET a URL and parse JSON safely with basic retries and diagnostics."""
    last_exc = None
    for attempt in range(1, retries + 2):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            status = resp.status_code
            ctype = resp.headers.get('Content-Type', '')
            if status >= 400:
                logger.warning("HTTP %s for %s", status, url)
                # Try to log a small snippet for diagnostics
                logger.debug("Response headers: %s", dict(resp.headers))
                snippet = (resp.text or '')[:500]
                logger.debug("Body snippet: %r", snippet)
                resp.raise_for_status()
            # Prefer JSON content type, but still try json() with guard
            try:
                return resp.json()
            except Exception as je:
                last_exc = je
                logger.warning("Failed to parse JSON (attempt %d/%d). Content-Type=%s", attempt, retries + 1, ctype)
                logger.debug("Raw body snippet: %r", (resp.text or '')[:500])
        except Exception as e:
            last_exc = e
            logger.warning("Request error on attempt %d/%d: %s", attempt, retries + 1, e)
    if last_exc:
        logger.error("Exhausted retries fetching %s: %s", url, last_exc)
    return None


def wetherspoonsCrawler(pub_id: int) -> pd.DataFrame:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'authorization': 'Bearer e3a3f707b51cf98660f536f7474dd4f1f3f0155d',
        'referer': 'https://allergens.jdwetherspoon.com/',
        'APIKey': 'YVB5QfeRKUK1+EGvXGjPgQA93reRTUJHsCuQSHR+=='
    }
    url = START_URL
    logger.info("Fetching Wetherspoons allergen data for pub_id=%s", pub_id)
    items = _fetch_json(url, headers=headers)
    file_json = f"{path_out}/pub_{pub_id}.json"
    if items is None:
        # Save raw body for debugging when possible (second best: note failure)
        with open(file_json.replace('.json', '_error.txt'), 'w') as f:
            f.write(f"Failed to fetch JSON from {url}. See logs for details.\n")
        return pd.DataFrame()

    # Persist the full JSON payload for reference
    try:
        with open(file_json, 'w') as f:
            json.dump(items, f)
    except Exception as e:
        logger.warning("Failed to write JSON to %s: %s", file_json, e)

    data_ = items.get('data') if isinstance(items, dict) else None
    if not data_:
        logger.warning("No 'data' field in API response for pub_id=%s", pub_id)
        return pd.DataFrame()
    return pd.DataFrame(data_)

if __name__ == '__main__':
    df = wetherspoonsCrawler(pub_id)
    if not df.empty:
        df.to_csv(file_csv, index=False)
        logger.info("Saved %d rows to %s", len(df), file_csv)
    else:
        logger.warning("No data returned; CSV not written")
