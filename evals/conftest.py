"""Evaluation suites (ADR-047, ADR-070). Run: `make evals`.

Suites run the real pipeline (retrieval, then the agent through the AI gateway) against the same
throwaway Postgres and S3 the integration tests use, so they exercise exactly what production
runs. Today the provider is `FakeModel`; with a real provider the same cases measure the model.
"""

import sys
from pathlib import Path

from abacus.kernel.config import settings

# Synthetic data only: suites never run against a deployed environment's data.
if settings().environment not in ("local", "test"):
    raise RuntimeError("evaluation suites run only in local or test environments")

# The suites reuse the backend's integration fixtures (`tests.integration`); appended, so nothing
# under backend/ can shadow an installed package.
sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

pytest_plugins = ["tests.integration.conftest"]
