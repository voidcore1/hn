import sys
import json
from datetime import datetime

from fetcher import (
    search_hn_stories,
    get_hn_item,
    fetch_comment_tree,
    stats,
)
from chunker import (
    build_thread_document_chunked,
    count_comments_in_tree,
)
from digest import generate_digest
from chat import chat_loop


# ---------------- DATA PERSISTENCE ---------------- #

def save_fetched_data(query, stories_meta, all_trees, filepath="hn_data.json"):
    """
    Save all fetched data to a JSON file.

    Purposes:
      1. Avoids re-fetching hundreds of comments during development/testing.
      2. Serves as an auditable artifact — shows exactly what was pulled
         from the API, what was kept, and what was discarded.
      3. Could be loaded by a future version to skip the fetch step.
    """
    payload = {
        "query": query,
        "fetched_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "stats": dict(stats),
        "stories": stories_meta,
        "comment_trees": all_trees,
    }

    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"💾 Data saved to {filepath}")


def print_audit(query, story_summaries):
    """Print the Stage 1 data audit to the console."""
    print("\n" + "=" * 50)
    print("📊 DATA AUDIT")
    print("=" * 50)
    print(f"Query: \"{query}\"")
    print(f"Stories fetched: {stats['stories_fetched']}")
    print(f"Stories with comments: {stats['stories_with_comments']}")
    print(f"Total comments attempted: {stats['total_comments']}")
    print(f"Valid comments used: {stats['valid_comments']}")
    print(f"Deleted/dead comments: {stats['deleted_comments']}")
    print(f"Empty comments (no text): {stats['empty_comments']}")
    print(f"Max thread depth seen: {stats['max_depth']}")

    print("\nPer-story breakdown:")
    for s in story_summaries:
        print(f"  • \"{s['title']}\" — {s['points']} pts, "
              f"{s['threads_fetched']} top threads, "
              f"{s['total_in_trees']} comments in trees")

    print(f"\nNote: HN Firebase API does not expose per-comment upvote counts.")
    print(f"Story-level points are used to prioritize high-signal threads.")
    print(f"Comment ordering relies on HN's default sort (roughly by votes).")


# ---------------- MAIN ---------------- #

def main():
    # --- user input ---
    query = input(
        "🔍 Enter search topic (or press Enter for 'SQLite in production'): "
    ).strip()
    if not query:
        query = "SQLite in production"

    print(f"\n📡 Searching HN for: \"{query}\"\n")

    # --- fetch top stories ---
    stories = search_hn_stories(query, num_stories=5)

    if not stories:
        print("❌ No stories found.")
        sys.exit(1)

    print(f"Found {len(stories)} stories. Fetching comments...\n")

    # char budget per story for smart chunking (total ~15k across all stories)
    per_story_budget = 15000 // len(stories)

    all_documents = ""
    story_summaries = []
    all_trees_serializable = []

    for i, story in enumerate(stories):
        title = story.get("title", "Untitled")
        story_id = story.get("objectID")
        points = story.get("points", 0)
        url = story.get("url") or ""  # None for Ask HN / Show HN posts
        num_comments = story.get("num_comments", 0)

        print(f"  [{i+1}] \"{title}\" ({points} pts, {num_comments} comments)")

        stats["stories_fetched"] += 1

        item_data = get_hn_item(story_id)

        if not item_data or "kids" not in item_data:
            print(f"      ⏭️  No comments, skipping.")
            continue

        stats["stories_with_comments"] += 1

        # fetch top-level comment threads (up to 15 per story)
        trees = []
        top_comment_ids = item_data["kids"][:15]

        print(f"      Fetching comments ", end="")
        for cid in top_comment_ids:
            tree = fetch_comment_tree(cid)
            if tree:
                trees.append(tree)
        print()  # newline after progress dots

        if trees:
            doc = build_thread_document_chunked(title, url, trees, per_story_budget)
            all_documents += doc + "\n---\n\n"

            all_trees_serializable.append({
                "story_title": title,
                "story_url": url,
                "story_points": points,
                "trees": trees,
            })

            story_summaries.append({
                "title": title,
                "points": points,
                "threads_fetched": len(trees),
                "total_in_trees": sum(count_comments_in_tree(t) for t in trees),
            })

    # --- save raw data to JSON ---
    stories_meta = [
        {
            "title": s.get("title"),
            "objectID": s.get("objectID"),
            "points": s.get("points", 0),
            "url": s.get("url") or "",
            "num_comments": s.get("num_comments", 0),
        }
        for s in stories
    ]

    save_fetched_data(query, stories_meta, all_trees_serializable)

    # --- print audit ---
    print_audit(query, story_summaries)

    # --- generate digest ---
    if not all_documents.strip():
        print("\n❌ No comment data to generate digest from.")
        sys.exit(1)

    print(f"\nTotal document size: {len(all_documents)} chars "
          f"(budget: 15000 chars, chunked at thread boundaries)")
    print("\n🤖 Generating digest...\n")

    digest = generate_digest(all_documents)

    print("\n" + "=" * 50)
    print("📋 FINAL DIGEST")
    print("=" * 50)
    print(digest)
    print("\n" + "=" * 50)

    # --- start chat ---
    chat_loop(digest, all_documents)


if __name__ == "__main__":
    main()
