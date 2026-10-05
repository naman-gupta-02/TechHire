import pytest

from api import _extract_json


def test_plain_json():
    assert _extract_json('{"score": 80}') == {"score": 80}


def test_fenced_json_block():
    raw = '```json\n{"score": 80, "matched_skills": ["python"]}\n```'
    assert _extract_json(raw) == {"score": 80, "matched_skills": ["python"]}


def test_fenced_block_without_language_tag():
    raw = '```\n{"score": 42}\n```'
    assert _extract_json(raw) == {"score": 42}


def test_json_embedded_in_prose():
    raw = 'Sure, here is the analysis:\n{"score": 55, "top_suggestions": ["Add metrics"]}\nHope that helps!'
    assert _extract_json(raw) == {"score": 55, "top_suggestions": ["Add metrics"]}


def test_unparseable_text_raises():
    with pytest.raises(ValueError):
        _extract_json("not json at all, no braces here")
