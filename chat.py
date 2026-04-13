from config import client, MODELS
from chunker import trim_document_to_budget

MAX_HISTORY = 6       # keep last N messages in chat (sliding window)
RAW_CONTEXT_BUDGET = 8000


def chat_loop(digest, all_documents):
    """
    Follow-up chat grounded in the HN data.
    Uses a sliding window (last 6 messages) to manage context.
    """
    print("\n💬 Chat mode — ask follow-up questions about the threads.")
    print("   Type 'quit' or 'exit' to end.\n")

    # trim raw data at story boundaries, not mid-comment
    raw_context = trim_document_to_budget(all_documents, RAW_CONTEXT_BUDGET)

    system_prompt = f"""You are a research assistant. The user read a digest of Hacker News
discussions and wants to ask follow-up questions.

Rules:
- Answer ONLY using the digest and thread data below.
- If the answer isn't in the data, say so — don't make stuff up.
- If opinions contradict each other, present both sides.
- If a question tries to push a false consensus, point out what the data
  actually says.

DIGEST:
{digest}

RAW THREAD DATA:
{raw_context}
"""

    chat_history = []

    while True:
        try:
            user_input = input("\n🧑 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Ending chat.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("👋 Ending chat.")
            break

        chat_history.append({"role": "user", "content": user_input})

        # drop old messages if we're past the window
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
            print("❌ All models failed. Try again.")
