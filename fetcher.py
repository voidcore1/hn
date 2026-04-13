import requests
import html
import sys
import time
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


def search_hn_stories(query, num_stories=5):
    """Search HN Algolia API, return top stories sorted by points."""
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        hits = res.json().get("hits", [])
        hits.sort(key=lambda x: x.get("points", 0), reverse=True)
        return hits[:num_stories]
    except Exception as e:
        print(f"❌ Failed to fetch stories: {e}")
        return []


def get_hn_item(item_id):
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Failed to fetch item {item_id}: {e}")
        return None


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


def fetch_comment_tree(comment_id, depth=0, max_depth=5):
    """
    Recursively grab a comment + its replies.
    
    Caps at max_depth=5 to avoid going too deep into tangential arguments.
    
    Re: upvotes — the Firebase API doesn't expose per-comment scores,
    only stories have that. So we rely on HN's default kids ordering
    which is roughly by votes anyway.
    """
    stats["total_comments"] += 1
    stats["max_depth"] = max(stats["max_depth"], depth)

    if depth > max_depth:
        return None

    data = get_hn_item(comment_id)
    time.sleep(0.15)  # don't hammer the API

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

    for kid in data.get("kids", []):
        child = fetch_comment_tree(kid, depth + 1, max_depth)
        if child:
            node["children"].append(child)

    return node
