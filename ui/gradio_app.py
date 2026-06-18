"""
Gradio UI for HireVoice AI — "Interview Room" experience.

Design:
- Live stage stepper (Opening -> Technical -> Behavioral -> Closing)
- Chat transcript as the centerpiece (gr.Chatbot, message bubbles)
- Compact mic dock for recording + submitting answers
- Collapsible Setup panel (resume + backend settings)
- Assessment scorecard that reveals when the interview ends
"""

from __future__ import annotations

import html
import logging
import traceback
from typing import Optional

import gradio as gr

from app.config import (
    AUTO_UNLOAD_MODELS,
    LLM_MODEL,
    MAX_RAM_USAGE_GB,
    STT_MODEL_SIZE,
    ensure_dirs,
    get_mode,
    get_openai_key,
    set_mode,
    set_openai_key,
)
from app.interviewer import Interviewer
from app.llm import check_ollama_available, check_openai_available
from utils.resource_manager import (
    cleanup_all,
    get_resource_manager,
    list_ollama_running_models,
)

logger = logging.getLogger(__name__)

_interviewer: Optional[Interviewer] = None

STAGES = [
    ("opening", "Opening"),
    ("technical", "Technical"),
    ("behavioral", "Behavioral"),
    ("closing", "Closing"),
]
_STAGE_INDEX = {key: i for i, (key, _) in enumerate(STAGES)}

REC_META = {
    "strong_hire": ("STRONG HIRE", "hv-rec-strong"),
    "hire": ("HIRE", "hv-rec-hire"),
    "maybe": ("MAYBE", "hv-rec-maybe"),
    "no_hire": ("NO HIRE", "hv-rec-no"),
    "pending": ("PENDING", "hv-rec-pending"),
}


def _get_interviewer() -> Interviewer:
    global _interviewer
    if _interviewer is None:
        _interviewer = Interviewer()
    return _interviewer


def _reset_interviewer() -> None:
    global _interviewer
    _interviewer = Interviewer()


# ── Renderers ────────────────────────────────────────────────────────────────

def _chat_messages(interviewer: Interviewer) -> list[dict]:
    """Build gr.Chatbot 'messages' from session turns."""
    msgs = []
    for t in interviewer.session.turns:
        role = "assistant" if t.role == "assistant" else "user"
        msgs.append({"role": role, "content": t.content})
    return msgs


def _render_stepper(current_stage: str = "", ended: bool = False) -> str:
    """Render the interview stage progress stepper as HTML."""
    cur = _STAGE_INDEX.get(current_stage, -1)
    parts = ['<div class="hv-stepper">']
    for i, (_key, label) in enumerate(STAGES):
        if ended or i < cur:
            cls, mark = "hv-done", "✓"
        elif i == cur:
            cls, mark = "hv-active", str(i + 1)
        else:
            cls, mark = "hv-todo", str(i + 1)
        parts.append(
            f'<div class="hv-step {cls}">'
            f'<span class="hv-dot">{mark}</span>'
            f'<span class="hv-step-label">{label}</span></div>'
        )
        if i < len(STAGES) - 1:
            bar_done = "hv-bar-done" if (ended or i < cur) else ""
            parts.append(f'<div class="hv-bar {bar_done}"></div>')
    parts.append("</div>")
    return "".join(parts)


def _render_status(text: str, kind: str = "idle") -> str:
    return f'<div class="hv-status hv-status-{kind}"><span class="hv-pulse"></span>{html.escape(text)}</div>'


def _score_bar(label: str, score: int) -> str:
    pct = max(0, min(100, int(score) * 10))
    return (
        f'<div class="hv-bar-row"><div class="hv-bar-label">{html.escape(label)}'
        f'<b>{score}/10</b></div><div class="hv-track"><div class="hv-fill" '
        f'style="width:{pct}%"></div></div></div>'
    )


def _li(items: list[str], css: str) -> str:
    if not items:
        return '<li class="hv-empty">None noted</li>'
    return "".join(f'<li class="{css}">{html.escape(str(x))}</li>' for x in items)


