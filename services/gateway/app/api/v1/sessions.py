"""
Live interview session router (candidate, token-scoped).

Flow: start → (answer → next question)* → complete → assessment.
Stage machine mirrors app/interviewer.py budgets; the gateway owns session state
(persisted as Question/Response rows) and calls the AI service for each turn.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.gateway.app.ai_client import AIClient, get_ai_client
from services.gateway.app.api.v1.meeting import resolve_link
from services.gateway.app.db import get_db
from services.gateway.app.ws.manager import manager as ws_manager
from services.gateway.app.models import (
    Assessment,
    Candidate,
    Interview,
    Question,
    Resume,
    Response,
)
from services.gateway.app.schemas import AnswerResponse, SessionStartResponse
from services.gateway.app.security import create_access_token, get_current_claims

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Stage budgets: opening 1, experience 2, technical/project deep-dive 4, behavioral 2, closing 1.
# An "experience" stage explores professional background before the technical deep-dive (spec #3).
_STAGE_BUDGET = [("opening", 1), ("experience", 2), ("technical", 4), ("behavioral", 2), ("closing", 1)]
_TOTAL_ESTIMATED = sum(n for _, n in _STAGE_BUDGET)
# Stages where a weak answer should trigger a deeper follow-up rather than advancing.
_PROBE_STAGES = {"experience", "technical"}


def _stage_for(answered: int) -> tuple[str, bool]:
    """Given count of answered questions, return (current_stage, is_complete)."""
    cum = 0
    for stage, budget in _STAGE_BUDGET:
        cum += budget
        if answered < cum:
            return stage, False
    return "closing", True


async def _resume_context(db: AsyncSession, interview: Interview) -> str:
    if not interview.resume_id:
        return ""
    resume = await db.get(Resume, interview.resume_id)
    return (resume.extracted_text or "")[:4000] if resume else ""


def _plan(interview: Interview) -> dict:
    return interview.interview_plan if isinstance(interview.interview_plan, dict) else {}


async def _structured_context(db: AsyncSession, interview: Interview) -> str:
    """
    Prefer the cached structured context (built once at create time, spec #6/#17).
    Falls back to building it from parsed_profile, then to raw resume text.
    """
    plan = _plan(interview)
    if plan.get("context"):
        return plan["context"]
    if interview.resume_id:
        resume = await db.get(Resume, interview.resume_id)
        if resume and resume.parsed_profile:
            from app.interview_context import build_interview_context
            ctx = build_interview_context(resume.parsed_profile)
            if ctx:
                return ctx
    return ""


def _vocabulary(interview: Interview) -> list[str]:
    """Cached candidate vocabulary for STT boosting + transcript correction (spec #9)."""
    return _plan(interview).get("vocabulary", []) or []


async def _parsed_profile(db: AsyncSession, interview: Interview) -> dict:
    """The structured resume profile, for experience-level inference + context."""
    if not interview.resume_id:
        return {}
    resume = await db.get(Resume, interview.resume_id)
    return (resume.parsed_profile or {}) if resume else {}


def _covered_skills(interview: Interview, history: list[dict]) -> list[str]:
    """Resume skills already mentioned by the candidate so far (drives 'advance', spec #12)."""
    focus = _plan(interview).get("focus", []) or []
    if not focus:
        return []
    said = " ".join(m["content"] for m in history if m.get("role") == "user").lower()
    return [s for s in focus if s and s.lower() in said]


async def _history(db: AsyncSession, interview_id: str) -> list[dict]:
    qs = (await db.execute(
        select(Question).where(Question.interview_id == interview_id).order_by(Question.seq)
    )).scalars().all()
    rs = {r.question_id: r for r in (await db.execute(
        select(Response).where(Response.interview_id == interview_id)
    )).scalars().all()}
    history: list[dict] = []
    for q in qs:
        history.append({"role": "assistant", "content": q.text})
        if q.id in rs and rs[q.id].transcript_text:
            history.append({"role": "user", "content": rs[q.id].transcript_text})
    return history


def _require_candidate(interview_id: str, claims: dict = Depends(get_current_claims)) -> dict:
    if claims.get("scope") != "candidate" or claims.get("interview_id") != interview_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid session token for this interview")
    return claims


@router.post("/{token}/start", response_model=SessionStartResponse)
async def start_session(
    token: str, db: AsyncSession = Depends(get_db), ai: AIClient = Depends(get_ai_client),
) -> SessionStartResponse:
    link, interview = await resolve_link(db, token)
    if interview.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview already completed")

    # Reconnect: candidate already started this interview (e.g. closed tab and came back).
    # Issue a fresh session token and resume from the last unanswered question.
    last_q = await db.scalar(
        select(Question).where(Question.interview_id == interview.id).order_by(Question.seq.desc())
    )
    if last_q is not None:
        answered = await db.scalar(
            select(func.count()).select_from(Response).where(Response.interview_id == interview.id)
        )
        stage, _ = _stage_for(answered)
        session_token = create_access_token(
            interview.candidate_id, "candidate", scope="candidate",
            extra={"interview_id": interview.id},
        )
        await db.commit()
        return SessionStartResponse(
            session_token=session_token, interview_id=interview.id,
            question=last_q.text, stage=stage,
            question_index=last_q.seq, total_estimated=_TOTAL_ESTIMATED,
        )

    # Fresh start
    from app.interview_context import infer_experience_level
    link.consumed_at = datetime.now(timezone.utc)
    interview.status = "in_progress"
    interview.started_at = datetime.now(timezone.utc)

    # Cache the inferred experience level once for the whole interview (spec #4).
    profile = await _parsed_profile(db, interview)
    plan = dict(_plan(interview))
    plan["experience_level"] = infer_experience_level(profile)
    interview.interview_plan = plan

    turn = await ai.interview_turn({
        "history": [], "stage": "opening",
        "structured_context": await _structured_context(db, interview),
        "resume_context": await _resume_context(db, interview),
        "experience_level": plan["experience_level"],
        "turn_count": 0, "max_turns": _TOTAL_ESTIMATED,
    })
    opening_text = (turn["question"] or "").strip()
    if not opening_text:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI service returned an empty opening question")
    q = Question(interview_id=interview.id, seq=1, stage="opening", text=opening_text)
    db.add(q)
    await db.commit()

    session_token = create_access_token(
        interview.candidate_id, "candidate", scope="candidate",
        extra={"interview_id": interview.id},
    )
    return SessionStartResponse(
        session_token=session_token, interview_id=interview.id,
        question=opening_text, stage="opening", question_index=1,
        total_estimated=_TOTAL_ESTIMATED,
    )


@router.post("/{interview_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    interview_id: str,
    audio: UploadFile = File(...),
    claims: dict = Depends(_require_candidate),
    db: AsyncSession = Depends(get_db),
    ai: AIClient = Depends(get_ai_client),
) -> AnswerResponse:
    interview = await db.get(Interview, interview_id)
    if not interview or interview.status != "in_progress":
        raise HTTPException(status.HTTP_409_CONFLICT, "Interview is not active")

    # Latest unanswered question
    last_q = await db.scalar(
        select(Question).where(Question.interview_id == interview_id).order_by(Question.seq.desc())
    )

    # Transcribe with the candidate's vocabulary (boosting + context-aware correction).
    vocab = _vocabulary(interview)
    prior = await _history(db, interview_id)
    history_text = " ".join(m["content"] for m in prior)
    stt = await ai.transcribe_detailed(
        await audio.read(), vocabulary=vocab,
        history=history_text, job_description=interview.job_description or "",
    )
    transcript = stt.get("text", "") if isinstance(stt, dict) else str(stt)

    db.add(Response(question_id=last_q.id, interview_id=interview_id, transcript_text=transcript))
    await db.flush()

    # Emit transcript immediately so the UI can show it before LLM responds
    await ws_manager.emit(interview_id, "transcript", {
        "text": transcript, "corrections": stt.get("corrections", []) if isinstance(stt, dict) else [],
    })

    answered = await db.scalar(
        select(func.count()).select_from(Response).where(Response.interview_id == interview_id)
    )
    stage, complete = _stage_for(answered)

    if complete:
        await _finalize(db, ai, interview)
        await db.commit()
        await ws_manager.emit(interview_id, "complete", {"interview_id": interview_id})
        return AnswerResponse(transcript=transcript, question="", stage="closing",
                              question_index=answered, completed=True)

    # Adaptive follow-up decision (spec #12): probe deeper on a weak answer in a probe stage.
    from app.interview_context import (
        assess_answer_quality, build_memory_summary, empty_memory,
        infer_experience_level, update_memory,
    )
    quality = assess_answer_quality(last_q.text, transcript)
    intent, is_followup = "advance", False
    if stage in _PROBE_STAGES and quality["weak"] and not last_q.is_followup:
        intent, is_followup = "followup", True  # one follow-up per question, avoid loops

    history = await _history(db, interview_id)

    # Update + persist conversation memory (spec #8).
    plan = dict(_plan(interview))
    skills_now = [s for s in _covered_skills(interview, history) if s.lower() in transcript.lower()]
    memory = update_memory(
        plan.get("memory") or empty_memory(),
        question=last_q.text, answer=transcript, quality=quality, skills_in_answer=skills_now,
    )
    plan["memory"] = memory
    interview.interview_plan = plan  # reassign so SQLAlchemy persists the JSON change

    profile = await _parsed_profile(db, interview)
    turn = await ai.interview_turn({
        "history": history, "stage": stage,
        "structured_context": await _structured_context(db, interview),
        "resume_context": await _resume_context(db, interview),
        "covered_skills": _covered_skills(interview, history),
        "last_answer_quality": quality,
        "intent": intent,
        "experience_level": plan.get("experience_level") or infer_experience_level(profile),
        "memory_summary": build_memory_summary(memory),
        "turn_count": answered, "max_turns": _TOTAL_ESTIMATED,
    })
    question_text = (turn["question"] or "").strip()
    if not question_text:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "AI service returned an empty question")
    next_seq = (last_q.seq or 0) + 1
    db.add(Question(interview_id=interview_id, seq=next_seq, stage=stage,
                    text=question_text, is_followup=is_followup))
    await db.commit()

    # Emit next question so the UI updates before the HTTP response resolves
    await ws_manager.emit(interview_id, "question", {
        "text": question_text, "stage": stage, "question_index": next_seq,
        "is_followup": is_followup,
    })
    return AnswerResponse(transcript=transcript, question=question_text, stage=stage,
                          question_index=next_seq, completed=False)


@router.post("/{interview_id}/end")
async def end_session(
    interview_id: str, claims: dict = Depends(_require_candidate),
    db: AsyncSession = Depends(get_db), ai: AIClient = Depends(get_ai_client),
) -> dict:
    interview = await db.get(Interview, interview_id)
    if not interview:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    if interview.status != "completed":
        await _finalize(db, ai, interview)
        await db.commit()
    return {"status": "completed", "interview_id": interview_id}


async def _finalize(db: AsyncSession, ai: AIClient, interview: Interview) -> None:
    """Build transcript, run AI assessment, persist, mark completed."""
    history = await _history(db, interview.id)
    transcript = "\n".join(
        f"{'Interviewer' if m['role'] == 'assistant' else 'Candidate'}: {m['content']}"
        for m in history
    )
    # Prefer the structured context for resume-consistency checking (spec #13).
    resume_ctx = await _structured_context(db, interview) or await _resume_context(db, interview)
    a = await ai.assess(transcript, resume_ctx)

    db.add(Assessment(
        interview_id=interview.id,
        overall_score=a.get("overall_score"), technical_score=a.get("technical_score"),
        communication_score=a.get("communication_score"), culture_fit_score=a.get("culture_fit_score"),
        confidence_score=a.get("confidence_score"),
        resume_alignment=a.get("resume_consistency_score"),
        strengths=a.get("strengths", []), weaknesses=a.get("weaknesses", []),
        red_flags=a.get("red_flags", []), recommendation=a.get("recommendation", "pending"),
        summary=a.get("summary", ""),
        # Persist the full assessment (evidence + extra dimensions) as JSON for the detail API.
        raw_output=json.dumps(a),
    ))
    interview.status = "completed"
    interview.completed_at = datetime.now(timezone.utc)
    if interview.started_at:
        from services.gateway.app.timeutil import aware_utc
        interview.duration_sec = int(
            (interview.completed_at - aware_utc(interview.started_at)).total_seconds()
        )
