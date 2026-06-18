"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export function KpiCard({
  label, value, suffix = "", delay = 0,
}: { label: string; value: number; suffix?: string; delay?: number }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    const start = performance.now();
    const dur = 900;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(value * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  const display = Number.isInteger(value) ? Math.round(n).toString() : n.toFixed(1);
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass-card p-5"
    >
      <div className="text-xs uppercase tracking-wider text-ink-muted">{label}</div>
      <div className="mt-2 text-3xl font-bold text-ink">
        {display}
        <span className="text-lg text-ink-muted">{suffix}</span>
      </div>
    </motion.div>
  );
}
