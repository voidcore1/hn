# hn-thread-intel

CLI tool that pulls Hacker News discussions on a topic, generates a useful technical digest, and lets you chat with the data afterward.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/hn-thread-intel.git
cd hn-thread-intel
pip install -r requirements.txt
```

Get a free Groq API key from https://console.groq.com/keys, then:

```bash
cp .env.example .env
```

Open `.env` and paste your key there.

## Usage

```bash
python main.py
```

It'll ask for a search topic — press Enter for the default ("SQLite in production"). Fetching takes a couple minutes because of API rate limiting. After that you get the data audit, a structured digest, and then a chat where you can ask follow-ups.

## Project Structure

- `main.py` — entry point, runs everything in order
- `config.py` — loads env vars, sets up Groq client
- `fetcher.py` — talks to the HN APIs, builds comment trees
- `chunker.py` — flattens trees into text, handles chunking
- `digest.py` — builds the prompt and calls the LLM
- `chat.py` — interactive follow-up chat

## Design Decisions

### Stage 1: Data Acquisition

I fetch the top 5 stories (sorted by points) and up to 15 top-level comment threads per story, recursing to depth 5. Everything gets saved to `hn_data.json` so I don't have to re-fetch every time during development.

What gets thrown out:
- **Deleted/dead comments** — moderated away, no useful content
- **Empty comments** — some have no text body, just children. I skip the node but still recurse into kids since replies might have substance
- **Threads deeper than 5 levels** — usually tangential flamewars at that point

One thing I couldn't get: the HN Firebase API doesn't give you upvote counts on individual comments (only stories have a `score` field). I work around this by sorting stories by points and relying on HN's default ordering of the `kids` array, which roughly maps to community ranking.

### Stage 2: Chunking

The big problem with HN data is that comments are trees — if you just slice at a character count, you break comments in half and lose the "who's replying to whom" context. My approach:

- Each comment gets flattened with a `[depth=N]` tag, author, and timestamp
- When building the document for the LLM, I add **complete threads** until the character budget is hit. If a thread doesn't fit, I skip it entirely instead of cutting it
- Total budget (15k chars) is split across stories so one big thread doesn't eat everything

The tradeoff is some threads get dropped, but a clean subset beats a corrupted full set.

### Stage 3: Digest

The LLM prompt asks for five specific sections: consensus points, controversial takes, pros/cons from real experiences, alternatives mentioned, and notable insights. I explain the data format in the prompt (what depth tags mean, the upvote limitation) so the model knows what it's working with.

Model fallback: if the primary model (llama-3.3-70b) is rate-limited on Groq's free tier, it tries mixtral-8x7b, then llama-3.1-8b.

### Stage 4: Chat

After the digest, you can ask follow-up questions like "what did they say about write performance?" The system is grounded — the model only answers from the actual HN data, and if something isn't there, it says so.

Context management: I use a sliding window of the last 6 messages. The digest + a trimmed chunk of raw thread data are always in the system prompt. I went with sliding window over summarization because it's simpler and avoids compounding errors from summarizing summaries. For a short research chat, 6 turns is plenty.

### Stage 5: Edge Cases

Handled through the system prompt:
- **No answer in data** — model is told to say "not covered in the threads"
- **Contradictory opinions** — model presents both sides
- **False consensus manipulation** — model pushes back and cites actual data
- **Old chat references** — sliding window keeps recent turns; older ones drop off (acknowledged tradeoff)

## Known Limitations

- Fetching is slow (~2-5 min) because of rate limiting. Progress dots show it's working.
- No per-comment upvotes (API limitation, documented above).
- Chat forgets messages older than 6 turns.
- Fixed character budgets tuned for Groq's context limits — could use more with bigger models.
- One query per run.

## Tech Stack

Python 3, Groq API (free tier), HN Algolia + Firebase APIs, BeautifulSoup, python-dotenv
