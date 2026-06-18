"use client";

import { motion } from "framer-motion";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TrendChart, SkillRadar } from "@/components/dashboard/Charts";

const FUNNEL = [
  { label: "Invited", value: 128, pct: 100 },
  { label: "Completed", value: 96, pct: 75 },
  { label: "Recommended", value: 34, pct: 27 },
  { label: "Hired", value: 21, pct: 16 },
];

const RECENT = [
  { name: "Alice Chen", role: "Backend Engineer", score: 8.4, rec: "Hire" },
  { name: "Pranit Raj", role: "Full-stack / AI", score: 7.8, rec: "Maybe" },
  { name: "Maria Gomez", role: "Platform Engineer", score: 9.1, rec: "Strong hire" },
];

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-2xl font-bold text-ink">Overview</h1>
      <p className="mb-6 text-sm text-ink-muted">Your hiring pipeline at a glance.</p>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KpiCard label="Interviews" value={128} delay={0} />
        <KpiCard label="Candidates" value={96} delay={0.05} />
        <KpiCard label="Avg score" value={7.8} suffix="/10" delay={0.1} />
        <KpiCard label="Recommended" value={34} delay={0.15} />
        <KpiCard label="Conversion" value={27} suffix="%" delay={0.2} />
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <div className="glass-card p-5">
          <h3 className="mb-3 text-sm font-semibold text-ink">Score trend</h3>
          <TrendChart />
        </div>
        <div className="glass-card p-5">
          <h3 className="mb-3 text-sm font-semibold text-ink">Skill breakdown</h3>
          <SkillRadar />
        </div>
      </div>

      <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        {/* Funnel */}
        <div className="glass-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-ink">Hiring funnel</h3>
          <div className="flex flex-col gap-3">
            {FUNNEL.map((f, i) => (
              <div key={f.label}>
                <div className="mb-1 flex justify-between text-xs text-ink-muted">
                  <span>{f.label}</span><span className="text-ink">{f.value}</span>
                </div>
                <motion.div
                  className="h-2.5 rounded-full accent-gradient"
                  initial={{ width: 0 }} animate={{ width: `${f.pct}%` }}
                  transition={{ delay: i * 0.08, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Recent */}
        <div className="glass-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-ink">Recent candidates</h3>
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wider text-ink-muted">
              <tr><th className="pb-2">Name</th><th className="pb-2">Role</th><th className="pb-2">Score</th><th className="pb-2">Rec</th></tr>
            </thead>
            <tbody className="text-ink">
              {RECENT.map((r) => (
                <tr key={r.name} className="border-t border-border">
                  <td className="py-2.5 font-medium">{r.name}</td>
                  <td className="py-2.5 text-ink-muted">{r.role}</td>
                  <td className="py-2.5">{r.score}</td>
                  <td className="py-2.5">
                    <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success">{r.rec}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
