from config import client, MODELS


def generate_digest(all_documents):
    prompt = f"""You are a technical research assistant analyzing Hacker News discussions.

The data below has comments from multiple HN threads on the same topic.
Comments are indented to show reply structure:
- [depth=0] = top-level comment
- [depth=1] = reply to depth=0, etc.
Each comment has author name and timestamp.

The HN API doesn't expose per-comment upvotes. Comments are in HN's default
order (roughly by votes), so earlier ones tend to be higher signal.

Extract the real signal from these discussions. Be specific, reference what
users actually said (paraphrase, don't copy verbatim).

Structure your response as:

## Key Consensus Points
What do most commenters agree on?

## Controversial / Debated Takes
Where do opinions split? Both sides.

## Pros & Cons (from real user experiences)
Practical advantages and disadvantages people reported.

## Tools & Alternatives Mentioned
Other tech or approaches people recommended.

## Notable Insights
Any sharp or unique points worth calling out.

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
