"use client";

import { motion } from "framer-motion";
import { Mic, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function MicButton({
  recording,
  busy,
  finishing = false,
  onPress,
  onRelease,
}: {
  recording: boolean;
  busy: boolean;
  /** Grace period after release — still capturing trailing speech. */
  finishing?: boolean;
  onPress: () => void;
  onRelease: () => void;
}) {
  const active = recording || finishing;
  return (
    <div className="flex flex-col items-center gap-2">
      <motion.button
        disabled={busy}
        onPointerDown={onPress}
        onPointerUp={onRelease}
        onPointerLeave={() => recording && onRelease()}
        whileTap={{ scale: 0.94 }}
        className={cn(
          "relative grid h-20 w-20 place-items-center rounded-full text-white transition-colors",
          "disabled:opacity-50",
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
        {busy ? <Loader2 className="h-7 w-7 animate-spin" /> : <Mic className="h-7 w-7" />}
      </motion.button>
      <span className="text-xs text-ink-muted">
        {busy ? "Processing…" : finishing ? "Finishing…" : recording ? "Release to send" : "Hold to speak"}
      </span>
    </div>
  );
}
