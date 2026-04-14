import html
import sys
import asyncio
import aiohttp
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# --- stats for the data audit ---

stats = {
    "total_comments": 0,
    "valid_comments": 0,
    "deleted_comments": 0,
    "empty_comments": 0,
    "max_depth": 0,
    "stories_fetched": 0,
    "stories_with_comments": 0,
}

async def fetch_json(session, url):
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.json()
    except Exception as e:
        # print(f"❌ Failed to fetch {url}: {e}") # Suppress to keep output clean
        return None

async def search_hn_stories_async(session, query, num_stories=5):
    """Search HN Algolia API asynchronously, return top stories sorted by points."""
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story"
    res = await fetch_json(session, url)
    if res and "hits" in res:
        hits = res["hits"]
        hits.sort(key=lambda x: x.get("points", 0), reverse=True)
        return hits[:num_stories]
    return []

def clean_text(raw_text):
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    if "<" not in text:
        return text.strip()
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ").strip()

def format_timestamp(unix_ts):
    if not unix_ts:
        return "Unknown date"
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

async def fetch_comment_node(session, comment_id, depth, max_depth, semaphore):
    """
    Recursively grab a comment + its replies using an async session and semaphore.
    """
    stats["total_comments"] += 1
    stats["max_depth"] = max(stats["max_depth"], depth)

    if depth > max_depth:
        return None

    url = f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
    
    # Throttle concurrency to avoid hammering the Firebase API
    async with semaphore:
        data = await fetch_json(session, url)

    if not data:
        stats["deleted_comments"] += 1
        return None

    if data.get("deleted") or data.get("dead"):
        stats["deleted_comments"] += 1
        return None

    text = clean_text(data.get("text", ""))
    if not text:
        stats["empty_comments"] += 1
        return None

    stats["valid_comments"] += 1
    sys.stdout.write(".")
    sys.stdout.flush()

    node = {
        "id": comment_id,
        "author": data.get("by", "Unknown"),
        "depth": depth,
        "text": text,
        "time": data.get("time", 0),
        "children": [],
    }

    if "kids" in data and data["kids"]:
        # Fetch replies concurrently
        tasks = [
            fetch_comment_node(session, kid, depth + 1, max_depth, semaphore)
            for kid in data["kids"]
        ]
        children = await asyncio.gather(*tasks)
        node["children"] = [c for c in children if c is not None]

    return node

async def fetch_comment_tree_async(session, comment_id, max_depth=5, semaphore=None):
    if semaphore is None:
        semaphore = asyncio.Semaphore(50)  # Limit to 50 concurrent requests
    return await fetch_comment_node(session, comment_id, 0, max_depth, semaphore)