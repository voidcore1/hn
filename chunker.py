from fetcher import format_timestamp

# ---------------- FLATTEN COMMENT TREES FOR LLM ---------------- #

def flatten_tree(node, lines=None):
    """
    Convert a comment tree into indented text lines with metadata.

    Each comment includes:
    - [depth=N] tag so the LLM understands reply nesting
    - Author name
    - Timestamp (when the comment was posted)
    - The comment text, indented to visually match depth

    This preserves the "who is replying to whom" structure that blind
    token-count splitting would destroy (as noted in the task spec).
    """
    if lines is None:
        lines = []

    indent = "  " * node["depth"]
    depth_tag = f"[depth={node['depth']}]"
    time_str = format_timestamp(node["time"])

    lines.append(f"{indent}{depth_tag} Author: {node['author']} | {time_str}")
    lines.append(f"{indent}{node['text']}")
    lines.append("")  # blank line between comments for readability

    for child in node["children"]:
        flatten_tree(child, lines)

    return lines


def flatten_tree_as_string(tree):
    """Flatten a single comment tree into one string."""
    lines = flatten_tree(tree)
    return "\n".join(lines)


def count_comments_in_tree(node):
    """Count total comments in a tree (used for audit reporting)."""
    count = 1
    for child in node["children"]:
        count += count_comments_in_tree(child)
    return count


# ---------------- SMART CHUNKING (Stage 2) ---------------- #

def build_thread_document_chunked(story_title, story_url, trees, char_budget):
    """
    Build a text document from comment trees for one story, respecting
    a character budget WITHOUT cutting mid-comment.

    Strategy: add complete top-level comment threads one at a time until
    the budget is exhausted. If a thread doesn't fit in the remaining
    space, skip it entirely rather than slicing it.

    Why this matters: blind character slicing (e.g. text[:15000]) can cut
    a comment in half, destroying context for the LLM. By chunking at
    thread boundaries, every comment the LLM sees is complete and its
    reply chain is intact.
    """
    header = f"Story: {story_title}\n"
    if story_url:
        header += f"URL: {story_url}\n"
    header += "\nComments:\n\n"

    doc = header
    remaining = char_budget - len(header)

    for tree in trees:
        chunk = flatten_tree_as_string(tree) + "\n"
        if len(chunk) <= remaining:
            doc += chunk
            remaining -= len(chunk)
        else:
            # thread doesn't fit — skip rather than cut mid-comment
            continue

    return doc


def trim_document_to_budget(document, char_budget):
    """
    Trim an already-built document to a character budget, cutting at
    section boundaries (story separators '---') rather than mid-comment.

    Used by the chat module to fit raw thread data into the context
    window without destroying comment integrity.
    """
    if len(document) <= char_budget:
        return document

    sections = document.split("\n---\n\n")
    trimmed = ""

    for section in sections:
        candidate = section + "\n---\n\n"
        if len(trimmed) + len(candidate) <= char_budget:
            trimmed += candidate
        else:
            break

    return trimmed if trimmed else sections[0][:char_budget]
