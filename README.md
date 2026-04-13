# HN Thread Intelligence Tool

A command-line tool that fetches Hacker News discussions on any topic, generates a structured technical digest, and lets you chat with the data to explore specific points.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/hn-digest.git
cd hn-digest

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up your API key
cp .env.example .env
# Edit .env and paste your Groq API key (free at https://console.groq.com/keys)

# 4. Run
python main.py
```

You'll be prompted for a search topic. Press Enter to use the default ("SQLite in production").

## Project Structure

```
hn-digest/
├── main.py            # Entry point — orchestrates all stages
├── config.py          # Loads .env, initializes Groq client
├── fetcher.py         # HN API calls, comment tree building, stats
├── chunker.py         # Flatten trees, smart chunking, document building
├── digest.py          # LLM prompt engineering and digest generation
├── chat.py            # Conversational follow-up (Stage 4)
├── requirements.txt
├── .env.example       # Template for API key
├── .gitignore
└── README.md
```

## How It Works

### Stage 1: Data Acquisition & Audit

**What we fetch:**
- Top 5 stories for the query, sorted by points (community signal).
- Up to 15 top-level comment threads per story, recursed to depth 5.

**What we discard and why:**
- **Deleted/dead comments**: These are moderated out by HN — no useful content.
- **Empty comments**: Some comments have no text body (just children). We skip the node but still recurse into children, since replies may have substance.
- **Deep nesting beyond depth 5**: Deeply nested replies are usually tangential arguments. Capping depth keeps the data focused.

**What we store:**
- All fetched data (stories, full comment trees with metadata) is saved to `hn_data.json` for auditability and to avoid re-fetching during development.

**Upvote limitation:**
The HN Firebase API (`/v0/item/{id}.json`) does not return a score field for individual comments — only stories have `score`. This is a known API limitation. We compensate by:
1. Sorting stories by points to prioritize high-signal threads.
2. Relying on HN's default `kids` array ordering, which roughly corresponds to community ranking.

The audit prints a per-story breakdown showing points, threads fetched, and comment counts, plus totals for valid/deleted/empty comments.

### Stage 2: Chunking & Structure

**The problem:** HN comments are a tree structure (replies nested under replies). Naive token-count splitting would cut comments in half and destroy the "who is replying to whom" context that makes discussions meaningful.

**Our strategy — thread-boundary chunking:**
1. Each comment is flattened with explicit metadata: `[depth=N] Author: name | timestamp`.
2. Indentation visually mirrors reply depth.
3. When building the document for the LLM, we add **complete top-level threads** one at a time until the character budget is reached. If a thread doesn't fit in the remaining space, it's skipped entirely — never sliced.
4. The total budget (15,000 chars) is split evenly across stories so no single story dominates.

This means every comment the LLM sees is complete, and every reply chain is intact. The tradeoff is that some threads may be dropped if they're too large, but a complete subset is better than a corrupted full set.

**What we preserve per comment:**
- **Thread depth**: `[depth=0]` = top-level, `[depth=1]` = reply, etc. Lets the LLM understand argument structure.
- **Timestamps**: Formatted as `YYYY-MM-DD HH:MM UTC`. Useful for the LLM to weigh recency.
- **Author names**: Allows the LLM to attribute viewpoints and notice when the same person makes multiple points.

### Stage 3: Generating the Digest

The LLM prompt:
- Explains the data format (what depth tags and timestamps mean).
- Notes the upvote limitation so the model doesn't hallucinate popularity signals.
- Requests five specific output sections: Key Consensus, Controversial Takes, Pros & Cons, Tools & Alternatives, and Notable Insights.
- Instructs the model to paraphrase rather than quote, and to reference specific users.

We use a model fallback chain (llama-3.3-70b → mixtral-8x7b → llama-3.1-8b) because Groq's free tier can rate-limit any single model. The fallback ensures the tool doesn't fail just because one model is busy.

### Stage 4: Conversational Chat (Brownie Points)

After the digest is printed, the user enters an interactive chat loop where they can ask follow-up questions like "What did they say about write performance?" or "Which commenters had actual production experience?"

**Context management — sliding window:**
- The system prompt always includes the full digest + a trimmed portion of raw thread data (8,000 chars, cut at story boundaries — not mid-comment).
- Chat history keeps the last 6 messages (user + assistant turns). Older messages are dropped FIFO.

**Why sliding window over summarization?**
- Simpler to implement and debug — no risk of summarization errors compounding.
- For a focused research conversation, 6 turns of context covers most use cases.
- Predictable token usage: the context size never surprises us.
- The tradeoff: if the user references something from 10 turns ago, it may be lost. This is documented and acceptable for a research chat tool.

**Grounding rules in the system prompt:**
- The model is told to answer ONLY from the provided data.
- If the answer isn't in the data, it must say so (prevents hallucination).
- If opinions are contradictory, it must present both sides.
- If a question tries to manufacture false consensus, the model pushes back.

### Stage 5: Edge Cases (Brownie Points)

These are handled via the system prompt and chat design:

| Scenario | How it's handled |
|---|---|
| No answer in data | System prompt instructs model to say "this isn't covered in the fetched threads" |
| Contradictory opinions | System prompt requires presenting both sides fairly |
| Reference to old chat message | Sliding window keeps last 6 messages; older ones are dropped (acknowledged tradeoff) |
| Manipulative false consensus | System prompt tells model to cite actual data diversity and push back |

## Known Limitations & Tradeoffs

- **Fetching speed**: With rate limiting (0.15s per API call), fetching 5 stories × 15 threads can take 2–5 minutes depending on thread sizes. Progress dots are printed so the user knows it's working.
- **No per-comment upvotes**: API limitation. We use story-level points and HN's default ordering as a proxy.
- **Fixed char budgets**: The 15,000 char digest budget and 8,000 char chat budget are tuned for Groq's context limits on the models we use. Larger models could use more.
- **Sliding window memory loss**: Chat turns older than 6 messages are forgotten. For longer research sessions, a summarization approach would be better but adds complexity.
- **Single query**: The tool processes one search query per run. Comparing multiple topics would require running it twice.

## Demo

The demo recording shows the tool running with the query "SQLite in production", including the data audit, generated digest, and a few chat follow-up questions.

## Tech Stack

- **Python 3** — standard library + minimal dependencies
- **Groq API** — fast LLM inference (free tier, llama-3.3-70b primary model)
- **HN Algolia API** — story search
- **HN Firebase API** — comment/item fetching
- **BeautifulSoup** — HTML cleaning for comment text
- **python-dotenv** — environment variable management
