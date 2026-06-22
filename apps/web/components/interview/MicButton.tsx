"use client";

import { motion } from "framer-motion";
import { Mic, MicOff, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function MicButton({
  recording,
  busy,
  finishing = false,
  locked = false,
  onPress,
  onRelease,
}: {
  recording: boolean;
  busy: boolean;
  /** Grace period after release — still capturing trailing speech. */
  finishing?: boolean;
  /** AI is speaking/thinking — candidate must wait, mic is unavailable. */
  locked?: boolean;
  onPress: () => void;
  onRelease: () => void;
}) {
  const active = recording || finishing;
  const disabled = busy || (locked && !active);

  const hint = busy
    ? "Processing…"
    : finishing
      ? "Finishing…"
      : recording
        ? "Release to send"
        : locked
          ? "Wait for the interviewer…"
          : "Hold to speak  ·  or hold Space";

  return (
    <div className="flex flex-col items-center gap-2">
      <motion.button
        disabled={disabled}
        onPointerDown={onPress}
        onPointerUp={onRelease}
        onPointerLeave={() => recording && onRelease()}
        whileTap={disabled ? undefined : { scale: 0.94 }}
        aria-label={hint}
        className={cn(
          "relative grid h-20 w-20 place-items-center rounded-full text-white transition-colors",
          disabled && "cursor-not-allowed opacity-40",
          finishing ? "bg-warn" : recording ? "bg-danger" : "accent-gradient shadow-glow",
        )}
      >
        {active &&
          [0, 0.5].map((d) => (
            <span
              key={d}
              className={cn(
                "absolute h-20 w-20 rounded-full animate-pulse-ring",
                finishing ? "bg-warn/30" : "bg-danger/30",
              )}
              style={{ animationDelay: `${d}s` }}
            />
          ))}
        {busy ? (
          <Loader2 className="h-7 w-7 animate-spin" />
        ) : locked && !active ? (
          <MicOff className="h-7 w-7" />
        ) : (
          <Mic className="h-7 w-7" />
        )}
      </motion.button>
      <span className={cn("text-xs", locked && !active ? "text-warn" : "text-ink-muted")}>{hint}</span>
    </div>
  );
}
