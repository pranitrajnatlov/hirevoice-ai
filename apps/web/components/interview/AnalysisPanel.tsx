"use client";

import { motion } from "framer-motion";

export interface Scores {
  communication: number;
  technical: number;
  confidence: number;
  alignment: number;
  keyword: number;
}

const ROWS: { key: keyof Scores; label: string }[] = [
  { key: "communication", label: "Communication" },
  { key: "technical", label: "Technical accuracy" },
  { key: "confidence", label: "Confidence" },
  { key: "alignment", label: "Resume alignment" },
  { key: "keyword", label: "Keyword match" },
];

export function AnalysisPanel({ scores }: { scores: Scores }) {
  return (
    <div className="flex flex-col gap-3.5">
      <h3 className="text-sm font-semibold text-ink">Live AI Analysis</h3>
      {ROWS.map(({ key, label }) => {
        const v = Math.round(scores[key]);
        return (
          <div key={key}>
            <div className="mb-1 flex justify-between text-xs text-ink-muted">
              <span>{label}</span>
              <span className="font-semibold text-ink">{v}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/5">
              <motion.div
                className="score-fill h-full rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${v}%` }}
                transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
