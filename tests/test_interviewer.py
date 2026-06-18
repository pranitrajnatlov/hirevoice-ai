"""Tests for Phase 2 interview state machine."""

from __future__ import annotations

import pytest
from app.interviewer import (
    InterviewSession,
    InterviewStage,
    InterviewState,
    _STAGE_ORDER,
    _STAGE_TURNS,
)


class TestInterviewStages:
    def test_initial_stage_is_opening(self):
        s = InterviewSession()
        assert s.stage == InterviewStage.OPENING

    def test_advance_from_opening_after_one_turn(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        s.add_turn("assistant", "Hello!")
        s.add_turn("user", "Hi there")
        advanced = s.advance_stage()
        assert advanced is True
        assert s.stage == InterviewStage.TECHNICAL

    def test_stage_does_not_advance_before_quota(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        # No user turns yet
        advanced = s.advance_stage()
        assert advanced is False
        assert s.stage == InterviewStage.OPENING

    def test_stage_order_is_complete(self):
        assert _STAGE_ORDER == [
            InterviewStage.OPENING,
            InterviewStage.TECHNICAL,
            InterviewStage.BEHAVIORAL,
            InterviewStage.CLOSING,
        ]

    def test_stage_turns_budget_covers_all_stages(self):
        for stage in InterviewStage:
            assert stage in _STAGE_TURNS, f"Missing budget for {stage}"
            assert _STAGE_TURNS[stage] >= 1

    def test_full_stage_progression(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        expected_progression = [
            (InterviewStage.OPENING, InterviewStage.TECHNICAL),
            (InterviewStage.TECHNICAL, InterviewStage.BEHAVIORAL),
            (InterviewStage.BEHAVIORAL, InterviewStage.CLOSING),
        ]
        for current_stage, next_stage in expected_progression:
            s.stage = current_stage
            s.stage_turn_count = 0
            budget = _STAGE_TURNS[current_stage]
            for _ in range(budget):
                s.add_turn("user", "answer")
            s.advance_stage()
            assert s.stage == next_stage, f"Expected {next_stage} after {current_stage}"

    def test_no_advance_past_closing(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        s.stage = InterviewStage.CLOSING
        s.stage_turn_count = _STAGE_TURNS[InterviewStage.CLOSING]
        s.advance_stage()
        assert s.stage == InterviewStage.CLOSING

    def test_turn_count_increments_only_for_user(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        s.add_turn("assistant", "Question?")
        assert s.turn_count == 0
        s.add_turn("user", "Answer.")
        assert s.turn_count == 1

    def test_is_complete_at_max_turns(self):
        from app.config import MAX_INTERVIEW_TURNS
        s = InterviewSession(state=InterviewState.ACTIVE)
        for _ in range(MAX_INTERVIEW_TURNS):
            s.add_turn("user", "answer")
        assert s.is_complete() is True

    def test_is_complete_at_closing_stage(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        s.stage = InterviewStage.CLOSING
        s.add_turn("user", "Thanks.")
        assert s.is_complete() is True

    def test_is_complete_on_wrap_phrase(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        s.add_turn("assistant", "That wraps up my questions for today. Thank you for your time — we will be in touch soon.")
        assert s.is_complete() is True

    def test_stage_turn_count_resets_on_advance(self):
        s = InterviewSession(state=InterviewState.ACTIVE)
        budget = _STAGE_TURNS[InterviewStage.OPENING]
        for _ in range(budget):
            s.add_turn("user", "answer")
        s.advance_stage()
        assert s.stage_turn_count == 0


class TestResumeIntegration:
    def test_load_txt_resume(self, tmp_path):
        from app.resume_integration import load_resume_from_file
        f = tmp_path / "resume.txt"
        f.write_text("Jane Smith\nPython developer\n3 years experience")
        text = load_resume_from_file(f)
        assert "Jane Smith" in text
        assert "Python" in text

    def test_missing_file_raises(self):
        from app.resume_integration import load_resume_from_file
        with pytest.raises(FileNotFoundError):
            load_resume_from_file("/nonexistent/resume.pdf")

    def test_no_resume_ai_returns_empty(self):
        from app.resume_integration import load_resume_from_resume_ai
        result = load_resume_from_resume_ai()
        assert result == ""
