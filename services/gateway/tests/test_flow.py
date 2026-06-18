"""End-to-end gateway flow test (AI service mocked)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def _register(client) -> tuple[str, str]:
    email = f"rec_{uuid.uuid4().hex[:8]}@acme.io"
    r = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "s3cret!", "full_name": "Rec Ruiter", "org_name": "Acme",
    })
    assert r.status_code == 201, r.text
    return r.json()["access_token"], email


async def test_auth_register_login_me(client):
    access, email = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["role"] == "recruiter"

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "s3cret!"})
    assert login.status_code == 200
    assert login.json()["access_token"]


async def test_login_bad_password(client):
    _access, email = await _register(client)
    bad = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401


async def test_create_interview_and_meeting_link(client):
    access, _ = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}
    r = await client.post(
        "/api/v1/interviews", headers=headers,
        data={"role_title": "Backend Engineer", "candidate_name": "Pat Lee",
              "candidate_email": "pat@cand.io", "job_description": "Build APIs"},
        files={"resume": ("resume.txt", b"Python FastAPI Postgres", "text/plain")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["meeting_token"]
    assert body["meeting_url"].endswith(body["meeting_token"])
    assert body["status"] == "invited"

    # public meeting resolution — no auth, no PII
    info = await client.get(f"/api/v1/meeting/{body['meeting_token']}")
    assert info.status_code == 200
    assert info.json()["valid"] is True
    assert info.json()["role_title"] == "Backend Engineer"
    assert "email" not in info.json()


async def test_interview_requires_recruiter(client):
    # No auth → 401
    r = await client.post("/api/v1/interviews",
                          data={"role_title": "x", "candidate_name": "y", "candidate_email": "z@z.io"})
    assert r.status_code == 401


async def test_full_interview_session_to_assessment(client):
    access, _ = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}
    created = (await client.post(
        "/api/v1/interviews", headers=headers,
        data={"role_title": "Backend Engineer", "candidate_name": "Pat Lee",
              "candidate_email": "pat2@cand.io"},
        files={"resume": ("r.txt", b"Python", "text/plain")},
    )).json()
    token = created["meeting_token"]
    interview_id = created["interview_id"]

    start = await client.post(f"/api/v1/sessions/{token}/start")
    assert start.status_code == 200, start.text
    s = start.json()
    assert s["question"]
    assert s["stage"] == "opening"
    session_headers = {"Authorization": f"Bearer {s['session_token']}"}

    # Answer until complete (1+4+2+1 = 8 turns)
    completed = False
    for _ in range(s["total_estimated"] + 2):
        ans = await client.post(
            f"/api/v1/sessions/{interview_id}/answer", headers=session_headers,
            files={"audio": ("a.wav", b"\x00\x00", "audio/wav")},
        )
        assert ans.status_code == 200, ans.text
        if ans.json()["completed"]:
            completed = True
            break
    assert completed

    # Recruiter sees the assessment
    lst = await client.get("/api/v1/interviews", headers=headers)
    assert lst.status_code == 200
    row = next(i for i in lst.json() if i["id"] == interview_id)
    assert row["overall_score"] == 8
    assert row["recommendation"] == "hire"

    detail = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)
    assert detail.json()["assessment"]["recommendation"] == "hire"


async def test_session_token_scoped_to_interview(client):
    """A candidate session token must not work for a different interview id."""
    access, _ = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}
    created = (await client.post(
        "/api/v1/interviews", headers=headers,
        data={"role_title": "X", "candidate_name": "N", "candidate_email": "n@c.io"},
        files={"resume": ("r.txt", b"x", "text/plain")},
    )).json()
    start = (await client.post(f"/api/v1/sessions/{created['meeting_token']}/start")).json()
    bad_headers = {"Authorization": f"Bearer {start['session_token']}"}
    r = await client.post("/api/v1/sessions/some-other-id/answer", headers=bad_headers,
                          files={"audio": ("a.wav", b"\x00", "audio/wav")})
    assert r.status_code == 403


async def test_analytics_overview(client):
    access, _ = await _register(client)
    headers = {"Authorization": f"Bearer {access}"}
    ov = await client.get("/api/v1/analytics/overview", headers=headers)
    assert ov.status_code == 200
    assert "total_interviews" in ov.json()
    assert "conversion_rate" in ov.json()
