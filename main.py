import sys
import json
import asyncio
import aiohttp
from datetime import datetime, timezone

from fetcher import search_hn_stories_async, fetch_json, fetch_comment_tree_async, stats
from chunker import build_thread_document_chunked, count_comments_in_tree
from digest import generate_digest
from chat import chat_loop

def save_fetched_data(query, stories_meta, all_trees, filepath="hn_data.json"):
    """Dump everything to JSON so we don't re-fetch while developing."""
    payload = {
        "query": query,
        "fetched_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stats": dict(stats),
        "stories": stories_meta,
        "comment_trees": all_trees,
    }
    with open(filepath, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"💾 Data saved to {filepath}")

def print_audit(query, story_summaries):
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

    print(f"\nNote: HN Firebase API doesn't expose per-comment upvotes.")
    print(f"We use story-level points to prioritize and HN's default sort order.")

async def main_async():
    query = input(
        "🔍 Enter search topic (or press Enter for 'SQLite in production'): "
    ).strip()
    if not query:
        query = "SQLite in production"

    print(f"\n📡 Searching HN for: \"{query}\"\n")

    async with aiohttp.ClientSession() as session:
        stories = await search_hn_stories_async(session, query, num_stories=5)
        if not stories:
            print("❌ No stories found.")
            sys.exit(1)

        print(f"Found {len(stories)} stories. Fetching comments...\n")

        per_story_budget = 15000 // len(stories)

        all_documents = ""
        story_summaries = []
        all_trees_serializable = []

        semaphore = asyncio.Semaphore(50)  # Concurrent connection limit

        for i, story in enumerate(stories):
            title = story.get("title", "Untitled")
            story_id = story.get("objectID")
            points = story.get("points", 0)
            url = story.get("url") or ""
            num_comments = story.get("num_comments", 0)

            print(f"  [{i+1}] \"{title}\" ({points} pts, {num_comments} comments)")
            stats["stories_fetched"] += 1

            item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            item_data = await fetch_json(session, item_url)

            if not item_data or "kids" not in item_data:
                print(f"      ⏭️  No comments, skipping.")
                continue

            stats["stories_with_comments"] += 1

            top_comment_ids = item_data["kids"][:15]
            print(f"      Fetching comments ", end="")
            sys.stdout.flush()

            # Fetch top level threads concurrently
            tasks = [
                fetch_comment_tree_async(session, cid, max_depth=5, semaphore=semaphore)
                for cid in top_comment_ids
            ]
            fetched_trees = await asyncio.gather(*tasks)
            
            trees = [t for t in fetched_trees if t is not None]
            print()

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

        # save raw data
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

        # audit
        print_audit(query, story_summaries)

        if not all_documents.strip():
            print("\n❌ No comment data to generate digest from.")
            sys.exit(1)

        print(f"\nDocument size: {len(all_documents)} chars (chunked at thread boundaries)")
        print("\n🤖 Generating digest...\n")

        digest = generate_digest(all_documents)

        print("\n" + "=" * 50)
        print("📋 FINAL DIGEST")
        print("=" * 50)
        print(digest)
        print("\n" + "=" * 50)

        # chat
        chat_loop(digest, all_documents)

def main():
    # Setup asyncio execution
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main_async())

if __name__ == "__main__":
    main()