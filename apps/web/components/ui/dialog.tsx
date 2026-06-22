"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";

/**
 * Lightweight modal / right-side drawer (no external dep). Portal + overlay + framer-motion,
 * Esc-to-close, scroll-locked body. Matches the glass design tokens.
 */
export function Dialog({
  open,
  onClose,
  title,
  children,
  variant = "drawer",
}: {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  variant?: "drawer" | "modal";
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  if (typeof document === "undefined") return null;

  const panelMotion =
    variant === "drawer"
      ? { initial: { x: "100%" }, animate: { x: 0 }, exit: { x: "100%" } }
      : { initial: { y: 20, opacity: 0, scale: 0.98 }, animate: { y: 0, opacity: 1, scale: 1 }, exit: { y: 20, opacity: 0 } };

  const panelClass =
    variant === "drawer"
      ? "glass fixed right-0 top-0 z-[70] flex h-full w-full max-w-lg flex-col p-6"
      : "glass-card fixed left-1/2 top-1/2 z-[70] flex max-h-[85vh] w-[92vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 flex-col p-6";

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className={panelClass}
            {...panelMotion}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            role="dialog"
            aria-modal="true"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-semibold text-ink">{title}</h2>
              <button onClick={onClose} className="rounded-full p-1.5 text-ink-muted hover:bg-white/10 hover:text-ink">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto pr-1">{children}</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body,
  );
}
