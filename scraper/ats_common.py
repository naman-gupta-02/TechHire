import html
import re


def html_to_text(raw: str) -> str:
    """Convert an HTML (or HTML-entity-encoded) job description into plain
    text with newlines preserved, so parse.py's section/bullet detection
    (written for JSearch's already-plain-text descriptions) still works
    on ATS APIs that return rich-text HTML instead."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r'<li[^>]*>', '\n- ', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|h[1-6])>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
