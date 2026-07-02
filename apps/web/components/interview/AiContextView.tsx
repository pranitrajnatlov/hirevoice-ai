"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown, Copy, Check, Download, Printer, Code2, Search,
  Building2, FolderGit2, GraduationCap, Award, Languages as LangIcon, AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { AiContext } from "@/lib/api";

/** Confidence dot: green ≥0.85, amber ≥0.6, muted below. */
function Dot({ c }: { c?: number | null }) {
  if (c == null) return null;
  const color = c >= 0.85 ? "bg-success" : c >= 0.6 ? "bg-warn" : "bg-danger";
  return <span className={cn("inline-block h-2 w-2 rounded-full", color)} title={`Confidence ${Math.round(c * 100)}%`} />;
}

function Badge({ children, tone = "default" }: { children: React.ReactNode; tone?: "default" | "accent" | "muted" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs",
        tone === "accent" ? "bg-accent/15 text-ink" : tone === "muted" ? "bg-white/5 text-ink-muted" : "bg-white/8 text-ink",
      )}
    >
      {children}
    </span>
  );
}

function Section({ id, title, count, action, children }: {
  id: string; title: string; count?: number; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-ink-muted">
          {title} {count != null && <span className="ml-1 text-ink-muted/60">({count})</span>}
        </h3>
        {action}
      </div>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="text-sm text-ink">{value}</dd>
    </div>
  );
}