def _render_assessment(assessment) -> str:
    """Render the assessment scorecard. Empty string -> placeholder."""
    if assessment is None:
        return (
            '<div class="hv-card hv-card-empty">'
            '<div class="hv-empty-ico">📋</div>'
            '<div>The assessment scorecard appears here once the interview ends.</div></div>'
        )
    if getattr(assessment, "parse_error", False):
        raw = html.escape(getattr(assessment, "raw_output", "") or "No output")
        return f'<div class="hv-card"><b>Assessment (raw)</b><pre class="hv-raw">{raw}</pre></div>'

    label, rec_cls = REC_META.get(assessment.recommendation, ("?", "hv-rec-pending"))
    name = html.escape(assessment.candidate_name or "Candidate")
    role = html.escape(assessment.role_assessed or "")
    summary = html.escape(assessment.summary or "")

    return f"""
<div class="hv-card">
  <div class="hv-card-head">
    <div>
      <div class="hv-cand">{name}</div>
      <div class="hv-role">{role}</div>
    </div>
    <div class="hv-rec {rec_cls}">{label}</div>
  </div>
  <div class="hv-overall-row">
    <div class="hv-ring"><span class="hv-ring-num">{assessment.overall_score}</span><span class="hv-ring-den">/10</span></div>
    <div class="hv-bars">
      {_score_bar("Technical", assessment.technical_score)}
      {_score_bar("Communication", assessment.communication_score)}
      {_score_bar("Culture fit", assessment.culture_fit_score)}
    </div>
  </div>
  <div class="hv-summary">{summary}</div>
  <div class="hv-cols">
    <div class="hv-col"><h4>Strengths</h4><ul>{_li(assessment.strengths, "hv-plus")}</ul></div>
    <div class="hv-col"><h4>Areas to develop</h4><ul>{_li(assessment.weaknesses, "hv-minus")}</ul></div>
  </div>
  {('<div class="hv-flags"><h4>Red flags</h4><ul>' + _li(assessment.red_flags, "hv-flag") + '</ul></div>') if assessment.red_flags else ''}
</div>
"""


def _format_resource_status() -> str:
    mode = get_mode()
    rm = get_resource_manager()
    snap = rm.get_status()
    lines = [snap.to_display(), "", f"Mode: {mode.upper()}"]
    if mode == "local":
        lines.append(f"LLM: {LLM_MODEL}  |  STT: {STT_MODEL_SIZE}")
        lines.append(f"Auto-unload: {'ON' if AUTO_UNLOAD_MODELS else 'OFF'}  |  RAM limit: {MAX_RAM_USAGE_GB} GB")
        ok, msg = check_ollama_available()
        lines.append(f"Ollama: {'OK' if ok else 'ERR'} {msg}")
        running = list_ollama_running_models()
        if running:
            lines.append(f"Ollama loaded: {', '.join(running)}")
        lines.append(f"RAM: {'OK' if rm.check_ram_limit() else 'WARNING near limit'}")
    else:
        from app.config import OPENAI_LLM_MODEL, OPENAI_STT_MODEL, OPENAI_TTS_VOICE
        lines.append(f"LLM: {OPENAI_LLM_MODEL}  |  STT: {OPENAI_STT_MODEL}  |  TTS: {OPENAI_TTS_VOICE}")
        lines.append(f"API key: {'set' if get_openai_key() else 'NOT SET'}")
    return "\n".join(lines)


# ── Resume ───────────────────────────────────────────────────────────────────

def load_resume_file(file) -> tuple[str, str]:
    if file is None:
        return "", "No file uploaded."
    try:
        from app.resume_integration import load_resume_from_file
        text = load_resume_from_file(file.name)
        preview = text[:160].strip().replace("\n", " ")
        return text, f"Loaded {len(text)} chars · {preview}…"
    except Exception as exc:
        logger.error("Resume load failed: %s", exc)
        return "", f"Error: {exc}"


# ── Interview handlers ─────────────────────────────────────────────────────────
# Main output order: [chatbot, ai_audio, stage_html, status_html,
#                      assessment_html, session_label, resource_box]

