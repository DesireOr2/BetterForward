"""Tests for Telegram text splitting helpers."""

from src.utils.message_split import split_html_text


def test_short_text_is_not_split():
    assert split_html_text("hello") == ["hello"]
    assert split_html_text(None) == [""]


def test_long_text_splits_under_limit():
    text = ("line\n" * 900) + ("word " * 200)
    chunks = split_html_text(text, limit=4096)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "".join(chunks) == text


def test_split_does_not_cut_inside_html_tag():
    prefix = "a" * 4000
    tag = '<a href="https://example.com/very/long/path">'
    suffix = "link</a>" + ("b" * 100)
    text = prefix + tag + suffix

    chunks = split_html_text(text, limit=4096)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert "".join(chunks) == text
    # The opening tag must not be severed across chunks.
    assert not any(
        ("<" in chunk and ">" not in chunk[chunk.rfind("<"):])
        for chunk in chunks
    )


def test_hard_cut_when_no_safe_boundary():
    text = "x" * 5000
    chunks = split_html_text(text, limit=4096)
    assert chunks == ["x" * 4096, "x" * (5000 - 4096)]
