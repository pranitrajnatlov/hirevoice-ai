/**
 * Typed client for the HireVoice API gateway.
 * Base URL is proxied via next.config rewrites (/api/v1 → gateway) in dev.
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

type Json = Record<string, unknown>;

async function req<T>(path: string, init?: RequestInit & { token?: string }): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.token) headers.set("Authorization", `Bearer ${init.token}`);
  if (init?.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${BASE}/api/v1${path}`, { ...init, headers });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export interface MeetingInfo {
  role_title: string;
  duration_min: number;
  status: string;
  valid: boolean;
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

export const api = {
  // ── Auth ──
  register: (b: Json) => req<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify(b) }),
  login: (b: Json) => req<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify(b) }),

  // ── Candidate journey ──
  getMeeting: (token: string) => req<MeetingInfo>(`/meeting/${token}`),
  startSession: (token: string) => req<SessionStart>(`/sessions/${token}/start`, { method: "POST" }),
  submitAnswer: (interviewId: string, audio: Blob, token: string) => {
    const fd = new FormData();
    fd.append("audio", audio, "answer.webm");
    return req<AnswerResult>(`/sessions/${interviewId}/answer`, { method: "POST", body: fd, token });
  },

  // ── Recruiter ──
  overview: (token: string) => req<Json>("/analytics/overview", { token }),
  listInterviews: (token: string) => req<Json[]>("/interviews", { token }),
};
