import requests
import html
import sys
import time
from datetime import datetime
from bs4 import BeautifulSoup

# ---------------- GLOBAL STATS (Stage 1 Audit) ---------------- #

stats = {
    "total_comments": 0,
    "valid_comments": 0,
    "deleted_comments": 0,
    "empty_comments": 0,
    "max_depth": 0,
    "stories_fetched": 0,
    "stories_with_comments": 0,
}


# ---------------- API CALLS ---------------- #

def search_hn_stories(query, num_stories=5):
    """
    Search HN via Algolia API for stories matching the query.
    Returns top results sorted by points (highest first) so we
    prioritize threads the community found most valuable.
    """
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        hits = data.get("hits", [])

        # sort by points — most upvoted stories first = higher signal
        hits.sort(key=lambda x: x.get("points", 0), reverse=True)

        return hits[:num_stories]
    except Exception as e:
        print(f"❌ Failed to fetch stories: {e}")
        return []


def get_hn_item(item_id):
    """Fetch a single HN item (story or comment) by ID from Firebase API."""
    url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Failed to fetch item {item_id}: {e}")
        return None


# ---------------- TEXT CLEANING ---------------- #

def clean_text(raw_text):
    """Strip HTML tags and unescape HTML entities from comment text."""
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    soup = BeautifulSoup(text, "html.parser")
    return soup.get_text(separator=" ").strip()


def format_timestamp(unix_ts):
    """Convert unix timestamp to a human-readable UTC date string."""
    if not unix_ts:
        return "Unknown date"
    return datetime.utcfromtimestamp(unix_ts).strftime("%Y-%m-%d %H:%M UTC")


# ---------------- COMMENT TREE BUILDING (Stage 2) ---------------- #

def fetch_comment_tree(comment_id, depth=0, max_depth=5):
    """
    Recursively fetch a comment and all its children from the HN API.

    Preserves per-comment: author, depth (reply nesting), timestamp, text.
    max_depth caps recursion to avoid runaway fetching on deeply nested
    flamewars that add noise rather than signal.

    NOTE on upvotes: The HN Firebase API does not expose a score/upvote
    field for individual comments — only stories have 'score'. This is
    an API limitation, not an oversight. We compensate by:
      1. Using story-level points to prioritize which stories to fetch.
      2. Relying on HN's default child ordering (kids array), which
         roughly corresponds to vote ranking.
    """
    stats["total_comments"] += 1
    stats["max_depth"] = max(stats["max_depth"], depth)

    if depth > max_depth:
        return None

    data = get_hn_item(comment_id)
    time.sleep(0.15)  # rate-limit to be polite to the Firebase API

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

    # progress dot so the user knows fetching is happening
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
