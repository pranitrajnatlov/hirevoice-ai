"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import Cookies from "js-cookie";

export default function NewInterviewPage() {
  const router = useRouter();
  const [step, setStep] = useState<"form" | "done">("form");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [meetingUrl, setMeetingUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const [form, setForm] = useState({
    role_title: "",
    candidate_name: "",
    candidate_email: "",
    job_description: "",
  });

  const set =
    (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const token = Cookies.get("hv_token") ?? "";
      const fd = new FormData();
      fd.append("role_title", form.role_title);
      fd.append("candidate_name", form.candidate_name);
      fd.append("candidate_email", form.candidate_email);
      if (form.job_description) fd.append("job_description", form.job_description);
      const file = fileRef.current?.files?.[0];
      if (file) fd.append("resume", file);
      const result = await api.createInterview(fd, token);
      setMeetingUrl(result.meeting_url);
      setStep("done");
    } catch (e) {
      // 401s redirect to login via the API client; show the real reason otherwise.
      const msg = e instanceof ApiError && e.status >= 500
        ? "The server hit an error creating the interview. Check that the gateway and AI service are running."
        : "Couldn't create the interview. Please try again.";
      setErr(msg);
    } finally {
      setLoading(false);
    }
  };

  const copy = () => {
    navigator.clipboard.writeText(meetingUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (step === "done") {
    return (
      <div className="mx-auto max-w-lg">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-8 text-center"
        >
          <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-success/20 text-3xl">
            ✓
          </div>
          <h2 className="mb-2 text-xl font-bold text-ink">Interview created!</h2>
          <p className="mb-6 text-sm text-ink-muted">
            Share this link with your candidate to start the AI interview.
          </p>
          <div className="mb-6 flex items-center gap-2 rounded-xl bg-white/5 px-4 py-3 text-sm font-mono text-ink">
            <span className="flex-1 truncate text-left">{meetingUrl}</span>
            <Button size="sm" variant="secondary" onClick={copy}>
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>
          <div className="flex justify-center gap-3">
            <Button
              variant="secondary"
              onClick={() => {
                setStep("form");
                setForm({ role_title: "", candidate_name: "", candidate_email: "", job_description: "" });
              }}
            >
              New interview
            </Button>
            <Button onClick={() => router.push("/interviews")}>View all interviews</Button>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg">
      <h1 className="mb-1 text-2xl font-bold text-ink">New Interview</h1>
      <p className="mb-6 text-sm text-ink-muted">
        Fill in the details — we&apos;ll generate a meeting link to share with your candidate.
      </p>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-8"
      >
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
              Role Title *
            </span>
            <input
              value={form.role_title}
              onChange={set("role_title")}
              required
              placeholder="e.g. Backend Engineer"
              className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
              Candidate Name *
            </span>
            <input
              value={form.candidate_name}
              onChange={set("candidate_name")}
              required
              placeholder="Full name"
              className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
              Candidate Email *
            </span>
            <input
              type="email"
              value={form.candidate_email}
              onChange={set("candidate_email")}
              required
              placeholder="candidate@company.com"
              className="h-11 rounded-xl glass px-4 text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
              Job Description (optional)
            </span>
            <textarea
              value={form.job_description}
              onChange={set("job_description")}
              rows={3}
              placeholder="Describe the role and what you're looking for…"
              className="resize-none rounded-xl glass px-4 py-3 text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-ink-muted">
              Resume (optional)
            </span>
            <input
              type="file"
              ref={fileRef}
              accept=".pdf,.docx,.txt"
              className="text-sm text-ink-muted file:mr-3 file:rounded-lg file:border-0 file:bg-accent/20 file:px-3 file:py-1.5 file:text-xs file:text-accent"
            />
          </label>

          {err && <p className="text-sm text-danger">{err}</p>}

          <Button type="submit" size="lg" disabled={loading} className="mt-2">
            {loading ? "Creating…" : "Create interview & get link"}
          </Button>
        </form>
      </motion.div>
    </div>
  );
}
