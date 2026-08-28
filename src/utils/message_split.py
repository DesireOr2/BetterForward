"""Helpers for splitting Telegram messages that exceed API length limits."""

import re

from telebot.util import MAX_MESSAGE_LENGTH

MAX_CAPTION_LENGTH = 1024

_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)(?:\s[^>]*)?>")
_SELF_CLOSING = {"br", "hr", "img"}


def split_html_text(text: str | None, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split HTML/text into chunks that fit Telegram's message length limit.

    Prefers breaking on newlines, sentence ends, or spaces. Cut points inside an
    HTML tag move before ``<``. Open tags are closed at chunk ends and reopened
    at the next chunk so ``parse_mode=HTML`` stays valid.

    Chunk length always accounts for the reopen prefix and closing suffix so the
    final string never exceeds ``limit``.
    """
    if text is None:
        return [""]
    if limit <= 0:
        raise ValueError("limit must be positive")
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    open_tags: list[tuple[str, str]] = []

    while remaining:
        prefix = _reopen_tags(open_tags)

        trial_stack = _track_tags(remaining, open_tags)
        trial_close = _close_tags(trial_stack)
        if len(prefix) + len(remaining) + len(trial_close) <= limit:
            parts.append(prefix + remaining + trial_close)
            break

        max_body = limit - len(prefix)
        if max_body <= 0:
            # Pathological reopen prefix; hard-cut raw remainder.
            parts.append(remaining[:limit])
            remaining = remaining[limit:]
            open_tags = _track_tags(parts[-1], [])
            continue

        cut = min(len(remaining), max_body)
        if cut < len(remaining):
            safe = _find_safe_cut(remaining, cut)
            if safe > 0:
                cut = safe

        fitted = False
        while cut > 0:
            body = remaining[:cut]
            stack = _track_tags(body, open_tags)
            close = _close_tags(stack)
            if len(prefix) + len(body) + len(close) <= limit:
                parts.append(prefix + body + close)
                remaining = remaining[cut:]
                open_tags = stack
                fitted = True
                break

            overflow = len(prefix) + len(body) + len(close) - limit
            new_budget = cut - max(overflow, 1)
            if new_budget <= 0:
                break
            safe = _find_safe_cut(remaining, new_budget)
            cut = safe if safe > 0 else new_budget

        if not fitted:
            # Cannot balance tags within limit; hard-cut raw body.
            hard = min(len(remaining), max(1, max_body))
            parts.append(prefix + remaining[:hard])
            remaining = remaining[hard:]
            open_tags = _track_tags(parts[-1], [])

    return [part for part in parts if part != ""] or [""]


def split_caption(text: str | None, limit: int = MAX_CAPTION_LENGTH) -> tuple[str | None, list[str]]:
    """Split a caption into a primary caption and follow-up text chunks.

    Returns (caption_for_media, extra_text_chunks). Extra chunks use the message
    length limit and HTML-safe splitting.
    """
    if text is None:
        return None, []
    if len(text) <= limit:
        return text, []

    chunks = split_html_text(text, limit=limit)
    caption = chunks[0]
    extras: list[str] = []
    for chunk in chunks[1:]:
        extras.extend(split_html_text(chunk, limit=MAX_MESSAGE_LENGTH))
    return caption, extras


def _find_safe_cut(text: str, limit: int) -> int:
    """Return a cut index in ``(0, limit]`` that avoids splitting HTML tags."""
    window = text[:limit]

    for separator in ("\n", ". ", " "):
        cut = _last_separator_cut(window, separator)
        if cut is not None and not _is_inside_tag(text, cut):
            return cut

    if _is_inside_tag(text, limit):
        tag_start = window.rfind("<")
        if tag_start > 0:
            return tag_start

    return limit


def _last_separator_cut(window: str, separator: str) -> int | None:
    index = window.rfind(separator)
    if index <= 0:
        return None
    return index + len(separator)


def _is_inside_tag(text: str, pos: int) -> bool:
    """Return True when ``pos`` lies between ``<`` and the matching ``>``."""
    last_open = text.rfind("<", 0, pos)
    if last_open < 0:
        return False
    last_close = text.rfind(">", 0, pos)
    return last_open > last_close


def _track_tags(fragment: str, open_tags: list[tuple[str, str]]) -> list[tuple[str, str]]:
    stack = list(open_tags)
    for match in _TAG_RE.finditer(fragment):
        raw = match.group(0)
        name = match.group(1).lower()
        if name in _SELF_CLOSING:
            continue
        if raw.startswith("</"):
            for idx in range(len(stack) - 1, -1, -1):
                if stack[idx][0] == name:
                    del stack[idx]
                    break
        else:
            stack.append((name, raw))
    return stack


def _close_tags(open_tags: list[tuple[str, str]]) -> str:
    return "".join(f"</{name}>" for name, _ in reversed(open_tags))


def _reopen_tags(open_tags: list[tuple[str, str]]) -> str:
    return "".join(raw for _, raw in open_tags)
