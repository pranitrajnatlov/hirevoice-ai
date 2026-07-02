"use client";

import { motion } from "framer-motion";

export interface Turn { role: "interviewer" | "candidate"; text: string }

export function LiveTranscript({ turns }: { turns: Turn[] }) {
  return (
    <div className="flex max-h-64 flex-col gap-3 overflow-y-auto pr-1">
      {turns.length === 0 && (
        <p className="text-sm text-ink-muted">Your conversation will appear here…</p>
      )}
      {turns.map((t, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: t.role === "candidate" ? 16 : -16 }}
          animate={{ opacity: 1, x: 0 }}
          className={t.role === "candidate" ? "self-end text-right" : "self-start"}
        >
          <span className="mb-0.5 block text-[10px] uppercase tracking-wider text-ink-muted">
            {t.role}
          </span>
          <span
            className={
              "inline-block max-w-xs rounded-2xl px-3.5 py-2 text-sm " +
              (t.role === "candidate" ? "bg-accent/20 text-ink" : "glass text-ink")
            }
          >
            {t.text}
          </span>
        </motion.div>
      ))}
    </div>
  );
}