def start_interview(resume_text: str) -> tuple:
    _reset_interviewer()
    try:
        interviewer = _get_interviewer()
        _greeting, audio_path = interviewer.start(resume_context=(resume_text or "").strip())
        return (
            _chat_messages(interviewer),
            audio_path,
            _render_stepper(interviewer.current_stage),
            _render_status("Interview live — record your answer when ready.", "active"),
            _render_assessment(None),
            interviewer.session_id,
            _format_resource_status(),
        )
    except Exception as exc:
        logger.error("Start failed: %s\n%s", exc, traceback.format_exc())
        return (
            [], None, _render_stepper(),
            _render_status(f"Error: {exc}", "error"),
            _render_assessment(None), "", _format_resource_status(),
        )


def process_audio(audio) -> tuple:
    interviewer = _get_interviewer()
    if not interviewer.is_active:
        return (
            gr.update(), gr.update(), gr.update(),
            _render_status("Start an interview first.", "idle"),
            gr.update(), gr.update(), gr.update(),
        )
    if audio is None:
        return (
            gr.update(), gr.update(), gr.update(),
            _render_status("No audio detected — record, then submit.", "idle"),
            gr.update(), gr.update(), gr.update(),
        )
    try:
        _transcript, _response, audio_path = interviewer.process_candidate_audio(audio)
        if not interviewer.is_active:
            try:
                assessment = interviewer.get_assessment()
                card = _render_assessment(assessment)
                status = _render_status(f"Interview complete · saved as {interviewer.session_id}", "ended")
            except Exception as exc:
                card = _render_assessment(None)
                status = _render_status(f"Ended (assessment error: {exc})", "error")
            stepper = _render_stepper(ended=True)
        else:
            card = gr.update()
            stepper = _render_stepper(interviewer.current_stage)
            status = _render_status(
                f"Turn {interviewer.session.turn_count} · {interviewer.current_stage.title()} stage", "active"
            )
        return (
            _chat_messages(interviewer), audio_path, stepper, status,
            card, gr.update(), _format_resource_status(),
        )
    except Exception as exc:
        logger.error("Audio processing failed: %s\n%s", exc, traceback.format_exc())
        return (
            gr.update(), gr.update(), gr.update(),
            _render_status(f"Error: {exc}", "error"),
            gr.update(), gr.update(), _format_resource_status(),
        )


def end_interview() -> tuple:
    interviewer = _get_interviewer()
    card = gr.update()
    session_id = gr.update()
    if interviewer.is_active:
        try:
            assessment = interviewer.get_assessment()
            card = _render_assessment(assessment)
            session_id = interviewer.session_id
        except Exception as exc:
            card = _render_assessment(None)
            logger.error("Assessment on end failed: %s", exc)
        interviewer.end()
        status = _render_status("Interview ended · resources cleaned up.", "ended")
    else:
        cleanup_all()
        status = _render_status("No active interview — resources cleaned up.", "idle")
    return (
        _chat_messages(interviewer), gr.update(), _render_stepper(ended=True),
        status, card, session_id, _format_resource_status(),
    )


def manual_cleanup() -> tuple:
    cleanup_all()
    return _render_status("Resources cleaned up.", "idle"), _format_resource_status()


def refresh_status() -> str:
    return _format_resource_status()


# ── Settings ───────────────────────────────────────────────────────────────────

def apply_settings(mode: str, api_key: str) -> tuple[str, str]:
    try:
        if api_key and api_key.strip() and set(api_key.strip()) != {"*"}:
            set_openai_key(api_key.strip())
        prev = get_mode()
        set_mode(mode)
        if prev != mode and prev == "local":
            cleanup_all()
        return _render_status(f"Settings saved · mode = {mode.upper()}", "active"), _format_resource_status()
    except Exception as exc:
        return _render_status(f"Error: {exc}", "error"), _format_resource_status()


def test_connection() -> str:
    mode = get_mode()
    ok, msg = check_openai_available() if mode == "openai" else check_ollama_available()
    return _render_status(f"{'Connected' if ok else 'Failed'} · {msg}", "active" if ok else "error")


def download_transcript():
    import tempfile
    interviewer = _get_interviewer()
    transcript = interviewer.get_transcript()
    if not transcript.strip():
        return gr.update(visible=False)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8",
        prefix=f"hirevoice_{interviewer.session_id}_",
    ) as f:
        f.write(transcript)
        path = f.name
    return gr.update(value=path, visible=True)


# ── Button-state transitions (immediate feedback) ──────────────────────────────

