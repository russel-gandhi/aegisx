"""
Tests for the FastAPI entrypoint's /api/health route (SENT-1-05, ENV-04).

Covers the plan's <behavior> list:
- GET /api/health returns 200 and a JSON body that equals
  {"status": "ok"} exactly — not a superset, not a different key.
- GET / returns 404, confirming no unintended catch-all route was
  registered.
- The application object imports without a database, an OPA server, or
  any network call (proved separately in this plan's verification step 5,
  not by this test module, which always runs with those services down or
  up equally since it never talks to them).
"""


def test_health_returns_200_with_exact_body(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_404(client):
    response = client.get("/")
    assert response.status_code == 404
