"""Helpers for splitting Telegram messages that exceed API length limits."""

from telebot.util import MAX_MESSAGE_LENGTH


def split_html_text(text: str | None, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split HTML/text into chunks that fit Telegram's message length limit.

    Prefers breaking on newlines, sentence ends, or spaces (same priority as
    telebot.util.smart_split). Cut points that fall inside an HTML tag are moved
    to before the opening ``<``. Oversized indivisible segments are hard-cut.
    """
    if text is None:
        return [""]
    if limit <= 0:
        raise ValueError("limit must be positive")
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break

        cut = _find_safe_cut(remaining, limit)
        if cut <= 0:
            cut = limit
        parts.append(remaining[:cut])
        remaining = remaining[cut:]

    return [part for part in parts if part != ""] or [""]


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
