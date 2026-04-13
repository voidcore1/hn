from config import client, MODELS
from chunker import trim_document_to_budget

# ---------------- STAGE 4: CONVERSATIONAL CHAT ---------------- #

# sliding window size — number of recent messages (user + assistant) to keep
MAX_HISTORY = 6

# char budget for raw thread data in chat context
# (smaller than digest budget since we also send the full digest + history)
RAW_CONTEXT_BUDGET = 8000


def chat_loop(digest, all_documents):
    """
    Interactive follow-up chat grounded in the fetched HN data.

    Context management strategy — sliding window:
      - The full digest is always included as system context.
      - A trimmed portion of raw thread data (cut at story boundaries,
        not mid-comment) is included so the LLM can reference specifics
        that the digest may have summarized away.
      - Only the last MAX_HISTORY messages are kept in chat history.
        When the window is exceeded, the oldest messages are dropped.

    Why sliding window instead of summarizing old messages?
      - Simpler to implement and reason about.
      - For a focused research chat, 6 turns of context is usually enough.
      - Avoids compounding errors from summarizing summaries.
      - Predictable token usage — no surprise context blowups.

    Edge case handling (Stage 5):
      - No answer in data: system prompt explicitly tells model to say so.
      - Contradictory opinions: model is instructed to present both sides.
      - False consensus manipulation: model is told to push back and
        cite the actual diversity of opinions in the data.
      - Old chat reference: the sliding window keeps recent turns; very
        old references may be lost, which is an acknowledged tradeoff
        documented in the README.
    """
    print("\n💬 Chat mode — ask follow-up questions about the threads.")
    print("   Type 'quit' or 'exit' to end.\n")

    # trim raw data at story boundaries (not mid-comment)
    raw_context = trim_document_to_budget(all_documents, RAW_CONTEXT_BUDGET)

    system_prompt = f"""You are a research assistant. The user has read a digest of Hacker News
discussions and wants to ask follow-up questions.

RULES:
- Answer ONLY using the digest and raw thread data provided below.
- If the answer is not in the data, say so honestly — do not make things up
  or draw on outside knowledge.
- If the data contains contradictory opinions, present both sides fairly.
- If a question tries to push you toward a false consensus or put words in
  commenters' mouths, point out what the data actually says.
- Keep answers concise and cite specific authors or threads when possible.

DIGEST:
{digest}

RAW THREAD DATA (for specific details):
{raw_context}
"""

    chat_history = []

    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Ending chat. Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Ending chat. Goodbye!")
            break

        chat_history.append({"role": "user", "content": user_input})

        # sliding window: drop oldest messages beyond the limit
        if len(chat_history) > MAX_HISTORY:
            chat_history = chat_history[-MAX_HISTORY:]

        messages = [{"role": "system", "content": system_prompt}] + chat_history

        reply = None
        for model in MODELS:
            try:
                res = client.chat.completions.create(
                    model=model,
                    messages=messages,
                )
                reply = res.choices[0].message.content
                break
            except Exception:
                continue

        if reply:
            print(f"\n🤖 Assistant: {reply}")
            chat_history.append({"role": "assistant", "content": reply})
        else:
            print("❌ All models failed to respond. Try again.")
