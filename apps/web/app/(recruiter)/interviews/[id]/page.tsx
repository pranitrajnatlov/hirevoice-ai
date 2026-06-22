"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { api, type TranscriptTurn } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { TranscriptViewer } from "@/components/interview/TranscriptViewer";

type Assessment = {
  overall_score: number;
  technical_score: number;
  communication_score: number;
  culture_fit_score: number;
  problem_solving_score?: number | null;
  experience_relevance_score?: number | null;
  confidence_score?: number | null;
  resume_consistency_score?: number | null;
  recommendation: string;
  strengths: string[];
  weaknesses: string[];
  summary: string;
  evidence?: Record<string, string[]>;
  unsupported_scores?: string[];
};

const EVIDENCE_LABELS: Record<string, string> = {
  technical: "Technical",
  communication: "Communication",
  problem_solving: "Problem solving",
  experience_relevance: "Experience relevance",
  confidence: "Confidence",
  resume_consistency: "Resume consistency",
};

type Interview = {
  id: string;
  role_title: string;
  status: string;
  job_description: string;
  meeting_token: string | null;
  meeting_url: string | null;
  candidate: { id: string; name: string; email: string };
  assessment: Assessment | null;
};

const REC_COLOR: Record<string, string> = {
  strong_hire: "text-emerald-400 bg-emerald-400/10",
  hire: "text-green-400 bg-green-400/10",
  maybe: "text-yellow-400 bg-yellow-400/10",
  no_hire: "text-red-400 bg-red-400/10",
  pending: "text-ink-muted bg-white/5",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span className="text-ink-muted">{label}</span>
        <span className="text-ink font-medium">{value}/10</span>
      </div>
      <div className="h-2 rounded-full bg-white/10">
        <motion.div
          className="h-full rounded-full accent-gradient"
          initial={{ width: 0 }}
          animate={{ width: `${value * 10}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  );
}

export default function InterviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [transcript, setTranscript] = useState<TranscriptTurn[] | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("hv_token") ?? "";
    api
      .getInterview(id, token)
      .then((d) => setInterview(d as unknown as Interview))
      .catch(() => router.push("/interviews"))
      .finally(() => setLoading(false));
  }, [id, router]);

  const openFullAnalysis = () => {
    setDrawerOpen(true);
    if (transcript === null) {
      const token = localStorage.getItem("hv_token") ?? "";
      api.getTranscript(id, token).then((d) => setTranscript(d.turns)).catch(() => setTranscript([]));
    }
  };

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) return <div className="text-sm text-ink-muted">Loading…</div>;
  if (!interview) return null;

  const { candidate, assessment } = interview;
  const recLabel = interview.assessment?.recommendation ?? "pending";
  const recClass = REC_COLOR[recLabel] ?? REC_COLOR.pending;

  return (
    <div className="mx-auto max-w-4xl">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link href="/interviews" className="mb-2 inline-block text-xs text-ink-muted hover:text-ink">
            ← Back to interviews
          </Link>
          <h1 className="text-2xl font-bold text-ink">{interview.role_title}</h1>
          <p className="text-sm text-ink-muted">{candidate.name} · {candidate.email}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${recClass}`}>
          {recLabel.replace("_", " ")}
        </span>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        {/* Left column */}
        <div className="flex flex-col gap-5">
          {/* Status card */}
          <div className="glass-card p-5">
            <h3 className="mb-3 text-sm font-semibold text-ink">Interview info</h3>
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-ink-muted">Status</dt>
                <dd className="capitalize text-ink">{interview.status}</dd>
              </div>
              {interview.job_description && (
                <div className="flex flex-col gap-1">
                  <dt className="text-ink-muted">Job description</dt>
                  <dd className="text-ink text-xs leading-relaxed">{interview.job_description}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Meeting link */}
          {interview.meeting_url && (
            <div className="glass-card p-5">
              <h3 className="mb-3 text-sm font-semibold text-ink">Interview link</h3>
              <p className="mb-3 text-xs text-ink-muted">Share with the candidate to start the AI interview.</p>
              <div className="flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2.5 text-xs font-mono text-ink">
                <span className="flex-1 truncate">{interview.meeting_url}</span>
                <Button size="sm" variant="secondary" onClick={() => copy(interview.meeting_url!)}>
                  {copied ? "Copied!" : "Copy"}
                </Button>
              </div>
              <Link
                href={`/interview/${interview.meeting_token}`}
                target="_blank"
                className="mt-2 inline-block text-xs text-accent hover:underline"
              >
                Open as candidate →
              </Link>
            </div>
          )}

          {/* Scores */}
          {assessment && (
            <div className="glass-card p-5">
              <h3 className="mb-4 text-sm font-semibold text-ink">Scores</h3>
              <div className="flex flex-col gap-3">
                <ScoreBar label="Overall" value={assessment.overall_score} />
                <ScoreBar label="Technical" value={assessment.technical_score} />
                <ScoreBar label="Communication" value={assessment.communication_score} />
                {assessment.problem_solving_score != null && (
                  <ScoreBar label="Problem solving" value={assessment.problem_solving_score} />
                )}
                {assessment.experience_relevance_score != null && (
                  <ScoreBar label="Experience relevance" value={assessment.experience_relevance_score} />
                )}
                {assessment.confidence_score != null && (
                  <ScoreBar label="Confidence" value={assessment.confidence_score} />
                )}
                {assessment.resume_consistency_score != null && (
                  <ScoreBar label="Resume consistency" value={assessment.resume_consistency_score} />
                )}
                <ScoreBar label="Culture fit" value={assessment.culture_fit_score} />
              </div>
            </div>
          )}
        </div>

        {/* Right column — assessment (bounded; full content opens in the drawer, spec #5) */}
        {assessment ? (
          <div className="flex flex-col gap-5">
            <div className="glass-card p-5">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-ink">Summary</h3>
                <Button size="sm" variant="secondary" onClick={openFullAnalysis}>
                  View full analysis
                </Button>
              </div>
              <p className="line-clamp-4 text-sm leading-relaxed text-ink-muted">
                {assessment.summary || "No summary available."}
              </p>
            </div>

            <div className="glass-card p-5">
              <h3 className="mb-3 text-sm font-semibold text-ink">Strengths</h3>
              <ul className="flex max-h-48 flex-col gap-2 overflow-y-auto pr-1">
                {assessment.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink">
                    <span className="mt-0.5 text-success">✓</span> {s}
                  </li>
                ))}
              </ul>
            </div>

            <div className="glass-card p-5">
              <h3 className="mb-3 text-sm font-semibold text-ink">Areas to improve</h3>
              <ul className="flex max-h-48 flex-col gap-2 overflow-y-auto pr-1">
                {assessment.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink-muted">
                    <span className="mt-0.5 text-danger">·</span> {w}
                  </li>
                ))}
              </ul>
            </div>

            {assessment.unsupported_scores && assessment.unsupported_scores.length > 0 && (
              <p className="rounded-lg bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
                ⚠ Scores without transcript evidence: {assessment.unsupported_scores.map((d) => EVIDENCE_LABELS[d] ?? d).join(", ")}
              </p>
            )}
          </div>
        ) : (
          <div className="glass-card flex flex-col items-center justify-center p-12 text-center">
            <p className="text-ink-muted">Assessment not yet available.</p>
            <p className="mt-1 text-xs text-ink-muted">
              {interview.status === "invited"
                ? "Candidate hasn't joined the interview yet."
                : "Assessment will appear here once the interview is complete."}
            </p>
          </div>
        )}
      </div>

      {/* Full analysis drawer (spec #5, #6) */}
      <Dialog open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Full analysis" variant="drawer">
        {assessment && (
          <div className="flex flex-col gap-6">
            {assessment.summary && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-ink">Summary</h3>
                <p className="text-sm leading-relaxed text-ink-muted">{assessment.summary}</p>
              </section>
            )}

            {assessment.strengths.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-ink">Strengths</h3>
                <ul className="flex flex-col gap-1.5">
                  {assessment.strengths.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-ink">
                      <span className="mt-0.5 text-success">✓</span> {s}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {assessment.weaknesses.length > 0 && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-ink">Areas to improve</h3>
                <ul className="flex flex-col gap-1.5">
                  {assessment.weaknesses.map((w, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-ink-muted">
                      <span className="mt-0.5 text-danger">·</span> {w}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {assessment.evidence && Object.keys(assessment.evidence).length > 0 && (
              <section>
                <h3 className="mb-1 text-sm font-semibold text-ink">Evidence</h3>
                <p className="mb-2 text-xs text-ink-muted">Transcript quotes backing each score.</p>
                <div className="flex flex-col gap-3">
                  {Object.entries(assessment.evidence).map(([dim, quotes]) => (
                    <div key={dim}>
                      <p className="mb-1 text-xs font-medium text-ink">{EVIDENCE_LABELS[dim] ?? dim}</p>
                      <ul className="flex flex-col gap-1">
                        {quotes.map((q, i) => (
                          <li key={i} className="border-l-2 border-accent/40 pl-3 text-xs italic text-ink-muted">
                            “{q}”
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h3 className="mb-2 text-sm font-semibold text-ink">Transcript</h3>
              {transcript === null ? (
                <p className="text-sm text-ink-muted">Loading transcript…</p>
              ) : (
                <TranscriptViewer turns={transcript} />
              )}
            </section>
          </div>
        )}
      </Dialog>
    </div>
  );
}
