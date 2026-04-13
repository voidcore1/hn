from fetcher import format_timestamp


def flatten_tree(node, lines=None):
    """Turn a comment tree into indented lines with metadata for the LLM."""
    if lines is None:
        lines = []

    indent = "  " * node["depth"]
    time_str = format_timestamp(node["time"])

    lines.append(f"{indent}[depth={node['depth']}] Author: {node['author']} | {time_str}")
    lines.append(f"{indent}{node['text']}")
    lines.append("")

    for child in node["children"]:
        flatten_tree(child, lines)

    return lines


def flatten_tree_as_string(tree):
    return "\n".join(flatten_tree(tree))


def count_comments_in_tree(node):
    count = 1
    for child in node["children"]:
        count += count_comments_in_tree(child)
    return count


def build_thread_document_chunked(story_title, story_url, trees, char_budget):
    """
    Build text from comment trees, but instead of slicing at a raw char
    limit (which can cut a comment in half), we add whole threads until
    the budget runs out. If a thread doesn't fit, skip it entirely.
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
            continue

    return doc


def trim_document_to_budget(document, char_budget):
    """Trim at story boundaries (--- separators) instead of mid-comment."""
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
