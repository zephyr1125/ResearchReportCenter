from app.highlighter import apply_numeric_highlights, apply_phrase_highlights, parse_highlight_candidates


def test_parse_highlight_candidates_from_json() -> None:
    assert parse_highlight_candidates('["关键句", "第二句"]') == ["关键句", "第二句"]


def test_apply_numeric_highlights() -> None:
    result = apply_numeric_highlights("2026年财政赤字维持在GDP的4%，规模达11.89万亿元人民币。")
    assert 'rrc-highlight-data' in result
    assert '11.89万亿元人民币' in result
    assert result.count('rrc-highlight-data') >= 2


def test_apply_phrase_highlights() -> None:
    result = apply_phrase_highlights("促进消费是今年的首要政策重点。", ["首要政策重点"])
    assert 'rrc-highlight-insight' in result


def test_apply_numeric_highlights_skip_inside_insight_mark() -> None:
    text = '<mark class="rrc-highlight-insight">2026年财政赤字维持在GDP的4%</mark>，规模达11.89万亿元人民币。'
    result = apply_numeric_highlights(text)
    assert result.count('rrc-highlight-insight') == 1
    assert result.count('rrc-highlight-data') == 1
    assert '<mark class="rrc-highlight-insight"><mark class="rrc-highlight-data">' not in result
