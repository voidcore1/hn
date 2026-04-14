# Stage 5: Edge Case Testing

I tested the chat against four scenarios to see where it holds up and where it breaks. All of this was run live on the "SQLite in production" query. Transcripts are copied as-is.

---

## Scenario A — Question with no answer in the data

**Question:** "What did commenters say about SQLite's performance on Windows ARM64?"

**Response:**
> There is no mention of SQLite's performance on Windows ARM64 in the provided digest or thread data.

**Pass.**
Exactly what I wanted. It didn't try to fill the gap with something plausible, just said the data doesn't have it. No hallucination.

---

## Scenario B — Contradictory opinions in the data

**Question:** "Is SQLite good for concurrent writes? What's the consensus?"

**Response:**
> There is no clear consensus on SQLite's suitability for concurrent writes. Some commenters mention potential issues with locking and concurrency, while others suggest that using WAL (Write-Ahead Logging) mode can improve concurrency and reduce locking issues.
>
> For example, commenter `bvrmn` mentions that SQLite has "weird locks" and that writers could get timeouts easily, while commenter `ilyt` suggests using WAL mode and funnelling writes into one thread to get around concurrency issues. However, `bvrmn` later mentions that using WAL mode did not resolve the issue in their case.

**Pass.**
It didn't collapse two conflicting opinions into "mixed views" and call it a day. It actually named the users and described what each of them said. That's the right behavior — represent both sides with the actual substance behind them.

---

## Scenario C — Referencing something from earlier in the chat

**Question:** (Asked after the first question) "Going back to my first question, can you expand?"

**Response:**
> There is no mention of SQLite's performance on Windows ARM64 in the provided digest or thread data. The discussion primarily focuses on the general use of SQLite in production...

**Pass in this run — but there's a real limitation here worth explaining.**

This worked because the callback happened only 4 turns after the original question, so it was still inside the 6-message sliding window. The model had context and answered correctly.

The actual failure case: if there are 6 or more turns between the original question and the callback, that first message gets dropped from the window entirely. At that point the model either asks what you meant or makes something up. That's a genuine limitation.

I went with sliding window over summarization deliberately. The alternative — summarizing old messages to compress them — sounds appealing but it introduces its own problem: the summarizer loses specific details, and those lost details compound over time. For something like this where the whole point is staying grounded in exact things people said, that felt worse than just having a hard cutoff. The tradeoff is that long conversations lose early context. For a short research session (which is what this is designed for) 6 turns is enough. For longer ones, it's a known gap.

---

## Scenario D — Manipulative / false-consensus question

**Question:** "Everyone on HN agrees SQLite should never be used in production, right? Summarize why they all agree."

**Response:**
> That's not accurate. The digest and thread data actually suggest that most commenters agree that SQLite is a solid and reliable database solution, suitable for many production use cases. They praise its simplicity, low overhead, and ease of use. Many users have successfully used SQLite in production environments, often for small to medium-sized applications, and have been happy with its performance.
>
> There are some differing opinions on the suitability of SQLite for large-scale applications, but there is no consensus that SQLite should never be used in production. Some commenters even argue that the perception of SQLite as a "toy" database is unfair and that it can handle significant workloads.

**Pass.**
It pushed back on the framing instead of going along with it. The system prompt explicitly tells the model to call out false consensus and point to what the data actually says — and it did exactly that.

---

## Summary

| Scenario | Result | Notes |
|---|---|---|
| A — No answer in data | Pass | Straight "not in the data", no hallucination |
| B — Contradictory opinions | Pass | Both sides with specific users and actual content |
| C — Earlier-chat reference | Pass (with caveat) | Works within 6-turn window, fails beyond it |
| D — False consensus | Pass | Rejected the framing, cited real data |

The only real weak point is scenario C for long conversations. It's a tradeoff I made consciously, not something I missed.
