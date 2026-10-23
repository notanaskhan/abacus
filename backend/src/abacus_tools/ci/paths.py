"""Which CI stage 2 jobs a change needs, from the paths it touches (F-01-T07; ADR-082).

Run: python -m abacus_tools.ci.paths <base> <head>

Prints `backend=…`, `frontend=…`, `gallery=…`, `agents=…` and `journeys=…` (`true` or `false`)
for `$GITHUB_OUTPUT`. The single source for every path filter in `ci.yml`. Standard library
only, so the filter job needs no environment. Anything it can't classify counts as backend: a
skipped suite must be provably irrelevant, and an unknown base (a new branch) runs everything.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from fnmatch import fnmatchcase

# Changes here can't affect a backend test: the SPA and its component library.
FRONTEND_ONLY = ("apps/web/**", "packages/ui/**")
# Prose no test reads; stage 1's validate_docs still checks ADRs, specs and tasks. Not here: YAML
# under docs/ (it feeds the code generators) and docs/product/ (a unit test reads the failure
# taxonomy).
DOCS_ONLY = ("docs/adr/**.md", "docs/specs/**.md", "work/tasks/**.md", "**README.md")
# The SPA's tests and build depend on these.
FRONTEND = (
    "apps/web/**",
    "packages/**",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    ".npmrc",
)
# What the gallery's visual run (parity Tier A and D, screenshot regression, axe) depends on
# (F-05-T17): the component library, the gallery, the harness, its manifest and its crop tools.
GALLERY = (
    "packages/ui/**",
    "apps/web/src/gallery/**",
    "apps/web/e2e/**",
    "apps/web/scripts/visual-ci.mjs",
    "apps/web/playwright.config.ts",
    "apps/web/vite.config.ts",
    "docs/design/**",
    "backend/src/abacus_tools/parity/**",
    "pnpm-lock.yaml",
)
# What an agent's behaviour depends on (stage 3, the fast evaluation subset).
AGENTS = (
    "backend/src/abacus/ai_gateway/**",
    "backend/src/abacus/modules/agents/**",
    "evals/**",
    "backend/src/abacus_tools/evals/**",
)
# What the fixture-mode journeys walk (F-04-T28; F-04.32): the SPA and portal sources, the
# component library, the journey specs and their harness, and the server and browser config. A
# pull request touching none of these cannot change a fixture journey's outcome.
JOURNEYS = (
    "apps/web/src/**",
    "apps/web/e2e/journeys/**",
    "apps/web/e2e/harness/**",
    "apps/web/index.html",
    "apps/web/portal.html",
    "apps/web/playwright.config.ts",
    "apps/web/vite.config.ts",
    "apps/web/package.json",
    "packages/ui/**",
    "packages/api-client/**",
    "pnpm-lock.yaml",
)
NO_BASE = frozenset({"", "0" * 40})


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    # fnmatch's `*` crosses `/`, so `**` needs no special handling.
    return any(fnmatchcase(path, p) for p in patterns)


def classify(paths: list[str] | None) -> dict[str, bool]:
    """`None` means the changed paths are unknown: every job runs."""
    if paths is None:
        return {"backend": True, "frontend": True, "gallery": True, "agents": True}
    return {
        "backend": any(not _matches(p, FRONTEND_ONLY + DOCS_ONLY) for p in paths),
        "frontend": any(_matches(p, FRONTEND) for p in paths),
        "gallery": any(_matches(p, GALLERY) for p in paths),
        "agents": any(_matches(p, AGENTS) for p in paths),
    }


def journeys(paths: list[str] | None) -> bool:
    """Whether a pull request's fixture journeys run; unknown paths run them."""
    return paths is None or any(_matches(p, JOURNEYS) for p in paths)


def changed(base: str, head: str) -> list[str] | None:
    git = shutil.which("git")
    if base in NO_BASE or git is None:
        return None
    result = subprocess.run(
        [git, "diff", "--name-only", base, head], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return None
    return [line for line in result.stdout.splitlines() if line]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    found = changed(argv[0], argv[1])
    for name, value in {**classify(found), "journeys": journeys(found)}.items():
        print(f"{name}={'true' if value else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
