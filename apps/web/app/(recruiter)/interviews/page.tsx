"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

type Interview = {
  id: string;
  role_title: string;
  status: string;
  candidate_name: string;
  created_at: string;
  overall_score?: number;
  recommendation?: string;
};

export default function InterviewsPage() {
  const router = useRouter();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("hv_token") ?? "";
    api
      .listInterviews(token)
      .then((data) => setInterviews(data as Interview[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">Interviews</h1>
          <p className="text-sm text-ink-muted">Manage and track all candidate interviews.</p>
        </div>
        <Link href="/interviews/new">
          <Button>+ New interview</Button>
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : interviews.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <p className="text-ink-muted mb-4">No interviews yet.</p>
          <Link href="/interviews/new">
            <Button>Create your first interview</Button>
          </Link>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wider text-ink-muted">
              <tr>
                <th className="px-5 py-3">Candidate</th>
                <th className="px-5 py-3">Role</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Score</th>
                <th className="px-5 py-3">Rec</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {interviews.map((iv, i) => (
                <motion.tr
                  key={iv.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-white/5"
                  onClick={() => router.push(`/interviews/${iv.id}`)}
                >
                  <td className="px-5 py-3 font-medium">{iv.candidate_name}</td>
                  <td className="px-5 py-3 text-ink-muted">{iv.role_title}</td>
                  <td className="px-5 py-3">
                    <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs capitalize">
                      {iv.status}
                    </span>
                  </td>
                  <td className="px-5 py-3">{iv.overall_score ?? "—"}</td>
                  <td className="px-5 py-3">
                    {iv.recommendation ? (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs text-success capitalize">
                        {iv.recommendation}
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
