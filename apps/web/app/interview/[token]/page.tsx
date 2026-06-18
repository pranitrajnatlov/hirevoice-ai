"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { api, type MeetingInfo, type SessionStart } from "@/lib/api";
import { AnswerRecorder } from "@/lib/audio/recorder";
import { fmtTime } from "@/lib/utils";

const GW_WS = process.env.NEXT_PUBLIC_GATEWAY_WS ?? "ws://localhost:8000";
import { Button } from "@/components/ui/button";
import { AiAvatar, type AvatarState } from "@/components/interview/AiAvatar";
import { VoiceWaveform } from "@/components/interview/VoiceWaveform";
import { MicButton } from "@/components/interview/MicButton";
import { QuestionCard } from "@/components/interview/QuestionCard";
import { LiveTranscript, type Turn } from "@/components/interview/LiveTranscript";
import { AnalysisPanel, type Scores } from "@/components/interview/AnalysisPanel";
import { ProgressRing } from "@/components/interview/ProgressRing";

type Phase = "lobby" | "live" | "complete" | "error";
const SEED: Scores = { communication: 0, technical: 0, confidence: 0, alignment: 0, keyword: 0 };

export default function InterviewRoom() {
  const { token } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>("lobby");
  const [info, setInfo] = useState<MeetingInfo | null>(null);
  const [session, setSession] = useState<SessionStart | null>(null);
  const [question, setQuestion] = useState({ text: "", stage: "opening", index: 0 });
  const [turns, setTurns] = useState<Turn[]>([]);
  const [scores, setScores] = useState<Scores>(SEED);
  const [avatar, setAvatar] = useState<AvatarState>("idle");
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");

  const recorder = useRef<AnswerRecorder | null>(null);
  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    api.getMeeting(token).then(setInfo).catch((e) => { setError(String(e)); setPhase("error"); });
    return () => { ws.current?.close(); };
  }, [token]);

  // interview timer
  useEffect(() => {
    if (phase !== "live") return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [phase]);

  const speakThenListen = useCallback((text: string, stage: string, index: number) => {
    setQuestion({ text, stage, index });
    setTurns((t) => [...t, { role: "interviewer", text }]);
    setAvatar("speaking");
    // Simulated speaking duration until TTS streaming is wired (Phase 3b).
    const ms = Math.min(7000, 1500 + text.length * 35);
    setTimeout(() => setAvatar("listening"), ms);
  }, []);

  const join = async () => {
    try {
      recorder.current = new AnswerRecorder();
      await recorder.current.init();
      const s = await api.startSession(token);
      setSession(s);
      setPhase("live");
      speakThenListen(s.question, s.stage, s.question_index);

      // Open WebSocket for real-time transcript/question events
      const socket = new WebSocket(`${GW_WS}/api/v1/ws/${s.interview_id}`);
      ws.current = socket;
      socket.onmessage = (e) => {
        const { event, data } = JSON.parse(e.data) as { event: string; data: Record<string, unknown> };
        if (event === "transcript") {
          setTurns((t) => [...t, { role: "candidate", text: data.text as string }]);
          setAvatar("thinking");
        } else if (event === "question") {
          bumpScores();
          speakThenListen(data.text as string, data.stage as string, data.question_index as number);
        } else if (event === "complete") {
          setAvatar("idle");
          setPhase("complete");
          recorder.current?.dispose();
        }
      };
      socket.onerror = () => console.warn("WS error — falling back to HTTP polling");
    } catch (e) {
      setError(String(e));
      setPhase("error");
    }
  };

  const onPress = () => {
    if (avatar !== "listening" || busy) return;
    recorder.current?.start();
    setRecording(true);
  };

  const onRelease = async () => {
    if (!recording || !session || !recorder.current) return;
    setRecording(false);
    setBusy(true);
    setAvatar("thinking");
    const wsConnected = ws.current?.readyState === WebSocket.OPEN;
    try {
      const blob = await recorder.current.stop();
      const res = await api.submitAnswer(session.interview_id, blob, session.session_token);
      // If WebSocket is connected it already updated the UI; use HTTP response as fallback only.
      if (!wsConnected) {
        setTurns((t) => [...t, { role: "candidate", text: res.transcript }]);
        bumpScores();
        if (res.completed) {
          setAvatar("idle");
          setPhase("complete");
          recorder.current.dispose();
        } else {
          speakThenListen(res.question, res.stage, res.question_index);
        }
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  // Gentle live-score animation (real per-turn scores arrive via WS in Phase 3b).
  const bumpScores = () =>
    setScores((s) => ({
      communication: Math.min(95, s.communication + 18 + Math.random() * 8),
      technical: Math.min(92, s.technical + 15 + Math.random() * 8),
      confidence: Math.min(96, s.confidence + 20 + Math.random() * 6),
      alignment: Math.min(90, s.alignment + 16 + Math.random() * 8),
      keyword: Math.min(88, s.keyword + 14 + Math.random() * 8),
    }));

  if (phase === "error")
    return <Centered><p className="text-danger">Unable to load interview.</p><p className="text-sm text-ink-muted">{error}</p></Centered>;

  if (phase === "lobby")
    return (
      <Centered>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="glass-card max-w-md p-8 text-center">
          <div className="mx-auto mb-5"><AiAvatar state="idle" /></div>
          <h1 className="text-2xl font-bold text-ink">{info?.role_title ?? "Interview"}</h1>
          <p className="mt-1 text-ink-muted">AI voice interview · ~{info?.duration_min ?? 20} min</p>
          <p className="mx-auto mt-4 max-w-sm text-sm text-ink-muted">
            You will speak with an AI interviewer. Allow microphone access, then hold the mic button to answer each question.
          </p>
          <Button size="lg" className="mt-6 w-full" onClick={join} disabled={!info?.valid}>
            Join Interview
          </Button>
        </motion.div>
      </Centered>
    );

  if (phase === "complete")
    return (
      <Centered>
        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="glass-card max-w-md p-10 text-center">
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-success/20 text-3xl">✓</div>
          <h1 className="text-2xl font-bold text-ink">Interview complete</h1>
          <p className="mt-2 text-ink-muted">Thank you. Your responses have been recorded and your assessment is being prepared for the hiring team.</p>
        </motion.div>
      </Centered>
    );

  // live
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {/* Top bar */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">{info?.role_title}</div>
          <div className="text-xs text-ink-muted">AI Interview · live</div>
        </div>
        <div className="flex items-center gap-5">
          <span className="rounded-full glass px-3 py-1 font-mono text-sm text-ink">{fmtTime(elapsed)}</span>
          <ProgressRing value={question.index} total={session?.total_estimated ?? 8} />
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        {/* Stage */}
        <div className="glass-card flex flex-col items-center gap-6 p-8">
          <AiAvatar state={avatar} />
          <VoiceWaveform active={avatar === "speaking" || recording} stream={recording ? recorder.current?.stream : null}
            color={recording ? "#FF5C7A" : "#4CC9F0"} />
          <QuestionCard text={question.text} stage={question.stage} />
          <MicButton recording={recording} busy={busy} onPress={onPress} onRelease={onRelease} />
        </div>

        {/* Side: analysis + transcript */}
        <div className="flex flex-col gap-5">
          <div className="glass-card p-5"><AnalysisPanel scores={scores} /></div>
          <div className="glass-card p-5">
            <h3 className="mb-3 text-sm font-semibold text-ink">Transcript</h3>
            <LiveTranscript turns={turns} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="grid min-h-screen place-items-center px-4">{children}</div>;
}