def _lock_for_start() -> tuple:
    """Immediate feedback when Start is pressed (before models load)."""
    return (
        gr.update(value="◌  Starting…", interactive=False),       # start_btn
        gr.update(interactive=False),                              # submit_btn
        _render_status("Warming up the interviewer & speech models…", "active"),
    )


def _lock_for_submit() -> tuple:
    """Immediate feedback when an answer is submitted (before STT/LLM/TTS run)."""
    return (
        gr.update(value="◌  Thinking…", interactive=False),       # submit_btn
        _render_status("Transcribing your answer and generating a reply…", "active"),
    )


def _sync_controls() -> tuple:
    """Set Start/Submit button states to match interview activity (handles auto-end)."""
    active = _get_interviewer().is_active
    if active:
        return (
            gr.update(value="●  Interview in progress", interactive=False),  # start_btn
            gr.update(value="Submit Answer", interactive=True),              # submit_btn
        )
    return (
        gr.update(value="▶  Start Interview", interactive=True),
        gr.update(value="Submit Answer", interactive=True),
    )


# ── Styling ────────────────────────────────────────────────────────────────────

def _build_theme() -> gr.themes.Base:
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.indigo,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_lg,
        text_size=gr.themes.sizes.text_md,
        spacing_size=gr.themes.sizes.spacing_lg,
        font=["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
    ).set(
        block_border_width="1px",
        block_label_text_weight="600",
        block_title_text_weight="600",
        button_large_radius="12px",
        button_small_radius="10px",
        button_primary_background_fill="*primary_500",
        button_primary_background_fill_hover="*primary_600",
        button_primary_text_color="white",
    )


