"use client";

import { motion, AnimatePresence } from "framer-motion";

export function QuestionCard({ text, stage }: { text: string; stage: string }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={text}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -12 }}
        transition={{ duration: 0.35 }}
        className="text-center"
      >
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-accent">{stage}</div>
        <p className="mx-auto max-w-xl text-lg leading-relaxed text-ink">{text}</p>
      </motion.div>
    </AnimatePresence>
  );
}
