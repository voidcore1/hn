# Stage 1: Data Audit

Query: "SQLite in production"

---

## What I pulled

5 stories, all with comments. Here's the breakdown:

| Story | Points | Top threads fetched | Comments in trees |
|---|---|---|---|
| Things that surprised me while running SQLite in production | 232 | 14 | 95 |
| SQLite in Production: Lessons from Running a Store on a Single File | 208 | 15 | 98 |
| How (and why) to run SQLite in production | 155 | 15 | 68 |
| Ask HN: SQLite in Production? | 111 | 15 | 45 |
| SQLite in production with WAL | 83 | 5 | 24 |

- Total comments attempted: 341
- Valid comments used: 330
- Deleted/dead: 7
- Empty (no text body): 0
- Max thread depth seen: 6
- Final document size: 13,254 chars

---

## Quality

Pretty clean. 330 out of 341 comments made it through — the 7 that didn't were deleted or dead (moderated away by HN, nothing I can do about those). Zero empty comments, which means every node that survived had actual text in it.

The WAL story had noticeably fewer comments (24 vs 95-98 for the top two), which makes sense — it's a more specific thread so the discussion was shallower. Still useful for the WAL-specific context.

---

## What I threw away and why

**Deleted/dead comments (7):** HN marks these in the API response. There's no text to recover, so I skip the node. I still recurse into their children though, because replies sometimes have substance even when the parent was removed.

**Comments deeper than depth 5:** Capped recursion at 5 levels. Beyond that you're usually in tangential flamewars or meta-arguments that don't add signal about the actual topic. Didn't hit this much — max depth in this run was 6, meaning a handful of threads went one level past the cap.

**Threads that didn't fit the character budget:** Each story gets an equal share of the 15k char total budget. If a thread is too large to fit in the remaining space for that story, I skip it entirely rather than cutting it mid-comment. A clean subset is more useful to the LLM than a corrupted full set.

---

## What I couldn't get

The HN Firebase API doesn't expose per-comment upvote counts — only stories have a `score` field. So I can't rank individual comments by votes. I worked around this by sorting stories by points and relying on HN's default `kids` ordering, which roughly maps to community ranking anyway. It's documented in the fetch output and in the digest prompt so the LLM knows not to treat comment order as authoritative.
