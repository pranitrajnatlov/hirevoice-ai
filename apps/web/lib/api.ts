import Cookies from "js-cookie";

/**
 * Typed client for the HireVoice API gateway.
 * Base URL is proxied via next.config rewrites (/api/v1 → gateway) in dev.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

type Json = Record<string, unknown>;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function req<T>(path: string, init?: RequestInit & { token?: string }): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.token) headers.set("Authorization", `Bearer ${init.token}`);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text();
    // Expired/invalid recruiter session → log out and bounce to login (avoids the
    // misleading "gateway is down" errors). Scoped to recruiter context (hv_token present)
    // so a candidate's session-token 401 doesn't redirect them.
    if (res.status === 401 && typeof window !== "undefined" && Cookies.get("hv_token")) {
      Cookies.remove("hv_token", { path: "/" });
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login?expired=1";
      }
    }
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export interface MeetingInfo {
  role_title: string;
  duration_min: number;
  status: string;
  valid: boolean;
  candidate_name: string;
}
export interface SessionStart {
  session_token: string;
  interview_id: string;
  question: string;
  stage: string;
  question_index: number;
  total_estimated: number;
}
export interface AnswerResult {
  transcript: string;
  question: string;
  stage: string;
  question_index: number;
  completed: boolean;
}
export interface CreateInterviewResponse {
  interview_id: string;
  candidate_id: string;
  meeting_url: string;
  meeting_token: string;
  status: string;
  plan: Json | null;
}
export interface AnalyticsOverview {
  total_interviews: number;
  total_candidates: number;
  average_score: number | null;
  recommended_hires: number;
  completed: number;
  conversion_rate: number;
}
export interface UserOut {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
}
export interface TranscriptTurn {
  role: "interviewer" | "candidate";
  text: string;
  stage: string;
  is_followup: boolean;
  ts: string | null;
}
export interface TranscriptResponse {
  interview_id: string;
  turns: TranscriptTurn[];
}

export interface SkillItem {
  value: string;
  confidence?: number;
}
export interface AiContext {
  summary: {
    name: string | null;
    years_experience: string | number | null;
    current_role: string | null;
    current_company: string | null;
    preferred_role: string | null;
    highest_qualification: string | null;
    location: string | null;
    domains: string[];
  };
  experience: {
    company: string | null;
    designation: string | null;
    duration: string | null;
    responsibilities: string[];
    technologies: string[];
    achievements: string[];
    confidence?: number | null;
  }[];
  skills_by_category: Record<string, SkillItem[]>;
  projects: {
    name: string | null;
    description: string;
    technologies: string[];
    responsibilities: string[];
    domain: string | null;
    team_size: number | null;
    achievements: string[];
    confidence?: number | null;
  }[];
  education: { degree: string | null; institution: string | null; dates: string | null; gpa: string | null; confidence?: number | null }[];
  certifications: string[];
  achievements: string[];
  languages: string[];
  metadata: {
    parsed: boolean;
    pages: number | null;
    parsing_confidence: number;
    skills_extracted: number;
    projects_detected: number;
    companies_detected: number;
    sections_found: string[];
  };
  warnings: string[];
  interview_context: {
    experience_years: string | number | null;
    primary_skills: string[];
    projects: string[];
    interview_focus: string[];
    missing_skills_to_validate: string[];
    potential_followup_areas: string[];
    context_text: string;
  };
  strategy: {
    experience_level: string;
    question_distribution: { label: string; pct: number }[];
    priority_skills: string[];
    focus_areas: string[];
    estimated_duration_min: number;
  };
  raw: { profile: unknown; plan: unknown };
}

export const api = {
  // ── Auth ──
  register: (b: Json) => req<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify(b) }),
  login: (b: Json) => req<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify(b) }),
  me: (token: string) => req<UserOut>("/auth/me", { token }),

  // ── Candidate journey ──
  getMeeting: (token: string) => req<MeetingInfo>(`/meeting/${token}`),
  startSession: (token: string) => req<SessionStart>(`/sessions/${token}/start`, { method: "POST" }),
  endSession: (interviewId: string, token: string) => req<Json>(`/sessions/${interviewId}/end`, { method: "POST", token }),
  submitAnswer: (interviewId: string, audio: Blob, token: string) => {
    const fd = new FormData();
    fd.append("audio", audio, "answer.webm");
    return req<AnswerResult>(`/sessions/${interviewId}/answer`, { method: "POST", body: fd, token });
  },

  // ── Recruiter ──
  overview: (token: string) => req<AnalyticsOverview>("/analytics/overview", { token }),
  listInterviews: (token: string) => req<Json[]>("/interviews", { token }),
  createInterview: (form: FormData, token: string) => req<CreateInterviewResponse>("/interviews", { method: "POST", body: form, token }),
  getInterview: (id: string, token: string) => req<Json>(`/interviews/${id}`, { token }),
  deleteInterview: (id: string, token: string) => req<void>(`/interviews/${id}`, { method: "DELETE", token }),
  deleteCandidate: (id: string, token: string) => req<void>(`/candidates/${id}`, { method: "DELETE", token }),
  getTranscript: (id: string, token: string) => req<TranscriptResponse>(`/interviews/${id}/transcript`, { token }),
  getAiContext: (id: string, token: string) => req<AiContext>(`/interviews/${id}/ai-context`, { token }),
};
