"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { MessageSquareText, PhoneOff } from "lucide-react";
import { api, type MeetingInfo, type SessionStart } from "@/lib/api";
import { AnswerRecorder } from "@/lib/audio/recorder";
import { Button } from "@/components/ui/button";
import { AiAvatar, type AvatarState } from "@/components/interview/AiAvatar";
import { VoiceWaveform } from "@/components/interview/VoiceWaveform";
import { MicButton } from "@/components/interview/MicButton";
import { QuestionCard } from "@/components/interview/QuestionCard";
import { type Turn } from "@/components/interview/LiveTranscript";
import { StatusBar } from "@/components/interview/StatusBar";
import { TranscriptDrawer } from "@/components/interview/TranscriptDrawer";

const GW_WS = process.env.NEXT_PUBLIC_GATEWAY_WS ?? "ws://localhost:8000";

type Phase = "lobby" | "live" | "complete" | "error";

export default function InterviewRoom() {
  const { token } = useParams<{ token: string }>();
  const [phase, setPhase] = useState<Phase>("lobby");
  const [info, setInfo] = useState<MeetingInfo | null>(null);
  const [session, setSession] = useState<SessionStart | null>(null);
  const [question, setQuestion] = useState({ text: "", stage: "opening", index: 0 });
  const [turns, setTurns] = useState<Turn[]>([]);
  const [avatar, setAvatar] = useState<AvatarState>("idle");
  const [recording, setRecording] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [partial, setPartial] = useState("");
  const [transcriptOpen, setTranscriptOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  const recorder = useRef<AnswerRecorder | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const sttWs = useRef<WebSocket | null>(null);

  useEffect(() => {
    api.getMeeting(token).then(setInfo).catch((e) => { setError(String(e)); setPhase("error"); });
    return () => { ws.current?.close(); sttWs.current?.close(); };
  }, [token]);

  useEffect(() => {
    if (phase !== "live") return;
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [phase]);

  const speakThenListen = useCallback(async (text: string, stage: string, index: number) => {
    setQuestion({ text, stage, index });
    setTurns((t) => [...t, { role: "interviewer", text }]);
    setAvatar("speaking");
    try {
      const resp = await fetch("/api/v1/tts/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!resp.ok) throw new Error(`TTS ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => { URL.revokeObjectURL(url); setAvatar("listening"); };
      audio.onerror = () => { URL.revokeObjectURL(url); setAvatar("listening"); };
      await audio.play();
    } catch {
      const ms = Math.min(7000, 1500 + text.length * 35);
      setTimeout(() => setAvatar("listening"), ms);
    }
  }, []);

  const join = async () => {
    try {
      recorder.current = new AnswerRecorder();
      await recorder.current.init();
      const s = await api.startSession(token);
      setSession(s);
      setPhase("live");
      speakThenListen(s.question, s.stage, s.question_index);

      const socket = new WebSocket(`${GW_WS}/api/v1/ws/${s.interview_id}`);
      ws.current = socket;
      socket.onopen = () => setWsConnected(true);
      socket.onclose = () => setWsConnected(false);
      socket.onmessage = (e) => {
        const { event, data } = JSON.parse(e.data) as { event: string; data: Record<string, unknown> };
        if (event === "transcript") {
          setTurns((t) => [...t, { role: "candidate", text: data.text as string }]);
          setAvatar("thinking");
        } else if (event === "question") {
          speakThenListen(data.text as string, data.stage as string, data.question_index as number);
        } else if (event === "complete") {
          setAvatar("idle");
          setPhase("complete");
          recorder.current?.dispose();
        }
      };
      socket.onerror = () => { setWsConnected(false); console.warn("WS error — HTTP fallback"); };
    } catch (e) {
      setError(String(e));
      setPhase("error");
    }
  };

  const onPress = () => {
    if (avatar !== "listening" || busy || finishing || !session) return;
    setPartial("");
    try {
      const s = new WebSocket(`${GW_WS}/api/v1/ws/stt/${session.interview_id}`);
      sttWs.current = s;
      s.onmessage = (e) => {
        try {
          const m = JSON.parse(e.data) as { event: string; text?: string };
          if (m.event === "partial") setPartial(m.text ?? "");
        } catch { /* ignore malformed partial */ }
      };
      s.onerror = () => console.warn("STT stream unavailable — final transcript only");
    } catch {
      sttWs.current = null;
    }
    recorder.current?.start((accumulated) => {
      const s = sttWs.current;
      if (s && s.readyState === WebSocket.OPEN) s.send(accumulated);
    });
    setRecording(true);
  };

  const onRelease = async () => {
    if (!recording || !session || !recorder.current) return;
    setRecording(false);
    // Grace period: keep capturing trailing speech, stop only once the candidate goes quiet.
    setFinishing(true);
    const blob = await recorder.current.stopGraceful();
    setFinishing(false);
    sttWs.current?.close();
    sttWs.current = null;
    setPartial("");

    setBusy(true);
    setAvatar("thinking");
    const wsLive = ws.current?.readyState === WebSocket.OPEN;
    try {
      const res = await api.submitAnswer(session.interview_id, blob, session.session_token);
      if (!wsLive) {
        setTurns((t) => [...t, { role: "candidate", text: res.transcript }]);
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

  const endEarly = () => {
    recorder.current?.dispose();
    ws.current?.close();
    sttWs.current?.close();
    setPhase("complete");
  };

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
            You'll speak with an AI interviewer. Allow microphone access, then hold the mic button to
            answer. Take your time — it keeps listening for a moment after you release.
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

  // live — meeting-style shell
  return (
    <div className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-5">
      <StatusBar
        stage={question.stage}
        avatar={avatar}
        elapsed={elapsed}
        questionIndex={question.index}
        total={session?.total_estimated ?? 10}
        wsConnected={wsConnected}
        roleTitle={info?.role_title}
      />

      {/* Center stage */}
      <div className="flex flex-1 flex-col items-center justify-center gap-8 py-8">
        <AiAvatar state={avatar} />
        <div className="w-full max-w-xl">
          <VoiceWaveform
            active={avatar === "speaking" || recording || finishing}
            stream={recording || finishing ? recorder.current?.stream : null}
            color={recording || finishing ? "#FF5C7A" : "#4CC9F0"}
          />
        </div>
        <QuestionCard text={question.text} stage={question.stage} />
      </div>

      {/* Bottom control dock */}
      <div className="glass-card flex items-center justify-between gap-4 px-6 py-4">
        <button
          onClick={() => setTranscriptOpen(true)}
          className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-ink-muted transition-colors hover:bg-white/5 hover:text-ink"
        >
          <MessageSquareText className="h-4 w-4" /> Transcript
        </button>

        <MicButton recording={recording} busy={busy} finishing={finishing} onPress={onPress} onRelease={onRelease} />

        <button
          onClick={endEarly}
          className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-danger transition-colors hover:bg-danger/10"
        >
          <PhoneOff className="h-4 w-4" /> End
        </button>
      </div>

      <TranscriptDrawer
        open={transcriptOpen}
        onClose={() => setTranscriptOpen(false)}
        turns={turns}
        partial={partial}
        recording={recording || finishing}
      />
    </div>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="grid min-h-screen place-items-center px-4">{children}</div>;
}
