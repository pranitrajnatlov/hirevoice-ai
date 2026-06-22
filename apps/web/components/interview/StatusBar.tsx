"use client";

import { motion } from "framer-motion";
import { cn, fmtTime } from "@/lib/utils";
import { ProgressRing } from "./ProgressRing";
import { ConnectionIndicator } from "./ConnectionIndicator";
import type { AvatarState } from "./AiAvatar";

const STAGES: { key: string; label: string }[] = [
  { key: "opening", label: "Intro" },
  { key: "experience", label: "Experience" },
  { key: "technical", label: "Technical" },
  { key: "behavioral", label: "Behavioral" },
  { key: "closing", label: "Wrap-up" },
];

const AI_STATUS: Record<AvatarState, { label: string; dot: string }> = {
  idle: { label: "Ready", dot: "bg-ink-muted" },
  speaking: { label: "AI speaking", dot: "bg-accent" },
  listening: { label: "Listening", dot: "bg-secondary" },
  thinking: { label: "Thinking", dot: "bg-warn" },
};

export function StatusBar({
  stage,
  avatar,
  elapsed,
  questionIndex,
  total,
  wsConnected,
  roleTitle,
}: {
  stage: string;
  avatar: AvatarState;
  elapsed: number;
  questionIndex: number;
  total: number;
  wsConnected: boolean;
  roleTitle?: string;
}) {
  const activeIdx = STAGES.findIndex((s) => s.key === stage);
  const ai = AI_STATUS[avatar];

  return (
    <div className="glass-card flex flex-wrap items-center justify-between gap-4 px-5 py-3">
      {/* Left: role + AI status */}
      <div className="flex items-center gap-3">
        <div className="hidden sm:block">
          <div className="text-sm font-semibold text-ink">{roleTitle ?? "Interview"}</div>
          <div className="text-[11px] text-ink-muted">AI Interview · live</div>
        </div>
        <span className="flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-1 text-xs text-ink">
          <span className={cn("h-2 w-2 rounded-full", ai.dot, avatar !== "idle" && "animate-pulse")} />
          {ai.label}
        </span>
      </div>

      {/* Center: stage stepper */}
      <div className="order-last flex w-full items-center justify-center gap-1.5 sm:order-none sm:w-auto">
        {STAGES.map((s, i) => {
          const done = i < activeIdx;
          const active = i === activeIdx;
          return (
            <div key={s.key} className="flex items-center gap-1.5">
              <div className="flex items-center gap-1.5">
                <span
                  className={cn(
                    "grid h-5 w-5 place-items-center rounded-full text-[10px] font-semibold transition-colors",
                    active ? "accent-gradient text-white" : done ? "bg-success/30 text-success" : "bg-white/8 text-ink-muted",
                  )}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span className={cn("text-xs", active ? "font-medium text-ink" : "text-ink-muted")}>
                  {s.label}
                </span>
              </div>
              {i < STAGES.length - 1 && <span className="h-px w-4 bg-white/10" />}
            </div>
          );
        })}
      </div>

      {/* Right: timer + progress + connection */}
      <div className="flex items-center gap-4">
        <ConnectionIndicator wsConnected={wsConnected} />
        <motion.span
          key={Math.floor(elapsed / 1)}
          className="rounded-full bg-white/5 px-2.5 py-1 font-mono text-sm text-ink"
        >
          {fmtTime(elapsed)}
        </motion.span>
        <ProgressRing value={questionIndex} total={total} size={44} />
      </div>
    </div>
  );
}
