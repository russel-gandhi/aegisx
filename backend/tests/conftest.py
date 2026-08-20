"""
Shared pytest fixtures for the backend test suite.

Ticket: SENT-1-05 | Requirement: ENV-04

These fixtures are deliberately generic so later wave-2 backend plans
reuse rather than redefine them:
- `client` — reused by test_health.py (this plan) and any future route test.
- `opa_base_url` — consumed by plan 02-05's test_opa_client.py.
- `pinned_now_ns` — a fixed reference clock any backend test needing one
  can share with the Rego test suite's own pinned constant.

Fixtures only — no assertions, no import of modules that do not yet exist.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture
def opa_base_url():
    return os.getenv("OPA_URL", "http://127.0.0.1:8181")


@pytest.fixture
def pinned_now_ns():
    # Fixed nanosecond-epoch reference clock, shared with the Rego suite's
    # own pinned "now" so backend and policy tests reason about the same
    # instant when a test needs a stable clock.
    return 1_800_000_000_000_000_000
