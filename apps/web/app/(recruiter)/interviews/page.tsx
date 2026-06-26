"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import Cookies from "js-cookie";

type Interview = {
  id: string;
  role_title: string;
  status: string;
  candidate_name: string;
  created_at: string;
  overall_score?: number;
  recommendation?: string;
};

const STATUS_COLOR: Record<string, string> = {
  invited: "bg-white/10 text-ink-muted",
  in_progress: "bg-secondary/15 text-secondary",
  completed: "bg-success/15 text-success",
};

function fmtDate(iso: string): string {
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "—" : d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

export default function InterviewsPage() {
  const router = useRouter();
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const token = Cookies.get("hv_token") ?? "";
    api
      .listInterviews(token)
      .then((data) => setInterviews(data as Interview[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return interviews;
    return interviews.filter(
      (iv) =>
        iv.candidate_name.toLowerCase().includes(q) ||
        iv.role_title.toLowerCase().includes(q) ||
        iv.status.toLowerCase().includes(q),
    );
  }, [interviews, query]);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Interviews</h1>
          <p className="text-sm text-ink-muted">Every interview session, most recent first.</p>
        </div>
        <div className="flex items-center gap-3">
          {interviews.length > 0 && (
            <div className="flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
              <Search className="h-4 w-4 text-ink-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search candidate, role, status…"
                className="w-48 bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
              />
            </div>
          )}
          <Link href="/interviews/new">
            <Button>+ New interview</Button>
          </Link>
        </div>
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
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Score</th>
                <th className="px-5 py-3">Rec</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {filtered.map((iv, i) => (
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
                  <td className="px-5 py-3 text-ink-muted">{fmtDate(iv.created_at)}</td>
                  <td className="px-5 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${STATUS_COLOR[iv.status] ?? "bg-white/10 text-ink-muted"}`}>
                      {iv.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-5 py-3">{iv.overall_score ?? "—"}</td>
                  <td className="px-5 py-3">
                    {iv.recommendation ? (
                      <span className="rounded-full bg-success/15 px-2 py-0.5 text-xs capitalize text-success">
                        {iv.recommendation.replace("_", " ")}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </motion.tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-center text-sm text-ink-muted">
                    No interviews match "{query}".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
