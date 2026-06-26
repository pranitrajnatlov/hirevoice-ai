"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { api } from "@/lib/api";
import Cookies from "js-cookie";

type Row = {
  id: string;
  candidate_id?: string;
  candidate_name: string;
  candidate_email?: string | null;
  role_title: string;
  status: string;
  overall_score?: number | null;
  recommendation?: string | null;
  created_at: string;
};

type Person = {
  candidateId: string;
  name: string;
  email: string | null;
  count: number;
  latestRole: string;
  latestStatus: string;
  latestId: string;
  bestScore: number | null;
  recommendation: string | null;
};

const REC_COLOR: Record<string, string> = {
  strong_hire: "text-emerald-400 bg-emerald-400/10",
  hire: "text-success bg-success/15",
  maybe: "text-warn bg-warn/10",
  no_hire: "text-danger bg-danger/10",
};

/** Collapse interview rows into one entry per unique candidate. */
function groupByCandidate(rows: Row[]): Person[] {
  const map = new Map<string, Row[]>();
  for (const r of rows) {
    const key = r.candidate_id || `${r.candidate_name}|${r.candidate_email ?? ""}`;
    (map.get(key) ?? map.set(key, []).get(key)!).push(r);
  }
  const people: Person[] = [];
  for (const [key, list] of map) {
    const sorted = [...list].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at));
    const latest = sorted[0];
    const scores = list.map((r) => r.overall_score).filter((s): s is number => s != null);
    const rec = sorted.find((r) => r.recommendation)?.recommendation ?? null;
    people.push({
      candidateId: key,
      name: latest.candidate_name,
      email: latest.candidate_email ?? null,
      count: list.length,
      latestRole: latest.role_title,
      latestStatus: latest.status,
      latestId: latest.id,
      bestScore: scores.length ? Math.max(...scores) : null,
      recommendation: rec,
    });
  }
  return people.sort((a, b) => a.name.localeCompare(b.name));
}

export default function CandidatesPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");

  useEffect(() => {
    const token = Cookies.get("hv_token") ?? "";
    api
      .listInterviews(token)
      .then((data) => setRows(data as Row[]))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const people = useMemo(() => groupByCandidate(rows), [rows]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return people;
    return people.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        (p.email ?? "").toLowerCase().includes(q) ||
        p.latestRole.toLowerCase().includes(q),
    );
  }, [people, query]);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-ink">Candidates</h1>
          <p className="text-sm text-ink-muted">
            {people.length} {people.length === 1 ? "person" : "people"} across your interviews.
          </p>
        </div>
        {people.length > 0 && (
          <div className="flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
            <Search className="h-4 w-4 text-ink-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, email, role…"
              className="w-56 bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
            />
          </div>
        )}
      </div>

      {loading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : people.length === 0 ? (
        <div className="glass-card p-12 text-center text-ink-muted">
          No candidates yet. Create an interview to get started.
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wider text-ink-muted">
              <tr>
                <th className="px-5 py-3">Candidate</th>
                <th className="px-5 py-3">Interviews</th>
                <th className="px-5 py-3">Latest role</th>
                <th className="px-5 py-3">Best score</th>
                <th className="px-5 py-3">Recommendation</th>
              </tr>
            </thead>
            <tbody className="text-ink">
              {filtered.map((p, i) => (
                <motion.tr
                  key={p.candidateId}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: i * 0.03 }}
                  onClick={() => router.push(`/interviews/${p.latestId}`)}
                  className="cursor-pointer border-b border-border last:border-0 hover:bg-white/5"
                >
                  <td className="px-5 py-3">
                    <div className="font-medium">{p.name}</div>
                    {p.email && <div className="text-xs text-ink-muted">{p.email}</div>}
                  </td>
                  <td className="px-5 py-3 text-ink-muted">
                    {p.count} {p.count === 1 ? "interview" : "interviews"}
                  </td>
                  <td className="px-5 py-3 text-ink-muted">{p.latestRole}</td>
                  <td className="px-5 py-3">{p.bestScore != null ? `${p.bestScore}/10` : "—"}</td>
                  <td className="px-5 py-3">
                    {p.recommendation ? (
                      <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${REC_COLOR[p.recommendation] ?? "bg-white/10 text-ink-muted"}`}>
                        {p.recommendation.replace("_", " ")}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                </motion.tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-sm text-ink-muted">
                    No candidates match "{query}".
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