CUSTOM_CSS = """
.gradio-container { max-width: 1180px !important; margin: 0 auto !important; }
#hv-header { text-align:center; padding: 14px 0 4px; }
#hv-header h1 {
  font-size: 1.9rem; font-weight: 800; letter-spacing:-0.02em; margin:0;
  background: linear-gradient(90deg,#6366f1,#0ea5e9 60%,#10b981);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
#hv-header p { color: var(--body-text-color-subdued); margin:4px 0 0; font-size:.9rem; }

/* Stepper */
.hv-stepper { display:flex; align-items:center; justify-content:center; gap:6px; padding:10px 4px 2px; flex-wrap:wrap; }
.hv-step { display:flex; flex-direction:column; align-items:center; gap:5px; min-width:78px; }
.hv-dot {
  width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:.85rem; border:2px solid var(--border-color-primary);
  color: var(--body-text-color-subdued); background: var(--background-fill-primary); transition:all .3s;
}
.hv-step-label { font-size:.78rem; color: var(--body-text-color-subdued); font-weight:600; }
.hv-bar { height:2px; width:42px; background: var(--border-color-primary); border-radius:2px; transition:all .3s; }
.hv-bar-done { background: linear-gradient(90deg,#6366f1,#0ea5e9); }
.hv-active .hv-dot { border-color:#6366f1; color:#fff; background:linear-gradient(135deg,#6366f1,#0ea5e9); box-shadow:0 0 0 4px rgba(99,102,241,.18); transform:scale(1.08); }
.hv-active .hv-step-label { color: var(--body-text-color); }
.hv-done .hv-dot { border-color:#10b981; color:#fff; background:#10b981; }

/* Status pill */
.hv-status { display:inline-flex; align-items:center; gap:8px; padding:7px 14px; border-radius:999px;
  font-size:.85rem; font-weight:600; border:1px solid var(--border-color-primary); background: var(--background-fill-secondary); }
.hv-pulse { width:8px; height:8px; border-radius:50%; background:var(--body-text-color-subdued); }
.hv-status-active { border-color:rgba(99,102,241,.4); color:#6366f1; }
.hv-status-active .hv-pulse { background:#6366f1; animation:hvpulse 1.4s infinite; }
.hv-status-ended { border-color:rgba(16,185,129,.4); color:#10b981; }
.hv-status-ended .hv-pulse { background:#10b981; }
.hv-status-error { border-color:rgba(239,68,68,.4); color:#ef4444; }
.hv-status-error .hv-pulse { background:#ef4444; }
@keyframes hvpulse { 0%{box-shadow:0 0 0 0 rgba(99,102,241,.5);} 70%{box-shadow:0 0 0 7px rgba(99,102,241,0);} 100%{box-shadow:0 0 0 0 rgba(99,102,241,0);} }
#hv-statuswrap { display:flex; justify-content:center; padding:8px 0; }

/* Chat */
#hv-chat { border-radius:16px !important; border:1px solid var(--border-color-primary) !important; }

/* Mic dock */
#hv-dock { background: var(--background-fill-secondary); border:1px solid var(--border-color-primary);
  border-radius:16px; padding:12px; margin-top:8px; }

/* Assessment scorecard */
.hv-card { border:1px solid var(--border-color-primary); border-radius:16px; padding:20px;
  background: var(--background-fill-primary); box-shadow:0 4px 24px rgba(0,0,0,.06); }
.hv-card-empty { text-align:center; color:var(--body-text-color-subdued); padding:34px 20px; }
.hv-empty-ico { font-size:2rem; margin-bottom:8px; opacity:.7; }
.hv-card-head { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:16px; }
.hv-cand { font-size:1.2rem; font-weight:800; }
.hv-role { color:var(--body-text-color-subdued); font-size:.85rem; }
.hv-rec { padding:7px 16px; border-radius:999px; font-weight:800; font-size:.8rem; letter-spacing:.04em; }
.hv-rec-strong { background:#10b981; color:#fff; }
.hv-rec-hire { background:rgba(16,185,129,.15); color:#10b981; border:1px solid #10b981; }
.hv-rec-maybe { background:rgba(245,158,11,.15); color:#f59e0b; border:1px solid #f59e0b; }
.hv-rec-no { background:rgba(239,68,68,.15); color:#ef4444; border:1px solid #ef4444; }
.hv-rec-pending { background:var(--background-fill-secondary); color:var(--body-text-color-subdued); }
.hv-overall-row { display:flex; gap:20px; align-items:center; margin-bottom:14px; }
.hv-ring { width:84px; height:84px; border-radius:50%; flex-shrink:0; display:flex; align-items:baseline;
  justify-content:center; background:conic-gradient(#6366f1 0,#0ea5e9 100%); color:#fff; font-weight:800; }
.hv-ring-num { font-size:1.9rem; line-height:84px; }
.hv-ring-den { font-size:.8rem; opacity:.85; line-height:84px; }
.hv-bars { flex:1; display:flex; flex-direction:column; gap:9px; }
.hv-bar-row { font-size:.82rem; }
.hv-bar-label { display:flex; justify-content:space-between; margin-bottom:3px; color:var(--body-text-color-subdued); }
.hv-bar-label b { color:var(--body-text-color); }
.hv-track { height:7px; background:var(--background-fill-secondary); border-radius:99px; overflow:hidden; }
.hv-fill { height:100%; border-radius:99px; background:linear-gradient(90deg,#6366f1,#0ea5e9); }
.hv-summary { font-size:.92rem; line-height:1.5; padding:12px 0; border-top:1px solid var(--border-color-primary);
  border-bottom:1px solid var(--border-color-primary); margin:8px 0 14px; }
.hv-cols { display:flex; gap:18px; }
.hv-col { flex:1; }
.hv-col h4, .hv-flags h4 { margin:0 0 8px; font-size:.8rem; text-transform:uppercase; letter-spacing:.05em; color:var(--body-text-color-subdued); }
.hv-card ul { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:6px; }
.hv-card li { font-size:.88rem; padding-left:20px; position:relative; line-height:1.4; }
.hv-plus:before { content:"＋"; position:absolute; left:0; color:#10b981; font-weight:700; }
.hv-minus:before { content:"–"; position:absolute; left:0; color:#f59e0b; font-weight:700; }
.hv-flag:before { content:"!"; position:absolute; left:2px; color:#ef4444; font-weight:800; }
.hv-flags { margin-top:14px; }
.hv-empty { color:var(--body-text-color-subdued); font-style:italic; padding-left:0 !important; }
.hv-empty:before { content:""; }
.hv-raw { white-space:pre-wrap; font-size:.8rem; }

/* ── Enterprise component polish ───────────────────────────────────────── */

/* Primary buttons — gradient with hover lift */
.gradio-container button.primary {
  background: linear-gradient(135deg,#6366f1,#4f46e5) !important;
  border: none !important; color:#fff !important; font-weight:600 !important;
  letter-spacing:.01em !important;
  box-shadow: 0 1px 2px rgba(79,70,229,.25), 0 6px 16px rgba(79,70,229,.18) !important;
  transition: transform .15s ease, box-shadow .15s ease, filter .15s ease !important;
}
.gradio-container button.primary:hover {
  transform: translateY(-1px) !important; filter: brightness(1.06) !important;
  box-shadow: 0 2px 4px rgba(79,70,229,.3), 0 10px 24px rgba(79,70,229,.28) !important;
}
.gradio-container button.primary:active { transform: translateY(0) !important; filter:brightness(.98) !important; }

/* Secondary buttons — quiet, bordered, accent on hover */
.gradio-container button.secondary {
  background: var(--background-fill-primary) !important;
  border: 1px solid var(--border-color-primary) !important;
  color: var(--body-text-color) !important; font-weight:600 !important;
  box-shadow: 0 1px 2px rgba(0,0,0,.04) !important;
  transition: all .15s ease !important;
}
.gradio-container button.secondary:hover {
  border-color: #6366f1 !important; color:#6366f1 !important;
  background: rgba(99,102,241,.06) !important; transform: translateY(-1px) !important;
}

/* End / stop button — ghost danger */
.gradio-container button.stop {
  background: transparent !important; color:#ef4444 !important; font-weight:600 !important;
  border: 1px solid rgba(239,68,68,.45) !important; box-shadow:none !important;
  transition: all .15s ease !important;
}
.gradio-container button.stop:hover {
  background: rgba(239,68,68,.1) !important; border-color:#ef4444 !important; transform: translateY(-1px) !important;
}

/* Panels — softer corners + subtle elevation */
.gradio-container .block {
  border-radius: 14px !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.05) !important;
}
/* Avoid double-bordered nesting inside the mic dock */
#hv-dock .block { box-shadow:none !important; border:none !important; background:transparent !important; }

/* Accordion header reads like a section title */
.gradio-container .label-wrap { font-weight:600 !important; padding:6px 2px !important; transition:color .15s ease !important; }
.gradio-container .label-wrap:hover { color:#6366f1 !important; }

/* Inputs — rounded with an accent focus ring */
.gradio-container textarea,
.gradio-container input[type=text],
.gradio-container input[type=password] {
  border-radius: 10px !important;
  transition: border-color .15s ease, box-shadow .15s ease !important;
}
.gradio-container textarea:focus,
.gradio-container input[type=text]:focus,
.gradio-container input[type=password]:focus {
  border-color:#6366f1 !important; box-shadow: 0 0 0 3px rgba(99,102,241,.16) !important; outline:none !important;
}

/* Radio (backend toggle) — segmented pill feel */
.gradio-container [data-testid="radio"] label,
.gradio-container fieldset label { border-radius:10px !important; transition: all .15s ease !important; }

/* Tighter, calmer footer */
footer { opacity:.5 !important; }
"""


