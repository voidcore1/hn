from config import client, MODELS

# ---------------- STAGE 3: DIGEST GENERATION ---------------- #

def generate_digest(all_documents):
    """
    Send combined thread documents to an LLM and get a structured digest.

    The prompt instructs the model to:
    - Understand the comment format (depth tags, timestamps, authors)
    - Extract signal from noise (consensus, debates, real experiences)
    - Produce specific, structured output sections

    Falls back through multiple models if the primary one is unavailable
    or rate-limited (common with free-tier Groq).
    """
    prompt = f"""You are a technical research assistant analyzing Hacker News discussions.

The data below contains comments from multiple HN threads on the same topic.
Comments are indented to show reply structure:
- [depth=0] = top-level comment
- [depth=1] = reply to depth=0, and so on.
Each comment includes the author name and timestamp.

Note: The HN API does not expose per-comment upvote counts. Comments appear
in HN's default order (roughly by upvotes), so earlier comments in each
thread tend to be higher-signal.

Your job: extract the real signal from these discussions. Be specific and
reference what actual users said (paraphrase, don't quote verbatim).

Structure your response as:

## Key Consensus Points
What do most commenters agree on?

## Controversial / Debated Takes
Where do opinions split? What are both sides?

## Pros & Cons (from real user experiences)
Practical advantages and disadvantages people actually reported.

## Tools & Alternatives Mentioned
Other technologies or approaches people recommended.

## Notable Insights
Any particularly sharp or unique points worth highlighting.

---

THREAD DATA:
{all_documents}
"""

    for model in MODELS:
        try:
            print(f"  Trying model: {model}")

            res = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )

            print(f"  ✅ Success with {model}")
            return res.choices[0].message.content

        except Exception as e:
            print(f"  ⚠️ {model} failed: {e}")

    return "❌ All models failed to generate digest."