function ExperienceCard({ exp, open, onToggle }: {
  exp: AiContext["experience"][number]; open: boolean; onToggle: () => void;
}) {
  return (
    <div className="glass-card overflow-hidden">
      <button onClick={onToggle} className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-white/[0.03]">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-ink">{exp.designation || "Role"}</span>
            <Dot c={exp.confidence} />
          </div>
          <div className="truncate text-xs text-ink-muted">
            {[exp.company, exp.duration].filter(Boolean).join(" · ") || "—"}
          </div>
        </div>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-ink-muted transition-transform", open && "rotate-180")} />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }} className="overflow-hidden"
          >
            <div className="flex flex-col gap-3 border-t border-border px-4 py-3">
              {exp.technologies.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {exp.technologies.map((t) => <Badge key={t} tone="accent">{t}</Badge>)}
                </div>
              )}
              {exp.responsibilities.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {exp.responsibilities.map((r, i) => (
                    <li key={i} className="flex gap-2 text-sm text-ink-muted"><span className="text-accent">·</span>{r}</li>
                  ))}
                </ul>
              )}
              {exp.achievements.length > 0 && (
                <ul className="flex flex-col gap-1">
                  {exp.achievements.map((a, i) => (
                    <li key={i} className="flex gap-2 text-sm text-ink"><span className="text-success">✓</span>{a}</li>
                  ))}
                </ul>
              )}
              {exp.responsibilities.length === 0 && exp.technologies.length === 0 && (
                <p className="text-xs text-ink-muted">No further detail extracted for this role.</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

const match = (q: string, ...parts: (string | null | undefined)[]) =>
  !q || parts.filter(Boolean).join(" ").toLowerCase().includes(q.toLowerCase());

export function AiContextView({ data, interviewId }: { data: AiContext; interviewId: string }) {
  const [q, setQ] = useState("");
  const [openExp, setOpenExp] = useState<Set<number>>(() => new Set([0]));
  const [devView, setDevView] = useState(false);
  const [copied, setCopied] = useState(false);

  const s = data.summary;
  const hasProjects = data.projects.length > 0;
  const hasEducation = data.education.length > 0;
  const hasCerts = data.certifications.length > 0;
  const hasAwards = data.achievements.length > 0;
  const hasLangs = data.languages.length > 0;

  const navItems = useMemo(() => {
    const items = [
      { id: "summary", label: "Summary", on: true },
      { id: "experience", label: "Experience", on: data.experience.length > 0 },
      { id: "skills", label: "Skills", on: Object.keys(data.skills_by_category).length > 0 },
      { id: "projects", label: "Projects", on: hasProjects },
      { id: "education", label: "Education", on: hasEducation },
      { id: "context", label: "AI Context", on: true },
      { id: "strategy", label: "Strategy", on: true },
    ];
    return items.filter((i) => i.on);
  }, [data, hasProjects, hasEducation]);

  const filteredExp = data.experience.filter((e) =>
    match(q, e.designation, e.company, e.technologies.join(" "), e.responsibilities.join(" ")));
  const filteredProjects = data.projects.filter((p) => match(q, p.name, p.description, p.technologies.join(" ")));

  const expandAll = () => setOpenExp(new Set(data.experience.map((_, i) => i)));
  const collapseAll = () => setOpenExp(new Set());

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `ai-context-${interviewId}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const copyContext = () => {
    const lines = [
      `Candidate: ${s.name ?? "—"}`,
      s.current_role && `Current role: ${s.current_role}`,
      s.years_experience != null && `Experience: ${s.years_experience}`,
      `Skills: ${Object.values(data.skills_by_category).flat().map((x) => x.value).join(", ")}`,
      `Interview focus: ${data.interview_context.interview_focus.join(", ")}`,
      `Missing to validate: ${data.interview_context.missing_skills_to_validate.join(", ")}`,
    ].filter(Boolean);
    navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const printPdf = () => { expandAll(); setTimeout(() => window.print(), 100); };

  return (
    <div className="flex gap-6">
      {/* Sticky section nav (spec #7) */}
      <nav data-print-hide className="sticky top-6 hidden h-fit w-40 shrink-0 flex-col gap-1 lg:flex">
        {navItems.map((n) => (
          <a key={n.id} href={`#${n.id}`} className="rounded-lg px-3 py-1.5 text-sm text-ink-muted transition-colors hover:bg-white/5 hover:text-ink">
            {n.label}
          </a>
        ))}
      </nav>

      <div id="ai-context-print" className="min-w-0 flex-1">
        {/* Toolbar */}
        <div data-print-hide className="mb-5 flex flex-wrap items-center gap-2">
          <div className="flex flex-1 items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
            <Search className="h-4 w-4 text-ink-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search context…"
              className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />
          </div>
          <ToolButton onClick={expandAll}>Expand all</ToolButton>
          <ToolButton onClick={collapseAll}>Collapse all</ToolButton>
          <ToolButton onClick={copyContext}>{copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />} Copy</ToolButton>
          <ToolButton onClick={exportJson}><Download className="h-3.5 w-3.5" /> JSON</ToolButton>
          <ToolButton onClick={printPdf}><Printer className="h-3.5 w-3.5" /> PDF</ToolButton>
          <ToolButton onClick={() => setDevView((v) => !v)} active={devView}><Code2 className="h-3.5 w-3.5" /> Developer</ToolButton>
        </div>

        {devView ? (
          <pre className="glass-card max-h-[70vh] overflow-auto p-4 text-xs text-ink-muted">
            {JSON.stringify(data.raw, null, 2)}
          </pre>
        ) : (
          <div className="flex flex-col gap-8">
            {/* Metadata strip + warnings */}
            <MetaStrip meta={data.metadata} />
            {data.warnings.length > 0 && (
              <div className="flex flex-col gap-2 rounded-xl border border-warn/30 bg-warn/10 p-4">
                {data.warnings.map((w, i) => (
                  <p key={i} className="flex items-start gap-2 text-sm text-warn">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {w}
                  </p>
                ))}
              </div>
            )}

            {/* Summary */}
            <Section id="summary" title="Candidate Summary">
              <dl className="glass-card grid grid-cols-2 gap-4 p-5 sm:grid-cols-3">
                <Field label="Name" value={s.name} />
                <Field label="Experience" value={s.years_experience != null ? String(s.years_experience) : null} />
                <Field label="Current role" value={s.current_role} />
                <Field label="Current company" value={s.current_company} />
                <Field label="Applying for" value={s.preferred_role} />
                <Field label="Highest qualification" value={s.highest_qualification} />
                <Field label="Location" value={s.location} />
                <Field label="Domains" value={s.domains.length ? s.domains.join(", ") : null} />
              </dl>
            </Section>

            {/* Experience */}
            {data.experience.length > 0 && (
              <Section id="experience" title="Professional Experience" count={data.experience.length}>
                <div className="flex flex-col gap-3">
                  {filteredExp.length === 0 ? (
                    <p className="text-sm text-ink-muted">No experience matches "{q}".</p>
                  ) : (
                    data.experience.map((e, i) =>
                      filteredExp.includes(e) ? (
                        <ExperienceCard key={i} exp={e} open={openExp.has(i)}
                          onToggle={() => setOpenExp((prev) => { const n = new Set(prev); n.has(i) ? n.delete(i) : n.add(i); return n; })} />
                      ) : null)
                  )}
                </div>
              </Section>
            )}

            {/* Skills (categorized) */}
            {Object.keys(data.skills_by_category).length > 0 && (
              <Section id="skills" title="Skills">
                <div className="glass-card flex flex-col gap-4 p-5">
                  {Object.entries(data.skills_by_category).map(([cat, items]) => {
                    const shown = items.filter((it) => match(q, it.value));
                    if (!shown.length) return null;
                    return (
                      <div key={cat}>
                        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">{cat}</p>
                        <div className="flex flex-wrap gap-1.5">
                          {shown.map((it) => (
                            <Badge key={it.value} tone="accent"><Dot c={it.confidence} /> {it.value}</Badge>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Section>
            )}

            {/* Projects */}
            {hasProjects && (
              <Section id="projects" title="Projects" count={data.projects.length}>
                <div className="grid gap-3 sm:grid-cols-2">
                  {filteredProjects.map((p, i) => (
                    <div key={i} className="glass-card flex flex-col gap-2 p-4">
                      <div className="flex items-center justify-between gap-2">
                        <span className="flex items-center gap-2 font-medium text-ink"><FolderGit2 className="h-4 w-4 text-accent" /> {p.name || "Project"}</span>
                        <Dot c={p.confidence} />
                      </div>
                      {p.description && <p className="text-sm text-ink-muted">{p.description}</p>}
                      {p.technologies.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">{p.technologies.map((t) => <Badge key={t}>{t}</Badge>)}</div>
                      )}
                      {p.domain && <span className="text-xs text-ink-muted">Domain: {p.domain}</span>}
                    </div>
                  ))}
                </div>
              </Section>
            )}

            {/* Education / Certs / Awards / Languages */}
            {(hasEducation || hasCerts || hasAwards || hasLangs) && (
              <Section id="education" title="Education & More">
                <div className="grid gap-3 sm:grid-cols-2">
                  {hasEducation && (
                    <div className="glass-card flex flex-col gap-2 p-4">
                      <p className="flex items-center gap-2 text-sm font-medium text-ink"><GraduationCap className="h-4 w-4 text-accent" /> Education</p>
                      {data.education.map((e, i) => (
                        <div key={i} className="text-sm text-ink-muted">
                          {[e.degree, e.institution].filter(Boolean).join(" — ") || "—"}
                          {e.dates && <span className="ml-1 text-xs">({e.dates})</span>}
                        </div>
                      ))}
                    </div>
                  )}
                  {hasCerts && (
                    <CardList icon={<Award className="h-4 w-4 text-accent" />} title="Certifications" items={data.certifications} />
                  )}
                  {hasAwards && (
                    <CardList icon={<Award className="h-4 w-4 text-accent" />} title="Awards & Achievements" items={data.achievements} />
                  )}
                  {hasLangs && (
                    <CardList icon={<LangIcon className="h-4 w-4 text-accent" />} title="Languages" items={data.languages} />
                  )}
                </div>
              </Section>
            )}

            {/* AI interview context (sanitized) */}
            <Section id="context" title="AI Interview Context">
              <div className="glass-card flex flex-col gap-4 p-5">
                <p className="text-xs text-ink-muted">The sanitized context supplied to the interview engine — no system prompts.</p>
                <ChipRow label="Interview focus" items={data.interview_context.interview_focus} tone="accent" />
                <ChipRow label="Missing skills to validate" items={data.interview_context.missing_skills_to_validate} tone="warn" />
                <ChipRow label="Potential follow-up areas" items={data.interview_context.potential_followup_areas} />
                {data.interview_context.context_text && (
                  <details className="rounded-xl bg-white/5 p-3">
                    <summary className="cursor-pointer text-sm text-ink">View raw context block</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-xs text-ink-muted">{data.interview_context.context_text}</pre>
                  </details>
                )}
              </div>
            </Section>

            {/* Strategy */}
            <Section id="strategy" title="Interview Strategy">
              <div className="glass-card flex flex-col gap-4 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="accent" >Level: {data.strategy.experience_level}</Badge>
                  <Badge tone="muted">~{data.strategy.estimated_duration_min} min (estimated)</Badge>
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">Question distribution</p>
                  <div className="flex flex-col gap-2">
                    {data.strategy.question_distribution.map((d) => (
                      <div key={d.label}>
                        <div className="mb-1 flex justify-between text-xs"><span className="text-ink-muted">{d.label}</span><span className="text-ink">{d.pct}%</span></div>
                        <div className="h-2 rounded-full bg-white/10">
                          <motion.div className="h-full rounded-full accent-gradient" initial={{ width: 0 }} animate={{ width: `${d.pct}%` }} transition={{ duration: 0.7 }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <ChipRow label="Priority skills" items={data.strategy.priority_skills} tone="accent" />
                <ChipRow label="Focus areas" items={data.strategy.focus_areas} />
              </div>
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}

function ToolButton({ children, onClick, active }: { children: React.ReactNode; onClick: () => void; active?: boolean }) {
  return (
    <button onClick={onClick}
      className={cn("flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs transition-colors",
        active ? "bg-accent/20 text-ink" : "bg-white/5 text-ink-muted hover:bg-white/10 hover:text-ink")}>
      {children}
    </button>
  );
}

function MetaStrip({ meta }: { meta: AiContext["metadata"] }) {
  const stat = (label: string, value: React.ReactNode) => (
    <div className="flex flex-col">
      <span className="text-lg font-semibold text-ink">{value}</span>
      <span className="text-xs text-ink-muted">{label}</span>
    </div>
  );
  return (
    <div className="glass-card flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
      <span className="flex items-center gap-2 text-sm text-success"><Check className="h-4 w-4" /> Resume parsed</span>
      {stat("Pages", meta.pages ?? "—")}
      {stat("Parsing confidence", `${meta.parsing_confidence}%`)}
      {stat("Skills", meta.skills_extracted)}
      {stat("Projects", meta.projects_detected)}
      {stat("Companies", meta.companies_detected)}
    </div>
  );
}

function CardList({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  return (
    <div className="glass-card flex flex-col gap-2 p-4">
      <p className="flex items-center gap-2 text-sm font-medium text-ink">{icon} {title}</p>
      <div className="flex flex-wrap gap-1.5">{items.map((it, i) => <Badge key={i}>{it}</Badge>)}</div>
    </div>
  );
}

function ChipRow({ label, items, tone = "default" }: { label: string; items: string[]; tone?: "default" | "accent" | "warn" }) {
  if (!items?.length) return null;
  return (
    <div>
      <p className="mb-2 text-xs font-medium uppercase tracking-wider text-ink-muted">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((it) => (
          <span key={it} className={cn("rounded-full px-2.5 py-1 text-xs",
            tone === "warn" ? "bg-warn/15 text-warn" : tone === "accent" ? "bg-accent/15 text-ink" : "bg-white/8 text-ink")}>
            {it}
          </span>
        ))}
      </div>
    </div>
  );
}