# ── Layout ─────────────────────────────────────────────────────────────────────

def build_ui() -> gr.Blocks:
    ensure_dirs()

    with gr.Blocks(title="HireVoice AI") as app:
        gr.HTML(
            '<div id="hv-header"><h1>HireVoice AI</h1>'
            '<p>Conversational voice interviews · local or cloud · models load on demand</p></div>'
        )

        stage_html = gr.HTML(_render_stepper())
        with gr.Row(elem_id="hv-statuswrap"):
            status_html = gr.HTML(_render_status("Set up below, then start your interview.", "idle"))

        # ── Setup (collapses when the interview starts) ─────────────────────
        with gr.Accordion("⚙  Setup — resume & backend", open=True) as setup_panel:
            with gr.Row():
                with gr.Column(scale=3):
                    resume_file = gr.File(
                        label="Resume (PDF / DOCX / TXT)",
                        file_types=[".pdf", ".docx", ".doc", ".txt"],
                        height=110,
                    )
                    resume_load_status = gr.Textbox(
                        label="", interactive=False, lines=1, show_label=False,
                        placeholder="Upload a resume for context-aware questions (optional)",
                    )
                    resume_text = gr.Textbox(
                        label="Resume text", lines=5,
                        placeholder="…or paste the resume here.",
                    )
                with gr.Column(scale=2):
                    mode_radio = gr.Radio(
                        choices=["local", "openai"], value=get_mode(), label="Backend",
                        info="local = Ollama + Piper (free, private) · openai = GPT-4o + Whisper (cloud)",
                    )
                    api_key_input = gr.Textbox(
                        label="OpenAI API key", placeholder="sk-…", type="password",
                        value="*" * 8 if get_openai_key() else "",
                        info="Used only for API calls — never written to disk.",
                    )
                    with gr.Row():
                        apply_btn = gr.Button("Apply settings", size="sm")
                        test_btn = gr.Button("Test connection", size="sm")

        with gr.Row():
            start_btn = gr.Button("▶  Start Interview", variant="primary", scale=3)
            end_btn = gr.Button("■  End", variant="stop", scale=1)

        # ── Conversation ────────────────────────────────────────────────────
        chatbot = gr.Chatbot(
            elem_id="hv-chat", height=420,
            label="Interview", show_label=False,
            placeholder="### 🎙 Your interview will appear here\nStart the interview and the interviewer will greet you.",
            avatar_images=(None, None),
        )
        ai_audio = gr.Audio(label="Interviewer voice", interactive=False, autoplay=True)

        with gr.Group(elem_id="hv-dock"):
            mic_input = gr.Audio(sources=["microphone"], type="numpy", label="🎤 Record your answer")
            with gr.Row():
                submit_audio_btn = gr.Button("Submit Answer", variant="primary", scale=3)
                download_transcript_btn = gr.Button("⬇ Transcript", size="sm", scale=1)
            transcript_file = gr.File(label="Download", visible=False)

        # ── Assessment ────────────────────────────────────────────────────────
        gr.Markdown("### Assessment")
        assessment_html = gr.HTML(_render_assessment(None))

        # ── Diagnostics (tucked away) ──────────────────────────────────────────
        with gr.Accordion("System & diagnostics", open=False):
            with gr.Row():
                session_label = gr.Textbox(label="Session ID", interactive=False, scale=2)
                with gr.Column(scale=3):
                    resource_box = gr.Textbox(
                        label="Memory & models", value=_format_resource_status(),
                        interactive=False, lines=8,
                    )
                    with gr.Row():
                        refresh_btn = gr.Button("Refresh", size="sm")
                        cleanup_btn = gr.Button("Cleanup resources", size="sm")

        # ── Wiring ──────────────────────────────────────────────────────────
        main_out = [chatbot, ai_audio, stage_html, status_html,
                    assessment_html, session_label, resource_box]

        resume_file.upload(load_resume_file, [resume_file], [resume_text, resume_load_status])

        # Start: immediate "Starting…" feedback → run → reflect active state → collapse setup
        start_btn.click(
            _lock_for_start, None, [start_btn, submit_audio_btn, status_html]
        ).then(
            start_interview, [resume_text], main_out
        ).then(
            _sync_controls, None, [start_btn, submit_audio_btn]
        ).then(
            lambda: gr.update(open=False), None, setup_panel
        )

        # Submit: immediate "Thinking…" feedback → run → re-sync (handles auto-end) → clear mic
        submit_audio_btn.click(
            _lock_for_submit, None, [submit_audio_btn, status_html]
        ).then(
            process_audio, [mic_input], main_out
        ).then(
            _sync_controls, None, [start_btn, submit_audio_btn]
        ).then(
            lambda: None, None, mic_input
        )

        # End: run → reset buttons to idle
        end_btn.click(end_interview, [], main_out).then(
            _sync_controls, None, [start_btn, submit_audio_btn]
        )

        download_transcript_btn.click(download_transcript, [], [transcript_file])
        apply_btn.click(apply_settings, [mode_radio, api_key_input], [status_html, resource_box])
        test_btn.click(test_connection, [], [status_html])
        cleanup_btn.click(manual_cleanup, [], [status_html, resource_box])
        refresh_btn.click(refresh_status, [], [resource_box])

    return app


def launch_app(server_name: str = "0.0.0.0", server_port: int = 7860, share: bool = False) -> None:
    app = build_ui()
    app.launch(
        server_name=server_name, server_port=server_port, share=share,
        theme=_build_theme(), css=CUSTOM_CSS,
    )
