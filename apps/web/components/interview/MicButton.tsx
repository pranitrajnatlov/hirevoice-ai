"use client";

import { motion } from "framer-motion";
import { Mic, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function MicButton({
  recording,
  busy,
  onPress,
  onRelease,
}: {
  recording: boolean;
  busy: boolean;
  onPress: () => void;
  onRelease: () => void;
}) {
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
          recording ? "bg-danger" : "accent-gradient shadow-glow",
        )}
      >
        {recording &&
          [0, 0.5].map((d) => (
            <span key={d} className="absolute h-20 w-20 rounded-full bg-danger/30 animate-pulse-ring"
              style={{ animationDelay: `${d}s` }} />
          ))}
        {busy ? <Loader2 className="h-7 w-7 animate-spin" /> : <Mic className="h-7 w-7" />}
      </motion.button>
      <span className="text-xs text-ink-muted">
        {busy ? "Processing…" : recording ? "Release to send" : "Hold to speak"}
      </span>
    </div>
  );
}
