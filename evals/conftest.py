"""Evaluation suites (ADR-047, ADR-070). Run: `make evals`.

Suites run the real pipeline (retrieval, then the agent through the AI gateway) against the same
throwaway Postgres and S3 the integration tests use, so they exercise exactly what production
runs. Today the provider is `FakeModel`; with a real provider the same cases measure the model.
"""

import sys
from pathlib import Path

# The suites reuse the backend's integration fixtures (`tests.integration`).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

pytest_plugins = ["tests.integration.conftest"]
