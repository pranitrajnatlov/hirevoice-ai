"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export type AvatarState = "idle" | "speaking" | "listening" | "thinking";

const labels: Record<AvatarState, string> = {
  idle: "Ready",
  speaking: "Speaking",
  listening: "Listening",
  thinking: "Thinking",
};

export function AiAvatar({ state }: { state: AvatarState }) {
  return (
    <div className="relative grid place-items-center" style={{ width: 200, height: 200 }}>
      {/* Pulsing rings while active */}
      {(state === "speaking" || state === "listening") &&
        [0, 0.6].map((delay) => (
          <span
            key={delay}
            className={cn(
              "absolute h-40 w-40 rounded-full animate-pulse-ring",
              state === "listening" ? "bg-secondary/20" : "bg-accent/20",
            )}
            style={{ animationDelay: `${delay}s` }}
          />
        ))}

      {/* Core orb */}
      <motion.div
        className="relative grid h-40 w-40 place-items-center rounded-full accent-gradient shadow-glow"
        animate={
          state === "speaking"
            ? { scale: [1, 1.06, 0.98, 1.04, 1] }
            : state === "idle"
              ? { scale: [1, 1.04, 1] }
              : { scale: 1 }
        }
        transition={{
          duration: state === "speaking" ? 0.8 : 4,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* Inner mark */}
        <div className="grid h-24 w-24 place-items-center rounded-full bg-bg/40 backdrop-blur-xs">
          {state === "thinking" ? (
            <div className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="h-2.5 w-2.5 rounded-full bg-white"
                  animate={{ opacity: [0.3, 1, 0.3], y: [0, -4, 0] }}
                  transition={{ duration: 1, repeat: Infinity, delay: i * 0.18 }}
                />
              ))}
            </div>
          ) : (
            <span className="text-3xl">🎙️</span>
          )}
        </div>
      </motion.div>

      <span className="absolute -bottom-2 rounded-full glass px-3 py-1 text-xs font-medium text-ink-muted">
        {labels[state]}
      </span>
    </div>
  );
}
