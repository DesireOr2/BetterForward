"""Tests for Telegram text splitting helpers."""

from src.utils.message_split import MAX_CAPTION_LENGTH, split_caption, split_html_text


def test_short_text_is_not_split():
    assert split_html_text("hello") == ["hello"]
    assert split_html_text(None) == [""]


def test_long_text_splits_under_limit():
    text = ("line\n" * 900) + ("word " * 200)
    chunks = split_html_text(text, limit=4096)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "".join(chunks) == text


def test_split_balances_html_tags_across_chunks():
    prefix = "a" * 4000
    text = prefix + "<b>bold text that continues</b>" + ("c" * 100)
    chunks = split_html_text(text, limit=4096)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 4096 for chunk in chunks)
    # Opening tag must not be severed mid-token.
    assert not any(
        ("<" in chunk and ">" not in chunk[chunk.rfind("<"):])
        for chunk in chunks
    )
    # If a chunk opens <b>, it should close it (or the next chunk reopens).
    assert any("</b>" in chunk for chunk in chunks)


def test_hard_cut_when_no_safe_boundary():
    text = "x" * 5000
    chunks = split_html_text(text, limit=4096)
    assert chunks == ["x" * 4096, "x" * (5000 - 4096)]


def test_split_caption_returns_followups():
    text = "c" * (MAX_CAPTION_LENGTH + 50)
    caption, extras = split_caption(text)
    assert len(caption) <= MAX_CAPTION_LENGTH
    assert extras
    assert caption + "".join(extras) == text
