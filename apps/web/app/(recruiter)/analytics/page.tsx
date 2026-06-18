"use client";

import { useEffect, useState } from "react";
import { api, type AnalyticsOverview } from "@/lib/api";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { TrendChart, SkillRadar } from "@/components/dashboard/Charts";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsOverview | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("hv_token") ?? "";
    api.overview(token).then(setData).catch(console.error);
  }, []);

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-1 text-2xl font-bold text-ink">Analytics</h1>
      <p className="mb-6 text-sm text-ink-muted">Hiring metrics and performance trends.</p>

      {data && (
        <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-5">
          <KpiCard label="Total" value={data.total_interviews} delay={0} />
          <KpiCard label="Candidates" value={data.total_candidates} delay={0.05} />
          <KpiCard label="Avg score" value={data.average_score ?? 0} suffix="/10" delay={0.1} />
          <KpiCard label="Recommended" value={data.recommended_hires} delay={0.15} />
          <KpiCard label="Conversion" value={data.conversion_rate} suffix="%" delay={0.2} />
        </div>
      )}

      {!data && (
        <p className="mb-6 text-sm text-ink-muted">Loading metrics…</p>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <div className="glass-card p-5">
          <h3 className="mb-3 text-sm font-semibold text-ink">Score trend</h3>
          <TrendChart />
        </div>
        <div className="glass-card p-5">
          <h3 className="mb-3 text-sm font-semibold text-ink">Skill breakdown</h3>
          <SkillRadar />
        </div>
      </div>
    </div>
  );
}
