-- HireVoice AI — PostgreSQL schema (canonical)
-- Deliverable #4. Conventions: UUID PKs, timestamptz, soft-delete via deleted_at,
-- blobs referenced by S3 key (never stored inline), org_id for multitenancy.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ── Enums ────────────────────────────────────────────────────────────────────
CREATE TYPE user_role        AS ENUM ('admin', 'recruiter', 'candidate');
CREATE TYPE auth_provider     AS ENUM ('password', 'google', 'microsoft');
CREATE TYPE interview_status  AS ENUM ('created','invited','in_progress','completed','assessed','archived');
CREATE TYPE interview_stage   AS ENUM ('opening','technical','behavioral','closing');
CREATE TYPE recommendation    AS ENUM ('strong_hire','hire','maybe','no_hire','pending');
CREATE TYPE ai_mode           AS ENUM ('local','openai','claude','gemini');

-- ── Orgs & Users ─────────────────────────────────────────────────────────────
CREATE TABLE organizations (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL,
    domain       TEXT UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email         CITEXT UNIQUE NOT NULL,
    full_name     TEXT,
    role          user_role NOT NULL DEFAULT 'recruiter',
    auth_provider auth_provider NOT NULL DEFAULT 'password',
    password_hash TEXT,                       -- null for OAuth users
    avatar_url    TEXT,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);
CREATE INDEX idx_users_org ON users(org_id);

-- Recruiter & candidate are role-specific profiles (1:1 with users when applicable)
CREATE TABLE recruiters (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE candidates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name   TEXT NOT NULL,
    email       CITEXT NOT NULL,
    phone       TEXT,
    created_by  UUID REFERENCES recruiters(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at  TIMESTAMPTZ,
    UNIQUE (org_id, email)
);
CREATE INDEX idx_candidates_org ON candidates(org_id);

-- ── Resumes ──────────────────────────────────────────────────────────────────
CREATE TABLE resumes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id  UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    s3_key        TEXT NOT NULL,              -- pdf/docx blob in object storage
    extracted_text TEXT,                      -- parsed text (resume_integration.py)
    parsed_profile JSONB,                     -- structured skills/experience from AI analyze
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_resumes_candidate ON resumes(candidate_id);

-- ── Interviews ─────────────────────────────────────────────────────────────────
CREATE TABLE interviews (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    recruiter_id   UUID NOT NULL REFERENCES recruiters(id),
    candidate_id   UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    resume_id      UUID REFERENCES resumes(id),
    role_title     TEXT NOT NULL,
    job_description TEXT,
    interview_plan JSONB,                     -- AI-generated plan (stages, focus areas)
    status         interview_status NOT NULL DEFAULT 'created',
    ai_mode        ai_mode NOT NULL DEFAULT 'local',
    duration_sec   INTEGER,                   -- actual elapsed once completed
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ
);
CREATE INDEX idx_interviews_org_status ON interviews(org_id, status);
CREATE INDEX idx_interviews_candidate ON interviews(candidate_id);

-- ── Meeting links (secure, single interview, expiring) ──────────────────────────
CREATE TABLE meeting_links (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID UNIQUE NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    token        TEXT UNIQUE NOT NULL,        -- secrets.token_urlsafe(32)
    expires_at   TIMESTAMPTZ NOT NULL,
    consumed_at  TIMESTAMPTZ,                 -- first session start
    revoked      BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_meeting_token ON meeting_links(token) WHERE revoked = false;

-- ── Questions & Responses ───────────────────────────────────────────────────────
CREATE TABLE questions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    seq          INTEGER NOT NULL,            -- order within interview
    stage        interview_stage NOT NULL,
    text         TEXT NOT NULL,
    is_followup  BOOLEAN NOT NULL DEFAULT false,
    asked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (interview_id, seq)
);

CREATE TABLE responses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id   UUID NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    interview_id  UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    started_at    TIMESTAMPTZ,
    ended_at      TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_responses_interview ON responses(interview_id);

CREATE TABLE transcripts (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id  UUID UNIQUE NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
    text         TEXT NOT NULL,
    language     TEXT DEFAULT 'en',
    stt_model    TEXT,                        -- e.g. small.en / whisper-1
    confidence   REAL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audio_files (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id  UUID REFERENCES responses(id) ON DELETE CASCADE,
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    s3_key       TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'candidate',  -- candidate | ai_tts
    duration_sec REAL,
    sample_rate  INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audio_interview ON audio_files(interview_id);

-- ── Assessments (scores + recommendation + raw audit) ───────────────────────────
CREATE TABLE assessments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id        UUID UNIQUE NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    overall_score       SMALLINT,             -- 1..10
    technical_score     SMALLINT,
    communication_score SMALLINT,
    confidence_score    SMALLINT,
    culture_fit_score   SMALLINT,
    resume_alignment    SMALLINT,
    keyword_match       SMALLINT,
    strengths           JSONB DEFAULT '[]',
    weaknesses          JSONB DEFAULT '[]',
    red_flags           JSONB DEFAULT '[]',
    recommendation      recommendation NOT NULL DEFAULT 'pending',
    summary             TEXT,
    raw_output          TEXT,                 -- model output kept for audit
    model               TEXT,                 -- which LLM produced it
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Analytics (append-only) & Audit ────────────────────────────────────────────
CREATE TABLE analytics_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID REFERENCES organizations(id) ON DELETE CASCADE,
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    event_type   TEXT NOT NULL,               -- interview_started, question_answered, assessed…
    properties   JSONB DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (created_at);
-- create monthly partitions in migrations, e.g. analytics_events_2026_06
CREATE INDEX idx_analytics_org_type ON analytics_events(org_id, event_type);

CREATE TABLE audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID REFERENCES organizations(id) ON DELETE CASCADE,
    actor_id    UUID REFERENCES users(id),
    action      TEXT NOT NULL,                -- e.g. interview.create, link.revoke
    target_type TEXT,
    target_id   UUID,
    metadata    JSONB DEFAULT '{}',
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_org_created ON audit_logs(org_id, created_at DESC);

-- ── Refresh tokens (rotating) ────────────────────────────────────────────────────
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id) WHERE revoked = false;
