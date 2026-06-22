"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { LiveTranscript, type Turn } from "./LiveTranscript";

/** Slide-in transcript panel for the candidate room (optional, toggled from the dock). */
export function TranscriptDrawer({
  open,
  onClose,
  turns,
  partial,
  recording,
}: {
  open: boolean;
  onClose: () => void;
  turns: Turn[];
  partial?: string;
  recording?: boolean;
}) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            className="glass fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col p-5"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Live transcript</h3>
              <button onClick={onClose} className="rounded-full p-1.5 text-ink-muted hover:bg-white/10 hover:text-ink">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <LiveTranscript turns={turns} />
              {recording && partial && (
                <p className="mt-3 border-l-2 border-accent/50 pl-3 text-sm italic text-ink-muted">
                  {partial}
                  <span className="ml-1 animate-pulse">…</span>
                </p>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
