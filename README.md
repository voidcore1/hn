# HN Thread Intelligence Tool

A CLI tool that searches Hacker News threads on any topic, pulls the comments, generates a structured digest of what the community actually thinks, and then lets you chat with the data to dig deeper.

I built this because HN threads are genuinely useful for making tech decisions, but reading through hundreds of comments to find the good stuff is painful. This automates that.
## Demo
Click to play the video

[![Watch the demo](https://img.youtube.com/vi/pEvVFG8CKtw/maxresdefault.jpg)](https://youtu.be/pEvVFG8CKtw)

## Setup

```bash
git clone https://github.com/voidcore1/hn.git
cd hn
pip install -r requirements.txt
```

You'll need a Groq API key (free) from https://console.groq.com/keys

```bash
cp .env.example .env
```

Open `.env` and put your key in there. This file is gitignored so it won't get pushed.

## Running it

```bash
python main.py
```

It asks for a topic, hit Enter to go with "SQLite in production". 
Fetching comments is incredibly fast. The tool uses asynchronous concurrent requests (aiohttp + asyncio) with a semaphore to pull entire comment trees in seconds without hitting Firebase API rate limits. You'll see a quick flash of progress dots while it works.
After fetching, it prints a data audit, then the digest, then drops you into a chat where you can ask follow-ups.

## Files

- `main.py` — runs everything, prints the audit, calls digest and chat
- `config.py` — loads the API key from `.env`, sets up the Groq client
- `fetcher.py` — handles all the HN API calls and builds comment trees
- `chunker.py` — turns comment trees into text the LLM can read
- `digest.py` — the prompt and LLM call for generating the digest
- `chat.py` — follow-up chat loop after the digest

## How I approached each stage

### Stage 1 : Data fetching and audit

I pull the top 5 stories for the query from the Algolia API, sorted by points so the most upvoted (and usually most discussed) stories come first. For each story I grab up to 15 top-level comment threads and recurse into replies up to depth 5.

I throw away three kinds of data:
- **Deleted/dead comments** — HN already moderated these out, nothing useful there
- **Empty text comments** — some comments are just containers for replies with no text of their own. I skip the node but still check its children since the replies might be good
- **Anything past depth 5** — in my testing, threads that deep are almost always off-topic arguments

Everything gets dumped to `hn_data.json` too, partly so I don't have to re-fetch every time while developing, and partly as proof of what data I actually pulled.

One limitation I ran into: the HN Firebase API (`/v0/item/{id}.json`) doesn't give you upvote counts on individual comments. Only stories have a `score` field. So I can't directly rank comments by popularity. My workaround is sorting stories by points (so we look at high-signal threads first) and relying on the order of the `kids` array, which HN sorts roughly by votes already.

Note on performance: Originally, fetching this data took 2-5 minutes because of synchronous blocking requests. I refactored the data acquisition layer to use aiohttp and asyncio. By using an async semaphore capped at 50 concurrent connections, I can fetch the entire nested comment structure concurrently without triggering HN's rate limits.

### Stage 2 : Chunking and structure

This was the trickiest part. HN comments are a tree — replies nested under replies. If you just do `text[:15000]` you'll chop a comment in half and the LLM loses all sense of who's replying to whom.

What I do instead: I flatten each comment with a `[depth=N]` tag, the author name, and a timestamp. Then when building the document for the LLM, I add **complete top-level threads** one by one until I hit the character budget. If a thread doesn't fit in the remaining space, I skip it entirely rather than slicing it.

The budget (15k chars) is split evenly across stories so one massive thread doesn't eat everything. The tradeoff is that some threads get dropped, but I'd rather give the LLM 80% of the data in clean form than 100% of it broken.

I also use the same boundary-aware trimming in the chat phase — when I need to fit raw thread data into the chat context, I cut at story separators (`---`) not in the middle of comments.

### Stage 3 : Digest

The prompt tells the LLM what the data format means (depth tags = reply nesting, timestamps, etc.) and asks for five sections: consensus points, controversial takes, pros/cons from real experiences, alternatives mentioned, and notable insights.

I also tell the model upfront that there are no per-comment upvote counts and that earlier comments tend to be higher signal. Without this context the model might try to infer popularity from things that don't actually indicate it.

For the LLM calls I use a fallback chain — try llama-3.3-70b first, fall back to mixtral, then llama-3.1-8b. Groq's free tier rate-limits individual models pretty aggressively, so having fallbacks means the tool doesn't just die randomly.

### Stage 4 : Chat

After the digest you can ask questions like "what did people say about write performance?" or "who had actual production experience with this?" The model answers only from the HN data — it's told explicitly not to make stuff up, and to say so if something isn't covered.

For context management I went with a sliding window: keep the last 6 messages, drop older ones. The full digest + a trimmed chunk of raw data stay in the system prompt so the model always has the source material.

I considered summarizing old messages instead of dropping them, but that adds complexity and can compound errors (summaries of summaries get lossy fast). For a focused research chat, 6 turns of history covers most use cases. If someone references something from way earlier in the chat it might be lost — that's a known tradeoff I'm okay with for the simplicity gain.

### Stage 5 : Edge cases

These are handled through the system prompt rules:
- If the data doesn't have an answer, the model says so instead of making something up
- If commenters disagree, the model presents both sides instead of picking one
- If someone asks a leading question trying to manufacture a consensus that doesn't exist, the model is told to push back and point to the actual spread of opinions

The one gap is very old chat references (past the 6-message window) — those fall off. I'd fix this with message summarization in a future version but it's not worth the added complexity right now.

## Limitations

- **No comment upvotes** — API doesn't expose them. Documented above.
- **Chat memory is limited** — 6 messages. Old stuff gets dropped.
- **Character budgets are fixed** — tuned for Groq's context window. Bigger models could handle more data.

## Demo link

https://youtu.be/pEvVFG8CKtw

## Tech

Python 3, aiohttp / asyncio, Groq (free tier), HN Algolia + Firebase APIs, BeautifulSoup, python-dotenv
