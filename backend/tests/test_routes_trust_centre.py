"""Tests for `app.routes.trust_centre` (Bible Section 11.8, Trust Centre)."""


def test_trust_centre_returns_three_provider_cascade_in_order(client):
    resp = client.get("/api/trust-centre")
    assert resp.status_code == 200
    body = resp.json()

    keys = [entry["provider_key"] for entry in body["llm_cascade"]]
    assert keys == ["ollama_qwen", "groq_gpt_oss", "openrouter_fallback"]


def test_trust_centre_never_exposes_api_key_values(client):
    resp = client.get("/api/trust-centre")
    body = resp.json()
    serialized = str(body)
    assert "api_key_env" not in serialized
    assert "GROQ_API_KEY" not in serialized
    assert "OPENROUTER_API_KEY" not in serialized


def test_trust_centre_reports_requires_api_key_correctly_per_provider(client):
    resp = client.get("/api/trust-centre")
    by_key = {e["provider_key"]: e for e in resp.json()["llm_cascade"]}
    assert by_key["ollama_qwen"]["requires_api_key"] is False
    assert by_key["groq_gpt_oss"]["requires_api_key"] is True
    assert by_key["openrouter_fallback"]["requires_api_key"] is True


def test_trust_centre_embedding_provider_is_ollama_no_key(client):
    resp = client.get("/api/trust-centre")
    embedding = resp.json()["embedding_provider"]
    assert embedding["provider"] == "ollama"
    assert embedding["requires_api_key"] is False


def test_trust_centre_lists_the_real_rego_policy_bundle(client):
    resp = client.get("/api/trust-centre")
    body = resp.json()
    assert body["opa_policy_count"] == len(body["opa_policy_files"])
    assert body["opa_policy_count"] >= 1
    assert all(f.endswith(".rego") for f in body["opa_policy_files"])
    assert all("_test" not in f for f in body["opa_policy_files"])


def test_trust_centre_reports_a_real_policy_bundle_hash(client):
    """2026-09-02 incident remediation: the Trust Centre must show an
    honest, non-hardcoded policy-bundle fingerprint (Bible Section 11.8),
    not the literal "unavailable" degraded value — the real policies/
    directory is present in this checkout, so get_policy_bundle_hash()
    must succeed."""
    resp = client.get("/api/trust-centre")
    body = resp.json()
    assert body["opa_policy_bundle_hash"] != "unavailable"
    assert len(body["opa_policy_bundle_hash"]) == 64

    # Same hash twice in a row -- the fingerprint must be stable across
    # requests when nothing on disk has changed (the property an operator
    # actually relies on to detect drift).
    second = client.get("/api/trust-centre").json()
    assert second["opa_policy_bundle_hash"] == body["opa_policy_bundle_hash"]
