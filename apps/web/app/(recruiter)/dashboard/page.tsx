"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api, type AnalyticsOverview } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TrendChart, SkillRadar } from "@/components/dashboard/Charts";
import Cookies from "js-cookie";

const FUNNEL_KEYS = [
  { label: "Invited", key: "total_interviews" },
  { label: "Completed", key: "completed" },
  { label: "Recommended", key: "recommended_hires" },
] as const;

export default function DashboardPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    const token = Cookies.get("hv_token") ?? "";
    api.overview(token).then(setData).catch(console.error);
  }, []);

  const total = data?.total_interviews ?? 0;

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-2xl font-bold text-ink">Overview</h1>
      <p className="mb-6 text-sm text-ink-muted">Your hiring pipeline at a glance.</p>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <KpiCard label="Interviews" value={data?.total_interviews ?? 0} delay={0} />
        <KpiCard label="Candidates" value={data?.total_candidates ?? 0} delay={0.05} />
        <KpiCard label="Avg score" value={data?.average_score ?? 0} suffix="/10" delay={0.1} />
        <KpiCard label="Recommended" value={data?.recommended_hires ?? 0} delay={0.15} />
        <KpiCard label="Conversion" value={data?.conversion_rate ?? 0} suffix="%" delay={0.2} />
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

      <div className="mt-6">
        <div className="glass-card p-5">
          <h3 className="mb-4 text-sm font-semibold text-ink">Hiring funnel</h3>
          <div className="flex flex-col gap-3">
            {FUNNEL_KEYS.map((f, i) => {
              const val = data?.[f.key as keyof AnalyticsOverview] as number ?? 0;
              const pct = total > 0 ? Math.round((val / total) * 100) : 0;
              return (
                <div key={f.label}>
                  <div className="mb-1 flex justify-between text-xs text-ink-muted">
                    <span>{f.label}</span>
                    <span className="text-ink">{val}</span>
                  </div>
                  <motion.div
                    className="h-2.5 rounded-full accent-gradient"
                    initial={{ width: 0 }}
                    animate={{ width: `${pct}%` }}
                    transition={{ delay: i * 0.08, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                  />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
