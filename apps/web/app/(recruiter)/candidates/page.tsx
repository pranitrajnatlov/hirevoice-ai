"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

type Row = {
  id: string;
  candidate_name: string;
  role_title: string;
  status: string;
  overall_score?: number;
  recommendation?: string;
  created_at: string;
};

export default function CandidatesPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("hv_token") ?? "";
    api
      .listInterviews(token)
      .then((data) => setRows(data as Row[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-1 text-2xl font-bold text-ink">Candidates</h1>
      <p className="mb-6 text-sm text-ink-muted">All candidates across your interviews.</p>

      {loading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <div className="glass-card p-12 text-center text-ink-muted">
          No candidates yet. Create an interview to get started.
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wider text-ink-muted">
              <tr>
                <th className="px-5 py-3">Name</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Score</th>
                <th className="px-5 py-3">Recommendation</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {rows.map((r, i) => (
                <motion.tr
                  key={r.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.04 }}
                  className="border-b border-border last:border-0 hover:bg-white/5"
                >
                  <td className="px-5 py-3 font-medium">{r.candidate_name}</td>
                  <td className="px-5 py-3 text-ink-muted">{r.role_title}</td>
                  <td className="px-5 py-3">
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs capitalize">
                      {r.status}
                    </span>
                  </td>
                  <td className="px-5 py-3">{r.overall_score ?? "—"}</td>
                  <td className="px-5 py-3">
                    {r.recommendation ? (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success capitalize">
                        {r.recommendation.replace("_", " ")}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
