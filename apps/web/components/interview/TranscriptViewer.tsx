"use client";

import { useMemo, useState } from "react";
import { Search, Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

export interface TranscriptTurn {
  role: "interviewer" | "candidate";
  text: string;
  stage: string;
  is_followup: boolean;
  ts: string | null;
}

const COLLAPSE_AT = 320;

function fmtTs(ts: string | null): string {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function highlight(text: string, q: string) {
  if (!q) return text;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i < 0) return text;
  return (
    <>
      {text.slice(0, i)}
      <mark className="rounded bg-warn/30 text-ink">{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

function Bubble({ turn, query }: { turn: TranscriptTurn; query: string }) {
  const [open, setOpen] = useState(false);
  const isCandidate = turn.role === "candidate";
  const long = turn.text.length > COLLAPSE_AT;
  const shown = long && !open ? turn.text.slice(0, COLLAPSE_AT) + "…" : turn.text;

  return (
    <div className={cn("flex flex-col", isCandidate ? "items-end" : "items-start")}>
      <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-ink-muted">
        <span>{isCandidate ? "Candidate" : "Interviewer"}</span>
        {turn.is_followup && <span className="rounded-full bg-accent/20 px-1.5 py-0.5 text-accent">follow-up</span>}
        {turn.ts && <span className="normal-case tracking-normal">{fmtTs(turn.ts)}</span>}
      </div>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
          isCandidate ? "bg-accent/15 text-ink" : "glass text-ink",
        )}
      >
        {highlight(shown, query)}
        {long && (
          <button
            onClick={() => setOpen((o) => !o)}
            className="mt-1 flex items-center gap-1 text-xs text-accent hover:underline"
          >
            {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
            {open ? "Show less" : "Show more"}
          </button>
        )}
      </div>
    </div>
  );
}

export function TranscriptViewer({ turns }: { turns: TranscriptTurn[] }) {
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);

  const filtered = useMemo(
    () => (query ? turns.filter((t) => t.text.toLowerCase().includes(query.toLowerCase())) : turns),
    [turns, query],
  );

  const copyAll = () => {
    const text = turns
      .map((t) => `${t.role === "candidate" ? "Candidate" : "Interviewer"}: ${t.text}`)
      .join("\n\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!turns.length) {
    return <p className="text-sm text-ink-muted">No transcript yet — it appears once the candidate answers.</p>;
  }

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex flex-1 items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
          <Search className="h-4 w-4 text-ink-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search transcript…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted"
          />
        </div>
        <button
          onClick={copyAll}
          className="flex items-center gap-1.5 rounded-xl bg-white/5 px-3 py-2 text-xs text-ink-muted hover:bg-white/10 hover:text-ink"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="flex flex-col gap-3 overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <p className="text-sm text-ink-muted">No turns match "{query}".</p>
        ) : (
          filtered.map((t, i) => <Bubble key={i} turn={t} query={query} />)
        )}
      </div>
    </div>
  );
}
