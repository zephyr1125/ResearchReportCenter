from app.translator import _split_text_for_volcengine


def test_split_text_for_volcengine_short_text() -> None:
    assert _split_text_for_volcengine("hello", limit=10) == ["hello"]


def test_split_text_for_volcengine_long_text() -> None:
    chunks = _split_text_for_volcengine("a" * 11, limit=5)
    assert chunks == ["aaaaa", "aaaaa", "a"]


def test_split_text_for_volcengine_keep_lines_when_possible() -> None:
    text = "line1\nline2\nline3"
    chunks = _split_text_for_volcengine(text, limit=11)
    assert chunks == ["line1\nline2", "line3"]
