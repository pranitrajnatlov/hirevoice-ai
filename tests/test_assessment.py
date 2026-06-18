"""Tests for Phase 3 assessment engine."""

from __future__ import annotations

import json
import pytest
from app.assessment import (
    AssessmentResult,
    _coerce_list,
    _coerce_recommendation,
    _coerce_score,
    _extract_json,
    _parse_assessment,
    _strip_fences,
)


VALID_JSON = json.dumps({
    "candidate_name": "Jane Smith",
    "role_assessed": "Backend Engineer",
    "overall_score": 8,
    "technical_score": 7,
    "communication_score": 8,
    "culture_fit_score": 7,
    "strengths": ["Strong Python", "Clear communicator"],
    "weaknesses": ["Limited distributed systems experience"],
    "technical_highlights": ["Designed async pipeline"],
    "red_flags": [],
    "recommendation": "hire",
    "summary": "Strong candidate with solid Python fundamentals.",
    "suggested_next_steps": ["Technical deep-dive with team lead"],
})


class TestStripFences:
    def test_removes_json_fence(self):
        raw = "```json\n{}\n```"
        assert _strip_fences(raw) == "{}"

    def test_removes_plain_fence(self):
        raw = "```\n{}\n```"
        assert _strip_fences(raw) == "{}"

    def test_noop_on_plain_json(self):
        assert _strip_fences('{"a": 1}') == '{"a": 1}'

    def test_strips_whitespace(self):
        assert _strip_fences("  {}  ") == "{}"


class TestExtractJson:
    def test_extracts_clean_json(self):
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_extracts_json_from_prose(self):
        text = 'Here is the result: {"score": 9} Thank you.'
        assert _extract_json(text) == '{"score": 9}'

    def test_returns_text_if_no_braces(self):
        assert _extract_json("no json here") == "no json here"


class TestCoercions:
    def test_score_clamps_low(self):
        assert _coerce_score(0) == 1

    def test_score_clamps_high(self):
        assert _coerce_score(11) == 10

    def test_score_valid(self):
        assert _coerce_score(7) == 7

    def test_score_string(self):
        assert _coerce_score("8") == 8

    def test_score_invalid_returns_default(self):
        assert _coerce_score("bad", default=5) == 5

    def test_recommendation_valid(self):
        assert _coerce_recommendation("strong_hire") == "strong_hire"

    def test_recommendation_normalizes_spaces(self):
        assert _coerce_recommendation("strong hire") == "strong_hire"

    def test_recommendation_unknown_returns_maybe(self):
        assert _coerce_recommendation("excellent") == "maybe"

    def test_list_from_list(self):
        assert _coerce_list(["a", "b"]) == ["a", "b"]

    def test_list_from_string(self):
        assert _coerce_list("single item") == ["single item"]

    def test_list_from_none(self):
        assert _coerce_list(None) == []


class TestParseAssessment:
    def test_parses_valid_json(self):
        result = _parse_assessment(VALID_JSON)
        assert not result.parse_error
        assert result.overall_score == 8
        assert result.recommendation == "hire"
        assert result.candidate_name == "Jane Smith"
        assert len(result.strengths) == 2

    def test_parses_fenced_json(self):
        raw = f"```json\n{VALID_JSON}\n```"
        result = _parse_assessment(raw)
        assert not result.parse_error
        assert result.overall_score == 8

    def test_handles_broken_json(self):
        result = _parse_assessment("{not valid json}")
        assert result.parse_error
        assert result.raw_output == "{not valid json}"

    def test_coerces_out_of_range_score(self):
        data = json.loads(VALID_JSON)
        data["overall_score"] = 15
        result = _parse_assessment(json.dumps(data))
        assert result.overall_score == 10

    def test_coerces_bad_recommendation(self):
        data = json.loads(VALID_JSON)
        data["recommendation"] = "definitely hire"
        result = _parse_assessment(json.dumps(data))
        assert result.recommendation == "maybe"

    def test_empty_lists_ok(self):
        data = json.loads(VALID_JSON)
        data["strengths"] = []
        data["red_flags"] = []
        result = _parse_assessment(json.dumps(data))
        assert result.strengths == []
        assert result.red_flags == []


class TestAssessmentResult:
    def test_is_valid_for_good_result(self):
        result = _parse_assessment(VALID_JSON)
        assert result.is_valid()

    def test_is_invalid_for_parse_error(self):
        result = AssessmentResult(parse_error=True)
        assert not result.is_valid()

    def test_is_invalid_for_zero_score(self):
        result = AssessmentResult(overall_score=0, recommendation="hire")
        assert not result.is_valid()

    def test_to_display_contains_recommendation(self):
        result = _parse_assessment(VALID_JSON)
        display = result.to_display()
        assert "HIRE" in display
        assert "8/10" in display

    def test_to_display_parse_error_shows_raw(self):
        result = AssessmentResult(parse_error=True, raw_output="raw LLM output here")
        display = result.to_display()
        assert "raw LLM output here" in display

    def test_to_dict_is_serializable(self):
        result = _parse_assessment(VALID_JSON)
        d = result.to_dict()
        assert json.dumps(d)  # no TypeError
        assert d["overall_score"] == 8


class TestSessionStore:
    def test_save_and_load(self, tmp_path, monkeypatch):
        import app.session_store as ss
        monkeypatch.setattr(ss, "SESSIONS_DIR", tmp_path / "sessions")
        result = _parse_assessment(VALID_JSON)
        path = ss.save_session(
            session_id="test_123",
            transcript="Interviewer: Hi\nCandidate: Hello",
            assessment=result,
            turn_count=3,
            final_stage="closing",
        )
        assert path.exists()
        loaded = ss.load_session("test_123")
        assert loaded["session_id"] == "test_123"
        assert loaded["turn_count"] == 3
        assert loaded["assessment"]["overall_score"] == 8

    def test_list_sessions_empty(self, tmp_path, monkeypatch):
        import app.session_store as ss
        monkeypatch.setattr(ss, "SESSIONS_DIR", tmp_path / "sessions")
        assert ss.list_sessions() == []

    def test_load_missing_raises(self, tmp_path, monkeypatch):
        import app.session_store as ss
        monkeypatch.setattr(ss, "SESSIONS_DIR", tmp_path / "sessions")
        with pytest.raises(FileNotFoundError):
            ss.load_session("nonexistent")
